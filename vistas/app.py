"""
Aplicación principal de KivyMD (WynikApp) encargada de la vista global y orquestación.
"""

import os

from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty

from kivymd.app import MDApp
from kivymd.uix.list import (
    MDListItem,
    MDListItemHeadlineText,
    MDListItemSupportingText,
    MDListItemTrailingIcon,
)

# Servicios (lógica musical, audio, captura y persistencia sin Kivy)
from servicios import (
    cargar_partitura,
    generar_audio_guia,
    formatear_tiempo,
    DetectorDeNotas,
    MicrofonoNoDisponibleError,
    cargar_historial,
    agregar_al_historial,
    nombre_para_mostrar,
    nota_coincide,
)

# Vistas y componentes UI
from .screens import (
    MenuScreen,
    ElegirPartituraScreen,
    AjustesInicioScreen,
    InterpreteScreen,
)
from .widgets import PartituraWidget
from .dialogs import abrir_selector_de_archivo

KV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wynik.kv")


class WynikApp(MDApp):
    """Aplicación KivyMD y controlador de vistas de Wynik."""

    # Propiedades reactivas de configuración y partitura
    bpm = NumericProperty(120)
    seguir_de_largo = BooleanProperty(True)
    notacion_solfeo = BooleanProperty(False)
    notas_partitura = ListProperty([])
    estado_notas = ListProperty([])
    nombre_partitura = StringProperty("(Sin partitura)")
    historial_partituras = ListProperty([])

    # Propiedades reactivas del reproductor de audio
    reproduciendo_audio = BooleanProperty(False)
    volumen_audio = NumericProperty(0.8)
    posicion_audio_actual = NumericProperty(0)
    duracion_audio_total = NumericProperty(1)
    tiempo_actual_str = StringProperty("00:00")
    duracion_total_str = StringProperty("00:00")

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Green"
        self.detector = None
        self.indice_actual = 0
        self.nota_esperada = None
        self.sonido_guia = None
        self._evento_actualizar_progreso = None
        self.historial_partituras = cargar_historial()
        return Builder.load_file(KV_PATH)

    def on_start(self):
        self._refrescar_lista_partituras()

    def change_screen(self, screen_name: str):
        self.root.current = screen_name

    # =========================================================================
    #  Subir y cargar partitura
    # =========================================================================

    def subir_partitura(self):
        abrir_selector_de_archivo(self._partitura_seleccionada)

    def _partitura_seleccionada(self, ruta):
        if not ruta:
            return
        try:
            self.notas_partitura = cargar_partitura(ruta)
        except Exception as error:
            print(f"[Wynik] Error al leer {ruta}: {error}")
            return

        self.nombre_partitura = os.path.splitext(os.path.basename(ruta))[0]

        # Guardar en historial si es una nueva partitura
        self.historial_partituras = agregar_al_historial(
            self.historial_partituras,
            self.nombre_partitura,
            ruta,
        )
        self._refrescar_lista_partituras()
        self.root.current = "ajustes_inicio"

    def _refrescar_lista_partituras(self):
        lista_widget = self.root.get_screen("elegir_partitura").ids.song_list
        lista_widget.clear_widgets()

        if not self.historial_partituras:
            lista_widget.add_widget(
                MDListItem(MDListItemHeadlineText(text="Aún no has subido ninguna partitura"))
            )
            return

        for entrada in self.historial_partituras:
            item = MDListItem(
                MDListItemHeadlineText(text=entrada["nombre"]),
                MDListItemSupportingText(text=entrada["ruta"]),
                MDListItemTrailingIcon(icon="play-circle"),
                on_release=lambda x, ruta=entrada["ruta"], nombre=entrada["nombre"]: (
                    self._elegir_partitura_del_historial(ruta, nombre)
                ),
            )
            lista_widget.add_widget(item)

    def _elegir_partitura_del_historial(self, ruta: str, nombre: str):
        if not os.path.exists(ruta):
            print(f"[Wynik] El archivo no existe en esta ubicación: {ruta}")
            return
        try:
            self.notas_partitura = cargar_partitura(ruta)
        except Exception as error:
            print(f"[Wynik] No se pudo abrir {ruta}: {error}")
            return
        self.nombre_partitura = nombre
        self.root.current = "ajustes_inicio"

    # =========================================================================
    #  Configuración de Tempo
    # =========================================================================

    def cambiar_bpm(self, delta: int):
        self.bpm = max(40, min(240, self.bpm + delta))

    # =========================================================================
    #  Control Multimedia y Reproducción de Audio Guía
    # =========================================================================

    def preparar_audio_guia(self):
        if self.sonido_guia:
            self.sonido_guia.stop()
            self.sonido_guia.unload()
            self.sonido_guia = None

        self.reproduciendo_audio = False
        self.posicion_audio_actual = 0
        self.tiempo_actual_str = "00:00"

        ruta_wav = generar_audio_guia(self.notas_partitura, self.bpm)
        if ruta_wav and os.path.exists(ruta_wav):
            self.sonido_guia = SoundLoader.load(ruta_wav)
            if self.sonido_guia:
                self.sonido_guia.volume = self.volumen_audio
                self.duracion_audio_total = self.sonido_guia.length or 1
                self.duracion_total_str = formatear_tiempo(self.duracion_audio_total)

    def toggle_reproduccion_audio(self):
        if not self.sonido_guia:
            self.preparar_audio_guia()

        if self.sonido_guia:
            if self.reproduciendo_audio:
                self.sonido_guia.stop()
                self.reproduciendo_audio = False
                if self._evento_actualizar_progreso:
                    self._evento_actualizar_progreso.cancel()
                    self._evento_actualizar_progreso = None
            else:
                self.sonido_guia.play()
                self.reproduciendo_audio = True
                self._evento_actualizar_progreso = Clock.schedule_interval(self._actualizar_progreso_ui, 0.2)

    def detener_audio(self):
        if self.sonido_guia:
            self.sonido_guia.stop()
            self.sonido_guia.seek(0)
        self.reproduciendo_audio = False
        self.posicion_audio_actual = 0
        self.tiempo_actual_str = "00:00"
        if self._evento_actualizar_progreso:
            self._evento_actualizar_progreso.cancel()
            self._evento_actualizar_progreso = None

    def adelantar_retroceder_audio(self, segundos: float):
        if self.sonido_guia:
            pos_actual = self.sonido_guia.get_pos()
            nueva_pos = max(0, min(self.duracion_audio_total, pos_actual + segundos))
            self.sonido_guia.seek(nueva_pos)
            self.posicion_audio_actual = nueva_pos
            self.tiempo_actual_str = formatear_tiempo(nueva_pos)

    def cambiar_posicion_audio(self, nuevo_tiempo: float):
        if self.sonido_guia and abs(self.sonido_guia.get_pos() - nuevo_tiempo) > 0.8:
            self.sonido_guia.seek(nuevo_tiempo)
            self.posicion_audio_actual = nuevo_tiempo
            self.tiempo_actual_str = formatear_tiempo(nuevo_tiempo)

    def ajustar_volumen(self, valor: float):
        self.volumen_audio = valor
        if self.sonido_guia:
            self.sonido_guia.volume = valor

    def _actualizar_progreso_ui(self, dt):
        if self.sonido_guia and self.reproduciendo_audio:
            pos = self.sonido_guia.get_pos()
            if pos >= self.duracion_audio_total or (self.sonido_guia.state == "stop" and pos > 0):
                self.detener_audio()
            else:
                self.posicion_audio_actual = pos
                self.tiempo_actual_str = formatear_tiempo(pos)

    # =========================================================================
    #  Lógica de Práctica e Interpretación
    # =========================================================================

    def iniciar_interpretacion(self):
        self.indice_actual = 0
        self.estado_notas = [None] * len(self.notas_partitura)
        self.preparar_audio_guia()

    def iniciar_escucha(self):
        if not self.notas_partitura:
            self._actualizar_label_estado("No hay partitura cargada", (1, 0.3, 0.3, 1))
            return

        self.detector = DetectorDeNotas(self._nota_detectada)
        try:
            self.detector.iniciar()
        except MicrofonoNoDisponibleError as error:
            self.detector = None
            self._actualizar_label_estado("No se pudo abrir el micrófono", (1, 0.3, 0.3, 1))
            print(f"[Wynik] {error}")
            return

        self._evento_refresco_visual = Clock.schedule_interval(self._refrescar_partitura_widget, 0.1)
        self._mostrar_nota_actual()

    def detener_escucha(self):
        if self.detector:
            self.detector.detener()
            self.detector = None
        Clock.unschedule(self._siguiente_nota)
        if getattr(self, "_evento_refresco_visual", None):
            self._evento_refresco_visual.cancel()
            self._evento_refresco_visual = None

    def _refrescar_partitura_widget(self, dt):
        pantalla = self.root.get_screen("interprete")
        if "partitura_widget" in pantalla.ids:
            pantalla.ids.partitura_widget.redibujar()

    def _mostrar_nota_actual(self):
        if self.indice_actual >= len(self.notas_partitura):
            self._actualizar_label_estado("¡Partitura completa!", (0.4, 1, 0.2, 1))
            return

        nota_info = self.notas_partitura[self.indice_actual]
        self.nota_esperada = nota_info["nombre"]

        nombre_mostrado = nombre_para_mostrar(self.nota_esperada, self.notacion_solfeo)
        self._actualizar_label_estado(f"Nota esperada: {nombre_mostrado}", (0, 0, 0, 1))

        if self.seguir_de_largo:
            segundos_por_beat = 60.0 / self.bpm
            duracion_segundos = max(nota_info["duracion_beats"] * segundos_por_beat, 0.15)
            Clock.schedule_once(self._siguiente_nota, duracion_segundos)

    def _avanzar(self):
        self.indice_actual += 1
        self._mostrar_nota_actual()

    def _siguiente_nota(self, dt):
        if self.indice_actual < len(self.estado_notas) and self.estado_notas[self.indice_actual] is None:
            self._marcar_estado_nota(self.indice_actual, False)
        self._avanzar()

    def _marcar_estado_nota(self, indice: int, es_correcta: bool):
        if indice >= len(self.estado_notas):
            return
        nuevos_estados = list(self.estado_notas)
        nuevos_estados[indice] = es_correcta
        self.estado_notas = nuevos_estados

    def _nota_detectada(self, nombre_nota: str, frecuencia: float):
        Clock.schedule_once(lambda dt: self._procesar_nota_detectada(nombre_nota))

    def _procesar_nota_detectada(self, nombre_nota: str):
        es_correcta = bool(self.nota_esperada and nota_coincide(nombre_nota, self.nota_esperada))
        self._marcar_estado_nota(self.indice_actual, es_correcta)

        nombre_tocado = nombre_para_mostrar(nombre_nota, self.notacion_solfeo)
        nombre_esperado = nombre_para_mostrar(self.nota_esperada, self.notacion_solfeo)

        if es_correcta:
            self._actualizar_label_estado(f"✓ {nombre_tocado} correcta", (0.2, 0.7, 0.2, 1))
            if not self.seguir_de_largo:
                self._avanzar()
        else:
            texto = f"✗ tocaste {nombre_tocado}, esperada {nombre_esperado}"
            self._actualizar_label_estado(texto, (0.8, 0.1, 0.1, 1))

    def _actualizar_label_estado(self, texto: str, color: tuple):
        pantalla = self.root.get_screen("interprete")
        if "label_estado" in pantalla.ids:
            pantalla.ids.label_estado.text = texto
            pantalla.ids.label_estado.text_color = color

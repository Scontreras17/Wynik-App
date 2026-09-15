import json
import os

import numpy as np
import sounddevice as sd
import librosa
from music21 import converter, note, chord

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.widget import Widget

from kivymd.app import MDApp
from kivymd.uix.list import (
    MDListItem,
    MDListItemHeadlineText,
    MDListItemSupportingText,
    MDListItemTrailingIcon,
)

# Ajuste de tamaño de ventana para simular un móvil en PC
Window.size = (360, 640)


# =====================================================================
#  PARTE 1: Carga de partituras en MusicXML  (antes: musicxml_loader.py)
# =====================================================================

def cargar_partitura(ruta_archivo):
    """
    Lee un archivo MusicXML y devuelve una lista de diccionarios:
    [{"nombre": "E4", "offset_beats": 0.0, "duracion_beats": 1.0}, ...]
    """
    partitura = converter.parse(ruta_archivo)
    notas_planas = partitura.flatten().notes

    resultado = []
    for elemento in notas_planas:
        if isinstance(elemento, note.Note):
            resultado.append({
                "nombre": elemento.nameWithOctave,
                "offset_beats": float(elemento.offset),
                "duracion_beats": float(elemento.quarterLength),
            })
        elif isinstance(elemento, chord.Chord):
            nota_top = elemento.notes[-1]
            resultado.append({
                "nombre": nota_top.nameWithOctave,
                "offset_beats": float(elemento.offset),
                "duracion_beats": float(elemento.quarterLength),
            })
    return resultado


def abrir_selector_de_archivo(callback_ruta_seleccionada):
    """
    Abre el explorador de archivos nativo filtrado a MusicXML.
    `callback_ruta_seleccionada` recibe la ruta (str) elegida, o None si se cancela.
    """
    from plyer import filechooser

    def _on_selection(seleccion):
        ruta = seleccion[0] if seleccion else None
        callback_ruta_seleccionada(ruta)

    filechooser.open_file(
        title="Selecciona una partitura MusicXML",
        filters=[("MusicXML", "*.xml", "*.musicxml", "*.mxl")],
        on_selection=_on_selection,
    )


# =====================================================================
#  PARTE 1.5: Historial de partituras subidas (persistente entre sesiones)
# =====================================================================

HISTORIAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historial_partituras.json")


def cargar_historial():
    """Lee el historial guardado en disco. Si no existe o está dañado, devuelve una lista vacía."""
    if os.path.exists(HISTORIAL_PATH):
        try:
            with open(HISTORIAL_PATH, "r", encoding="utf-8") as archivo:
                return json.load(archivo)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def guardar_historial(historial):
    with open(HISTORIAL_PATH, "w", encoding="utf-8") as archivo:
        json.dump(historial, archivo, ensure_ascii=False, indent=2)


# =====================================================================
#  PARTE 2: Detección de notas por micrófono  (antes: pitch_listener.py)
# =====================================================================

SAMPLE_RATE = 22050
BLOCK_SIZE = 2048


def frecuencia_a_nota(frecuencia_hz):
    """Convierte una frecuencia en Hz al nombre de nota más cercano (ej: 'A4')."""
    if frecuencia_hz is None or frecuencia_hz <= 0 or np.isnan(frecuencia_hz):
        return None
    midi = librosa.hz_to_midi(frecuencia_hz)
    return librosa.midi_to_note(round(midi))


class MicrofonoNoDisponibleError(Exception):
    """Se lanza cuando no se pudo abrir ningún micrófono (dispositivo ocupado,
    permisos de Windows denegados, sample rate no soportado, etc.)."""
    pass


class DetectorDeNotas:
    """
    Escucha el micrófono en un hilo aparte y llama a `callback_nota(nombre, frecuencia)`
    cada vez que detecta una nota distinta a la anterior.

    IMPORTANTE: el callback se dispara desde el hilo de audio, NO desde el hilo
    principal de Kivy — por eso en WynikApp._nota_detectada lo reenviamos con
    Clock.schedule_once antes de tocar cualquier cosa de la interfaz.
    """

    def __init__(self, callback_nota, device=None):
        self.callback_nota = callback_nota
        self.device = device  # None = usar el micrófono por defecto de Windows
        self.stream = None
        self.samplerate = SAMPLE_RATE  # se ajusta en iniciar() al valor real del dispositivo
        self._ultima_nota = None

    def _procesar_bloque(self, indata, frames, time_info, status):
        audio = indata[:, 0]

        f0, voiced_flag, _ = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=self.samplerate,
            frame_length=BLOCK_SIZE,
        )

        frecuencias_validas = f0[voiced_flag]
        if len(frecuencias_validas) == 0:
            return

        frecuencia = float(np.nanmedian(frecuencias_validas))
        nota = frecuencia_a_nota(frecuencia)

        if nota and nota != self._ultima_nota:
            self._ultima_nota = nota
            self.callback_nota(nota, frecuencia)

    def iniciar(self):
        try:
            # Le preguntamos al propio dispositivo cuál es SU sample rate nativo
            # en vez de forzar uno fijo (22050 Hz suele fallar con drivers MME en Windows).
            info_dispositivo = sd.query_devices(self.device, 'input')
            self.samplerate = int(info_dispositivo['default_samplerate'])

            self.stream = sd.InputStream(
                device=self.device,
                channels=1,
                samplerate=self.samplerate,
                blocksize=BLOCK_SIZE,
                callback=self._procesar_bloque,
            )
            self.stream.start()
        except Exception as error:
            self.stream = None
            raise MicrofonoNoDisponibleError(
                f"No se pudo abrir el micrófono ({error}). "
                f"Revisa los permisos de micrófono de Windows o si otra app "
                f"(Zoom, Discord, etc.) lo está usando en modo exclusivo."
            ) from error

    def detener(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None


def nota_coincide(nota_detectada, nota_esperada, tolerancia_semitonos=0):
    """Compara la nota detectada contra la esperada por la partitura."""
    if nota_detectada is None:
        return False
    midi_detectada = round(librosa.note_to_midi(nota_detectada))
    midi_esperada = round(librosa.note_to_midi(nota_esperada))
    return abs(midi_detectada - midi_esperada) <= tolerancia_semitonos


# =====================================================================
#  PARTE 2.5: Dibujo del pentagrama con las notas (nuevo)
# =====================================================================

_LETRA_A_PASO = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}


def paso_diatonico(nombre_nota):
    """
    Convierte un nombre de nota tipo 'E4', 'F#4' o 'Bb3' en un número entero
    que representa su altura "diatónica" (ignora sostenidos/bemoles para la
    posición vertical en el pentagrama — solo importa la letra + la octava).
    """
    letra = nombre_nota[0]
    octava = int(nombre_nota[-1])
    return octava * 7 + _LETRA_A_PASO[letra]


PASO_E4 = paso_diatonico("E4")  # línea inferior del pentagrama en clave de sol


class PartituraWidget(Widget):
    """
    Dibuja un pentagrama simple con un tramo de la partitura actual.
    Colorea cada nota según app.estado_notas:
        None  -> negro   (todavía no se evaluó)
        True  -> verde   (se tocó correctamente)
        False -> rojo    (se tocó mal, o se pasó de largo sin tocarla)
    La nota que está sonando "ahora" (app.indice_actual) se marca en azul
    mientras no tenga un resultado todavía.
    """

    NOTAS_VISIBLES = 8
    ESPACIO_ENTRE_LINEAS = 14  # separación vertical entre líneas del pentagrama, en px

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.redibujar, size=self.redibujar)

    def redibujar(self, *args):
        app = MDApp.get_running_app()
        if app is None:
            return

        self.canvas.clear()
        centro_y = self.center_y

        with self.canvas:
            # --- Las 5 líneas del pentagrama ---
            Color(0, 0, 0, 1)
            for i in range(5):
                y = centro_y + (i - 2) * self.ESPACIO_ENTRE_LINEAS
                Line(points=[self.x + 20, y, self.right - 20, y], width=1.2)

            if not app.notas_partitura:
                return

            inicio = max(0, app.indice_actual - 1)
            fin = min(len(app.notas_partitura), inicio + self.NOTAS_VISIBLES)
            notas_a_mostrar = app.notas_partitura[inicio:fin]
            if not notas_a_mostrar:
                return

            ancho_disponible = max((self.right - 20) - (self.x + 40), 10)
            paso_x = ancho_disponible / len(notas_a_mostrar)
            y_min_pentagrama = centro_y - 2 * self.ESPACIO_ENTRE_LINEAS
            y_max_pentagrama = centro_y + 2 * self.ESPACIO_ENTRE_LINEAS

            for offset, nota_info in enumerate(notas_a_mostrar):
                indice_real = inicio + offset
                x = self.x + 40 + offset * paso_x

                paso = paso_diatonico(nota_info["nombre"])
                diferencia_pasos = paso - PASO_E4
                y = centro_y + diferencia_pasos * (self.ESPACIO_ENTRE_LINEAS / 2)

                # Líneas adicionales (ledger lines) si la nota queda fuera del pentagrama
                if (diferencia_pasos % 2 == 0) and (y < y_min_pentagrama or y > y_max_pentagrama):
                    Color(0, 0, 0, 1)
                    Line(points=[x - 8, y, x + 8, y], width=1.2)

                estado = app.estado_notas[indice_real] if indice_real < len(app.estado_notas) else None
                if estado is True:
                    Color(0.2, 0.7, 0.2, 1)      # correcta
                elif estado is False:
                    Color(0.85, 0.1, 0.1, 1)     # incorrecta / no tocada a tiempo
                elif indice_real == app.indice_actual:
                    Color(0.2, 0.45, 0.9, 1)     # sonando ahora, sin resultado aún
                else:
                    Color(0, 0, 0, 1)            # nota futura

                Ellipse(pos=(x - 6, y - 5), size=(12, 10))


# =====================================================================
#  PARTE 3: La app Wynik en sí
# =====================================================================

KV = '''
ScreenManager:
    MenuScreen:
    ElegirPartituraScreen:
    AjustesInicioScreen:
    InterpreteScreen:

<MenuScreen>:
    name: 'menu'
    MDBoxLayout:
        orientation: 'vertical'
        theme_bg_color: "Custom"
        md_bg_color: 0.1, 0.1, 0.1, 1

        MDTopAppBar:
            type: "small"
            MDTopAppBarTitle:
                text: "Wynik"
                halign: "center"

        MDGridLayout:
            cols: 3
            padding: "20dp"
            spacing: "15dp"
            pos_hint: {"center_x": .5, "center_y": .5}
            size_hint_y: None
            height: self.minimum_height

            MDBoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: "100dp"
                MDLabel:
                    text: "Subir\\nPartitura"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 1, 1, 1, 1
                    font_style: "Label"
                    role: "small"
                MDIconButton:
                    icon: "upload"
                    style: "filled"
                    theme_bg_color: "Custom"
                    md_bg_color: 1, 1, 1, 1
                    theme_icon_color: "Custom"
                    icon_color: 0, 0, 0, 1
                    icon_size: "48sp"
                    pos_hint: {"center_x": .5}
                    on_release: app.subir_partitura()

            MDBoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: "100dp"
                MDLabel:
                    text: "Elegir\\nPartitura"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 1, 1, 1, 1
                    font_style: "Label"
                    role: "small"
                MDIconButton:
                    icon: "music-note-eighth"
                    style: "filled"
                    theme_bg_color: "Custom"
                    md_bg_color: 1, 1, 1, 1
                    theme_icon_color: "Custom"
                    icon_color: 0, 0, 0, 1
                    icon_size: "48sp"
                    pos_hint: {"center_x": .5}
                    on_release: app.root.current = 'elegir_partitura'

            MDBoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: "100dp"
                MDLabel:
                    text: "Ajustes"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 1, 1, 1, 1
                    font_style: "Label"
                    role: "small"
                MDIconButton:
                    icon: "cog"
                    style: "filled"
                    theme_bg_color: "Custom"
                    md_bg_color: 1, 1, 1, 1
                    theme_icon_color: "Custom"
                    icon_color: 0, 0, 0, 1
                    icon_size: "48sp"
                    pos_hint: {"center_x": .5}

        Widget:
            size_hint_y: 1

<ElegirPartituraScreen>:
    name: 'elegir_partitura'
    MDBoxLayout:
        orientation: 'vertical'

        MDTopAppBar:
            type: "small"
            MDTopAppBarLeadingButtonContainer:
                MDActionTopAppBarButton:
                    icon: "arrow-left"
                    on_release: app.change_screen('menu')
            MDTopAppBarTitle:
                text: "Menú de canciones"

        ScrollView:
            MDList:
                id: song_list

<AjustesInicioScreen>:
    name: 'ajustes_inicio'
    MDBoxLayout:
        orientation: 'vertical'
        theme_bg_color: "Custom"
        md_bg_color: 0.1, 0.1, 0.1, 1

        MDTopAppBar:
            type: "small"
            MDTopAppBarLeadingButtonContainer:
                MDActionTopAppBarButton:
                    icon: "arrow-left"
                    on_release: app.change_screen('elegir_partitura')
            MDTopAppBarTitle:
                text: "Ajustes de inicio"

        MDBoxLayout:
            orientation: 'horizontal'
            padding: "20dp"
            spacing: "15dp"
            size_hint_y: 0.6

            MDCard:
                orientation: 'vertical'
                style: "outlined"
                theme_bg_color: "Custom"
                md_bg_color: 0, 0, 0, 1
                line_color: 1, 1, 1, 1
                padding: "10dp"
                radius: [15, 15, 15, 15]

                MDLabel:
                    text: "Seguir de largo al\\nfallar"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 1, 1, 1, 1

                MDCheckbox:
                    size_hint: None, None
                    size: "48dp", "48dp"
                    pos_hint: {'center_x': .5, 'center_y': .5}
                    active: app.seguir_de_largo
                    on_active: app.seguir_de_largo = self.active

            MDCard:
                orientation: 'vertical'
                style: "outlined"
                theme_bg_color: "Custom"
                md_bg_color: 0, 0, 0, 1
                line_color: 1, 1, 1, 1
                padding: "10dp"
                radius: [15, 15, 15, 15]

                MDLabel:
                    text: "Tocar a mi\\nritmo (sin tempo)"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 1, 1, 1, 1

                MDCheckbox:
                    size_hint: None, None
                    size: "48dp", "48dp"
                    pos_hint: {'center_x': .5, 'center_y': .5}
                    active: app.modo_libre
                    on_active: app.modo_libre = self.active

            MDCard:
                orientation: 'vertical'
                style: "outlined"
                theme_bg_color: "Custom"
                md_bg_color: 0, 0, 0, 1
                line_color: 1, 1, 1, 1
                padding: "10dp"
                radius: [15, 15, 15, 15]
                opacity: 0.4 if app.modo_libre else 1

                MDLabel:
                    text: "Tempo\\nBPM"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 1, 1, 1, 1
                    size_hint_y: 0.3

                MDBoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: 0.7
                    MDIconButton:
                        icon: "arrow-left-bold"
                        theme_icon_color: "Custom"
                        icon_color: 0.5, 0.8, 0.2, 1
                        disabled: app.modo_libre
                        on_release: app.cambiar_bpm(-5)
                    MDLabel:
                        text: str(app.bpm)
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 1, 1, 1, 1
                        theme_bg_color: "Custom"
                        md_bg_color: 0.2, 0.2, 0.2, 1
                    MDIconButton:
                        icon: "arrow-right-bold"
                        theme_icon_color: "Custom"
                        icon_color: 0.5, 0.8, 0.2, 1
                        disabled: app.modo_libre
                        on_release: app.cambiar_bpm(5)

        MDFloatLayout:
            size_hint_y: 0.4
            MDButton:
                style: "filled"
                theme_bg_color: "Custom"
                md_bg_color: 0.6, 0.9, 0.4, 1
                pos_hint: {"right": 0.9, "bottom": 0.9}
                on_release:
                    app.iniciar_interpretacion()
                    app.root.current = 'interprete'
                MDButtonText:
                    text: "Iniciar"
                    theme_text_color: "Custom"
                    text_color: 0, 0, 0, 1

<InterpreteScreen>:
    name: 'interprete'
    MDBoxLayout:
        orientation: 'vertical'

        MDTopAppBar:
            type: "small"
            MDTopAppBarLeadingButtonContainer:
                MDActionTopAppBarButton:
                    icon: "arrow-left"
                    on_release: app.change_screen('ajustes_inicio')
            MDTopAppBarTitle:
                text: app.nombre_partitura

        MDFloatLayout:
            theme_bg_color: "Custom"
            md_bg_color: 1, 1, 1, 1

            PartituraWidget:
                id: partitura_widget
                size_hint: 0.95, 0.5
                pos_hint: {"center_x": .5, "center_y": .6}

            MDLabel:
                id: label_estado
                text: "Esperando nota..."
                halign: "center"
                theme_text_color: "Custom"
                text_color: 0, 0, 0, 1
                bold: True
                size_hint: 0.9, None
                height: "40dp"
                pos_hint: {"center_x": .5, "y": 0.08}
'''


class MenuScreen(Screen):
    pass


class ElegirPartituraScreen(Screen):
    pass


class AjustesInicioScreen(Screen):
    pass


class InterpreteScreen(Screen):
    def on_enter(self):
        MDApp.get_running_app().iniciar_escucha()

    def on_leave(self):
        MDApp.get_running_app().detener_escucha()


class WynikApp(MDApp):
    bpm = NumericProperty(120)
    seguir_de_largo = BooleanProperty(True)
    modo_libre = BooleanProperty(False)  # True = sin tempo, avanza cuando tocas la nota correcta
    notas_partitura = ListProperty([])
    estado_notas = ListProperty([])  # uno por nota: None=sin evaluar, True=correcta, False=incorrecta
    nombre_partitura = StringProperty("(Sin partitura)")
    historial_partituras = ListProperty([])  # [{"nombre": ..., "ruta": ...}, ...]

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Green"
        self.detector = None
        self.indice_actual = 0
        self.nota_esperada = None
        self.historial_partituras = cargar_historial()
        return Builder.load_string(KV)

    def on_start(self):
        self._refrescar_lista_partituras()

    def change_screen(self, screen_name):
        self.root.current = screen_name

    # ---------- Subir partitura (MusicXML) ----------

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

        ya_estaba = any(entrada["ruta"] == ruta for entrada in self.historial_partituras)
        if not ya_estaba:
            nuevo_historial = list(self.historial_partituras)
            nuevo_historial.append({"nombre": self.nombre_partitura, "ruta": ruta})
            self.historial_partituras = nuevo_historial
            guardar_historial(self.historial_partituras)
            self._refrescar_lista_partituras()

        self.root.current = 'ajustes_inicio'

    def _refrescar_lista_partituras(self):
        lista_widget = self.root.get_screen('elegir_partitura').ids.song_list
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
                on_release=lambda x, ruta=entrada["ruta"], nombre=entrada["nombre"]:
                    self._elegir_partitura_del_historial(ruta, nombre),
            )
            lista_widget.add_widget(item)

    def _elegir_partitura_del_historial(self, ruta, nombre):
        try:
            self.notas_partitura = cargar_partitura(ruta)
        except Exception as error:
            print(f"[Wynik] No se pudo volver a abrir {ruta}: {error}")
            return
        self.nombre_partitura = nombre
        self.root.current = 'ajustes_inicio'

    # ---------- Tempo / ajustes ----------

    def cambiar_bpm(self, delta):
        self.bpm = max(40, min(240, self.bpm + delta))

    # ---------- Reproducción / escucha ----------

    def iniciar_interpretacion(self):
        self.indice_actual = 0
        self.estado_notas = [None] * len(self.notas_partitura)

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
            print(f"[Wynik] {error}")  # detalle completo en la consola para depurar
            return

        self._evento_refresco_visual = Clock.schedule_interval(self._refrescar_partitura_widget, 0.1)
        self._mostrar_nota_actual()

    def detener_escucha(self):
        if self.detector:
            self.detector.detener()
            self.detector = None
        Clock.unschedule(self._siguiente_nota)
        if getattr(self, '_evento_refresco_visual', None):
            self._evento_refresco_visual.cancel()
            self._evento_refresco_visual = None

    def _refrescar_partitura_widget(self, dt):
        pantalla = self.root.get_screen('interprete')
        if 'partitura_widget' in pantalla.ids:
            pantalla.ids.partitura_widget.redibujar()

    def _mostrar_nota_actual(self):
        if self.indice_actual >= len(self.notas_partitura):
            self._actualizar_label_estado("¡Partitura completa!", (0.4, 1, 0.2, 1))
            return

        nota_info = self.notas_partitura[self.indice_actual]
        self.nota_esperada = nota_info["nombre"]
        self._actualizar_label_estado(f"Nota esperada: {self.nota_esperada}", (0, 0, 0, 1))

        segundos_por_beat = 60.0 / self.bpm
        duracion_segundos = max(nota_info["duracion_beats"] * segundos_por_beat, 0.15)
        Clock.schedule_once(self._siguiente_nota, duracion_segundos)

    def _siguiente_nota(self, dt):
        if self.indice_actual < len(self.estado_notas) and self.estado_notas[self.indice_actual] is None:
            self._marcar_estado_nota(self.indice_actual, False)  # se pasó sin tocarla
        self.indice_actual += 1
        self._mostrar_nota_actual()

    def _marcar_estado_nota(self, indice, es_correcta):
        if indice >= len(self.estado_notas):
            return
        nuevos_estados = list(self.estado_notas)
        nuevos_estados[indice] = es_correcta
        self.estado_notas = nuevos_estados  # reasignar la lista completa dispara el binding

    def _nota_detectada(self, nombre_nota, frecuencia):
        Clock.schedule_once(lambda dt: self._procesar_nota_detectada(nombre_nota))

    def _procesar_nota_detectada(self, nombre_nota):
        es_correcta = bool(self.nota_esperada and nota_coincide(nombre_nota, self.nota_esperada))
        self._marcar_estado_nota(self.indice_actual, es_correcta)

        if es_correcta:
            self._actualizar_label_estado(f"✓ {nombre_nota} correcta", (0.2, 0.7, 0.2, 1))
        else:
            texto = f"✗ tocaste {nombre_nota}, esperada {self.nota_esperada}"
            self._actualizar_label_estado(texto, (0.8, 0.1, 0.1, 1))

    def _actualizar_label_estado(self, texto, color):
        pantalla = self.root.get_screen('interprete')
        if 'label_estado' in pantalla.ids:
            pantalla.ids.label_estado.text = texto
            pantalla.ids.label_estado.text_color = color


if __name__ == '__main__':
    WynikApp().run()
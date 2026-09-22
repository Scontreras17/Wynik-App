import json
import os
import struct
import wave

import numpy as np
import sounddevice as sd
import librosa

from music21 import converter, note, chord

from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.graphics import Color, Ellipse, Line
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.widget import Widget
from kivy.uix.modalview import ModalView
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.boxlayout import BoxLayout

from kivymd.app import MDApp
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.slider import MDSlider
from kivymd.uix.list import (
    MDListItem,
    MDListItemHeadlineText,
    MDListItemSupportingText,
    MDListItemTrailingIcon,
)

# Ajuste de tamaño de ventana para simular un móvil en PC
Window.size = (360, 640)


# =====================================================================
#  SINTETIZADOR Y CARGA DE PARTITURAS
# =====================================================================

def generar_audio_guia(notas_partitura, bpm, ruta_salida="temp_guia.wav", sample_rate=22050):
    """
    Genera un archivo WAV de audio síntesis temporal a partir de las notas de la partitura.
    """
    if not notas_partitura:
        return None

    segundos_por_beat = 60.0 / max(bpm, 1)
    duracion_total_beats = sum(n["duracion_beats"] for n in notas_partitura)
    total_samples = int(duracion_total_beats * segundos_por_beat * sample_rate)

    if total_samples <= 0:
        return None

    buffer_audio = np.zeros(total_samples, dtype=np.float32)
    sample_actual = 0

    for item in notas_partitura:
        duracion_sec = item["duracion_beats"] * segundos_por_beat
        num_samples = int(duracion_sec * sample_rate)

        try:
            freq = librosa.note_to_hz(item["nombre"])
            t = np.linspace(0, duracion_sec, num_samples, False)
            # Genera tono senoidal suave con desvanecimiento gradual (decay)
            onda = 0.5 * np.sin(2 * np.pi * freq * t) * np.exp(-3 * t / max(duracion_sec, 0.001))
        except Exception:
            onda = np.zeros(num_samples)

        fin_sample = min(sample_actual + num_samples, total_samples)
        len_copia = fin_sample - sample_actual
        if len_copia > 0:
            buffer_audio[sample_actual:fin_sample] += onda[:len_copia]
        sample_actual = fin_sample

    # Normalización para evitar saturación
    max_val = np.max(np.abs(buffer_audio))
    if max_val > 1.0:
        buffer_audio = buffer_audio / max_val

    buffer_int16 = (buffer_audio * 32767).astype(np.int16)

    with wave.open(ruta_salida, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(buffer_int16.tobytes())

    return ruta_salida


def cargar_partitura(ruta_archivo):
    """
    Lee un archivo MusicXML y devuelve una lista de diccionarios con las notas.
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
    Selector de archivos multiplataforma basado en Kivy.
    """
    popup = ModalView(size_hint=(0.95, 0.85), auto_dismiss=False)
    layout = BoxLayout(orientation='vertical', padding='10dp', spacing='10dp')

    filechooser = FileChooserListView(
        filters=['*.xml', '*.musicxml', '*.mxl'],
        path=os.path.expanduser("~")
    )

    btn_layout = BoxLayout(size_hint_y=None, height='48dp', spacing='10dp')

    def _cancelar(instance):
        popup.dismiss()
        callback_ruta_seleccionada(None)

    def _seleccionar(instance):
        seleccion = filechooser.selection
        ruta = seleccion[0] if seleccion else None
        popup.dismiss()
        callback_ruta_seleccionada(ruta)

    btn_cancelar = MDButton(on_release=_cancelar)
    btn_cancelar.add_widget(MDButtonText(text="Cancelar"))

    btn_aceptar = MDButton(on_release=_seleccionar)
    btn_aceptar.add_widget(MDButtonText(text="Seleccionar"))

    btn_layout.add_widget(btn_cancelar)
    btn_layout.add_widget(btn_aceptar)

    layout.add_widget(filechooser)
    layout.add_widget(btn_layout)

    popup.add_widget(layout)
    popup.open()


# =====================================================================
#  HISTORIAL DE PARTITURAS
# =====================================================================

HISTORIAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historial_partituras.json")


def cargar_historial():
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
#  DETECCIÓN DE NOTAS POR MICRÓFONO
# =====================================================================

SAMPLE_RATE = 22050
BLOCK_SIZE = 2048


def frecuencia_a_nota(frecuencia_hz):
    if frecuencia_hz is None or frecuencia_hz <= 0 or np.isnan(frecuencia_hz):
        return None
    midi = librosa.hz_to_midi(frecuencia_hz)
    return librosa.midi_to_note(round(midi))


class MicrofonoNoDisponibleError(Exception):
    pass


class DetectorDeNotas:
    def __init__(self, callback_nota, device=None):
        self.callback_nota = callback_nota
        self.device = device
        self.stream = None
        self.samplerate = SAMPLE_RATE
        self._ultima_nota = None

    def _procesar_bloque(self, indata, frames, time_info, status):
        audio = indata[:, 0]
        # 1. Filtro de ruido un poco más estricto
        rms = np.sqrt(np.mean(audio**2))
        if rms < 0.234:  # Si sigue sensible, sube este valor a 0.08
            self._ultima_nota = None
            return

        # 2. Detección instantánea con FFT (reemplaza a librosa.pyin)
        fft_data = np.fft.rfft(audio)
        fft_freqs = np.fft.rfftfreq(len(audio), 1.0 / self.samplerate)
        magnitudes = np.abs(fft_data)
        
        # Ignorar frecuencias menores a 65Hz (ruido de fondo o golpes)
        magnitudes[fft_freqs < 65.0] = 0 

        peak_idx = np.argmax(magnitudes)
        frecuencia = float(fft_freqs[peak_idx])

        # 3. Validar que la frecuencia sea de un instrumento (C2 a C7 aprox)
        if 65.0 < frecuencia < 2100.0:
            nota = frecuencia_a_nota(frecuencia)
            if nota and nota != self._ultima_nota:
                self._ultima_nota = nota
                self.callback_nota(nota, frecuencia)

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
                f"No se pudo abrir el micrófono ({error})."
            ) from error

    def detener(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None


def nota_coincide(nota_detectada, nota_esperada, tolerancia_semitonos=0):
    if nota_detectada is None:
        return False
    midi_detectada = round(librosa.note_to_midi(nota_detectada))
    midi_esperada = round(librosa.note_to_midi(nota_esperada))
    
    # Compara si es la misma nota ignorando la octava (usando módulo 12)
    return (midi_detectada % 12) == (midi_esperada % 12)


# =====================================================================
#  NOTACIÓN: nombres de nota en notación inglesa vs. solfeo (Do-Re-Mi)
# =====================================================================

_LETRA_A_SOLFEO = {"C": "Do", "D": "Re", "E": "Mi", "F": "Fa", "G": "Sol", "A": "La", "B": "Si"}


def nombre_para_mostrar(nombre_nota, usar_solfeo):
    """
    Convierte 'E4' -> 'Mi4', 'F#4' -> 'Fa#4', etc. Si usar_solfeo es False,
    devuelve el nombre tal cual (notación inglesa, la que usa music21/librosa
    internamente para todas las comparaciones).
    """
    if not usar_solfeo or not nombre_nota:
        return nombre_nota
    letra = nombre_nota[0]
    resto = nombre_nota[1:]  # alteración (# / -) y octava, se mantienen igual
    return _LETRA_A_SOLFEO.get(letra, letra) + resto


# =====================================================================
#  DIBUJO DEL PENTAGRAMA
# =====================================================================

_LETRA_A_PASO = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}


def paso_diatonico(nombre_nota):
    letra = nombre_nota[0]
    octava = int(nombre_nota[-1])
    return octava * 7 + _LETRA_A_PASO[letra]


PASO_E4 = paso_diatonico("E4")


class PartituraWidget(Widget):
    NOTAS_VISIBLES = 8
    ESPACIO_ENTRE_LINEAS = 14

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

                if (diferencia_pasos % 2 == 0) and (y < y_min_pentagrama or y > y_max_pentagrama):
                    Color(0, 0, 0, 1)
                    Line(points=[x - 8, y, x + 8, y], width=1.2)

                estado = app.estado_notas[indice_real] if indice_real < len(app.estado_notas) else None
                if estado is True:
                    Color(0.2, 0.7, 0.2, 1)
                elif estado is False:
                    Color(0.85, 0.1, 0.1, 1)
                elif indice_real == app.indice_actual:
                    Color(0.2, 0.45, 0.9, 1)
                else:
                    Color(0, 0, 0, 1)

                Ellipse(pos=(x - 6, y - 5), size=(12, 10))


# =====================================================================
#  DISEÑO KV DE LA APLICACIÓN
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
                    text: "Ver notas en\\nDo-Re-Mi"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 1, 1, 1, 1

                MDCheckbox:
                    size_hint: None, None
                    size: "48dp", "48dp"
                    pos_hint: {'center_x': .5, 'center_y': .5}
                    active: app.notacion_solfeo
                    on_active: app.notacion_solfeo = self.active

            MDCard:
                orientation: 'vertical'
                style: "outlined"
                theme_bg_color: "Custom"
                md_bg_color: 0, 0, 0, 1
                line_color: 1, 1, 1, 1
                padding: "10dp"
                radius: [15, 15, 15, 15]

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
        theme_bg_color: "Custom"
        md_bg_color: 1, 1, 1, 1

        MDTopAppBar:
            type: "small"
            MDTopAppBarLeadingButtonContainer:
                MDActionTopAppBarButton:
                    icon: "arrow-left"
                    on_release:
                        app.detener_audio()
                        app.change_screen('ajustes_inicio')
            MDTopAppBarTitle:
                text: app.nombre_partitura

        MDBoxLayout:
            orientation: 'vertical'
            padding: "10dp"
            spacing: "5dp"

            PartituraWidget:
                id: partitura_widget
                size_hint_y: 0.45

            MDLabel:
                id: label_estado
                text: "Esperando nota..."
                halign: "center"
                theme_text_color: "Custom"
                text_color: 0, 0, 0, 1
                bold: True
                size_hint_y: None
                height: "30dp"

            # --- Panel Multimedia de Control de Audio ---
            MDBoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: "170dp"
                padding: ["10dp", "5dp", "10dp", "5dp"]
                spacing: "5dp"

                # Línea de Progreso y Tiempo
                MDBoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: "30dp"
                    spacing: "5dp"

                    MDLabel:
                        text: app.tiempo_actual_str
                        theme_text_color: "Custom"
                        text_color: 0, 0, 0, 1
                        size_hint_x: None
                        width: "45dp"
                        font_style: "Label"
                        role: "small"

                    MDSlider:
                        id: slider_progreso
                        min: 0
                        max: app.duracion_audio_total if app.duracion_audio_total > 0 else 1
                        value: app.posicion_audio_actual
                        on_value: app.cambiar_posicion_audio(self.value)

                    MDLabel:
                        text: app.duracion_total_str
                        theme_text_color: "Custom"
                        text_color: 0, 0, 0, 1
                        size_hint_x: None
                        width: "45dp"
                        font_style: "Label"
                        role: "small"

                # Botones de Control de Reproducción (-5s | Play/Pausa | Stop | +5s)
                MDBoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: "60dp"
                    spacing: "10dp"
                    pos_hint: {"center_x": .5}

                    Widget:
                        size_hint_x: 0.1

                    MDIconButton:
                        icon: "rewind-5"
                        style: "standard"
                        on_release: app.adelantar_retroceder_audio(-5)

                    MDIconButton:
                        icon: "play" if not app.reproduciendo_audio else "pause"
                        style: "filled"
                        icon_size: "32sp"
                        on_release: app.toggle_reproduccion_audio()

                    MDIconButton:
                        icon: "stop"
                        style: "standard"
                        on_release: app.detener_audio()

                    MDIconButton:
                        icon: "fast-forward-5"
                        style: "standard"
                        on_release: app.adelantar_retroceder_audio(5)

                    Widget:
                        size_hint_x: 0.1

                # Slider de Volumen
                MDBoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: "35dp"
                    spacing: "5dp"

                    MDIconButton:
                        icon: "volume-high" if app.volumen_audio > 0 else "volume-off"
                        style: "standard"
                        icon_size: "20sp"

                    MDSlider:
                        min: 0.0
                        max: 1.0
                        value: app.volumen_audio
                        on_value: app.ajustar_volumen(self.value)
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
        app = MDApp.get_running_app()
        app.detener_escucha()
        app.detener_audio()


# =====================================================================
#  CLASE PRINCIPAL DE LA APLICACIÓN
# =====================================================================

class WynikApp(MDApp):
    bpm = NumericProperty(120)
    seguir_de_largo = BooleanProperty(True)
    notacion_solfeo = BooleanProperty(False)
    notas_partitura = ListProperty([])
    estado_notas = ListProperty([])
    nombre_partitura = StringProperty("(Sin partitura)")
    historial_partituras = ListProperty([])

    # Propiedades para el reproductor de audio
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
        return Builder.load_string(KV)

    def on_start(self):
        self._refrescar_lista_partituras()

    def change_screen(self, screen_name):
        self.root.current = screen_name

    # ---------- Subir y cargar partitura ----------

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
        if not os.path.exists(ruta):
            print(f"[Wynik] El archivo no existe en esta ubicación: {ruta}")
            return
        try:
            self.notas_partitura = cargar_partitura(ruta)
        except Exception as error:
            print(f"[Wynik] No se pudo abrir {ruta}: {error}")
            return
        self.nombre_partitura = nombre
        self.root.current = 'ajustes_inicio'

    # ---------- Configuración de Tempo ----------

    def cambiar_bpm(self, delta):
        self.bpm = max(40, min(240, self.bpm + delta))

    # ---------- Control Multimedia y Sintetizador ----------

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
                self.duracion_total_str = self._formatear_tiempo(self.duracion_audio_total)

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

    def adelantar_retroceder_audio(self, segundos):
        if self.sonido_guia:
            pos_actual = self.sonido_guia.get_pos()
            nueva_pos = max(0, min(self.duracion_audio_total, pos_actual + segundos))
            self.sonido_guia.seek(nueva_pos)
            self.posicion_audio_actual = nueva_pos
            self.tiempo_actual_str = self._formatear_tiempo(nueva_pos)

    def cambiar_posicion_audio(self, nuevo_tiempo):
        if self.sonido_guia and abs(self.sonido_guia.get_pos() - nuevo_tiempo) > 0.8:
            self.sonido_guia.seek(nuevo_tiempo)
            self.posicion_audio_actual = nuevo_tiempo
            self.tiempo_actual_str = self._formatear_tiempo(nuevo_tiempo)

    def ajustar_volumen(self, valor):
        self.volumen_audio = valor
        if self.sonido_guia:
            self.sonido_guia.volume = valor

    def _actualizar_progreso_ui(self, dt):
        if self.sonido_guia and self.reproduciendo_audio:
            pos = self.sonido_guia.get_pos()
            if pos >= self.duracion_audio_total or (self.sonido_guia.state == 'stop' and pos > 0):
                self.detener_audio()
            else:
                self.posicion_audio_actual = pos
                self.tiempo_actual_str = self._formatear_tiempo(pos)

    @staticmethod
    def _formatear_tiempo(segundos):
        if segundos is None or np.isnan(segundos) or segundos < 0:
            return "00:00"
        mins = int(segundos // 60)
        secs = int(segundos % 60)
        return f"{mins:02d}:{secs:02d}"

    # ---------- Lógica de Interpretación ----------

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

        # --- AJUSTE PARA COINCIDIR CON EL PENTAGRAMA ---
        # El archivo pide un "La", pero el pentagrama dibuja un "Mi" (desfase de +7 semitonos).
        # Transformamos la nota esperada sumando 7 semitonos para que el Label 
        # y el micrófono te pidan exactamente lo que estás viendo en la pantalla.
        try:
            midi_original = librosa.note_to_midi(nota_info["nombre"])
            self.nota_esperada = librosa.midi_to_note(midi_original + 7).replace('♯', '#')
        except Exception:
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
        # Solo se llama vía Clock cuando seguir_de_largo está activo.
        if self.indice_actual < len(self.estado_notas) and self.estado_notas[self.indice_actual] is None:
            self._marcar_estado_nota(self.indice_actual, False)  # se pasó el tiempo sin tocarla (o la tocó mal)
        self._avanzar()

    def _marcar_estado_nota(self, indice, es_correcta):
        if indice >= len(self.estado_notas):
            return
        nuevos_estados = list(self.estado_notas)
        nuevos_estados[indice] = es_correcta
        self.estado_notas = nuevos_estados

    def _nota_detectada(self, nombre_nota, frecuencia):
        Clock.schedule_once(lambda dt: self._procesar_nota_detectada(nombre_nota))

    def _procesar_nota_detectada(self, nombre_nota):
        es_correcta = bool(self.nota_esperada and nota_coincide(nombre_nota, self.nota_esperada))
        self._marcar_estado_nota(self.indice_actual, es_correcta)

        nombre_tocado = nombre_para_mostrar(nombre_nota, self.notacion_solfeo)
        nombre_esperado = nombre_para_mostrar(self.nota_esperada, self.notacion_solfeo)

        if es_correcta:
            self._actualizar_label_estado(f"✓ {nombre_tocado} correcta", (0.2, 0.7, 0.2, 1))
            if not self.seguir_de_largo:
                # Con "seguir de largo" DESACTIVADO, tocar la nota correcta es lo único
                # que hace avanzar la partitura (se frena hasta que aciertas).
                self._avanzar()
        else:
            texto = f"✗ tocaste {nombre_tocado}, esperada {nombre_esperado}"
            self._actualizar_label_estado(texto, (0.8, 0.1, 0.1, 1))
            # Con "seguir de largo" desactivado, simplemente no avanzamos: se queda
            # esperando en la misma nota hasta que la toques bien.

    def _actualizar_label_estado(self, texto, color):
        pantalla = self.root.get_screen('interprete')
        if 'label_estado' in pantalla.ids:
            pantalla.ids.label_estado.text = texto
            pantalla.ids.label_estado.text_color = color


if __name__ == '__main__':
    WynikApp().run()
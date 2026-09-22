"""
Escucha el micrófono en tiempo real y detecta qué nota está sonando.


"""

import numpy as np
import sounddevice as sd
import librosa

SAMPLE_RATE = 22050
BLOCK_SIZE = 2048  # tamaño de cada "trozo" de audio que se analiza a la vez


def frecuencia_a_nota(frecuencia_hz):
    """Convierte una frecuencia en Hz al nombre de nota más cercano (ej: 'A4')."""
    if frecuencia_hz is None or frecuencia_hz <= 0 or np.isnan(frecuencia_hz):
        return None
    midi = librosa.hz_to_midi(frecuencia_hz)
    return librosa.midi_to_note(round(midi))


class DetectorDeNotas:
    """
    Escucha el micrófono en un hilo aparte y llama a `callback_nota(nombre, frecuencia)`
    cada vez que detecta una nota distinta a la anterior.

    IMPORTANTE: este callback se dispara desde el hilo de audio, NO desde el hilo
    principal de Kivy. Si vas a tocar cosas de la UI (labels, colores de notas, etc.)
    dentro del callback, hazlo con Clock.schedule_once, por ejemplo:

        from kivy.clock import Clock

        def callback_nota(nombre, frecuencia):
            Clock.schedule_once(lambda dt: self.actualizar_nota_en_pantalla(nombre))
    """

    def __init__(self, callback_nota):
        self.callback_nota = callback_nota
        self.stream = None
        self._ultima_nota = None

    def _procesar_bloque(self, indata, frames, time_info, status):
        audio = indata[:, 0]  # nos quedamos con un solo canal (mono)

        # pYIN: algoritmo robusto para estimar la frecuencia fundamental (f0)
        # de una sola voz/instrumento sonando a la vez (monofónico).
        f0, voiced_flag, _ = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=SAMPLE_RATE,
            frame_length=BLOCK_SIZE,
        )

        frecuencias_validas = f0[voiced_flag]
        if len(frecuencias_validas) == 0:
            return  # silencio o ruido de fondo, no se detectó una nota clara

        frecuencia = float(np.nanmedian(frecuencias_validas))
        nota = frecuencia_a_nota(frecuencia)

        if nota and nota != self._ultima_nota:
            self._ultima_nota = nota
            self.callback_nota(nota, frecuencia)

    def iniciar(self):
        self.stream = sd.InputStream(
            channels=1,
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            callback=self._procesar_bloque,
        )
        self.stream.start()

    def detener(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None


def nota_coincide(nota_detectada, nota_esperada, tolerancia_semitonos=0):
    """
    Compara la nota detectada contra la esperada por la partitura.
    tolerancia_semitonos=0 exige coincidencia exacta; puedes subirlo a 1 si
    quieres ser un poco más permisivo con la afinación.
    """
    if nota_detectada is None:
        return False
    midi_detectada = round(librosa.note_to_midi(nota_detectada))
    midi_esperada = round(librosa.note_to_midi(nota_esperada))
    
    return (midi_detectada % 12) == (midi_esperada % 12)


if __name__ == "__main__":
    def mostrar(nota, frecuencia):
        print(f"Nota detectada: {nota}  ({frecuencia:.1f} Hz)")

    detector = DetectorDeNotas(mostrar)
    detector.iniciar()
    print("Escuchando... toca una nota. Presiona Ctrl+C para salir")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        detector.detener()
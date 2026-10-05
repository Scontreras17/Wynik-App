"""
Servicio para la captura de micrófono en tiempo real y detección de notas (pitch detection).
"""

from typing import Callable, Optional
import numpy as np
import sounddevice as sd
import librosa

from .notacion_service import nota_coincide

SAMPLE_RATE = 22050
BLOCK_SIZE = 4096  # Búfer amplio para mejorar precisión en notas graves (E2, F#2)
UMBRAL_RMS_SILENCIO = 0.15


class MicrofonoNoDisponibleError(Exception):
    """Excepción lanzada cuando no se puede abrir el dispositivo de entrada de audio."""
    pass


def frecuencia_a_nota(frecuencia_hz: Optional[float]) -> Optional[str]:
    """Convierte una frecuencia en Hertz a la nota musical en notación científica (ej. 'A4')."""
    if frecuencia_hz is None or frecuencia_hz <= 0 or np.isnan(frecuencia_hz):
        return None
    midi = librosa.hz_to_midi(frecuencia_hz)
    return librosa.midi_to_note(round(midi))


class DetectorDeNotas:
    """
    Escucha el flujo de audio del micrófono en un hilo secundario y notifica
    vía callback cada vez que se detecta una nota diferente a la anterior.
    """

    def __init__(self, callback_nota: Callable[[str, float], None], device=None, umbral_rms: float = UMBRAL_RMS_SILENCIO):
        self.callback_nota = callback_nota
        self.device = device
        self.umbral_rms = umbral_rms
        self.stream: Optional[sd.InputStream] = None
        self.samplerate: int = SAMPLE_RATE
        self._ultima_nota: Optional[str] = None

    def _procesar_bloque(self, indata, frames, time_info, status):
        audio = indata[:, 0]

        # 1. Filtro RMS para ignorar silencios y ruidos débiles
        rms = float(np.sqrt(np.mean(audio**2)))
        if rms < self.umbral_rms:
            self._ultima_nota = None
            return

        # 2. Detección por algoritmo pYIN
        try:
            f0, voiced_flag, _ = librosa.pyin(
                audio,
                fmin=librosa.note_to_hz("E2"),  # Mi2 (Guitarra grave)
                fmax=librosa.note_to_hz("E5"),  # Mi5 (Guitarra aguda)
                sr=self.samplerate,
                frame_length=len(audio),
            )

            frecuencias_validas = f0[voiced_flag]
            if len(frecuencias_validas) == 0:
                return

            frecuencia = float(np.nanmedian(frecuencias_validas))
            nota = frecuencia_a_nota(frecuencia)

            if nota and nota != self._ultima_nota:
                self._ultima_nota = nota
                self.callback_nota(nota, frecuencia)
        except Exception as error:
            print(f"[DetectorDeNotas] Error procesando bloque: {error}")

    def iniciar(self):
        """Inicia la captura del micrófono."""
        try:
            info_dispositivo = sd.query_devices(self.device, "input")
            self.samplerate = int(info_dispositivo["default_samplerate"])

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
        """Detiene y cierra el stream de captura."""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            self._ultima_nota = None

"""
Servicio para la síntesis de audio guía y utilidades de reproducción.
"""

import wave
from typing import List, Dict, Any, Optional
import numpy as np
import librosa


def formatear_tiempo(segundos: Optional[float]) -> str:
    """
    Formatea una duración en segundos a una cadena MM:SS.
    """
    if segundos is None or np.isnan(segundos) or segundos < 0:
        return "00:00"
    mins = int(segundos // 60)
    secs = int(segundos % 60)
    return f"{mins:02d}:{secs:02d}"


def generar_audio_guia(
    notas_partitura: List[Dict[str, Any]],
    bpm: float,
    ruta_salida: str = "temp_guia.wav",
    sample_rate: int = 22050
) -> Optional[str]:
    """
    Sintetiza una pista de audio WAV de guía a partir de las notas de la partitura
    usando síntesis senoidal con decaimiento exponencial.
    """
    if not notas_partitura:
        return None

    segundos_por_beat = 60.0 / max(bpm, 1.0)
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
            t = np.linspace(0, duracion_sec, num_samples, endpoint=False)
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

    with wave.open(ruta_salida, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(buffer_int16.tobytes())

    return ruta_salida

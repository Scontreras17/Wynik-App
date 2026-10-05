"""
Servicio para cálculos de notación musical, pasos diatónicos y coincidencia de afinación.
No depende de librerías gráficas (Kivy/KivyMD).
"""

from typing import Optional
import librosa

_LETRA_A_SOLFEO = {
    "C": "Do",
    "D": "Re",
    "E": "Mi",
    "F": "Fa",
    "G": "Sol",
    "A": "La",
    "B": "Si",
}

_LETRA_A_PASO = {
    "C": 0,
    "D": 1,
    "E": 2,
    "F": 3,
    "G": 4,
    "A": 5,
    "B": 6,
}


def paso_diatonico(nombre_nota: str) -> int:
    """
    Calcula el paso diatónico de una nota musical para su posicionamiento en el pentagrama.
    Ejemplo: 'C4' -> 4 * 7 + 0 = 28
    """
    letra = nombre_nota[0]
    octava = int(nombre_nota[-1])
    return octava * 7 + _LETRA_A_PASO[letra]


PASO_B4 = paso_diatonico("B4")  # Línea 3 (central) en Clave de Sol es Si4 (B4)


def nombre_para_mostrar(nombre_nota: Optional[str], usar_solfeo: bool) -> str:
    """
    Convierte el nombre de una nota (ej. 'C4') a solfeo ('Do4') si usar_solfeo es True.
    """
    if not usar_solfeo or not nombre_nota:
        return nombre_nota or ""
    letra = nombre_nota[0]
    resto = nombre_nota[1:]
    return _LETRA_A_SOLFEO.get(letra, letra) + resto


def nota_coincide(nota_detectada: Optional[str], nota_esperada: Optional[str], tolerancia_semitonos: int = 0) -> bool:
    """
    Compara la nota detectada contra la esperada por la partitura (mismo tono módulo 12).
    """
    if nota_detectada is None or nota_esperada is None:
        return False
    try:
        midi_detectada = round(librosa.note_to_midi(nota_detectada))
        midi_esperada = round(librosa.note_to_midi(nota_esperada))
        return (midi_detectada % 12) == (midi_esperada % 12)
    except Exception:
        return False

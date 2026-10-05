"""
Servicio para la carga y procesamiento de partituras MusicXML.
"""

import os
from typing import List, Dict, Any
from music21 import converter, note, chord

EXTENSIONES_PERMITIDAS = {".xml", ".musicxml", ".mxl"}


def validar_extension_partitura(ruta_archivo: str) -> bool:
    """Verifica si la ruta corresponde a un formato de partitura soportado."""
    if not ruta_archivo:
        return False
    _, extension = os.path.splitext(ruta_archivo.lower())
    return extension in EXTENSIONES_PERMITIDAS


def cargar_partitura(ruta_archivo: str) -> List[Dict[str, Any]]:
    """
    Lee un archivo MusicXML (.xml, .musicxml, .mxl) y devuelve una lista de notas:
    [
        {"nombre": "E4", "offset_beats": 0.0, "duracion_beats": 1.0},
        ...
    ]

    - nombre: nota en notación científica (ej. C4 = Do central).
    - offset_beats: posición en pulsos desde el inicio de la pieza.
    - duracion_beats: duración de la nota en pulsos (quarterLength).
    """
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"No se encontró el archivo de partitura: {ruta_archivo}")

    partitura = converter.parse(ruta_archivo)
    notas_planas = partitura.flatten().notes

    resultado: List[Dict[str, Any]] = []
    for elemento in notas_planas:
        if isinstance(elemento, note.Note):
            resultado.append({
                "nombre": elemento.nameWithOctave,
                "offset_beats": float(elemento.offset),
                "duracion_beats": float(elemento.quarterLength),
            })
        elif isinstance(elemento, chord.Chord):
            # En caso de acordes, se toma la nota más aguda
            nota_top = elemento.notes[-1]
            resultado.append({
                "nombre": nota_top.nameWithOctave,
                "offset_beats": float(elemento.offset),
                "duracion_beats": float(elemento.quarterLength),
            })

    return resultado

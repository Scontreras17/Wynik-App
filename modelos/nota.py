"""
Modelo de datos para la representación musical de notas.
Las funciones de cálculo musical residen en servicios.notacion_service.
"""

from dataclasses import dataclass
from servicios.notacion_service import (
    paso_diatonico,
    PASO_B4,
    nombre_para_mostrar,
    nota_coincide,
)


@dataclass
class Nota:
    """
    Representa una nota individual de una partitura.
    """
    nombre: str
    offset_beats: float
    duracion_beats: float

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "offset_beats": self.offset_beats,
            "duracion_beats": self.duracion_beats,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Nota":
        return cls(
            nombre=data["nombre"],
            offset_beats=float(data["offset_beats"]),
            duracion_beats=float(data["duracion_beats"]),
        )

    def __getitem__(self, item: str):
        # Permite acceder como diccionario (compatibilidad: nota["nombre"])
        return getattr(self, item)


__all__ = [
    "Nota",
    "paso_diatonico",
    "PASO_B4",
    "nombre_para_mostrar",
    "nota_coincide",
]

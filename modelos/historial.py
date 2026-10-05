"""
Modelo para una entrada en el historial de partituras recientes.
"""

from dataclasses import dataclass


@dataclass
class EntradaHistorial:
    """
    Representa un registro de partitura en el historial.
    """
    nombre: str
    ruta: str

    def to_dict(self) -> dict:
        return {"nombre": self.nombre, "ruta": self.ruta}

    @classmethod
    def from_dict(cls, data: dict) -> "EntradaHistorial":
        return cls(nombre=data["nombre"], ruta=data["ruta"])

    def __getitem__(self, item: str):
        # Permite acceso estilo diccionario: item["nombre"]
        return getattr(self, item)

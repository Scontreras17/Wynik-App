"""
Modelo de datos para una partitura cargada.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Partitura:
    """
    Representa una partitura completa con su metadata y lista de notas.
    """
    nombre: str
    ruta: str
    notas: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def total_notas(self) -> int:
        return len(self.notas)

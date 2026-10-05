"""
Módulo de compatibilidad hacia atrás para la carga de partituras MusicXML.
Delega en los servicios modulares correspondientes.
"""

from servicios.partitura_service import cargar_partitura
from vistas.dialogs import abrir_selector_de_archivo

__all__ = ["cargar_partitura", "abrir_selector_de_archivo"]

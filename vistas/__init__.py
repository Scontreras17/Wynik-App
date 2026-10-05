"""
Módulo de vistas y componentes de interfaz de usuario de Wynik.
Todas las pantallas y componentes gráficos residen en este paquete.
"""

from .screens import (
    MenuScreen,
    ElegirPartituraScreen,
    AjustesInicioScreen,
    InterpreteScreen,
)
from .widgets import PartituraWidget
from .dialogs import abrir_selector_de_archivo
from .app import WynikApp, KV_PATH

__all__ = [
    "MenuScreen",
    "ElegirPartituraScreen",
    "AjustesInicioScreen",
    "InterpreteScreen",
    "PartituraWidget",
    "abrir_selector_de_archivo",
    "WynikApp",
    "KV_PATH",
]

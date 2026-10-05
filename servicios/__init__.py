"""
Módulo de servicios de Wynik: procesamiento musical, audio, captura y persistencia.
Todas las funciones que no hacen uso de Kivy ni KivyMD residen en esta capa de servicios.
"""

from .partitura_service import (
    cargar_partitura,
    validar_extension_partitura,
)
from .audio_service import (
    generar_audio_guia,
    formatear_tiempo,
)
from .detector_service import (
    DetectorDeNotas,
    MicrofonoNoDisponibleError,
    frecuencia_a_nota,
)
from .historial_service import (
    cargar_historial,
    guardar_historial,
    agregar_al_historial,
    HISTORIAL_PATH_DEFAULT,
)
from .notacion_service import (
    paso_diatonico,
    PASO_B4,
    nombre_para_mostrar,
    nota_coincide,
)

__all__ = [
    "cargar_partitura",
    "validar_extension_partitura",
    "generar_audio_guia",
    "formatear_tiempo",
    "DetectorDeNotas",
    "MicrofonoNoDisponibleError",
    "frecuencia_a_nota",
    "cargar_historial",
    "guardar_historial",
    "agregar_al_historial",
    "HISTORIAL_PATH_DEFAULT",
    "paso_diatonico",
    "PASO_B4",
    "nombre_para_mostrar",
    "nota_coincide",
]

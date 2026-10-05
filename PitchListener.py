"""
Módulo de compatibilidad hacia atrás para la detección de afinación por micrófono.
Delega en los servicios modulares correspondientes.
"""

from servicios.notacion_service import nota_coincide
from servicios.detector_service import (
    SAMPLE_RATE,
    BLOCK_SIZE,
    DetectorDeNotas,
    MicrofonoNoDisponibleError,
    frecuencia_a_nota,
)

__all__ = [
    "SAMPLE_RATE",
    "BLOCK_SIZE",
    "DetectorDeNotas",
    "MicrofonoNoDisponibleError",
    "frecuencia_a_nota",
    "nota_coincide",
]

if __name__ == "__main__":
    def mostrar(nota, frecuencia):
        print(f"Nota detectada: {nota}  ({frecuencia:.1f} Hz)")

    detector = DetectorDeNotas(mostrar)
    try:
        detector.iniciar()
        print("Escuchando... toca una nota. Presiona Ctrl+C para salir")
        import time
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        detector.detener()
        print("\nDetenido.")
    except MicrofonoNoDisponibleError as err:
        print(f"Error de micrófono: {err}")
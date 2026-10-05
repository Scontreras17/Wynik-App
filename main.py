"""
Wynik 🎵
Punto de entrada de la aplicación de práctica musical con reconocimiento en tiempo real.
"""

from kivy.core.window import Window
from vistas import WynikApp

# Fijar tamaño de ventana para simular formato de dispositivo móvil
Window.size = (360, 640)


def main():
    """Inicializa y ejecuta la aplicación Wynik."""
    app = WynikApp()
    app.run()


if __name__ == "__main__":
    main()
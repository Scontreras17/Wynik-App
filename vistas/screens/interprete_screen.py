"""
Pantalla de práctica e interpretación en tiempo real.
"""

from kivy.uix.screenmanager import Screen
from kivymd.app import MDApp


class InterpreteScreen(Screen):
    """
    Pantalla interactiva que contiene el pentagrama, detector de micrófono
    y reproductor de audio guía.
    """

    def on_enter(self):
        """Al ingresar a la pantalla, se activa la escucha del micrófono."""
        MDApp.get_running_app().iniciar_escucha()

    def on_leave(self):
        """Al salir, se detiene la escucha y la reproducción de audio."""
        app = MDApp.get_running_app()
        app.detener_escucha()
        app.detener_audio()

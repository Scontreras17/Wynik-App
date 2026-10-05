"""
Componentes de diálogo para la interfaz de Wynik.
"""

import os
from typing import Callable, Optional
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserListView
from kivymd.uix.button import MDButton, MDButtonText


def abrir_selector_de_archivo(callback_ruta_seleccionada: Callable[[Optional[str]], None]) -> None:
    """
    Abre un diálogo modal para seleccionar archivos MusicXML (.xml, .musicxml, .mxl).
    Llama a `callback_ruta_seleccionada` pasando la ruta absoluta o None si se cancela.
    """
    popup = ModalView(size_hint=(0.95, 0.85), auto_dismiss=False)
    layout = BoxLayout(orientation="vertical", padding="10dp", spacing="10dp")

    filechooser = FileChooserListView(
        filters=["*.xml", "*.musicxml", "*.mxl"],
        path=os.path.expanduser("~"),
    )

    btn_layout = BoxLayout(size_hint_y=None, height="48dp", spacing="10dp")

    def _cancelar(instance):
        popup.dismiss()
        callback_ruta_seleccionada(None)

    def _seleccionar(instance):
        seleccion = filechooser.selection
        ruta = seleccion[0] if seleccion else None
        popup.dismiss()
        callback_ruta_seleccionada(ruta)

    btn_cancelar = MDButton(on_release=_cancelar)
    btn_cancelar.add_widget(MDButtonText(text="Cancelar"))

    btn_aceptar = MDButton(on_release=_seleccionar)
    btn_aceptar.add_widget(MDButtonText(text="Seleccionar"))

    btn_layout.add_widget(btn_cancelar)
    btn_layout.add_widget(btn_aceptar)

    layout.add_widget(filechooser)
    layout.add_widget(btn_layout)

    popup.add_widget(layout)
    popup.open()

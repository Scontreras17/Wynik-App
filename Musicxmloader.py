"""
Utilidades para cargar una partitura en formato MusicXML (.xml / .musicxml / .mxl)
y convertirla en una lista simple de notas que Wynik pueda usar para comparar
contra lo que el usuario está tocando.

Instalación:
    pip install music21 plyer
"""

from music21 import converter, note, chord


def cargar_partitura(ruta_archivo):
    """
    Lee un archivo MusicXML y devuelve una lista de diccionarios:
    [{"nombre": "E4", "offset_beats": 0.0, "duracion_beats": 1.0}, ...]

    - nombre: nota en notación científica (C4 = Do central)
    - offset_beats: en qué pulso (beat) empieza la nota, desde el inicio de la partitura
    - duracion_beats: cuántos pulsos dura esa nota
    """
    partitura = converter.parse(ruta_archivo)
    notas_planas = partitura.flatten().notes  # ignora silencios, dinámicas, texto, etc.

    resultado = []
    for elemento in notas_planas:
        if isinstance(elemento, note.Note):
            resultado.append({
                "nombre": elemento.nameWithOctave,   # ej: "E4"
                "offset_beats": float(elemento.offset),
                "duracion_beats": float(elemento.quarterLength),
            })
        elif isinstance(elemento, chord.Chord):
            # Si la partitura trae un acorde, por ahora tomamos solo la nota más aguda.
            # (Detectar acordes completos con el micrófono es mucho más difícil —
            # ver la nota sobre esto en la explicación.)
            nota_top = elemento.notes[-1]
            resultado.append({
                "nombre": nota_top.nameWithOctave,
                "offset_beats": float(elemento.offset),
                "duracion_beats": float(elemento.quarterLength),
            })
    return resultado


def abrir_selector_de_archivo(callback_ruta_seleccionada):
    """
    Abre el explorador de archivos nativo del sistema operativo filtrado a MusicXML.
    `callback_ruta_seleccionada` recibe la ruta (str) del archivo elegido, o None si
    el usuario canceló.

    Uso típico (por ejemplo en el botón "Subir Partitura" del menú):

        from musicxml_loader import abrir_selector_de_archivo, cargar_partitura

        def on_release_subir_partitura(self):
            abrir_selector_de_archivo(self.procesar_partitura_subida)

        def procesar_partitura_subida(self, ruta):
            if ruta:
                notas = cargar_partitura(ruta)
                # guarda `notas` donde tu app lo necesite (App, ScreenManager, etc.)
    """
    from plyer import filechooser

    def _on_selection(seleccion):
        ruta = seleccion[0] if seleccion else None
        callback_ruta_seleccionada(ruta)

    filechooser.open_file(
        title="Selecciona una partitura MusicXML",
        filters=[("MusicXML", "*.xml", "*.musicxml", "*.mxl")],
        on_selection=_on_selection,
    )


if __name__ == "__main__":
    # Prueba rápida por consola: reemplaza por la ruta de un .xml de prueba
    notas = cargar_partitura("mi_partitura.xml")
    for n in notas[:10]:
        print(n)
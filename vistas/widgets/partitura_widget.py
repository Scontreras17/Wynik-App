"""
Widget personalizado para la visualización del pentagrama y notas musicales.
"""

from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Line
from kivymd.app import MDApp

from servicios.notacion_service import paso_diatonico, PASO_B4


class PartituraWidget(Widget):
    """
    Dibuja dinámicamente un pentagrama musical con las notas actuales y próximas,
    resaltando la nota esperada y coloreando los aciertos (verde) o fallos (rojo).
    """
    NOTAS_VISIBLES = 8
    ESPACIO_ENTRE_LINEAS = 14

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.redibujar, size=self.redibujar)

    def redibujar(self, *args):
        app = MDApp.get_running_app()
        if app is None:
            return

        self.canvas.clear()
        centro_y = self.center_y

        with self.canvas:
            Color(0, 0, 0, 1)
            # Dibujar las 5 líneas del pentagrama
            for i in range(5):
                y = centro_y + (i - 2) * self.ESPACIO_ENTRE_LINEAS
                Line(points=[self.x + 20, y, self.right - 20, y], width=1.2)

            if not getattr(app, "notas_partitura", None):
                return

            inicio = max(0, app.indice_actual - 1)
            fin = min(len(app.notas_partitura), inicio + self.NOTAS_VISIBLES)
            notas_a_mostrar = app.notas_partitura[inicio:fin]
            if not notas_a_mostrar:
                return

            ancho_disponible = max((self.right - 20) - (self.x + 40), 10)
            paso_x = ancho_disponible / len(notas_a_mostrar)
            y_min_pentagrama = centro_y - 2 * self.ESPACIO_ENTRE_LINEAS
            y_max_pentagrama = centro_y + 2 * self.ESPACIO_ENTRE_LINEAS

            for offset, nota_info in enumerate(notas_a_mostrar):
                indice_real = inicio + offset
                x = self.x + 40 + offset * paso_x

                paso = paso_diatonico(nota_info["nombre"])
                diferencia_pasos = paso - PASO_B4  # Referenciado a Si4 (línea central)
                y = centro_y + diferencia_pasos * (self.ESPACIO_ENTRE_LINEAS / 2)

                # Líneas adicionales si la nota está fuera del rango del pentagrama
                if (diferencia_pasos % 2 == 0) and (y < y_min_pentagrama or y > y_max_pentagrama):
                    Color(0, 0, 0, 1)
                    Line(points=[x - 8, y, x + 8, y], width=1.2)

                # Colorear según el estado de la nota
                estado = app.estado_notas[indice_real] if indice_real < len(app.estado_notas) else None
                if estado is True:
                    Color(0.2, 0.7, 0.2, 1)      # Acierto: Verde
                elif estado is False:
                    Color(0.85, 0.1, 0.1, 1)     # Error: Rojo
                elif indice_real == app.indice_actual:
                    Color(0.2, 0.45, 0.9, 1)     # Nota actual esperada: Azul
                else:
                    Color(0, 0, 0, 1)            # Futuras notas: Negro

                # Cabeza de la nota
                Ellipse(pos=(x - 6, y - 5), size=(12, 10))

                # Plica (plica vertical)
                largo_plica = 28
                if y < centro_y:
                    Line(points=[x + 5, y, x + 5, y + largo_plica], width=1.2)
                else:
                    Line(points=[x - 5, y, x - 5, y - largo_plica], width=1.2)

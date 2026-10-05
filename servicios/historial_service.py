"""
Servicio para la persistencia del historial de partituras recientes en JSON.
"""

import os
import json
from typing import List, Dict

# Ruta predeterminada al archivo JSON en el directorio raíz del proyecto
DIRECTORIO_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORIAL_PATH_DEFAULT = os.path.join(DIRECTORIO_RAIZ, "historial_partituras.json")


def cargar_historial(ruta_archivo: str = HISTORIAL_PATH_DEFAULT) -> List[Dict[str, str]]:
    """
    Carga la lista de partituras guardadas en el historial.
    Retorna una lista de diccionarios con formato:
    [{"nombre": "the-entertainer", "ruta": "/ruta/al/archivo.mxl"}, ...]
    """
    if os.path.exists(ruta_archivo):
        try:
            with open(ruta_archivo, "r", encoding="utf-8") as archivo:
                datos = json.load(archivo)
                if isinstance(datos, list):
                    return datos
        except (json.JSONDecodeError, OSError) as error:
            print(f"[HistorialService] Error al leer historial: {error}")
            return []
    return []


def guardar_historial(historial: List[Dict[str, str]], ruta_archivo: str = HISTORIAL_PATH_DEFAULT) -> None:
    """
    Guarda la lista de partituras en el archivo de historial en formato JSON con indentación.
    """
    try:
        with open(ruta_archivo, "w", encoding="utf-8") as archivo:
            json.dump(historial, archivo, ensure_ascii=False, indent=2)
    except OSError as error:
        print(f"[HistorialService] Error al guardar historial: {error}")


def agregar_al_historial(
    historial: List[Dict[str, str]],
    nombre: str,
    ruta: str,
    ruta_archivo: str = HISTORIAL_PATH_DEFAULT
) -> List[Dict[str, str]]:
    """
    Agrega una partitura al historial si no se encuentra ya presente y guarda los cambios.
    """
    ya_estaba = any(entrada.get("ruta") == ruta for entrada in historial)
    if not ya_estaba:
        nuevo_historial = list(historial)
        nuevo_historial.append({"nombre": nombre, "ruta": ruta})
        guardar_historial(nuevo_historial, ruta_archivo)
        return nuevo_historial
    return historial

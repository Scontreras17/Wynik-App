# Wynik 🎵

Wynik es una aplicación de escritorio (hecha con **Kivy / KivyMD**) que te ayuda a practicar un instrumento: carga una partitura en formato MusicXML, la app la reproduce como guía de audio y, usando el micrófono, verifica en tiempo real si estás tocando la nota correcta.

Esta guía está pensada para que cualquier persona, **sin conocimientos previos de Python**, pueda dejar la app funcionando desde cero.

---

## 1. Requisitos previos

Antes de instalar nada, necesitas tener en tu computador:

| Requisito | Versión recomendada | Para qué se usa |
|---|---|---|
| Python | 3.10 u 11 (evitar 3.12+ por compatibilidad con Kivy) | Ejecutar la aplicación |
| pip | (viene con Python) | Instalar las librerías |
| Micrófono | Cualquiera (integrado o externo) | Detectar las notas que tocas |
| Sistema operativo | Windows 10/11, macOS o Linux | — |

> 💡 Si nunca has instalado Python, descárgalo desde [python.org/downloads](https://www.python.org/downloads/). **En Windows**, durante la instalación marca la casilla **"Add python.exe to PATH"**, es fundamental.

Para comprobar que Python quedó bien instalado, abre una terminal (o *Símbolo del sistema* en Windows) y escribe:

```bash
python --version
```

Debería mostrarte algo como `Python 3.11.x`. Si te da error, revisa la instalación antes de continuar.

---

## 2. Instalación paso a paso

### Paso 1 — Descargar el proyecto

Copia la carpeta del proyecto (con el archivo `main.py`) a algún lugar de tu computador, por ejemplo `Documentos/Wynik`.

### Paso 2 — Abrir una terminal en esa carpeta

- **Windows:** entra a la carpeta en el Explorador, haz clic en la barra de dirección, escribe `cmd` y presiona Enter.
- **macOS:** abre *Terminal*, escribe `cd ` (con un espacio) y arrastra la carpeta del proyecto a la ventana, luego Enter.
- **Linux:** clic derecho dentro de la carpeta → "Abrir terminal aquí".

### Paso 3 — Crear un entorno virtual (recomendado)

Esto evita que las librerías de Wynik interfieran con otros programas de Python que tengas instalados.

```bash
python -m venv venv
```

Actívalo:

- **Windows (cmd):**
  ```bash
  venv\Scripts\activate
  ```
- **macOS / Linux:**
  ```bash
  source venv/bin/activate
  ```

Sabrás que quedó activado porque en la terminal aparecerá `(venv)` al inicio de la línea.

### Paso 4 — Instalar las dependencias del sistema

Algunas librerías necesitan un componente extra instalado en el sistema operativo (no basta con `pip`):

- **Windows:** normalmente no necesitas nada extra, `sounddevice` trae lo necesario.
- **macOS:**
  ```bash
  brew install portaudio
  ```
  (si no tienes Homebrew, instálalo primero desde [brew.sh](https://brew.sh))
- **Linux (Ubuntu/Debian):**
  ```bash
  sudo apt update
  sudo apt install portaudio19-dev python3-dev
  ```

### Paso 5 — Instalar las librerías de Python

Con el entorno virtual activado, ejecuta:

```bash
pip install kivy kivymd numpy sounddevice librosa music21
```

Esto puede tardar unos minutos, especialmente `librosa` y `kivy`.

> ⚠️ Si `pip install kivy` falla en Windows, prueba primero actualizar pip con `python -m pip install --upgrade pip` y vuelve a intentarlo.

### Paso 6 — Ejecutar la aplicación

Todavía dentro de la carpeta del proyecto y con `(venv)` activo:

```bash
python main.py
```

Debería abrirse una ventana de 360x640 (simulando un celular) con el menú principal de Wynik.

---

## 3. Cómo usar la aplicación

### Pantalla de Menú principal

Verás tres botones:

| Botón | Qué hace |
|---|---|
| **Subir Partitura** | Abre un explorador de archivos para cargar un archivo `.xml`, `.musicxml` o `.mxl` desde tu computador |
| **Elegir Partitura** | Muestra el historial de partituras que ya subiste antes, para volver a abrirlas sin buscarlas de nuevo |
| **Ajustes** | (Acceso directo, actualmente los ajustes de cada partitura se configuran justo antes de tocarla, ver más abajo) |

### Paso a paso para practicar una canción

1. **Sube una partitura:** toca **"Subir Partitura"**, navega hasta tu archivo MusicXML y selecciónalo con el botón **"Seleccionar"**. La app te llevará automáticamente a la pantalla de **Ajustes de inicio**.
   - Si ya la habías subido antes, en vez de esto puedes ir a **"Elegir Partitura"** y tocarla directamente de la lista.
2. **Configura los ajustes de inicio** (pantalla "Ajustes de inicio"):
   - **"Seguir de largo al fallar"** (activado por defecto): si lo dejas activado, la partitura avanza sola según el tempo aunque falles una nota. Si lo desactivas, la app **se detiene y espera** hasta que toques la nota correcta antes de avanzar.
   - **"Ver notas en Do-Re-Mi"**: cambia la notación de inglesa (C, D, E...) a solfeo (Do, Re, Mi...) en pantalla.
   - **Tempo (BPM)**: usa las flechas ◀ ▶ para subir o bajar la velocidad de reproducción, en pasos de 5 BPM (rango 40–240).
3. Presiona el botón verde **"Iniciar"** (abajo a la derecha) para pasar a la pantalla de práctica.
4. **Pantalla de intérprete:**
   - Verás un mini-pentagrama con las próximas notas de la canción.
   - Debajo, un texto te indica la **nota esperada** en cada momento.
   - Toca esa nota con tu instrumento cerca del micrófono:
     - Si es correcta, la nota se pinta de **verde** y aparece "✓ ... correcta".
     - Si es incorrecta, se pinta de **rojo** y aparece "✗ tocaste X, esperada Y".
   - Abajo tienes un reproductor con la guía de audio sintetizada de la partitura: **Play/Pausa**, **Stop**, **retroceder/adelantar 5 segundos** y control de **volumen**. Puedes usarlo para escuchar cómo debería sonar la canción antes o durante la práctica.
5. Para salir, presiona la flecha (←) arriba a la izquierda; esto detiene el micrófono y el audio y te devuelve a Ajustes de inicio.

---

## 4. Sobre la detección por micrófono (importante)

- La app escucha continuamente por el micrófono mientras estás en la pantalla de práctica.
- Existe un **umbral de sensibilidad** interno: si el sonido captado es muy débil (por debajo del umbral), se ignora para evitar que ruido ambiente se detecte como nota. Si notas que la app **no reacciona** cuando tocas suave, tendrás que tocar/soplar/pulsar con un poco más de volumen, o acercar el instrumento al micrófono.
- Si por el contrario la app **detecta notas sin que estés tocando nada** (ruido de fondo, voces, roce), significa que el umbral de sensibilidad configurado en el código es demasiado bajo para tu ambiente; hay que subirlo.
- Deja el entorno lo más silencioso posible mientras practicas para obtener mejores resultados, y usa preferentemente auriculares o parlantes con volumen moderado si estás reproduciendo la guía de audio al mismo tiempo (para que el micrófono no capte esa guía como si fuera tu instrumento).

---

## 5. Solución de problemas comunes

| Problema | Posible causa / solución |
|---|---|
| `ModuleNotFoundError: No module named 'kivy'` (o kivymd, librosa, etc.) | No activaste el entorno virtual, o falta instalar esa librería. Repite el Paso 5. |
| La app dice "No se pudo abrir el micrófono" | Otro programa está usando el micrófono, o el sistema operativo no le dio permisos a Python/la terminal para usarlo (revisa Configuración → Privacidad → Micrófono). |
| Al tocar la app no detecta nada | Sube el volumen al tocar / acerca el instrumento al micrófono; revisa el punto 4 de esta guía. |
| Detecta notas todo el tiempo aunque no estés tocando | Hay ruido de fondo o la sensibilidad del micrófono está muy alta; prueba en un ambiente más silencioso. |
| Error al cargar el archivo de partitura | Verifica que el archivo sea realmente `.xml`, `.musicxml` o `.mxl` válido (exportado desde MuseScore, Finale, Sibelius, etc.). |
| La ventana se ve muy pequeña o cortada | La app está fijada a 360x640 px simulando un celular; simplemente no la redimensiones, o ajusta la resolución de tu pantalla. |
| `pip install kivy` falla en Windows | Actualiza pip (`python -m pip install --upgrade pip`) y vuelve a intentar; si persiste, instala Microsoft C++ Build Tools. |

---

## 6. Resumen rápido (para quien ya instaló todo antes)

```bash
cd Wynik
source venv/bin/activate      # o venv\Scripts\activate en Windows
python main.py
```

¡Y listo! 🎶
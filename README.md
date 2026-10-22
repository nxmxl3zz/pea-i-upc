# PEA-i UPC

Programa Estadístico de Análisis de Investigación para la Universidad Popular del Cesar. Incluye una consola C++17 y una aplicación Python con interfaz CustomTkinter. La ventana usa el motor C++ como proceso local (mensajes JSON por `stdin`/`stdout`) y, si no puede iniciarlo, su propio motor Python.

## Organización del repositorio

```text
Iniciar PEA-i.pyw                 Lanzador de doble clic en Windows
src/cpp/Taller2_REMR.cpp          Consola y backend C++
src/python/Taller2_REMR.py        Interfaz Tkinter y motor Python autónomo
bin/windows/                      Ejecutable C++ de 64 bits y huellas de integridad
data/pea_upc.csv                  Archivo único de datos (captura pública UPC)
data/README.md                    Procedencia y límites de los datos
docs/especificacion_tecnica.docx  Especificación técnica: modelo, estructuras, esquema y protocolo
docs/ENUNCIADO_TALLER_2.md        Requisitos del taller
docs/video_taller.mp4             Video del Taller 2: pilas, colas e interfaz
docs/video_parcial.mp4            Video del Parcial 2: indicador de producción
scripts/                          Regeneración de datos, documento y binario
tests/                            Pruebas del dominio, integración y carga
CMakeLists.txt                    Compilación C++
```

## Videos

- [**«PEA-i por dentro»**](docs/video_taller.mp4) (Taller 2, 5 min): la pila y la cola en el código y en la aplicación.
- [**«PEA-i: el indicador»**](docs/video_parcial.mp4) (Parcial 2, 5 min): las categorías del modelo Minciencias 2024, el cálculo del indicador y su uso en la aplicación.

## Instalación y ejecución

Se necesita Python 3.10 o posterior con Tkinter y CustomTkinter (`requirements.txt`). Si falta CustomTkinter, PEA-i ofrece instalarlo la primera vez que se abre.

- **Windows (64 bits):** doble clic en **`Iniciar PEA-i.pyw`**, o `py -3 src/python/Taller2_REMR.py`. Usa el ejecutable incluido `bin/windows/pea_cpp.exe`, que solo se acepta si su SHA-256 coincide con las fuentes; no hace falta compilar.
- **Linux:** `python3 src/python/Taller2_REMR.py`. Si el Python del sistema no admite `pip` (PEP 668), cree un entorno virtual con `python3 -m venv .venv` y `.venv/bin/pip install -r requirements.txt`, y ejecute con `.venv/bin/python`. Con CMake y un compilador C++17, la ventana compila el motor C++ en Release cuando hace falta.
- **Solo la consola C++:** `bin\windows\pea_cpp.exe` en Windows; en Linux `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --config Release && ./build/pea_cpp`.

Opciones: `--data ARCHIVO` abre otro archivo de datos, `--python-backend` fuerza el motor Python y `--cpp-binary RUTA` usa otro ejecutable C++. El motor activo aparece en **Ayuda → Acerca de PEA-i**.

## Uso

- **Datos:** al iniciar se abre `data/pea_upc.csv` y **Guardar** escribe en él. **Archivo** permite iniciar vacío, abrir otro archivo, guardar como y exportar una copia para hoja de cálculo.
- **Registros:** grupos, investigadores, productos, planes y sus relaciones se crean, editan, desactivan y eliminan desde las tablas y las fichas. **Ctrl+Z** deshace.
- **Dashboard y Gráficos:** resúmenes, histogramas y distribuciones en las vistas Todos, Grupo, Investigador y Producto, con filtros de años y validación.
- **Validación y cola:** un producto queda validado si tiene año, tipología, un autor o un grupo activos y una URL o un DOI válido. La **Cola de revisión** atiende los rechazados en orden de llegada.

### Indicador de producción

PEA-i calcula el indicador del modelo Minciencias 2024 para un grupo o un investigador:

`Ind = 3,7·Nc.Top + 2,3·Nc.A + 0,4·Nc.B + 1,5·AP + 0,5·DPC + 1·Fr.A + 0,2·Fr.B + 0,1·Cohe + 0,3·Coop`

Cada término es un índice de 0 a 1 relativo al máximo entre las entidades activas cargadas, así que el indicador vale como máximo 10. Cada producto aporta según su categoría, uno de los 169 subtipos del modelo.

- **En la ventana:** **Importar → URL pública…**, pegue la ficha GrupLAC del grupo o la hoja de vida CvLAC del investigador, pulse **Importar datos detectados** y luego **Ver indicador**. También aparece en el dashboard al elegir un grupo o un investigador.
- **Categorías:** el importador estima la más baja de cada familia, porque las fichas públicas no la publican. Una categoría elegida a mano se conserva al reimportar.
- **Consola C++:** opción **12. Indicador**.

El cálculo completo está en el apartado 9 de la [especificación técnica](docs/especificacion_tecnica.docx).

### Importar información

La ventana importa CSV, Excel `.xlsx` (con `openpyxl`), URL públicas (fichas GrupLAC y CvLAC), PDF con texto (con `pdftotext`) y Word `.docx` (con `mammoth`), siempre con vista previa. Cada importación se guarda al instante y no duplica registros: agrega lo nuevo y actualiza lo que cambió. La consola C++ importa CSV. Los límites y controles de seguridad de las fuentes están en el apartado 7 de la especificación.

## Datos

`data/pea_upc.csv` (19 de octubre de 2026) reúne 66 grupos, 2.748 investigadores y 21.419 productos de las fichas públicas GrupLAC y CvLAC de la UPC, con sus planes y relaciones. Todo se guarda en un solo archivo (esquema 5) junto con la cola de revisión y el historial, y cada guardado deja una copia en `.backup/`. La procedencia, los límites y cómo actualizar la captura están en [data/README.md](data/README.md).

## Pruebas

```bash
python3 -m unittest discover -s tests/python -v
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
ctest --test-dir build --output-on-failure
```

En Windows use `py -3`. Las pruebas de interfaz necesitan una sesión gráfica y CustomTkinter; para repetirlas con el motor C++, defina `PEA_TEST_CPP=build/pea_cpp`. Las pruebas no modifican `data/`.


### Rafael Miranda

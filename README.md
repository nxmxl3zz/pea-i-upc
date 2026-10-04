# PEA-i UPC

Programa Estadístico de Análisis de Investigación para la Universidad Popular del Cesar. El proyecto contiene dos soluciones: una consola C++17 y una aplicación Python con Tkinter. La ventana inicia el motor C++ como proceso local cuando está disponible y usa el motor Python autónomo si no puede iniciarlo. La comunicación entre ambos usa JSON por `stdin`/`stdout`; no requiere abrir dos ventanas ni un servidor.

## Organización del repositorio

```text
Iniciar PEA-i.pyw                 Lanzador de doble clic en Windows
src/cpp/Taller2_REMR.cpp         Consola y backend C++
src/python/Taller2_REMR.py       Interfaz Tkinter y motor Python autónomo
bin/windows/                    Ejecutable C++ de 64 bits y huellas de integridad
data/real/                       Captura pública de grupos UPC y procedencia
docs/especificacion_tecnica.docx Especificación técnica de entrega
docs/esquema_datos.md            Contrato de persistencia CSV
docs/protocolo_backend.md        Protocolo entre Tkinter y C++
scripts/                       Regeneración de datos, documento y binario
tests/                         Pruebas del dominio, integración y carga
CMakeLists.txt                  Compilación C++
ENUNCIADO_TALLER_2.md           Requisitos del taller
```


## Instalación y ejecución

Descargue el ZIP del repositorio en GitHub y **extraiga la carpeta completa**, o use `git clone`. Se necesita Python 3.10 o posterior con Tkinter y una sesión de escritorio. Las funciones básicas no requieren paquetes de `pip`.

### Windows de 64 bits

Haga doble clic en **`Iniciar PEA-i.pyw`**. El repositorio incluye `bin/windows/pea_cpp.exe`, por lo que el uso normal no requiere CMake, NMake, Dev-C++ ni `g++`. Si la asociación de `.pyw` no funciona, abra PowerShell en la raíz del proyecto y ejecute:

```powershell
py -3 src/python/Taller2_REMR.py
```

El motor activo aparece en **Ayuda → Acerca de PEA-i**. Para ejecutar solo la consola C++ use `bin\windows\pea_cpp.exe`. Para forzar el motor Python use `py -3 src/python/Taller2_REMR.py --python-backend`.

### Linux

```bash
python3 src/python/Taller2_REMR.py
```

Si CMake y un compilador C++17 están instalados, la ventana compila y ejecuta el backend C++ cuando hace falta. Si no están disponibles, inicia el motor Python. Para compilar y abrir la consola por separado:

```bash
cmake -S . -B build
cmake --build build
./build/pea_cpp
```

Para indicar un ejecutable C++ propio use `--cpp-binary RUTA`. Para abrir una carpeta guardada al iniciar use `--data-dir RUTA`; la consola también admite esa opción.

## Uso de la ventana

Al iniciar se abre automáticamente `data/real`, salvo que se indique `--data-dir`. El menú **Archivo** permite iniciar vacío, abrir otra carpeta y guardar una copia. `data/real` se trata como muestra de solo lectura desde la ventana: use **Guardar como** para conservar cambios en otra carpeta.

La navegación lateral contiene Dashboard, Gráficos, Grupos, Investigadores, Productos, Planes, Relaciones y Cola de revisión. La sección actual queda resaltada; el botón ☰ contrae o despliega el menú. Las tablas muestran 100 filas por página y la búsqueda abarca el conjunto completo. Puede filtrar entidades por **Todos**, **Activos** o **Inactivos**.

Pulse un producto para abrir su ficha completa, con **Resumen**, **Autores**, **Grupos** y **Estadísticas**. Abrir la ficha conserva la búsqueda y la página de la lista. Para otras entidades, haga doble clic o pulse **Abrir ficha**. Los grupos incluyen pestañas de integrantes, planes y productos; los investigadores incluyen sus grupos y productos. Desde estas fichas puede editar registros, crear planes, vincular entidades y editar, desactivar o eliminar vínculos. Los vínculos inactivos siguen visibles para consultar su historia. El resumen muestra solo los campos con datos y lista los vacíos en una línea «Sin registrar». Las tablas ocultan las columnas que ningún registro ha llenado y las muestran en cuanto alguno lo tiene. Las categorías aparecen solo en el módulo de grupos: la del grupo y la de sus integrantes.

El dashboard reúne filtros, cuatro tarjetas de resumen, un histograma anual, barras por tipología y los productos de la consulta. Ofrece vistas **Todos**, **Grupo**, **Investigador** y **Producto**, con filtros de año y validación. Todos los filtros responden automáticamente al seleccionar o escribir; el rango personalizado también acepta Enter. No hay botones Aplicar/Limpiar. **Elegir…** abre un selector por nombre o ID con búsqueda y páginas sobre todos los registros, incluso los posteriores a la fila 100.

El histograma agrupa los productos de **20 años o más** en una columna; en 2026 incluye **2006 y anteriores**. El corte avanza con el año actual y siempre respeta la ventana elegida. La vista previa agrupa las tipologías menos frecuentes como «Otras tipologías (agrupadas)». **Gráficos** ofrece el desglose completo por año, tipología, validación y reglas incumplidas, con el mismo contexto del dashboard y barras desplazables. Un dato vacío no se inventa: el producto sigue en el total y aparece como «Sin dato». Los porcentajes usan el total de productos de la consulta, incluidos los datos desconocidos.

Puede crear, editar, desactivar y eliminar entidades y relaciones. Los formularios muestran campos obligatorios y conservan lo escrito si falla la validación. La **validación es automática**: un producto queda validado si tiene año, tipología, un autor y un grupo activos, y una URL o un DOI válido; si no, queda rechazado y su ficha indica qué reglas incumple. En la muestra incluida, 6.323 productos quedan validados y 40 rechazados (37 sin autor del censo y 3 con DOI mal formado). La **Cola de revisión** atiende esos casos por orden de llegada: **Enviar rechazados** los encola en una acción y **Revisar siguiente** permite corregir el producto y cerrar la revisión con una nota obligatoria. **Editar → Deshacer** revierte acciones. Los datos, la cola y el historial se conservan al guardar.

La barra superior indica la carpeta o muestra abierta y los cambios pendientes, con **Guardar** o **Guardar copia**. La barra inferior muestra resultados y errores. Atajos: **Ctrl+S** guardar, **Ctrl+Shift+S** guardar como, **Ctrl+N** iniciar vacío, **Ctrl+Z** deshacer y **Ctrl+Enter** guardar un formulario. El dashboard se desplaza verticalmente en ventanas pequeñas y ambas apariencias se conservan al navegar.

### Importar información

- **CSV:** ambos motores importan los archivos con los encabezados de [esquema_datos.md](docs/esquema_datos.md). La ventana propone el tipo según los encabezados y permite seleccionarlo por nombre. La vista previa indica filas aceptables y rechazadas.
- **Excel `.xlsx`:** la interfaz Python convierte la primera hoja a CSV antes de la vista previa. Requiere `openpyxl` (`pip install openpyxl`).
- **URL pública:** la interfaz Python muestra HTML, texto, CSV o PDF de texto antes de crear registros. Reconoce fichas GrupLAC/CvLAC y metadatos explícitos de artículos; otros sitios pueden mostrarse sin proponer campos. No ejecuta JavaScript de la página ni inicia sesión en sitios externos.
- **PDF local:** la interfaz Python requiere `pdftotext` de Poppler y texto seleccionable. Un PDF escaneado necesita OCR externo.
- **Word `.docx`:** la interfaz Python extrae texto para vista previa mediante `mammoth` (`pip install mammoth`).

La consola C++ importa CSV; en el uso integrado, Python consulta las fuentes y envía a C++ los registros aceptados.

## Datos incluidos y persistencia

`data/real` contiene **66 grupos, 2.736 investigadores, 6.363 productos, 66 planes, 3.291 membresías, 6.735 vínculos grupo-producto y 9.703 autorías** de fichas públicas GrupLAC. De los investigadores, 274 tienen una categoría CvLAC capturada; los campos sin fuente suficiente quedan vacíos. La [procedencia y límites de la captura](data/real/README.md) están documentados aparte. No se necesita Internet para consultar los CSV incluidos.

Cada carpeta de trabajo contiene `manifest.csv`, cuatro CSV de entidades, tres de relaciones, `cola_validacion.csv` e `historial.csv`. El esquema actual es la **versión 3**: los productos ya no tienen categoría, porque las fichas GrupLAC no la publican por producto. Las carpetas anteriores de versiones 1 y 2 se abren en ambos motores y se convierten al guardar (una categoría de producto escrita a mano se conserva en la observación); conviene conservar una copia antes de abrirlas. La carpeta `.backup` guarda los archivos del guardado anterior. Abra una carpeta editable en una sola instancia a la vez.

El esquema neutraliza en disco los valores que una hoja de cálculo podría interpretar como fórmulas y los recupera al cargar. **Archivo → Exportar para hoja de cálculo** crea una copia segura para consulta; esa exportación no incluye la cola ni el historial y no sustituye una carpeta de trabajo.

## Medidas y límites de seguridad

Las consultas web aceptan HTTP/HTTPS en puertos 80/443, rechazan direcciones locales y privadas, comprueban también cada redirección, desactivan el proxy heredado del entorno y conectan a una IP pública ya validada. La descarga limita la respuesta a 8 MB. La conexión tiene un tiempo de espera por operación de 15 segundos; un servidor que envía datos muy lentamente puede prolongar la consulta, por lo que no debe tratarse como una garantía de duración total.

Los archivos locales PDF, Word y Excel tienen un límite de 32 MB. Word y Excel se inspeccionan como archivos comprimidos antes de procesarlos: máximo 10.000 entradas y 128 MB declarados al descomprimir. La extracción PDF limita el texto a 5 millones de caracteres y aplica 25 segundos de espera total; en sistemas POSIX también impone límites de memoria y CPU al conversor. Las importaciones CSV limitan cada campo a 100.000 caracteres y cada archivo a 500.000 filas.

El binario Windows incluido se usa solo cuando coinciden su SHA-256 y la huella de las fuentes. Esas huellas detectan cambios accidentales o desajustes; al distribuirse junto con el ejecutable, **no autentican al autor**. Descargue el proyecto de una fuente en la que confíe. No se deben pegar tokens o contraseñas en URL de importación; el programa elimina parámetros de consulta al guardar las URL propuestas, salvo los identificadores públicos necesarios de GrupLAC/CvLAC.

## Verificación y actualización

Desde la raíz del proyecto:

```bash
python3 -m unittest discover -s tests/python -v
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

En Windows, sustituya `python3` por `py -3`. Las pruebas de PDF, Excel y Word omiten lo que dependa de herramientas opcionales no instaladas. Para actualizar un clon, cierre PEA-i y ejecute `git pull` desde la carpeta del proyecto; conserve sus datos de trabajo fuera de `data/real`, por ejemplo en `data/local/`.

Las regresiones de interfaz requieren una sesión gráfica y se omiten si no existe. Para recorrerlas también con C++, después de compilar:

```bash
PEA_TEST_CPP=build/pea_cpp python3 -m unittest discover -s tests/python -v
```

En Windows PowerShell: `$env:PEA_TEST_CPP = 'bin/windows/pea_cpp.exe'`, seguido de `py -3 -m unittest discover -s tests/python -v`. Estas pruebas usan repositorios temporales y no guardan cambios en `data/real`. El [plan UI/UX](PLAN_UI_UX.md) y la [guía de verificación](docs/UI_UX_VERIFICACION.md) describen el alcance, las comprobaciones y el recorrido manual para Windows.

`python3 scripts/import_upc_dataset.py` vuelve a consultar la lista de grupos públicos; necesita Internet, no reemplaza el conjunto existente si falla alguna importación y puede producir datos diferentes si cambian las fichas. Para consultar solo parte de la lista, use `--limit N --output OTRA_CARPETA`. `python3 scripts/build_real_sample.py` genera por separado una muestra pequeña en `data/sample_scienti/` y no reemplaza el conjunto de 66 grupos.

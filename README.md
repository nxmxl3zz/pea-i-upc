# PEA-i UPC

Programa Estadístico de Análisis de Investigación para la Universidad Popular del Cesar. El proyecto contiene dos soluciones: una consola C++17 y una aplicación Python con Tkinter. La ventana inicia el motor C++ como proceso local cuando está disponible y usa el motor Python autónomo si no puede iniciarlo. La comunicación entre ambos usa JSON por `stdin`/`stdout`; no requiere abrir dos ventanas ni un servidor.

## Organización del repositorio

```text
Iniciar PEA-i.pyw                 Lanzador de doble clic en Windows
src/cpp/Taller2_REMR.cpp         Consola y backend C++
src/python/Taller2_REMR.py       Interfaz Tkinter y motor Python autónomo
bin/windows/                    Ejecutable C++ de 64 bits y huellas de integridad
data/demo/                       Datos ficticios para demostración
data/real/                       Captura pública de grupos UPC y procedencia
docs/especificacion_tecnica.docx Especificación técnica de entrega
docs/esquema_datos.md            Contrato de persistencia CSV
docs/protocolo_backend.md        Protocolo entre Tkinter y C++
scripts/                       Regeneración de datos, documento y binario
tests/                         Pruebas del dominio, integración y carga
CMakeLists.txt                  Compilación C++
ENUNCIADO_TALLER_2.md           Requisitos del taller
```

`build/`, `data/local/`, `.claude/` y los archivos temporales no forman parte de la entrega. El documento de cambios de trabajo `docs/cambios_sesion.md` tampoco se publica.

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

Para indicar un ejecutable C++ propio use `--cpp-binary RUTA`. Para abrir una carpeta guardada al iniciar use `--data-dir RUTA`. La consola admite `--demo` y `--data-dir RUTA`.

## Uso de la ventana

Al iniciar se abre automáticamente `data/real`, salvo que se indique `--data-dir`. El menú **Archivo** permite iniciar vacío, abrir otra carpeta, cargar la demostración y guardar una copia. `data/demo` y `data/real` se tratan como muestras de solo lectura desde la ventana: use **Guardar como** para conservar cambios en otra carpeta.

La navegación lateral contiene Dashboard, Gráficos, Grupos, Investigadores, Productos, Planes, Relaciones y Cola de revisión. El botón ☰ contrae o despliega el menú. Las tablas muestran 100 filas por página y la búsqueda abarca el conjunto completo. En las pestañas de entidades, haga doble clic en una fila o pulse **Información** para abrir sus campos y productos relacionados.

El dashboard muestra productos únicos por vista (Todos, Grupo, Investigador o Producto), con filtros de año, categoría y validación. Los filtros de selección se aplican al cambiarlos. Los gráficos agrupan por año, tipología, categoría y validación. Un dato vacío no se inventa: el producto sigue en el total y figura como «Sin dato» en la distribución correspondiente. La categoría del **grupo** no se copia a la categoría del **producto**.

Puede crear, editar, desactivar y eliminar entidades y relaciones. El cambio de categoría o validación de un producto exige una observación nueva. La **Cola de revisión** procesa productos por orden de llegada; **Editar → Deshacer** revierte acciones. Los datos, la cola y el historial se conservan al guardar.

### Importar información

- **CSV:** ambos motores importan los archivos con los encabezados de [esquema_datos.md](docs/esquema_datos.md). La vista previa indica filas aceptables y rechazadas.
- **Excel `.xlsx`:** la interfaz Python convierte la primera hoja a CSV antes de la vista previa. Requiere `openpyxl` (`pip install openpyxl`).
- **URL pública:** la interfaz Python muestra HTML, texto, CSV o PDF de texto antes de crear registros. Reconoce fichas GrupLAC/CvLAC y metadatos explícitos de artículos; otros sitios pueden mostrarse sin proponer campos. No ejecuta JavaScript de la página ni inicia sesión en sitios externos.
- **PDF local:** la interfaz Python requiere `pdftotext` de Poppler y texto seleccionable. Un PDF escaneado necesita OCR externo.
- **Word `.docx`:** la interfaz Python extrae texto para vista previa mediante `mammoth` (`pip install mammoth`).

La consola C++ importa CSV; en el uso integrado, Python consulta las fuentes y envía a C++ los registros aceptados.

## Datos incluidos y persistencia

`data/demo` contiene 2 grupos, 3 investigadores, 4 productos y 2 revisiones ficticias. `data/real` contiene **66 grupos, 2.736 investigadores, 6.363 productos, 66 planes, 3.291 membresías, 6.735 vínculos grupo-producto y 9.703 autorías** de fichas públicas GrupLAC. De los investigadores, 274 tienen una categoría CvLAC capturada; los campos sin fuente suficiente quedan vacíos. La [procedencia y límites de la captura](data/real/README.md) están documentados aparte. No se necesita Internet para consultar los CSV incluidos.

Cada carpeta de trabajo contiene `manifest.csv`, cuatro CSV de entidades, tres de relaciones, `cola_validacion.csv` e `historial.csv`. El esquema actual es la **versión 2**. Las carpetas anteriores de versión 1 se abren en ambos motores y se convierten al guardar; conviene conservar una copia antes de abrirlas. La carpeta `.backup` guarda los archivos del guardado anterior. Abra una carpeta editable en una sola instancia a la vez.

La versión 2 neutraliza en disco los valores que una hoja de cálculo podría interpretar como fórmulas y los recupera al cargar. **Archivo → Exportar para hoja de cálculo** crea una copia segura para consulta; esa exportación no incluye la cola ni el historial y no sustituye una carpeta de trabajo.

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

En Windows, sustituya `python3` por `py -3`. Las pruebas de PDF, Excel y Word omiten lo que dependa de herramientas opcionales no instaladas. Para actualizar un clon, cierre PEA-i y ejecute `git pull` desde la carpeta del proyecto; conserve sus datos de trabajo fuera de `data/demo` y `data/real`, por ejemplo en `data/local/`.

`python3 scripts/build_demo.py` regenera la demostración. `python3 scripts/import_upc_dataset.py` vuelve a consultar la lista de grupos públicos; necesita Internet, no reemplaza el conjunto existente si falla alguna importación y puede producir datos diferentes si cambian las fichas. Para consultar solo parte de la lista, use `--limit N --output OTRA_CARPETA`. `python3 scripts/build_real_sample.py` genera por separado una muestra pequeña en `data/sample_scienti/` y no reemplaza el conjunto de 66 grupos.

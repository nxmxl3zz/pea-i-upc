# PEA-i UPC — gestor de investigación

Dos programas para gestionar grupos de investigación, investigadores, productos, planes y sus relaciones. **C++** ofrece menús de consola y también actúa como backend de la **interfaz Python Tkinter**. Al abrir la ventana, Python inicia C++ automáticamente cuando está disponible: C++ gestiona los datos, validaciones, estadísticas, cola, historial y CSV; Tkinter muestra formularios y gráficos. Si C++ no puede arrancar, la ventana abre con el motor Python independiente.

> **Estado actual:** las dos versiones están implementadas y usan los nombres de entrega `Taller2_REMR.py` y `Taller2_REMR.cpp`. La aplicación abre en Windows; la revisión completa de sus flujos en ese sistema sigue pendiente. La [especificación técnica en Word](docs/especificacion_tecnica.docx) es el único documento de entrega.

## Organización del repositorio

```text
pea-i-upc/
├── Iniciar PEA-i.pyw              Inicio con doble clic en Windows
├── src/
│   ├── cpp/Taller2_REMR.cpp       Consola y motor de datos C++
│   └── python/Taller2_REMR.py     Interfaz Tkinter y motor Python autónomo
├── bin/windows/                   Ejecutable C++ de 64 bits y huella de fuentes
├── data/
│   ├── demo/                      Muestra ficticia en CSV
│   └── real/                      Muestra pública y procedencia de sus datos
├── docs/
│   ├── especificacion_tecnica.docx  Especificación técnica de entrega
│   ├── esquema_datos.md           Campos CSV y reglas de integridad
│   └── protocolo_backend.md       Comunicación local entre Python y C++
├── scripts/                       Generación de muestras, Word y binario Windows
├── tests/                         Pruebas Python, integración y carga
├── CMakeLists.txt                  Compilación del motor C++
├── ENUNCIADO_TALLER_2.md          Requisitos del profesor
├── PLAN_PROYECTO.md               Alcance y criterios de aceptación
├── PROGRESO.md                    Avance y verificaciones del desarrollo
└── README.md                      Esta guía
```

`build/` contiene compilaciones locales y no se sube al repositorio. `data/local/` queda reservado para datos de trabajo y también está excluido de Git. El Word de `docs/` puede abrirse y editarse en LibreOffice; `scripts/build_technical_spec.py` lo regenera desde código y sobrescribe los cambios manuales.

## Descargar y ejecutar

En GitHub, abra **Code → Download ZIP** y descomprima el proyecto. Si prefiere Git, copie la URL HTTPS del botón **Code** y ejecute `git clone URL_COPIADA`; después entre en la carpeta creada. Abra una terminal **dentro de la carpeta descomprimida o clonada**, donde está este `README.md`. GitHub muestra el código, pero la ventana Tkinter se ejecuta en su computadora.

Para abrir la ventana necesita **Python 3.10 o posterior con Tkinter** y una sesión de escritorio. No hay paquetes de `pip` obligatorios. En Windows de 64 bits, el repositorio incluye el ejecutable C++ necesario para la conexión; **el usuario no necesita instalar CMake, NMake ni `g++`**. En otros sistemas, Python intenta compilar C++ con CMake y un compilador C++17 disponibles. Si no puede, la ventana funciona con el motor Python. La consola C++ y el modo Python independiente funcionan por separado.

### Linux

Compruebe que Python y Tkinter están disponibles:

```bash
python3 --version
python3 -m tkinter
```

El segundo comando abre una pequeña ventana de prueba; ciérrela y ejecute:

```bash
python3 src/python/Taller2_REMR.py
```

La ventana inicia y cierra su propio proceso de backend; no necesita abrir la consola C++ aparte. Para comprobar qué motor está usando, abra **Ayuda → Acerca de PEA-i**.

### Windows — doble clic

Extraiga el ZIP completo o clone el repositorio. Haga doble clic en **`Iniciar PEA-i.pyw`** en la carpeta principal. También puede abrir directamente **`src/python/Taller2_REMR.py`**. En Windows de 64 bits la interfaz usa el backend C++ incluido, sin abrir Dev-C++ ni instalar CMake. El archivo `.pyw` evita que aparezca una ventana de consola. Para comprobar el motor activo, abra **Ayuda → Acerca de PEA-i**.

Si Windows abre el archivo como texto, instale Python 3.10 o posterior con Tkinter y asocie los archivos `.pyw` con Python; también puede iniciarlo desde PowerShell:

```powershell
py -3 --version
py -3 -m tkinter
py -3 src/python/Taller2_REMR.py
```

Si `py` no está disponible, pruebe los mismos comandos con `python`. Cierre la ventana de prueba de Tkinter antes de iniciar PEA-i.

Si desea usar un ejecutable C++ propio, indique su ruta con `--cpp-binary`; en ese caso, un error de ese ejecutable se muestra en lugar de cambiar al motor Python.

Si descargó un ZIP, **extraiga todos los archivos** antes de ejecutar el programa: la opción de demostración busca `data/demo` dentro del proyecto.

### C++ — Linux

Desde la raíz del proyecto:

```bash
cmake -S . -B build
cmake --build build --config Release
./build/pea_cpp
```

### C++ — Windows (PowerShell)

Esta compilación manual es opcional para el usuario de la interfaz. Para compilar con Dev-C++, configure el `PATH` de Windows para que encuentre `g++.exe` y `mingw32-make.exe`, instale CMake y ejecute:

```powershell
cmake -S . -B build-mingw -G "MinGW Makefiles"
cmake --build build-mingw
.\build-mingw\pea_cpp.exe
```

Si ya existe una carpeta de compilación configurada con NMake, use la carpeta nueva `build-mingw` del ejemplo para evitar conflictos de generador. Los comandos de Windows todavía no se han probado en un equipo Windows.

Para actualizar el ejecutable Windows incluido después de modificar C++, ejecute `python scripts/build_windows_backend.py` con un compilador MinGW de 64 bits. El script vuelve a generar `bin/windows/pea_cpp.exe` y su huella de fuentes. Los usuarios de la interfaz no necesitan ejecutar este paso.

### Dos modos de la ventana

`python3 src/python/Taller2_REMR.py` prefiere C++ como backend y usa Python si C++ no está disponible. Para forzar la implementación Python independiente, use `python3 src/python/Taller2_REMR.py --python-backend`. La consola C++ se ejecuta con `./build/pea_cpp` en Linux o con `bin\windows\pea_cpp.exe` en Windows. Los tres modos usan el mismo [esquema CSV](docs/esquema_datos.md), pero abra una misma carpeta de datos en una sola instancia a la vez. La [conexión entre Tkinter y C++](docs/protocolo_backend.md) funciona localmente, sin red.

### Mostrar el cruce en una demostración

1. Abra `python3 src/python/Taller2_REMR.py`. En **Ayuda → Acerca de PEA-i** puede ver el motor de datos activo; por defecto se inicia un proceso C++ en segundo plano.
2. Cargue la demostración y guarde una copia en otra carpeta, por ejemplo `data/local`. Cree o edite un registro en la ventana y guarde.
3. Cierre la ventana y ejecute `./build/pea_cpp --data-dir data/local`. Consulte el mismo registro desde los menús C++. Para mostrar la segunda implementación autónoma, también puede abrir la copia con `python3 src/python/Taller2_REMR.py --python-backend --data-dir data/local`.

## Primer uso y demostración

Al abrir la ventana Python, elija una de estas opciones:

| Opción | Resultado |
|---|---|
| **Iniciar vacío** | Crea un espacio sin registros. Puede agregar datos con los formularios de Python o los menús de C++, o importar CSV. |
| **Abrir carpeta de datos** | Recupera un espacio PEA-i guardado antes; indique la carpeta que contiene `manifest.csv`. |
| **Cargar datos reales** | Abre [data/real](data/real/README.md), una captura de las fichas públicas GrupLAC/CvLAC del enunciado con 85 integrantes, un plan y 202 productos fechados. |
| **Cargar demostración** | Abre `data/demo`, con datos **ficticios** para recorrer la aplicación sin Internet. |

Para ver las fuentes reales, elija **Cargar datos reales** o ejecute `python3 src/python/Taller2_REMR.py --data-dir data/real`. El dashboard muestra 202 productos fechados del grupo GISICO, con gráficos por año y tipología. La pestaña **Investigadores** contiene los 85 integrantes publicados en la ficha; **Relaciones → Integrantes** distingue 67 membresías actuales y 18 finalizadas. Hay 319 autorías vinculadas por coincidencia de nombre con el censo, y un plan estratégico en **Planes**. Solo el perfil CvLAC de Adith Bismarck Pérez Orozco se consultó individualmente para añadir su categoría; los demás conservan los datos publicados en el censo. Seleccione un grupo o investigador y pulse **Consultar fuente** para revisar su página pública y, si corresponde, completar su ficha. Las categorías de producto quedan vacías porque la fuente no declara una categoría comparable con ese campo.

Para comprobar rápidamente los filtros, cargue la demostración. En el **Dashboard** de Python o **Estadísticas** de C++, la vista **Todos** muestra cuatro productos. El rango **2025–2026** muestra dos; **2022–2026** muestra tres. El producto `P-DEMO-1` está vinculado a dos grupos y se cuenta una sola vez en el total institucional. En C++, seleccione la opción **4. Rango** para indicar esos años.

Las carpetas `data/demo` y `data/real` se tratan como muestras de solo lectura en la ventana Python. Para conservar cambios en otra carpeta, por ejemplo `data/local`, use **Archivo → Guardar como...** en Python o **Datos → Guardar como** en C++. Después puede abrirla desde **Archivo → Abrir carpeta de datos...** en Python, desde **Datos → Abrir carpeta** en C++, o iniciar directamente con:

```bash
python3 src/python/Taller2_REMR.py --data-dir data/local
./build/pea_cpp --data-dir data/local
```

En Windows, sustituya `python3` por `py -3` y `./build/pea_cpp` por la ruta del ejecutable C++ de la sección anterior. La ruta indicada con `--data-dir` debe contener los CSV previamente guardados; si todavía no existe, se mostrará el selector de inicio. Para abrir directamente la demostración de C++, use `./build/pea_cpp --demo`.

En C++, los menús principales son **Grupos**, **Investigadores**, **Productos**, **Planes**, **Relaciones**, **Importar CSV**, **Estadísticas**, **Cola de revisión**, **Deshacer** y **Datos**. Escriba el número de la opción y pulse Enter. Al crear un registro, Enter acepta el valor sugerido; al editar, Enter conserva el valor anterior y `:vaciar` borra un campo. Para guardar, use **11. Guardar** o **Datos → Guardar como**. El asterisco del menú indica cambios sin guardar.

## Funciones disponibles

- **Grupos, Investigadores, Productos y Planes:** crear, buscar, consultar, editar, activar/desactivar y eliminar registros en ambos programas. Los IDs son estables. Para eliminar una entidad con relaciones o planes, primero quite esas dependencias o desactive la entidad.
- **Relaciones:** gestionar integrantes de grupos, autorías y vínculos entre grupos y productos. Cada relación se puede editar, desactivar o eliminar.
- **Productos:** registrar año, fecha, familia, tipología, categoría y validación (`pendiente`, `validado`, `rechazado`). Cambiar categoría o validación requiere una observación nueva.
- **Cola de revisión:** encolar productos y procesarlos en orden de llegada. **Editar → Deshacer** en Python u **9. Deshacer** en C++ recupera el estado anterior; el historial y los trabajos pendientes se guardan con los datos.
- **Estadísticas:** ver productos por grupo, investigador, producto o en total; filtrar por últimos dos años, últimos cinco años, rango personalizado, categoría y validación. Ambos muestran productos únicos y distribuciones por año, tipología, categoría y validación. Python incluye gráficos y tabla en el dashboard; C++ muestra resúmenes y tabla en consola.
- **Importación CSV en ambos programas:** seleccione un tipo de registro y un archivo del [esquema PEA-i](docs/esquema_datos.md); revise cuántas filas se aceptarán o rechazarán antes de mezclarlo con los datos. Importe primero entidades y después relaciones que las referencien.
- **Consulta de URL solo en Python:** **Importar → URL pública...** acepta una página pública HTTP/HTTPS en HTML, texto, CSV o PDF de texto. Muestra título, fuente, metadatos declarados, tablas HTML y texto visible antes de crear nada. Puede revisar y crear un grupo, investigador o producto desde esa vista. En una ficha GrupLAC, **Importar datos detectados** incorpora el grupo, su censo de integrantes, el plan, los productos fechados de las secciones bibliográficas y técnicas reconocidas y las autorías cuyos nombres coinciden con el censo; puede volver a consultar la ficha sin duplicar esos registros. Una ficha CvLAC propone el investigador y permite completar un registro existente. Una página académica con metadatos de artículo puede proponer título, año y DOI. Un CSV descargado puede importarse si usa los encabezados del esquema PEA-i. **Importar → PDF de texto GrupLAC/CvLAC...** también acepta un PDF local con `pdftotext` de Poppler instalado y solicita la URL de origen.

Las tablas de Tkinter muestran 100 registros por página; use **Anterior** y **Siguiente** para recorrerlos. La búsqueda filtra el conjunto completo. En **Grupos**, **Investigadores**, **Productos** y **Planes** puede arrastrar directamente el borde entre la tabla y **Información general** para ajustar sus alturas; ambos paneles conservan un tamaño mínimo. Los campos de ID en filtros y formularios aceptan escribir un ID aunque no aparezca entre las primeras sugerencias.

En la ventana conectada, Python descarga y presenta la URL; solo envía al backend C++ el registro que el usuario revise y guarde. Los registros creados mediante el formulario de esa vista conservan la URL y la fecha de consulta en `fuente`. Los CSV descargados conservan los campos que declara el propio archivo.

Una página cualquiera puede mostrar información legible sin contener datos de investigación estructurados. En ese caso la vista previa no propone campos ni crea registros; si corresponde, el usuario puede escoger el tipo y completar el formulario con lo que la página demuestra. Los gráficos se construyen únicamente con **productos guardados**: si falta año, tipología o categoría, ese gráfico indica «Sin valores registrados»; el producto sigue en el total. No se inventan categorías, autores ni relaciones. La descarga consulta una sola URL y limita la respuesta a 8 MB; páginas que requieren inicio de sesión, ejecutan su contenido solo con JavaScript o sirven PDF escaneado pueden necesitar un CSV o PDF preparado aparte. El CSV de importación necesita los encabezados exactos del [contrato de datos](docs/esquema_datos.md); para recuperar una carpeta completa use la opción de abrir carpeta. Las categorías de la demostración son ejemplos, no clasificaciones oficiales.

## Datos guardados

Cada espacio de trabajo es una carpeta con `manifest.csv` y CSV de grupos, investigadores, productos, planes, relaciones, cola e historial. **Conserve juntos todos esos archivos** al mover los datos a otra computadora. Las fechas usan `AAAA-MM-DD`; los CSV usan UTF-8. Antes de sustituir un guardado existente, el programa conserva la versión anterior en `.backup` dentro de esa carpeta. Evite abrir la misma carpeta en dos instancias al mismo tiempo.

Los datos de [data/demo](data/demo/README.md) son inventados para pruebas y no describen personas o grupos reales de la UPC. [data/real](data/real/README.md) documenta las fuentes y las decisiones de extracción de la muestra pública real.

## Compartir y recibir actualizaciones

Para recibir cambios futuros, es mejor obtener el proyecto con `git clone` una sola vez. Desde esa carpeta, cierre PEA-i y ejecute:

```bash
git pull --ff-only origin main
```

Esto actualiza el código y las muestras incluidas en el repositorio. Las carpetas de trabajo guardadas en `data/local/` están ignoradas por Git y no se sobrescriben al actualizar. Si se descargó un ZIP en lugar de clonar, habrá que descargar y extraer un ZIP nuevo para obtener cada versión; Git no puede actualizar automáticamente una carpeta extraída sin historial.

Quien tenga permiso para escribir en el repositorio puede publicar sus propios cambios con `git add`, `git commit` y `git push origin main`. Antes de hacer `git pull`, guarde o confirme los cambios locales de código para evitar conflictos. Quien no tenga permiso puede crear una copia (*fork*) y enviar una solicitud de cambios (*pull request*).

## Ejecutar pruebas

Desde la raíz del proyecto:

```bash
python3 -m unittest discover -s tests/python -v
cmake -S . -B build
cmake --build build --config Release
ctest --test-dir build --output-on-failure
```

En Windows use `py -3` en los comandos Python. CTest ejecuta la autoprueba C++ y, si CMake encuentra Python 3.10 o posterior, tres pruebas de integración, incluida la conexión directa de la interfaz Python al backend. Las pruebas del núcleo Python usan la biblioteca estándar. La prueba de importación PDF se omite automáticamente si `pdftotext` no está instalado. `python3 scripts/build_demo.py` regenera los datos ficticios de muestra. `python3 scripts/build_real_sample.py` regenera `data/real` desde las dos URL del enunciado; necesita Internet y puede generar una captura distinta si las páginas cambian. Ninguno es necesario para usar la aplicación.

### Prueba de carga

El backend C++ usa índices para códigos externos, lee CSV por registros, guarda cambios compactos para deshacer y entrega páginas de hasta 200 filas a la interfaz. Para repetir una prueba sintética sin modificar `data/demo` ni sus propios datos:

```bash
python3 tests/performance/stress_backend.py build/pea_cpp --products 20000 --people 1000 --links 20000 --memory-mb 768 --check-import
```

En Linux se probó también `--products 225000 --people 9000 --links 225000 --jobs 225000 --memory-mb 1024 --timeout 120 --check-import`. Con textos sintéticos cortos, cargar y reabrir tardó unos 16–17 s cada vez; guardar tardó cerca de 1,6 s; el mayor pico observado del proceso C++ fue aproximadamente 729 MiB. Treinta ediciones y treinta acciones de deshacer tardaron menos de 0,02 s. La vista previa, importación y deshacer de 225 000 productos tardaron unos 34 s. El límite de memoria se aplica al **proceso C++**, no a Tkinter ni al sistema completo. Los tiempos y la memoria dependen del equipo, la longitud de los campos y la cantidad de relaciones. En Windows el script ejecuta la prueba funcional, pero no aplica el límite de memoria de Linux.

## Si algo no abre

- **No encuentra `src/python/Taller2_REMR.py`:** abra la terminal en la carpeta que contiene este README y repita el comando.
- **El motor aparece como Python en Ayuda → Acerca de PEA-i:** la ventana está funcionando con el respaldo Python. En Windows de 64 bits, compruebe que descargó o clonó el repositorio completo y que existe `bin/windows/pea_cpp.exe`. En otros sistemas, instale CMake y un compilador C++17 para activar la conexión C++.
- **Aparece `CMAKE_CXX_COMPILER not set` o un error de NMake al compilar manualmente:** CMake no está encontrando el compilador de Dev-C++. Agregue al `PATH` la carpeta que contiene `g++.exe` y `mingw32-make.exe`, y use `-G "MinGW Makefiles"` con una carpeta de compilación nueva. Para abrir la ventana normalmente en Windows, estos programas no son necesarios.
- **Falla `python3 -m tkinter` o `py -3 -m tkinter`:** instale una distribución de Python que incluya Tkinter o el paquete Tkinter de su sistema.
- **Error de pantalla o `display`:** ejecute el programa desde una sesión gráfica local; necesita poder abrir ventanas de escritorio.
- **No se puede importar PDF:** compruebe que `pdftotext` está instalado y que el PDF tiene texto seleccionable. También puede usar CSV.
- **Una URL no muestra datos útiles:** compruebe que es pública y que el contenido aparece en el HTML o documento descargado. Si la página carga todo mediante JavaScript o exige cuenta, use un CSV o PDF de texto exportado por el sitio.
- **No se puede abrir una carpeta guardada:** verifique que contiene `manifest.csv` y todos los CSV del [esquema](docs/esquema_datos.md). Si un guardado se dañó y existe `.backup`, la aplicación ofrece abrir la copia anterior.

La lógica Python y sus pruebas se verificaron en Linux con Python 3.14. C++ se compiló y probó en Linux; las pruebas de integración comprobaron la comunicación Tkinter/C++, el intercambio de CSV y el historial. La ventana conectada abrió y cargó la muestra pública en Linux. El ejecutable Windows incluido pasó su autoprueba y respondió al protocolo JSON bajo Wine; la interfaz también abrió en Windows. Todavía falta recorrer allí todos los formularios, importaciones y ciclos de guardado. El avance real y los límites se registran en [PROGRESO.md](PROGRESO.md); el [enunciado](ENUNCIADO_TALLER_2.md) y el [plan](PLAN_PROYECTO.md) conservan los requisitos del taller.

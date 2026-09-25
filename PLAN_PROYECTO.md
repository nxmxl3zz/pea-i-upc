# PEA-i UPC — Plan maestro de desarrollo y verificación

> **Estado:** plan de trabajo de septiembre de 2026; la implementación y el esquema vigentes se describen en `README.md` y `docs/esquema_datos.md`. El registro histórico está en `PROGRESO.md`.<br>
> **Fuente principal:** `ENUNCIADO_TALLER_2.md`, transcripción del PDF «Taller 2», Estructura de Datos, Universidad Popular del Cesar, entregado el 24/09/2026.<br>
> **Fecha de entrega que figura en el PDF:** lunes 19 de octubre de 2026, antes de las 11:59 a. m.<br>
> **Alcance de este plan:** código de las dos aplicaciones, datos, pruebas, documentación técnica y preparación de un repositorio descargable y ejecutable. La sustentación y el video quedan a cargo de Rafael.

## 1. Objetivo y reglas de trabajo

Construir un **Programa Estadístico de Análisis de Investigación (PEA-i)** para información de grupos, investigadores y productos de investigación de la UPC. Habrá dos implementaciones con comportamiento comparable:

1. **C++:** gestión y estadísticas descriptivas en consola, con tablas y resúmenes.
2. **Python:** gestión y estadísticas mediante una aplicación de escritorio Tkinter, con dashboard, histogramas y diagramas de barras.

Ambos programas compartirán **un contrato de datos documentado**, podrán iniciarse sin registros, cargar datos guardados y operar sin conexión una vez que haya datos locales. El funcionamiento básico no dependerá de cuentas, rutas absolutas del equipo de desarrollo, claves privadas ni servicios remotos disponibles durante la ejecución.

**Cruce aprobado por el profesor:** la ventana Tkinter usa normalmente un proceso C++ como backend mediante mensajes JSON locales. La consola C++ permanece autónoma y la interfaz conserva la implementación Python independiente con `--python-backend`. Los detalles y comandos de demostración están en `docs/protocolo_backend.md`.

**Jerarquía de decisiones:** instrucciones posteriores de Rafael; enunciado del profesor; este plan. Si una decisión de implementación contradice una exigencia explícita del taller, se ajustará el diseño y se registrará la decisión en la documentación. Este archivo es una guía viva: marcar tareas solamente después de verificarlas.

### Resultado que debe recibir quien clone el repositorio

- Instrucciones completas para instalar, compilar y ejecutar en Linux y Windows.
- Las dos aplicaciones y datos de demostración suficientes para probar cada vista.
- Un modo de crear/cargar datos sin depender de que Scienti responda en ese momento.
- Pruebas automáticas y una secuencia corta de comprobación manual.
- Especificación técnica detallada y trazabilidad frente al enunciado.

## 2. Alcance del taller y comprobaciones

Los identificadores **R** se usarán en el código, las pruebas y la documentación. «Aceptación» significa una prueba observable, no solamente que existe una pantalla o un botón.

| ID | Requisito | Criterio observable de aceptación |
|---|---|---|
| R01 | Dos soluciones, C++ y Python | Ambas arrancan desde un clon limpio siguiendo el README y trabajan con el mismo conjunto de datos de muestra. |
| R02 | Grupos de investigación | Alta, consulta, edición, desactivación, eliminación controlada, búsqueda y restauración desde disco. |
| R03 | Investigadores | Los mismos flujos; ficha con información personal pública pertinente, afiliaciones y productos. |
| R04 | Productos | Los mismos flujos; nombre, fecha/año, tipo, categoría, estado de validación, autores y grupos. |
| R05 | Integrantes y plan de cada grupo | Se pueden asociar integrantes con rol y registrar al menos objetivos, horizonte temporal y actividades/indicadores del plan. |
| R06 | Entradas y salidas del modelo | La especificación enumera campos de entrada, reglas de validación, consultas y estadísticas producidas. |
| R07 | Carga externa | Ambos programas procesan CSV; Python incorpora además la importación por URL pública de GrupLAC/CvLAC y, si los documentos lo permiten, PDF de texto. Cada vía implementada tiene prueba con archivo o captura reproducible. |
| R08 | Listas | Las entidades se almacenan en listas enlazadas implementadas explícitamente; la estructura se usa en operaciones reales. |
| R09 | Multilistas | Relaciones entre grupo, investigador y producto permiten recorridos en más de una dirección sin duplicar la entidad principal. |
| R10 | Pilas | Historial de acciones reversibles; apilar, consultar cima, desapilar, vaciar y recuperar el estado previsto. |
| R11 | Colas | Trabajos de importación o revisión de productos atendidos en orden de llegada; encolar, consultar frente, desencolar y recuperar pendientes. |
| R12 | CRUD, desactivación y persistencia | Operaciones disponibles para entidades y relaciones; los estados y trabajos pendientes se conservan al cerrar y reabrir. Se documentan las operaciones que para una pila o cola se expresan como acciones LIFO/FIFO. |
| R13 | Categoría y validación de productos | Se pueden cambiar separadamente la tipología/categoría y el estado de validación; consta una razón u observación del cambio. |
| R14 | Ventana de observación | Últimos 2, últimos 5 años y rango personalizado; las tres vistas y sus totales respetan el filtro. |
| R15 | Estadísticas por grupo, investigador y producto | Totales, distribución temporal, distribución por tipo/categoría y estados; definición de denominador y tratamiento de duplicados documentados. |
| R16 | Presentación C++ | Menú comprensible, tablas legibles y cifras coherentes con los datos. No exige GUI. |
| R17 | Presentación Python | Dashboard Tkinter con navegación, filtros, histogramas por año y barras por tipología/categoría; datos vacíos tratados con mensajes claros. |
| R18 | Inicio con o sin archivo | Al arrancar se puede crear un espacio vacío o cargar una carpeta de datos existente; no se sobrescriben los archivos de demostración. |
| R19 | Archivos fuente y datos | Se identifican los dos fuentes entregables con iniciales definitivas, un conjunto de datos persistidos y archivos de identificación cuando Rafael los facilite. |
| R20 | Especificación técnica en Word | Diseño de estructuras, algoritmo y estrategia, diagramas, casos de uso, requisitos, historias de usuario, instrucciones y evidencia de verificación. |

**Complementos posibles:** Git/GitHub y commits legibles; base de datos; GUI creativa; interoperabilidad; documentación ampliada. No reemplazan ningún R01–R20. La interoperabilidad básica ya se resuelve mediante el formato CSV común. Una base de datos adicional se considerará únicamente si el núcleo ya funciona y supera las pruebas de portabilidad.

### Interpretaciones que evitaremos ocultar

- El enunciado dice «URL **o** PDF **o** CSV». Se garantizará CSV en los dos programas y se ampliarán las entradas donde puedan verificarse. No se afirmará que el raspado web funciona solo porque existe código para solicitar una página.
- «Editar cualquier dato» incluye relaciones y estados, además de campos de texto. Las restricciones de integridad se explicarán al usuario.
- Una entidad desactivada permanece en el historial y puede excluirse de una vista activa sin perder referencias anteriores.
- El «hipercubo» figura como recomendación. La solución utilizará dimensiones **año × grupo × investigador × tipología/categoría**, materializadas como consultas y agregaciones, sin afirmar que se implementó un motor OLAP completo.
- La clasificación oficial de Minciencias y el estado interno de validación de un registro son **cosas distintas**. Las categorías y sus reglas se basarán en la fuente consultada, no se inventarán puntajes oficiales.

## 3. Referencias de dominio

- Enunciado local para trabajar desde CLI: `ENUNCIADO_TALLER_2.md` (conserva el texto y los enlaces del PDF original `Taller 2 EdD (2026-09-24) - G 5.pdf`).
- Página de modelo de Minciencias enlazada desde el PDF: <https://minciencias.gov.co/sistemas-informacion/modelo-medicion-grupos>.
- Ejemplo de ficha de grupo SIGIIP/UNIMINUTO incluido por el profesor: <https://sistemainvestigacion.uniminuto.edu/PGrupos/Ver/141>.
- Manual del proveedor sobre grupos y carga de GrupLAC: <https://letmeknow.com.co/ostic/kb/faq.php?id=105>.
- Manual del proveedor sobre planes de grupos: <https://letmeknow.com.co/ostic/kb/faq.php?id=75>.
- Manual del proveedor sobre aval y rechazo de productos: <https://letmeknow.com.co/ostic/kb/faq.php?id=83>.

SIGIIP es **referencia funcional y visual**; los datos de UNIMINUTO no se presentarán como datos de la UPC. Las páginas de Scienti pueden cambiar o no responder: se guardarán datos de prueba cuya procedencia sea comprobable y se registrará cuándo fueron consultados.

## 4. Modelo de información propuesto

Las claves internas son identificadores estables. El código externo de un grupo, un CvLAC o un DOI se guarda por separado porque puede faltar, cambiar de formato o coincidir entre fuentes.

| Entidad | Campos iniciales propuestos | Relaciones |
|---|---|---|
| Grupo | id, código GrupLAC, nombre, fecha de creación, unidad académica, responsable, categoría Minciencias, estado, descripción, objetivos, misión, visión, líneas, URL y fuente | N investigadores; N productos; N planes |
| Investigador | id, nombre, identificador CvLAC si existe, afiliación, categoría si consta, contacto público opcional, perfil/URL, estado, fuente | N grupos con rol y fechas; N productos con rol de autor |
| Producto | id, título, año/fecha, familia, tipología, categoría, estado de validación, observación, DOI/identificador externo, URL, estado activo, fuente | N autores; 1 o más grupos cuando lo justifique la fuente |
| Membresía | id del grupo, id del investigador, rol, fecha de inicio y fin, activo | Relación explícita entre grupo e investigador |
| Autoría | id del producto, id del investigador, orden/rol de autor si aparece | Relación explícita entre producto e investigador |
| Vinculación de producto | id del producto, id del grupo, procedencia de la asociación | Evita contar el mismo registro varias veces en un total institucional |
| Plan | id, grupo, nombre/tipo, fecha inicial/final, objetivo, indicador, meta, actividad, estado | Pertenece a un grupo; opcionalmente enlaza productos |
| Fuente/importación | tipo de fuente, URL o nombre de archivo, fecha de captura, resultado, filas aceptadas/rechazadas, motivo | Permite auditar el origen de datos |

**Reglas iniciales:** identificadores únicos; año válido; enlaces siempre apuntan a entidades existentes; una autoría no se repite; DOI normalizado para detección de duplicados; si no hay DOI, comparar ID externo y después título+año+autor con revisión manual de coincidencias dudosas. No se eliminarán en cascada personas o grupos con productos sin una acción expresa y una confirmación. Las fechas se almacenarán en formato ISO (`AAAA-MM-DD`) y los textos en UTF-8.

### Estructuras exigidas: implementación con uso visible

| Estructura | Uso real | Cómo demostrarla |
|---|---|---|
| Lista doblemente enlazada | Almacenamiento y recorrido de grupos, investigadores y productos; inserción, búsqueda, edición, eliminación y navegación | Documentar nodos, referencias anterior/siguiente, complejidades y un recorrido en consola o pruebas |
| Multilista | Nodos de relación con enlace «siguiente por grupo» y «siguiente por investigador/producto», según la relación | Consultar investigadores de un grupo y grupos de un investigador; autores de un producto y productos de un autor |
| Pila | Deshacer acciones CRUD reversibles, con registro de valor previo; rehacer si es viable | Ejecutar modificación → deshacer → comprobar restauración |
| Cola | Ingesta/revisión de productos pendientes en orden FIFO | Encolar A y B → procesar A → procesar B; persistir pendientes |

En **ambos lenguajes**, las estructuras y operaciones estarán escritas de forma explícita y documentada. C++ podrá usar la biblioteca estándar para cadenas, archivos y apoyo en pruebas, pero no sustituirá todas las listas del ejercicio por `std::vector`. Python tampoco usará únicamente `list` o `dict` como si fueran la estructura solicitada: los diccionarios pueden servir como índices auxiliares; la fuente de verdad y los recorridos que se evalúan serán los nodos definidos para el proyecto.

## 5. Intercambio y persistencia

**Contrato común propuesto:** CSV UTF-8 con encabezados y reglas de escape; un archivo por entidad o relación. Python utilizará su módulo estándar `csv`; C++ incluirá un lector/escritor que soporte comillas, comas, saltos de línea en campos y encabezados. La especificación indicará versión de esquema, nombres y campos obligatorios.

```text
data/
  demo/                   # Ejemplo versionado y documentado; se trata como solo lectura
    manifest.csv
    grupos.csv
    investigadores.csv
    productos.csv
    membresias.csv
    autorias.csv
    grupos_productos.csv
    planes.csv
    cola_validacion.csv
    historial.csv
  local/                  # Espacio de trabajo creado en ejecución; ignorado por Git
```

`manifest.csv` contiene versión de esquema y metadatos necesarios para detectar datos incompatibles. Un guardado escribirá archivos temporales, comprobará su integridad y sustituirá los anteriores; se conservará una copia recuperable cuando corresponda. Los datos de `demo/` se copiarán a `local/` antes de editar. Si ambos programas apuntan a la misma carpeta, se usarán **por turnos** hasta que exista control de acceso concurrente probado.

Los enlaces se reconstruirán a partir de CSV al cargar y se comprobará integridad referencial antes de mostrar estadísticas. Se guardarán estados desactivados, trabajos pendientes y el historial necesario para que la funcionalidad prometida sobreviva a un reinicio. Una carpeta sin datos debe ser válida y producir tablas/gráficos vacíos sin fallos.

## 6. Importación: decisiones y límites comprobables

1. **CSV: obligatorio en C++ y Python.** Validar antes de aplicar, mostrar un resumen de errores por fila y confirmar antes de mezclar con los datos actuales. En C++, la validación y la aplicación recorren el CSV por registros, con reversión si falla la importación.
2. **URL pública: objetivo en Python.** Primero estudiar una ficha real de GrupLAC/CvLAC, acordar campos extraíbles y guardar un ejemplo de prueba. Descargar con tiempo límite, identificar cambios de formato, normalizar datos y registrar URL/fecha. No suponer la existencia de una API oficial.
3. **PDF: objetivo condicionado a PDFs de texto.** Extraer campos verificables con `pdftotext` de Poppler; si el archivo es un escaneo sin texto, informar que requiere OCR y conservar una alternativa CSV. No atribuir datos inventados a una extracción fallida.
4. **C++: ruta autónoma de CSV.** Puede consumir los CSV generados por la importación Python, pero su propia opción de CSV funcionará aunque Python no esté instalado.
5. **Casos difíciles:** duplicados, tildes, codificación, títulos repetidos, campos ausentes, productos de varios autores, grupos compartidos, años no disponibles, HTML cambiante, Internet caído y archivos malformados.

Se mantendrá una **muestra comprobable** para pruebas y demostración sin conexión. La amplitud de datos reales de la UPC se decidirá después de validar la calidad de una primera importación; no se prometerá cobertura institucional completa sin comprobarla.

## 7. Experiencia de uso

### C++: consola

- Menú principal: cargar/iniciar vacío, grupos, investigadores, productos, relaciones/planes, importación CSV, estadísticas, pendientes, deshacer, guardar/salir.
- Submenús CRUD con búsqueda por ID, nombre, código o título, y confirmaciones en operaciones destructivas.
- Listados paginados o limitados para no inundar la terminal; salida alineada que tolere ancho de consola habitual.
- En estadísticas: selector de vista, intervalo de años, total de productos únicos, tablas por año y tipología, desglose de estados de validación.
- Errores de entrada y archivos expresados en español comprensible; volver al menú sin caída.

### Python: aplicación de escritorio Tkinter

- **Tkinter** para ejecutarlo como aplicación local con `python src/python/Taller2_REMR.py`. No requiere publicar el sistema ni abrir una cuenta.
- Controles para grupo/investigador/producto, año inicial/final o últimos 2/5 años, estado y categoría.
- Tarjetas de cifras con definiciones claras; histograma temporal de productos; barras por tipología/categoría; tabla consultable y fichas detalladas.
- Formularios de creación/edición/desactivación; administración de relaciones y plan; importación con vista previa de aciertos/rechazos; guardado explícito.
- El dashboard consultará las estructuras del programa. No deberá calcular resultados desde una copia divergente en un archivo auxiliar.

Tkinter forma parte de la biblioteca estándar de Python, aunque algunas distribuciones Linux lo separan en un paquete como `python3-tk`. El soporte de Python y del sistema gráfico se verificará en los entornos objetivo. La importación opcional de PDF de texto utiliza `pdftotext` de Poppler si está instalado.

## 8. Estructura prevista del repositorio

```text
pea-i-upc/
├── README.md                       # Instalación, ejecución, demostración y solución de errores
├── PLAN_PROYECTO.md               # Este plan y lista de aceptación
├── ENUNCIADO_TALLER_2.md          # Transcripción consultable del PDF del profesor
├── PROGRESO.md                    # Avance verificado, próximo paso y bloqueos concretos
├── CMakeLists.txt                  # Compilación C++17, pruebas C++
├── .gitignore
├── .gitattributes
├── src/
│   ├── cpp/Taller2_REMR.cpp          # Fuente C++ con las iniciales indicadas
│   └── python/Taller2_REMR.py        # Fuente Python requerido
├── data/
│   └── demo/                       # CSV reproducibles y sus fuentes
├── tests/
│   ├── cpp/                        # Casos C++ de estructuras e integración
│   ├── python/                     # Casos Python y comprobación del dashboard
│   └── fixtures/                   # Datos de prueba pequeños y casos inválidos
├── docs/
│   ├── especificacion_tecnica.docx
│   ├── esquema_datos.md
│   ├── decisiones.md
│   └── diagramas/                  # Casos de uso, modelo y flujo de importación
└── .github/workflows/ci.yml       # Verificación de compilación y pruebas al subir cambios
```

El árbol muestra la estructura objetivo. Las fuentes con nombres definitivos, CMake, datos de demostración, pruebas y especificación DOCX ya existen; CI y algunas carpetas previstas aún no. GitHub conserva y muestra el contenido de carpetas; los problemas de ejecución al mover archivos se previenen usando rutas relativas a la raíz del proyecto, argumentos `--data-dir` y comandos de compilación explícitos.

**Exclusiones en Git:** `.venv/`, `build/`, `data/local/`, `__pycache__/`, cachés de pruebas, copias locales de respaldo, contraseñas y exportaciones temporales. **Incluidos en Git:** fuentes, plan, documentación, muestras reproducibles, manifiestos y pruebas. Evitar archivos personales o datos innecesarios en un repositorio público.

## 9. Contrato de instalación y ejecución en otra computadora

Los comandos definitivos del README se probarán literalmente desde una **clonación nueva**. Estos son los comandos previstos, ejecutados desde la raíz del repositorio:

### Linux, incluida Garuda

```bash
git clone URL_DEL_REPOSITORIO
cd pea-i-upc
python3 src/python/Taller2_REMR.py --data-dir data/local
```

Para C++:

```bash
cmake -S . -B build
cmake --build build --config Release
./build/pea_cpp --data-dir data/local
```

### Windows, terminal PowerShell

```powershell
git clone URL_DEL_REPOSITORIO
cd pea-i-upc
py -3 "Iniciar PEA-i.pyw"
```

La interfaz de Windows de 64 bits usa el ejecutable C++ incluido y no exige instalar CMake ni un compilador. La compilación manual de la consola es opcional:

```powershell
cmake -S . -B build
cmake --build build --config Release
.\build\Release\pea_cpp.exe --data-dir data/local
```

**Prerrequisitos de uso:** Python 3.10 o posterior con Tkinter; Git solo para clonar. La conexión a Internet se necesita durante la importación por URL. Para compilar C++ por cuenta propia se necesitan además CMake y un compilador C++17. La ruta del ejecutable compilado depende del generador: puede ser `build\pea_cpp.exe` o `build\Release\pea_cpp.exe`.

`URL_DEL_REPOSITORIO` representa la URL del repositorio; la URL real y las instrucciones actuales se encuentran en el README. El uso de CSV y las estadísticas locales funcionan sin Internet.

### Demostración reproducible desde CLI

1. Clonar y ejecutar los comandos anteriores sin corregir rutas ni instalar archivos fuera de las dependencias declaradas.
2. Elegir «iniciar vacío»: crear un grupo, un investigador y un producto; relacionarlos y guardar.
3. Cerrar y reabrir las dos aplicaciones; comprobar que los datos y las relaciones siguen presentes.
4. Copiar `data/demo/` a una carpeta local separada o importarla desde el menú; mostrar las tres vistas y filtros 2/5 años.
5. Encolar dos revisiones y demostrar FIFO; modificar un dato y demostrar deshacer mediante pila; comprobar persistencia.
6. Ejecutar pruebas automáticas; confirmar que el conjunto de demostración incluido no se modificó.

## 10. Plan de ejecución y puertas de salida

Cada fase produce cambios **revisables**. Ninguna fase se marcará terminada si no pasan sus comprobaciones. Los cambios de código se harán en commits pequeños, con mensajes que indiquen qué se añadió o corrigió.

| Fase | Trabajo | Evidencia para cerrarla |
|---|---|---|
| 0. Línea base | Crear repositorio, README inicial, CMake mínimo, entorno Python, `.gitignore`, muestra mínima y `PROGRESO.md`. | Compila un «hola/estado» C++ y abre una pantalla Python desde clon limpio. |
| 1. Investigación y especificación | Revisar modelo Minciencias y 1–2 fichas UPC verificables; definir campos, categorías, reglas, casos de uso y esquema CSV. | `docs/esquema_datos.md`, decisiones registradas, muestras con procedencia. |
| 2. Núcleo de estructuras | Listas, multilistas, pila, cola y comprobación de invariantes en C++ y Python. | Pruebas de inserción, recorrido bidireccional, relaciones N:M, LIFO, FIFO y ausencia de enlaces rotos. |
| 3. Gestión y persistencia | CRUD, desactivación, relaciones, planes, carga/guardado y reconstrucción. | Prueba de ida y vuelta archivo → memoria → archivo, reinicio y edición de todos los campos relevantes. |
| 4. Importación | CSV en ambos; URL en Python con captura verificable; evaluar e implementar PDF de texto. | Datos aceptados/rechazados identificados; origen guardado; fallo de red no bloquea uso local. |
| 5. Análisis e interfaces | Vistas, filtros, tablas C++, dashboard Python, histogramas y barras. | Totales contrastados manualmente con fixture de resultados conocidos; mismo significado en ambos programas. |
| 6. Documentación | Especificación técnica Word detallada, diagramas, casos de uso, historias, complejidad, decisiones, guía y trazabilidad R01–R20. | Documento legible, coherente con **el código real** y probado visualmente. |
| 7. Calidad y portabilidad | Pruebas de integración, errores, clones limpios Linux/Windows, CI, corrección de instrucciones. | Compilación y pruebas verdes; demostración completa sin rutas locales; README final copiable. |
| 8. Preparación final | Nombres definitivos de fuentes, datos persistidos, archivo de identificación si Rafael aporta datos y revisión de entregables. | Checklist de la sección 13 completo y último commit identificable. |

**Orden deliberado:** validar modelo y CSV antes de construir pantallas; terminar datos, integridad y estadísticas antes de pulir la apariencia; probar importación real tempranamente para descubrir limitaciones de Scienti con tiempo.

### Cadencia de trabajo y visibilidad desde CLI

En `PROGRESO.md` se mantendrá una tabla con **fecha, fase, realizado, pruebas ejecutadas, resultado y siguiente acción**. Después de cada bloque funcional: actualizar ese archivo, ejecutar las pruebas pertinentes, mostrar cambios con `git diff --stat` y dejar un commit revisable. Un fallo de prueba se registra y corrige antes de marcar el punto como hecho.

Comandos útiles para Rafael desde otra terminal, en el clon local:

```bash
git status --short
git log --oneline -8
git diff --stat
git diff
python -m unittest discover -s tests/python -v
ctest --test-dir build --output-on-failure
```

Las pruebas Python utilizan `unittest` de la biblioteca estándar. CTest ejecuta la autoprueba C++ y, cuando encuentra Python 3.10 o posterior, los tres scripts de `tests/integration/` para menús, interoperabilidad y conexión del backend. Los ejecutables se generan localmente con CMake en `build/`. Todavía faltan la configuración de CI y la verificación en un clon nuevo y en Windows.

### Hitos orientativos hasta la fecha del PDF

- **24–27 septiembre:** base, especificación, muestra inicial y primer análisis de Scienti.
- **28 septiembre–4 octubre:** estructuras, modelo, CRUD y persistencia.
- **5–10 octubre:** importación, estadísticas y las dos interfaces utilizables.
- **11–15 octubre:** documentación detallada y pruebas cruzadas.
- **16–18 octubre:** clones limpios, correcciones de portabilidad y preparación de archivos finales.

Las fechas son una planificación inicial, no una afirmación de trabajo terminado. Si una fuente externa falla, se mantiene el conjunto de datos local y se prioriza que las dos aplicaciones sean utilizables y verificables.

## 11. Pruebas autónomas y casos límite

Las pruebas automatizadas se concentrarán en **comportamientos que pueden fallar de verdad**, no en repetir exactamente el código bajo prueba:

- Lista vacía, un elemento y varios; inserción/eliminación al inicio, medio y final; búsqueda inexistente.
- Relaciones N:M y eliminación/desactivación sin referencias colgantes; producto con varios autores y más de un grupo.
- CSV con tildes, UTF-8, comillas, comas y salto de línea; columna ausente, ID duplicado y fecha incorrecta.
- Guardar y volver a cargar; persistencia de inactivos, cola pendiente, historial, metadatos y versión de esquema.
- Filtro por año en límites exactos; misma cifra al consultar por grupo, investigador y total institucional, con una regla explícita para no contar dos veces un producto.
- Orden FIFO y LIFO; deshacer tras editar relaciones y categorías; comportamiento definido cuando ya no hay nada que deshacer.
- Inicio sin datos, fallo HTTP, respuesta HTML alterada, PDF sin texto, directorio sin permisos y guardado interrumpido.
- Dashboard Python con muestra conocida y sin registros; C++ compilado en modo Release y con avisos del compilador atendidos.

Al crear `.github/workflows/ci.yml`, ejecutar la suite en **Ubuntu y Windows**, al menos una versión de Python con Tkinter, y los compiladores que ofrezca cada plataforma. CI confirma automatismos; la prueba de interfaz y el clon manual en otra computadora siguen siendo necesarios.

## 12. Documentación técnica que se producirá

`docs/especificacion_tecnica.docx` deberá ser autónoma y corresponder a la versión final del software:

1. Portada e identificación que Rafael proporcione.
2. Objetivo, alcance, fuentes consultadas y supuestos explícitos.
3. Requisitos funcionales y no funcionales, con IDs R01–R20 y evidencias.
4. Actores y casos de uso: cargar, gestionar, relacionar, validar, consultar, filtrar, guardar.
5. Historias de usuario y criterios de aceptación.
6. Entradas, salidas, tipos de datos, diccionario CSV y reglas de validación.
7. Modelo conceptual y diagramas de relaciones/multilistas.
8. Diseño y pseudocódigo de listas, multilistas, pila y cola; complejidad temporal y espacial razonada.
9. Estrategia de importación, normalización, duplicados y procedencia.
10. Persistencia, integridad, errores y funcionamiento sin conexión.
11. Estadísticas: definiciones, fórmulas de conteo, filtros y ejemplo con cifras comprobadas.
12. Arquitectura de C++ y Python, equivalencias y diferencias justificadas.
13. Instalación Linux/Windows, operaciones frecuentes, pruebas y resultados reales.
14. Limitaciones comprobadas y trabajo futuro, sin prometer características inexistentes.
15. Referencias y capturas/diagramas legibles.

El DOCX se revisará visualmente antes de entregar: saltos, imágenes, tablas, encabezados y enlaces. Los cambios posteriores al código que alteren funciones o campos obligan a actualizar el documento y el README.

## 13. Definición de «listo para subir a GitHub y probar»

- [ ] Requisitos R01–R20 revisados uno a uno con evidencia.
- [x] Código C++ compila de cero con CMake y ejecuta desde ruta documentada.
- [x] Python con Tkinter abre el dashboard de escritorio.
- [ ] Ambas versiones cargan el mismo esquema CSV; sus estadísticas coinciden con las reglas documentadas.
- [ ] CRUD, desactivación, relaciones, pila, cola, filtros y persistencia resisten reinicios.
- [ ] Dataset de demostración completo, pequeño, lícito de compartir y con fuente/fecha.
- [ ] Importación CSV probada en ambos; importaciones URL/PDF declaradas según funcionamiento real.
- [ ] Pruebas relevantes y CI pasan; errores de red y datos defectuosos se manejan.
- [ ] README probado literalmente en un clon nuevo en Linux y Windows; sin rutas absolutas ni archivos omitidos.
- [x] DOCX técnico redactado y visualmente revisado; diagramas y ejemplos coinciden con el programa. Falta completar la identificación de integrantes.
- [x] Archivos finales llevan nombres definitivos con las iniciales indicadas por el profesor.
- [ ] `git status` limpio después del commit final, sin secretos, cachés ni datos locales accidentales.

## 14. Decisiones abiertas para resolver al llegar a la fase pertinente

| Tema | Decisión pendiente | Política provisional |
|---|---|---|
| Iniciales y nombres de archivos | Resuelto: Rafael indicó `Taller2_REMR.cpp` y `Taller2_REMR.py`. | Mantener esos nombres en fuentes, CMake, pruebas y documentación. |
| Muestra UPC | Determinar grupos y perfiles con información pública suficiente y procedencia verificable. | Empezar pequeño y ampliar tras comprobar la importación. |
| Campos oficiales de productos | Precisar tipologías y categorías según el modelo consultado. | Conservar categoría textual, fuente y estado de validación separados. |
| Extracción PDF | Comprobar si hay PDF de texto con campos aprovechables. | CSV obligatorio; PDF no se anunciará como completado antes de probarlo. |
| Compatibilidad Python | Instalar en la versión disponible de Rafael y en Windows de prueba. | Mantener dependencia fijada y registrar versiones validadas. |
| Base de datos adicional | Evaluar si aporta algo tras satisfacer el núcleo. | CSV compartidos como persistencia e interoperabilidad principal. |
| Repositorio y licencia | Rafael indicará URL y si será público o privado. | Ninguna ruta remota, token ni licencia se inventará. |

## 15. Instrucción breve para retomar el trabajo desde Codex CLI

Guardar este archivo como `PLAN_PROYECTO.md` en la raíz del repositorio y abrir el CLI allí. Mensaje de arranque recomendado:

> Lee PLAN_PROYECTO.md y ENUNCIADO_TALLER_2.md; consulta el PDF original si está disponible. Trabaja la primera fase pendiente; revisa el estado real del repositorio antes de editar. Implementa cambios completos y verificables, ejecuta las pruebas pertinentes, actualiza PROGRESO.md con evidencia y deja los cambios listos para que yo los inspeccione con git diff y los pruebe en otra computadora. Si encuentras una ambigüedad que cambia el modelo de datos, explícala y registra la decisión antes de continuar.

Cuando cambien las instrucciones de Rafael, actualizar este plan, el esquema y los criterios de aceptación para que el CLI siempre trabaje sobre la versión actual.

# Esquema de datos PEA-i, versión 2

Ambos programas usan CSV UTF-8 con encabezados exactos y `\n` como fin de registro. Los campos de texto pueden contener comas, comillas y saltos de línea mediante las reglas normales de CSV. Una carpeta completa contiene `manifest.csv`, cuatro archivos de entidades, tres de relaciones, `cola_validacion.csv` e `historial.csv`. Los archivos vacíos conservan el encabezado. Los guardados nuevos declaran la versión `2`; las carpetas de versión `1` se pueden abrir y se convierten al guardar.

| Archivo | Campos, en orden |
|---|---|
| `manifest.csv` | `version,guardado` |
| `grupos.csv` | `id,nombre,codigo_gruplac,fecha_creacion,unidad,responsable,categoria,descripcion,objetivos,mision,vision,lineas,url,fuente,activo` |
| `investigadores.csv` | `id,nombre,codigo_cvlac,afiliacion,categoria,contacto,url,fuente,activo` |
| `productos.csv` | `id,titulo,anio,fecha,familia,tipologia,categoria,validacion,observacion,doi,url,fuente,activo` |
| `planes.csv` | `id,grupo_id,nombre,inicio,fin,objetivo,indicador,meta,actividad,activo` |
| `membresias.csv` | `grupo_id,investigador_id,rol,inicio,fin,activo` |
| `autorias.csv` | `producto_id,investigador_id,orden,rol,activo` |
| `grupos_productos.csv` | `grupo_id,producto_id,origen,activo` |
| `cola_validacion.csv` | `id,producto_id,motivo,creado` |
| `historial.csv` | `orden,snapshot` |

## Reglas

- `id` y nombres/títulos son obligatorios; los IDs de entidades son únicos y estables. Las relaciones se identifican por sus dos extremos. Todos los extremos deben existir.
- `activo` vale `1` o `0`. `validacion` vale `pendiente`, `validado` o `rechazado`; el valor predeterminado es `pendiente`. Cambiar la categoría o la validación de un producto exige una observación nueva.
- Las fechas no vacías usan `AAAA-MM-DD`. El año del producto, si se conoce, está entre 1900 y el año siguiente al actual. Si hay fecha y año, deben coincidir.
- Un DOI no vacío se compara sin distinguir mayúsculas ni el prefijo `https://doi.org/`. También se exige unicidad de código GrupLAC/CvLAC no vacío. Los títulos iguales sin DOI se revisan manualmente: no se fusionan automáticamente.
- No hay borrado en cascada de entidades. Eliminar una entidad con vínculos, un grupo con planes o un producto con revisiones pendientes requiere resolver primero esas dependencias. Desactivar conserva la historia.
- Las listas dobles guardan entidades. Las multilistas guardan vínculos con recorrido por cualquiera de los dos extremos. Los índices auxiliares aceleran la búsqueda por ID y por código GrupLAC, CvLAC o DOI sin sustituir esas estructuras. La pila conserva hasta 30 acciones para deshacer; la cola atiende las revisiones en orden FIFO.
- Los totales institucionales cuentan IDs de producto activos una sola vez, incluso con varios autores o grupos. Las vistas de grupo/investigador solo usan relaciones activas. Un rango de años excluye productos sin año. Los filtros de categoría y validación se aplican antes de agrupar.
- La categoría del grupo y la del producto son campos distintos. Una ficha GrupLAC que solo declara la clasificación del grupo no determina la categoría de cada producto; ese campo queda vacío hasta encontrar una fuente específica o registrarlo manualmente.
- La carpeta `.backup` conserva los CSV previos al último guardado. Ninguno de los dos programas guarda directamente sobre `data/demo` desde su interfaz.

## Compatibilidad y apertura en hojas de cálculo

Al abrir una carpeta de versión `1`, ambos motores admiten `sigla` en `grupos.csv` (se descarta), un `productos.csv` sin `validacion` (se asigna `pendiente`) y la ausencia de `cola_validacion.csv` (se inicia vacía). Una carpeta de versión `2` exige todos los archivos y encabezados de la tabla. El historial de deshacer anterior se conserva y se adapta al usarlo.

Para evitar la interpretación de fórmulas al abrir los CSV persistidos en una hoja de cálculo, la versión `2` antepone una comilla simple a las celdas cuyo primer carácter es `=`, `+`, `-`, `@`, tabulación, retorno de carro o comilla simple. Ambos motores retiran exactamente esa comilla al cargar la carpeta; así se conserva el valor original. La opción **Archivo → Exportar para hoja de cálculo** produce una copia para consulta que neutraliza fórmulas y no incluye historial ni cola; no se debe usar como carpeta de trabajo.

## Entrada y salida

**Entradas compartidas:** registros de entidades y relaciones, carpeta persistida y archivos CSV por tipo. Python usa formularios Tkinter y consulta URL públicas HTTP/HTTPS de HTML, texto, CSV o PDF de texto. La consulta presenta primero el contenido y la fuente; la extracción automática de campos se limita a fichas GrupLAC/CvLAC o metadatos explícitos de artículos académicos. En GrupLAC puede incorporar el censo de integrantes con su período textual, el plan estratégico, productos fechados de secciones bibliográficas y técnicas reconocidas, vínculos al grupo y autorías cuyos nombres coincidan con el censo. Otros sitios permiten crear un registro tras completar y revisar el formulario. Un CSV remoto solo se incorpora si coincide con el esquema PEA-i. Por defecto, la ventana envía las operaciones de datos al [backend C++](protocolo_backend.md); la implementación Python independiente se activa con `--python-backend`. C++ también ofrece menús de consola e importa CSV.

**Salidas:** fichas consultables, relaciones por ambos extremos, revisiones pendientes, totales por vista y ventana, distribuciones por año, tipología, categoría y validación, y carpeta CSV persistida. El dashboard Python dibuja gráficos con Tkinter Canvas; los campos vacíos siguen contando en el total. C++ presenta tablas y resúmenes en consola. `historial.csv` conserva el nombre de columna `snapshot` por compatibilidad: puede contener una instantánea anterior o un registro JSON de cambios reversibles (`__undo`). Ambos modos pueden leer y deshacer los dos formatos. C++ escribe cambios compactos; el modo Python independiente aún escribe instantáneas.

# Datos públicos de investigación UPC

[`pea_upc.csv`](pea_upc.csv) es el archivo único de datos de PEA-i: reúne grupos, investigadores, productos, planes, sus vínculos, la cola de revisión y el historial para deshacer, en secciones leídas en orden ([esquema](../docs/esquema_datos.md)). Contiene una captura de fichas GrupLAC de grupos asociados a la Universidad Popular del Cesar, enumerados en la búsqueda pública de la Convocatoria 957 de 2024. La importación se realizó el 25 de septiembre de 2026 con [`scripts/import_upc_dataset.py`](../scripts/import_upc_dataset.py). El script conserva los 66 identificadores de grupo de esa consulta y descarga cada ficha desde `https://scienti.minciencias.gov.co/gruplac/jsp/visualiza/visualizagr.jsp?nro=IDENTIFICADOR`. Entre las fuentes están las dos fichas del enunciado: [GISICO en GrupLAC](https://scienti.minciencias.gov.co/gruplac/jsp/visualiza/visualizagr.jsp?nro=00000000002099) y [Adith Bismarck Pérez Orozco en CvLAC](https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000494917).

| Registro | Cantidad |
|---|---:|
| Grupos | 66 |
| Investigadores distintos | 2.736 |
| Productos distintos | 6.363 |
| Planes | 66 |
| Membresías grupo-investigador | 3.291 |
| Vínculos grupo-producto | 6.735 |
| Autorías vinculadas | 9.703 |

Un producto listado en varios grupos se conserva una sola vez por ID. Por eso la ficha GISICO registra 197 productos distintos vinculados en este conjunto, mientras que una captura aislada anterior de esa ficha identificaba 202; la deduplicación institucional y el contenido publicado pueden cambiar los conteos. Los vínculos y autorías solo se crean cuando la extracción reconoce las secciones y nombres de la ficha. La captura no representa todas las actividades que pueden aparecer en GrupLAC.

La categoría de **grupo** procede de su campo de clasificación. Los productos no tienen categoría: GrupLAC no la publica por producto y la clasificación del grupo no la determina (el esquema 3 retiró ese campo). `validacion` la calcula PEA-i con reglas de completitud y verificabilidad ([esquema](../docs/esquema_datos.md#validación-automática)): 6.323 productos quedan validados y 40 rechazados, 37 por no tener un autor del censo y 3 por un DOI mal formado. No constituye una validación oficial de Minciencias. Los datos se guardaron en el esquema 3 el 2 de octubre de 2026 y se convirtieron sin cambios al archivo único (esquema 4) el 3 de octubre de 2026. Los campos de afiliación y contacto de investigadores permanecen vacíos cuando la ficha pública no los expone.

[`scripts/populate_cvlac.py`](../scripts/populate_cvlac.py) consultó enlaces CvLAC individuales y obtuvo una categoría para **274** investigadores: 182 Junior, 54 Asociado, 37 Senior y 1 Emérito. Los **2.462** restantes no tienen categoría almacenada en esta captura; ese vacío no demuestra que carezcan de una categoría oficial. Las páginas de origen pueden cambiar después de la fecha de consulta.

La interfaz abre este archivo al iniciar y guarda en él. Cada importación (URL, PDF, Word o CSV) se incorpora y se guarda de inmediato: agrega lo nuevo y actualiza lo que la fuente cambió, sin borrar nada, así que el conjunto crece con cada consulta. La copia del guardado anterior queda en `data/.backup/pea_upc.csv`. [`scripts/import_upc_dataset.py`](../scripts/import_upc_dataset.py) vuelve a consultar los 66 grupos y fusiona los cambios en este archivo. El script [`scripts/build_real_sample.py`](../scripts/build_real_sample.py) crea por separado una muestra pequeña de las dos URL del enunciado en `data/sample_scienti.csv`; no reemplaza este archivo.

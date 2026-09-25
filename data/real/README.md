# Datos públicos de investigación UPC

Esta carpeta contiene una captura de fichas GrupLAC de grupos asociados a la Universidad Popular del Cesar, enumerados en la búsqueda pública de la Convocatoria 957 de 2024. La importación se realizó el 25 de septiembre de 2026 con [`scripts/import_upc_dataset.py`](../../scripts/import_upc_dataset.py). El script conserva los 66 identificadores de grupo de esa consulta y descarga cada ficha desde `https://scienti.minciencias.gov.co/gruplac/jsp/visualiza/visualizagr.jsp?nro=IDENTIFICADOR`. Entre las fuentes están las dos fichas del enunciado: [GISICO en GrupLAC](https://scienti.minciencias.gov.co/gruplac/jsp/visualiza/visualizagr.jsp?nro=00000000002099) y [Adith Bismarck Pérez Orozco en CvLAC](https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000494917).

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

La categoría de **grupo** procede de su campo de clasificación. La categoría de **producto** se deja vacía porque esa clasificación no determina la del producto. `validacion=pendiente` es el estado interno inicial de PEA-i y no constituye una validación oficial de Minciencias. Los campos de afiliación y contacto de investigadores permanecen vacíos cuando la ficha pública no los expone.

[`scripts/populate_cvlac.py`](../../scripts/populate_cvlac.py) consultó enlaces CvLAC individuales y obtuvo una categoría para **274** investigadores: 182 Junior, 54 Asociado, 37 Senior y 1 Emérito. Los **2.462** restantes no tienen categoría almacenada en esta captura; ese vacío no demuestra que carezcan de una categoría oficial. Las páginas de origen pueden cambiar después de la fecha de consulta.

La interfaz abre esta carpeta automáticamente al iniciar. Para editar sin cambiar la muestra, use **Archivo → Guardar como** y elija otra carpeta. El script [`scripts/build_real_sample.py`](../../scripts/build_real_sample.py) reconstruye por separado la muestra pequeña de las dos URL del enunciado en `data/sample_scienti/`; no reemplaza este conjunto.

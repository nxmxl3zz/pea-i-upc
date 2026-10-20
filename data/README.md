# Datos públicos de investigación UPC

[`pea_upc.csv`](pea_upc.csv) es el archivo único de datos de PEA-i: reúne grupos, investigadores, productos, planes, sus vínculos, la cola de revisión y el historial para deshacer. La captura se actualizó el **19 de octubre de 2026** con [`scripts/import_upc_dataset.py`](../scripts/import_upc_dataset.py), consultando los 66 grupos asociados a la Universidad Popular del Cesar enumerados en la búsqueda pública de la Convocatoria 957 de 2024, y la ficha CvLAC de Adith Bismarck Pérez Orozco. Las 67 consultas terminaron sin errores. El archivo se guardó en el **esquema 5**; se conservaron todos los registros anteriores y sus observaciones de revisión.

El script conserva los 66 identificadores de grupo de esa consulta y descarga cada ficha desde `https://scienti.minciencias.gov.co/gruplac/jsp/visualiza/visualizagr.jsp?nro=IDENTIFICADOR`. Las dos fuentes del enunciado están incluidas: [GISICO en GrupLAC](https://scienti.minciencias.gov.co/gruplac/jsp/visualiza/visualizagr.jsp?nro=00000000002099) y [Adith Bismarck Pérez Orozco en CvLAC](https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000494917).

| Registro | Cantidad |
|---|---:|
| Grupos | 66 |
| Investigadores distintos | 2.748 |
| Productos distintos | 21.419 |
| Planes | 66 |
| Membresías grupo-investigador | 3.303 |
| Vínculos grupo-producto | 22.781 |
| Autorías vinculadas | 17.170 |
| Entradas en la cola de revisión | 0 |
| Entradas en el historial de deshacer | 0 |

Un producto listado en varios grupos o en GrupLAC y CvLAC se conserva una sola vez por ID. El ID se deriva del DOI cuando está disponible; en los demás casos, del título y año, más la tipología para productos distintos de artículos. Una misma tesis repetida en la ficha también se fusiona. GISICO tiene 438 productos distintos vinculados y el investigador del enunciado tiene 86. Los vínculos y autorías solo se crean cuando la extracción reconoce las secciones y nombres de la ficha. La captura no representa todas las actividades publicadas en Scienti; las importaciones agregan y actualizan, sin borrar registros que hayan desaparecido de la fuente.

## Categorías y validación automática

La categoría de **grupo** procede de su campo de clasificación. La categoría de **producto** es independiente: se estima de forma conservadora a partir de la sección y la tipología declaradas, usando el catálogo de 169 subtipos del modelo Minciencias 2024. La captura contiene **20.917 productos con categoría**, de los cuales **20.917 tienen origen estimado** y **0 origen manual**; **502 productos no tienen categoría** porque su tipología no corresponde a un subtipo del modelo (por ejemplo «Otro capítulo de libro publicado», «Otro libro publicado» o «Revisión (Survey)»). GrupLAC publica la prensa y la divulgación («Revista de divulgación», «Periódico de noticias», «Columna de opinión») entre los otros artículos; se estiman como publicación editorial no especializada (`PEE_C2`), igual que en CvLAC. Los productos de una captura anterior que ya no aparecen en la ficha se categorizaron con la misma tabla de estimación. La clasificación del grupo no determina la del producto. Una categoría elegida manualmente se conserva al reimportar. **66 de los 66 grupos** tienen `fecha_creacion`, obtenida del año y mes de formación.

`validacion` la calcula PEA-i con reglas de completitud y verificabilidad: año, tipología, un autor **o** un grupo activos, DOI bien formado si lo hay y una URL o un DOI que permita verificar el producto. **Los 21.419 productos quedan validados y ninguno rechazado.** GrupLAC publica eventos, proyectos, consultorías y redes sin lista de autores, así que esos productos se atribuyen por su vínculo con el grupo; los productos traídos de CvLAC se atribuyen por la autoría del investigador aunque ningún grupo los declare.

GrupLAC publicó tres DOI defectuosos. El de *Cancellation of Surgeries by the Patient, Doctor or Institution* aparecía partido por un espacio (`10.5539/ gjhs.v11n9p34`) y se reparó como `10.5539/gjhs.v11n9p34`. Los de *Violencia obstétrica desde la percepción y vivencias de mujeres en labor de parto* (`10.15446/`) y *Propensión a asumir riesgos…* (`10.15658`) están truncados en la fuente: no se guardan como DOI y la `fuente` del producto registra «DOI incompleto en la fuente»; ambos siguen verificables por su ficha GrupLAC. Ni la validación automática ni las categorías estimadas constituyen una validación o clasificación oficial de Minciencias.

[`scripts/populate_cvlac.py`](../scripts/populate_cvlac.py) había consultado enlaces CvLAC individuales. Esta captura conserva una categoría para **274 investigadores**: 182 Investigador Junior (IJ); 54 Investigador Asociado (I); 37 Investigador Senior (IS); 1 Investigador Emérito (IE). Los **2.474** restantes no tienen categoría almacenada; ese vacío no demuestra que carezcan de una categoría oficial. Los campos de afiliación y contacto permanecen vacíos cuando la ficha pública no los expone. Las páginas pueden cambiar después de la fecha de consulta.

## Indicadores de las fichas del enunciado

Medidos sobre este archivo con `end=2026`, sin año inicial ni filtro de validación:

| Entidad | Productos vinculados | Con categoría dentro de su ventana | Sin categoría en los últimos 10 años | Indicador sobre 10 |
|---|---:|---:|---:|---:|
| GISICO | 438 | 146 | 2 | 0,501368 |
| Adith Bismarck Pérez Orozco | 86 | 5 | 0 | 0,087751 |

Las categorías de todos los productos contados en estos dos indicadores son estimadas. Los máximos de normalización se calculan entre los **66 grupos activos** para GISICO y los **2.748 investigadores activos** para el investigador. Son resultados relativos a la población cargada, no una clasificación nacional oficial. El total vinculado incluye productos fuera de las ventanas de observación.

## Actualizar y guardar

La interfaz abre este archivo al iniciar y guarda en él. Cada importación se incorpora y se guarda de inmediato: agrega lo nuevo y actualiza lo que la fuente cambió, sin borrar nada. La copia del guardado anterior queda en `data/.backup/pea_upc.csv`. La carga masiva desactiva el historial de deshacer; en esta captura la cola y el historial están vacíos.

Para repetir la actualización de los 66 grupos e incorporar los productos del investigador:

```bash
python3 scripts/import_upc_dataset.py --cvlac "https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000494917"
```

`--cvlac URL` admite varias fichas repitiendo la opción. Si una fuente falla, conserva sus registros anteriores y el script informa de la importación incompleta. [`scripts/build_real_sample.py`](../scripts/build_real_sample.py) genera una muestra pequeña por separado en `data/sample_scienti.csv`; no reemplaza este archivo.

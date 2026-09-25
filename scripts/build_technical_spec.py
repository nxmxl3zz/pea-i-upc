"""Genera la especificación técnica de PEA-i UPC en formato DOCX."""

from __future__ import annotations

from pathlib import Path
import tempfile

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/especificacion_tecnica.docx"
FONT = "/usr/share/fonts/TTF/DejaVuSans.ttf"
BOLD_FONT = "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
NAVY = (25, 52, 78)
PALE = (232, 239, 246)
GRAY = (90, 103, 115)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(BOLD_FONT if bold else FONT, size)


def box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int],
        lines: list[str], fill: tuple[int, int, int] = PALE) -> None:
    draw.rounded_rectangle(xy, radius=17, fill=fill, outline=NAVY, width=3)
    left, top, right, bottom = xy
    widths = [draw.textbbox((0, 0), line, font=font(28, i == 0))[2] for i, line in enumerate(lines)]
    total_height = len(lines) * 40
    y = top + (bottom - top - total_height) // 2
    for i, (line, width) in enumerate(zip(lines, widths)):
        draw.text((left + (right - left - width) // 2, y), line,
                  font=font(28, i == 0), fill=NAVY)
        y += 40


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int],
          end: tuple[int, int]) -> None:
    draw.line((start, end), fill=NAVY, width=5)
    x1, y1 = start
    x2, y2 = end
    if abs(x2 - x1) >= abs(y2 - y1):
        sign = 1 if x2 > x1 else -1
        draw.polygon([(x2, y2), (x2 - 18 * sign, y2 - 10),
                      (x2 - 18 * sign, y2 + 10)], fill=NAVY)
    else:
        sign = 1 if y2 > y1 else -1
        draw.polygon([(x2, y2), (x2 - 10, y2 - 18 * sign),
                      (x2 + 10, y2 - 18 * sign)], fill=NAVY)


def architecture_image(path: Path) -> None:
    canvas = Image.new("RGB", (1600, 545), "white")
    draw = ImageDraw.Draw(canvas)
    box(draw, (25, 60, 350, 215), ["Usuario", "Tkinter"])
    box(draw, (475, 60, 800, 215), ["Mensajes JSON", "stdin / stdout"])
    box(draw, (925, 60, 1250, 215), ["Motor C++", "Repository"])
    box(draw, (1350, 60, 1570, 215), ["CSV", "persistencia"])
    arrow(draw, (355, 135), (468, 135))
    arrow(draw, (805, 135), (918, 135))
    arrow(draw, (1255, 135), (1343, 135))
    box(draw, (25, 315, 550, 475), ["Fuentes", "URL / PDF / CSV / Office"])
    box(draw, (690, 315, 1215, 475), ["Importador Python", "vista previa y validación"])
    arrow(draw, (555, 395), (683, 395))
    arrow(draw, (950, 308), (950, 225))
    draw.text((1230, 380), "Motor Python autónomo", font=font(24), fill=GRAY)
    draw.text((1230, 418), "misma interfaz", font=font(24), fill=GRAY)
    canvas.save(path)


def model_image(path: Path) -> None:
    canvas = Image.new("RGB", (1600, 730), "white")
    draw = ImageDraw.Draw(canvas)
    box(draw, (575, 260, 1025, 460), ["PRODUCTO", "hecho contado una vez"], (220, 235, 245))
    box(draw, (15, 270, 395, 445), ["GRUPO", "grupo_producto"])
    box(draw, (1205, 270, 1585, 445), ["INVESTIGADOR", "autoría"])
    box(draw, (575, 15, 1025, 175), ["TIEMPO", "año / fecha"])
    box(draw, (390, 555, 790, 715), ["TIPO", "familia / tipología"])
    box(draw, (815, 555, 1240, 715), ["ESTADO", "categoría / validación"])
    arrow(draw, (400, 357), (565, 357))
    arrow(draw, (1195, 357), (1035, 357))
    arrow(draw, (800, 180), (800, 250))
    arrow(draw, (635, 545), (700, 470))
    arrow(draw, (1015, 545), (925, 470))
    canvas.save(path)


def use_case_image(path: Path) -> None:
    canvas = Image.new("RGB", (1600, 570), "white")
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((120, 125, 200, 205), outline=NAVY, width=5)
    draw.line((160, 205, 160, 390), fill=NAVY, width=5)
    draw.line((75, 260, 245, 260), fill=NAVY, width=5)
    draw.line((160, 390, 85, 500), fill=NAVY, width=5)
    draw.line((160, 390, 235, 500), fill=NAVY, width=5)
    draw.text((60, 520), "Usuario", font=font(30, True), fill=NAVY)
    labels = [
        "Cargar o iniciar sin datos",
        "Gestionar registros y relaciones",
        "Importar y revisar fuentes",
        "Filtrar y consultar estadísticas",
        "Revisar cola y deshacer",
        "Guardar o recuperar datos CSV",
    ]
    for index, line in enumerate(labels):
        top = 8 + index * 92
        xy = (475, top, 1540, top + 76)
        draw.ellipse(xy, fill=PALE, outline=NAVY, width=3)
        width = draw.textbbox((0, 0), line, font=font(29, True))[2]
        draw.text((475 + (1065 - width) // 2, top + 20),
                  line, font=font(29, True), fill=NAVY)
        arrow(draw, (280, 285), (465, top + 38))
    canvas.save(path)


def shade(cell, color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def borders(cell) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    edges = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        item = OxmlElement("w:" + edge)
        item.set(qn("w:val"), "single")
        item.set(qn("w:sz"), "4")
        item.set(qn("w:color"), "D9D9D9")
        edges.append(item)
    tc_pr.append(edges)


def margins(cell) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    cell_mar = OxmlElement("w:tcMar")
    for edge, value in (("top", "90"), ("left", "100"), ("bottom", "90"), ("right", "100")):
        node = OxmlElement("w:" + edge)
        node.set(qn("w:w"), value)
        node.set(qn("w:type"), "dxa")
        cell_mar.append(node)
    tc_pr.append(cell_mar)


def add_table(doc: Document, headers: list[str], rows: list[list[str]],
              widths: list[float]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for row_index, values in enumerate([headers] + rows):
        row = table.rows[0] if row_index == 0 else table.add_row()
        tr_pr = row._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
        for col_index, value in enumerate(values):
            cell = row.cells[col_index]
            cell.width = Cm(widths[col_index])
            cell.text = str(value)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            borders(cell)
            margins(cell)
            if row_index == 0:
                shade(cell, "1C3955")
            elif row_index % 2 == 0:
                shade(cell, "F3F7FA")
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.line_spacing = 1.05
                if col_index == 0:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in paragraph.runs:
                    run.font.name = "Liberation Sans"
                    run.font.size = Pt(8.4 if len(headers) > 2 else 8.7)
                    if row_index == 0:
                        run.font.bold = True
                        run.font.color.rgb = RGBColor(255, 255, 255)
    header = table.rows[0]._tr
    tr_pr = header.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    tr_pr.append(repeat)
    doc.add_paragraph()


def paragraph(doc: Document, text: str, style: str | None = None) -> None:
    doc.add_paragraph(text, style=style)


def bullet(doc: Document, text: str) -> None:
    doc.add_paragraph(text, style="List Bullet")


def heading(doc: Document, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def figure(doc: Document, path: Path, caption: str) -> None:
    image = doc.add_paragraph()
    image.alignment = WD_ALIGN_PARAGRAPH.CENTER
    image.add_run().add_picture(str(path), width=Cm(14.5))
    label = doc.add_paragraph(caption)
    label.alignment = WD_ALIGN_PARAGRAPH.CENTER
    label.style = "Caption"


def setup(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2.1)
    section.right_margin = Cm(2.1)
    normal = doc.styles["Normal"]
    normal.font.name = "Liberation Sans"
    normal.font.size = Pt(9.2)
    normal.font.color.rgb = RGBColor(25, 25, 25)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.12
    for name, size, above, below in (
        ("Title", 20, 0, 13), ("Heading 1", 13, 12, 6),
        ("Heading 2", 10.7, 11, 5),
    ):
        style = doc.styles[name]
        style.font.name = "Liberation Sans"
        style.font.size = Pt(size)
        style.font.bold = name != "Title"
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(above)
        style.paragraph_format.space_after = Pt(below)
        style.paragraph_format.keep_with_next = True
        ppr = style.element.get_or_add_pPr()
        for border in ppr.findall(qn("w:pBdr")):
            ppr.remove(border)
    doc.styles["Title"].font.bold = True
    subtitle = doc.styles["Subtitle"]
    subtitle.font.name = "Liberation Sans"
    subtitle.font.size = Pt(9)
    subtitle.font.italic = False
    subtitle.font.color.rgb = RGBColor(0, 0, 0)
    subtitle.paragraph_format.space_after = Pt(9)
    doc.styles["Caption"].font.name = "Liberation Sans"
    doc.styles["Caption"].font.size = Pt(8.5)
    doc.styles["Caption"].font.color.rgb = RGBColor(70, 70, 70)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.style.font.name = "Liberation Sans"
    footer.style.font.size = Pt(8)
    footer.style.font.color.rgb = RGBColor(90, 90, 90)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)


def build() -> None:
    doc = Document()
    doc.core_properties.title = "Especificación técnica del Programa Estadístico de Análisis de Investigación"
    doc.core_properties.subject = "Modelo de datos, estructuras, algoritmos y contratos de PEA-i"
    doc.core_properties.author = ""
    doc.core_properties.last_modified_by = ""
    setup(doc)
    doc.add_paragraph("UNIVERSIDAD POPULAR DEL CESAR  ·  INGENIERÍA DE SISTEMAS", style="Subtitle")
    doc.add_paragraph("Especificación técnica del Programa Estadístico de Análisis de Investigación",
                      style="Title")
    paragraph(doc, "PEA-i administra grupos de investigación, investigadores, productos y planes de la "
                   "Universidad Popular del Cesar. El modelo conserva cada entidad una sola vez y representa "
                   "sus relaciones mediante multilistas. Esta especificación define las entradas y salidas, "
                   "estructuras, reglas de integridad, consultas estadísticas, persistencia e interoperabilidad "
                   "de las soluciones C++ y Python.")

    heading(doc, "1 Objetivo y alcance")
    paragraph(doc, "Las operaciones de dominio son alta, consulta, edición, desactivación, reactivación y baja "
                   "de entidades y relaciones. C++ ofrece menús de consola y un protocolo local de solicitudes; "
                   "Python ofrece un panel Tkinter y conserva un motor autónomo con el mismo esquema de datos. "
                   "Tkinter inicia el proceso C++ en modo API cuando encuentra un binario vigente y, en caso "
                   "contrario, ejecuta el motor Python.")
    paragraph(doc, "Las salidas comprenden fichas y relaciones consultables, revisión pendiente, historial de "
                   "deshacer, distribuciones descriptivas y diez archivos CSV por carpeta. La adquisición "
                   "externa usa fichas públicas GrupLAC o CvLAC, CSV, Excel, Word y PDF con texto extraíble. "
                   "El conjunto incluido reúne fichas públicas de 66 grupos UPC; no es un censo institucional.")

    heading(doc, "2 Arquitectura y casos de uso")
    paragraph(doc, "La interfaz Tkinter envía una solicitud JSON por línea a la entrada estándar de "
                   "pea_cpp --api y recibe una respuesta JSON por la salida estándar. No intervienen puertos "
                   "ni servicios de red en la conexión entre procesos. Repository mantiene listas, "
                   "multilistas, pila y cola en memoria y coordina el guardado CSV. Python obtiene y "
                   "previsualiza las fuentes web; los registros confirmados se incorporan mediante "
                   "operaciones del motor activo.")
    with tempfile.TemporaryDirectory(prefix="pea-doc-") as folder:
        temp = Path(folder)
        architecture = temp / "arquitectura.png"
        model = temp / "modelo.png"
        use_case = temp / "casos.png"
        architecture_image(architecture)
        model_image(model)
        use_case_image(use_case)
        figure(doc, architecture, "Figura 1. Procesos y flujo de datos de la aplicación.")
        paragraph(doc, "Los casos de uso cubren inicio vacío o desde carpeta, mantenimiento de entidades y "
                       "vínculos, incorporación de fuentes, consulta estadística, revisión, deshacer y guardado.")
        figure(doc, use_case, "Figura 2. Casos de uso principales del usuario.")

        heading(doc, "3 Modelo de información")
        paragraph(doc, "El producto es la unidad que se cuenta en las estadísticas. Cada grupo, investigador, "
                       "producto o plan tiene un ID estable. Las multilistas vinculan entidades sin duplicarlas. "
                       "Membresías unen grupo e investigador; autorías unen investigador y producto; "
                       "grupos_productos unen grupo y producto. Un plan pertenece a un grupo.")
        figure(doc, model, "Figura 3. Dimensiones del hipercubo lógico alrededor del producto.")

    heading(doc, "Variables de entrada y salida", 2)
    add_table(doc,
              ["Registro", "Entrada principal", "Salida y relación"],
              [
                  ["Grupo", "ID, nombre, código GrupLAC, unidad, categoría, líneas, estado y fuente.",
                   "Ficha y productos vinculados; integrantes y planes."],
                  ["Investigador", "ID, nombre, CvLAC, afiliación, categoría, contacto público, estado y fuente.",
                   "Ficha, grupos y productos de autoría."],
                  ["Producto", "ID, título, año o fecha, familia, tipología, categoría, validación, observación, DOI y fuente.",
                   "Ficha, grupos, autores y contribución a estadísticas."],
                  ["Plan", "ID, grupo, plazo, objetivo, indicador, meta y actividad.",
                   "Plan consultable dentro del grupo."],
              ], [2.5, 7.3, 7.0])
    paragraph(doc, "Las salidas estadísticas son total de productos únicos, conteos por año, tipología, "
                   "categoría y validación, más listas paginadas. Los campos vacíos no se completan con valores "
                   "supuestos. Las variables exactas de persistencia figuran en el diccionario del apartado 12.")

    heading(doc, "4 Estructuras de datos y complejidad")
    add_table(doc,
              ["Estructura", "Uso concreto", "Costos relevantes"],
              [
                  ["Lista doble", "Entidades: grupos, investigadores, productos y planes. Nodos anterior/siguiente; índices auxiliares por ID.",
                   "Inserción al final O(1); recorrido O(n); búsqueda por ID O(1) promedio con índice."],
                  ["Multilista", "Membresías, autorías y vínculos grupo-producto recorridos desde cualquiera de sus extremos.",
                   "Inserción O(1) promedio con índice; recorrer vecinos O(k)."],
                  ["Pila", "Deshacer las últimas 30 operaciones. Python conserva instantáneas; C++ guarda cambios compactos.",
                   "Apilar y desapilar O(1); el tamaño del registro de deshacer depende del cambio."],
                  ["Cola", "Revisiones pendientes de productos en orden de llegada.",
                   "Encolar, consultar frente y desencolar O(1)."],
              ], [2.8, 8.0, 6.0])
    paragraph(doc, "Los nodos son la fuente de verdad. Los diccionarios y mapas sirven de índices auxiliares. "
                   "La consulta estadística recorre productos activos y vínculos pertinentes; no existe una "
                   "matriz densa con todas las combinaciones posibles. Python materializa temporalmente los "
                   "productos de la vista; C++ recorre la lista principal y limita la página devuelta.")

    heading(doc, "5 Operaciones y reglas de integridad")
    bullet(doc, "Alta, búsqueda, consulta, edición, desactivación, reactivación y baja de entidades y relaciones; los IDs y los extremos de una relación no se editan.")
    bullet(doc, "No se elimina en cascada un grupo, investigador o producto con relaciones pendientes; primero se resuelven esos vínculos o se desactiva el registro.")
    bullet(doc, "Los códigos GrupLAC, CvLAC y DOI no vacíos son únicos. El DOI se compara sin distinguir mayúsculas ni el prefijo doi.org. Las fechas siguen AAAA-MM-DD; el año del producto debe concordar con su fecha.")
    bullet(doc, "Cambiar categoría o validación de un producto exige una observación nueva. La validación de PEA-i es interna y no equivale a la clasificación oficial de Minciencias.")
    bullet(doc, "La cola conserva trabajos pendientes y la pila permite deshacer. Ambas se guardan junto con las entidades y relaciones.")

    heading(doc, "6 Persistencia e interoperabilidad")
    paragraph(doc, "Cada carpeta de datos contiene manifest.csv, cuatro archivos de entidades, tres de relaciones, "
                   "cola_validacion.csv e historial.csv. El formato común es CSV UTF-8 con encabezados, "
                   "comillas y saltos de línea conforme al formato CSV. manifest.csv declara la versión 2. "
                   "Ambos motores leen la versión 1 y la migran al guardar. La versión 2 neutraliza los "
                   "valores que una hoja de cálculo interpretaría como fórmulas y recupera su valor original "
                   "al cargar. Se valida la integridad referencial. Se preparan archivos temporales "
                   "y se conserva .backup del guardado previo para recuperación.")
    paragraph(doc, "Las dos aplicaciones pueden abrir por turnos la misma carpeta. No existe bloqueo de "
                   "escritura multiusuario; abrir simultáneamente una carpeta editable puede producir "
                   "conflictos. data/demo y data/real se tratan como muestras: las modificaciones se guardan "
                   "en otra carpeta mediante Guardar como.")

    heading(doc, "7 Adquisición e importación")
    paragraph(doc, "Ambos programas importan CSV del esquema PEA-i con vista previa y conteo de filas "
                   "aceptables o rechazadas. Python también admite Excel XLSX y Word DOCX mediante "
                   "dependencias opcionales, y consulta URL públicas HTTP/HTTPS de HTML, texto, "
                   "CSV o PDF de texto y muestra su contenido antes de crear registros. La extracción "
                   "estructurada se limita a fichas GrupLAC/CvLAC y metadatos explícitos de artículos. "
                   "Las páginas de estructura desconocida se limitan a vista previa y captura supervisada.")
    paragraph(doc, "La importación de PDF de texto requiere pdftotext de Poppler. Los escaneos sin texto "
                   "seleccionable requieren OCR externo. C++ dispone de importación CSV autónoma.")

    heading(doc, "Controles de seguridad de las fuentes", 2)
    paragraph(doc, "La descarga limita la respuesta a 8 MB, permite solo HTTP y HTTPS en los puertos 80 y "
                   "443, rechaza destinos locales o privados y verifica cada redirección. La conexión usa "
                   "una dirección pública previamente validada, sin proxy heredado del entorno. El tiempo "
                   "de espera por operación es 15 segundos; no constituye un límite total de duración.")
    paragraph(doc, "Los archivos locales PDF, XLSX y DOCX tienen un límite de 32 MB. Los documentos Office "
                   "se inspeccionan antes de extraerlos, con un máximo de 10.000 entradas y 128 MB "
                   "de tamaño declarado sin comprimir. El conversor PDF tiene 25 segundos para extraer "
                   "hasta cinco millones de caracteres y límites adicionales de CPU y memoria en POSIX. "
                   "Cada CSV admite hasta 500.000 filas y 100.000 caracteres por campo.")
    paragraph(doc, "El ejecutable Windows incluido se usa cuando su SHA-256 y la huella de las fuentes "
                   "coinciden. Esas huellas detectan cambios accidentales, pero no autentican al autor. "
                   "Los parámetros privados de URL se omiten al guardar la procedencia; se retienen solo "
                   "identificadores públicos necesarios para las fichas GrupLAC y CvLAC.")

    heading(doc, "8 Hipercubo lógico y estadísticas")
    paragraph(doc, "El hipercubo se implementa como consulta multidimensional calculada bajo demanda: "
                   "cada producto es un hecho único; grupo e investigador son dimensiones "
                   "relacionales, y año, tipología, categoría y validación son atributos de análisis. "
                   "La vista selecciona todos los productos o un grupo, investigador o producto. Después "
                   "se aplican rango de años, categoría y estado; el resultado se agrupa por año, "
                   "tipología, categoría y validación.")
    paragraph(doc, "Total(vista, filtros) = número de IDs de producto activos distintos que satisfacen "
                   "los vínculos activos y todos los filtros. Un producto unido a varios grupos o autores "
                   "se cuenta una sola vez dentro de la vista. Cuando se fija un rango temporal, "
                   "los productos sin año quedan fuera; fuera del rango sí cuentan en el total y aparecen "
                   "como Sin dato en la distribución correspondiente.")
    paragraph(doc, "No se almacena un cubo OLAP materializado. Cada solicitud selecciona una dimensión "
                   "relacional; la consulta no admite una intersección simultánea de grupo e investigador. "
                   "La consola muestra tablas y cifras; Tkinter muestra "
                   "barras por año, tipología, categoría y validación, además de una tabla de productos.")

    heading(doc, "9 Historias de usuario y aceptación")
    add_table(doc,
              ["Historia", "Necesidad", "Criterio de aceptación"],
              [
                  ["HU01", "Como gestor quiero iniciar vacío o abrir datos guardados.",
                   "La aplicación permite elegir y conserva cambios al cerrar y reabrir."],
                  ["HU02", "Como gestor quiero relacionar grupos, personas y productos.",
                   "Los vínculos se consultan desde ambos extremos sin duplicar entidades."],
                  ["HU03", "Como revisor quiero procesar productos en orden y deshacer errores.",
                   "La cola atiende FIFO; la pila restaura la acción reversible más reciente."],
                  ["HU04", "Como analista quiero filtrar los resultados.",
                   "Las vistas por grupo, investigador y producto respetan años, categoría y validación."],
                  ["HU05", "Como gestor quiero importar una fuente pública o CSV.",
                   "La vista previa identifica la fuente, muestra campos y registra aceptación o rechazo."],
              ], [1.8, 7.2, 7.8])

    heading(doc, "10 Correspondencia entre requisitos y diseño")
    rows = [
        ("R01", "Dos soluciones", "Consola C++17; interfaz Tkinter y motor Python autónomo."),
        ("R02", "Grupos", "Registro con ID, código GrupLAC, categoría, líneas, fuente y estado."),
        ("R03", "Investigadores", "Registro con ID, CvLAC, afiliación, categoría, fuente y estado."),
        ("R04", "Productos", "Registro con fecha, tipología, categoría, validación y DOI."),
        ("R05", "Integrantes y planes", "Membresía grupo-investigador y plan con grupo_id."),
        ("R06", "Entradas y salidas", "Campos del apartado 3; CSV y distribuciones del apartado 8."),
        ("R07", "Fuentes externas", "CSV en ambos motores; URL pública, PDF, XLSX y DOCX en Python."),
        ("R08", "Listas", "Lista doble enlazada por tipo de entidad."),
        ("R09", "Multilistas", "Vínculos indexados y recorribles desde ambos extremos."),
        ("R10", "Pilas", "Deshacer LIFO de hasta 30 acciones, persistido en historial.csv."),
        ("R11", "Colas", "Revisión FIFO persistida en cola_validacion.csv."),
        ("R12", "CRUD y persistencia", "Operaciones de dominio y esquema CSV versión 2, con migración de la versión 1."),
        ("R13", "Categoría y validación", "Actualización condicionada a observación nueva."),
        ("R14", "Ventanas temporales", "Dos años, cinco años o intervalo personalizado."),
        ("R15", "Vistas estadísticas", "Total, grupo, investigador o producto sin duplicar IDs."),
        ("R16", "Presentación C++", "Menús, tablas y resúmenes numéricos en consola."),
        ("R17", "Presentación Python", "Barras por año, tipología, categoría y validación; tabla paginada."),
        ("R18", "Inicio con o sin datos", "Carga inicial de data/real, inicio vacío y apertura de carpeta CSV."),
        ("R19", "Archivos fuente", "Taller2_REMR.cpp y Taller2_REMR.py."),
        ("R20", "Especificación", "Modelo, estructuras, algoritmos, contratos y diagramas."),
    ]
    add_table(doc, ["ID", "Requisito", "Diseño correspondiente"], [list(row) for row in rows],
              [1.25, 4.5, 11.05])

    heading(doc, "11 Restricciones del sistema y alcance de los datos")
    paragraph(doc, "El conjunto data/real reúne fichas públicas GrupLAC de 66 grupos UPC. Contiene "
                   "2.736 investigadores, 3.291 membresías, 66 planes, 6.363 productos únicos, 6.735 "
                   "vínculos grupo-producto y 9.703 autorías. Hay 274 investigadores con categoría "
                   "CvLAC capturada. La categoría del grupo no se asigna a sus productos: cuando la "
                   "fuente no clasifica un producto, su categoría queda vacía. Las fichas públicas pueden "
                   "cambiar; este conjunto no constituye un censo institucional actualizado.")
    paragraph(doc, "La extracción de URL depende del contenido público entregado por el servidor. Los PDF "
                   "escaneados requieren OCR externo; las páginas que generan sus datos exclusivamente con "
                   "JavaScript o exigen autenticación no suministran registros estructurados por esta vía. "
                   "La persistencia no implementa bloqueo de escritura entre procesos: una carpeta editable "
                   "debe abrirse en una instancia a la vez.")
    paragraph(doc, "El motor Python autónomo guarda instantáneas en el historial; el motor C++ conserva "
                   "registros compactos de cambios. La consulta estadística construye agregados bajo demanda "
                   "y no reserva una celda para cada combinación de dimensiones. El tamaño de la memoria "
                   "depende del número de entidades, vínculos y longitud de los campos almacenados.")

    heading(doc, "12 Diccionario de persistencia")
    add_table(doc, ["Archivo", "Campos guardados"], [
        ["manifest.csv", "version, guardado"],
        ["grupos.csv", "id, nombre, codigo_gruplac, fecha_creacion, unidad, responsable, categoria, descripcion, objetivos, mision, vision, lineas, url, fuente, activo"],
        ["investigadores.csv", "id, nombre, codigo_cvlac, afiliacion, categoria, contacto, url, fuente, activo"],
        ["productos.csv", "id, titulo, anio, fecha, familia, tipologia, categoria, validacion, observacion, doi, url, fuente, activo"],
        ["planes.csv", "id, grupo_id, nombre, inicio, fin, objetivo, indicador, meta, actividad, activo"],
        ["membresias.csv", "grupo_id, investigador_id, rol, inicio, fin, activo"],
        ["autorias.csv", "producto_id, investigador_id, orden, rol, activo"],
        ["grupos_productos.csv", "grupo_id, producto_id, origen, activo"],
        ["cola_validacion.csv", "id, producto_id, motivo, creado"],
        ["historial.csv", "orden, snapshot"],
    ], [4.0, 12.8])

    heading(doc, "13 Ejecución y referencias")
    paragraph(doc, "En Windows de 64 bits, con Python 3.10 o posterior y Tkinter, se abre "
                   "Iniciar PEA-i.pyw mediante doble clic; el repositorio incluye pea_cpp.exe. "
                   "Para la consola se ejecuta bin/windows/pea_cpp.exe. En Linux se ejecuta "
                   "python3 src/python/Taller2_REMR.py; CMake compila C++17 si no existe el binario. "
                   "El modo Python independiente se fuerza con --python-backend. El README del "
                   "repositorio contiene los comandos completos.")
    bullet(doc, "Enunciado del taller: ENUNCIADO_TALLER_2.md, Universidad Popular del Cesar, 2026.")
    bullet(doc, "Esquema y reglas exactas: docs/esquema_datos.md; protocolo: docs/protocolo_backend.md.")
    bullet(doc, "Procedencia de datos: data/real/README.md y fichas públicas GrupLAC y CvLAC enlazadas allí.")
    bullet(doc, "Código fuente: src/cpp/Taller2_REMR.cpp y src/python/Taller2_REMR.py.")

    heading(doc, "14 Algoritmos principales")
    paragraph(doc, "Consulta estadística: la multilista selecciona los IDs de producto asociados a la "
                   "vista. Se recorren los productos activos, se aplican los filtros y se incrementan "
                   "los conteos. La lista visible se pagina sin alterar el total. Con P productos, R "
                   "vínculos de la vista y D valores distintos de distribución, Python emplea O(P + R) "
                   "tiempo promedio y O(P + R + D) memoria temporal. C++ usa conjuntos y mapas ordenados: "
                   "el tiempo es O(P + R log(R + 1) + P log(R + 1) + P log(D + 1)) y la memoria adicional "
                   "es O(R + L + D), donde L es el tamaño de página solicitado.")
    paragraph(doc, "Guardado: se valida el esquema y las relaciones; se escriben CSV temporales; "
                   "se conservan los archivos anteriores en .backup; y se sustituyen los archivos "
                   "de destino. En una carga, la versión del manifiesto y los encabezados se "
                   "comprueban antes de reconstruir vínculos, cola e historial.")
    paragraph(doc, "Revisión: encolar añade al final; procesar lee el frente, exige una observación "
                   "y cambia el estado del producto; el registro de deshacer entra en la pila; "
                   "por último se retira el frente. Deshacer aplica la acción inversa más reciente.")

    heading(doc, "15 Contratos de operación")
    add_table(doc, ["Operación", "Entrada y precondición", "Salida y postcondición"], [
        ["Crear producto", "ID y título no vacíos; ID y DOI sin colisión; año y fecha concordantes.",
         "Un nodo activo queda indexado por ID; no se crean relaciones implícitas."],
        ["Vincular grupo y producto", "IDs de ambos extremos existentes; par no duplicado.",
         "La relación activa se consulta desde grupo y desde producto."],
        ["Actualizar validación", "Producto existente, estado permitido y observación nueva.",
         "Se conserva el nuevo estado y la modificación entra en la pila de deshacer."],
        ["Consultar estadísticas", "Vista válida; ID seleccionado cuando corresponde; rango inicial no mayor que el final.",
         "Total único y distribuciones calculadas tras filtrar; paginar no modifica el total."],
        ["Guardar carpeta", "Datos con integridad referencial y ruta de destino escribible.",
         "Se escriben diez CSV del esquema 2 y se conserva el guardado anterior en .backup."],
    ], [3.15, 6.8, 6.85])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(f"Documento generado: {OUTPUT}")


if __name__ == "__main__":
    build()

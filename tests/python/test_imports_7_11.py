"""Regresiones de diagnósticos y trabajo duplicado en importaciones (7–11)."""

from email.message import Message
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pea_imports_7_11", ROOT / "src/python/Taller2_REMR.py")
pea = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pea)
SCRIPT_SPEC = importlib.util.spec_from_file_location("populate_cvlac_7_11", ROOT / "scripts/populate_cvlac.py")
populate = importlib.util.module_from_spec(SCRIPT_SPEC)
SCRIPT_SPEC.loader.exec_module(populate)

GROUP_URL = "https://scienti.minciencias.gov.co/gruplac/jsp/visualiza/visualizagr.jsp?nro=123"
CV_URL = "https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=42"
GROUP = "<h1>Grupo de prueba</h1><h2>Datos básicos</h2>"
ARTICLE = "<p>1.- Publicado en revista especializada: Válido</p><p>2025, DOI:10.1000/valido</p>"
CV = "<h1>Hoja de vida</h1><p>Nombre</p><p>Ana Pérez</p>"


class ImportDiagnosticsTests(unittest.TestCase):
    def test_profile_failure_is_visible_and_does_not_become_an_article(self):
        preview = pea.parse_web_page('<h1>Acceso temporalmente no disponible</h1>'
                                     '<meta name="citation_title" content="No es el perfil">', CV_URL)
        self.assertIsNone(preview.suggested_kind)
        self.assertTrue(any("Perfil Scienti" in item and "nombre" in item for item in preview.diagnostics))
        self.assertIn("Acceso temporalmente", preview.title)

    def test_group_stages_preserve_products_and_plan_after_roster_failure(self):
        html = GROUP + '<h2>Plan Estratégico</h2><p>Publicar</p><h2>Estado del arte</h2>' \
            '<h2>Artículos publicados</h2>' + ARTICLE + '<h2>Libros publicados</h2>'
        with patch.object(pea, "parse_gruplac_members", side_effect=pea.DataError("Censo inválido")):
            preview = pea.parse_web_page(html, GROUP_URL)
        self.assertEqual(preview.suggested_kind, "grupos")
        self.assertEqual(len(preview.related_products), 1)
        self.assertEqual(preview.related_plan["actividad"], "Publicar")
        self.assertEqual(preview.related_members, ())
        self.assertTrue(any("Integrantes GrupLAC" in item and "Censo inválido" in item
                            for item in preview.diagnostics))

    def test_bad_group_product_does_not_discard_valid_neighbors(self):
        html = GROUP + '<h2>Artículos publicados</h2>' + ARTICLE + \
            '<p>2.- Publicado en revista especializada: ' + 'x' * 100001 + \
            '</p><p>2025,</p><p>3.- Publicado en revista especializada: Posterior</p>' \
            '<p>2024,</p><h2>Libros publicados</h2>'
        preview = pea.parse_web_page(html, GROUP_URL)
        self.assertEqual([row["titulo"] for row in preview.related_products], ["Válido", "Posterior"])
        self.assertTrue(any("Productos GrupLAC" in item and "tamaño" in item for item in preview.diagnostics))
        self.assertTrue(all(len(item) < 1000 for item in preview.diagnostics))
        with self.assertRaises(pea.DataError):
            pea.parse_gruplac_products(html, GROUP_URL)

    def test_missing_year_reports_incomplete_candidate_without_inventing_it(self):
        html = GROUP + '<h2>Artículos publicados</h2>' + ARTICLE + \
            '<p>2.- Publicado en revista especializada: Sin fecha</p><p>Revista sin año</p>' \
            '<h2>Libros publicados</h2>'
        preview = pea.parse_web_page(html, GROUP_URL)
        self.assertEqual(len(preview.related_products), 1)
        self.assertTrue(any("Sin fecha" in item and "año" in item for item in preview.diagnostics))

    def test_bad_roster_row_preserves_following_member(self):
        html = GROUP + '<table><tr><th>Nombre</th><th>Vinculación</th><th>Horas</th>' \
            '<th>Inicio - Fin</th></tr><tr><td>1.- ' + 'x' * 100001 + \
            '</td><td>Integrante</td><td>10</td><td>2020/1 - Actual</td></tr>' \
            '<tr><td>2.- Ana Pérez</td><td>Integrante</td><td>10</td>' \
            '<td>2021/1 - Actual</td></tr></table><h2>Artículos publicados</h2>' + ARTICLE
        preview = pea.parse_web_page(html, GROUP_URL)
        self.assertEqual(len(preview.related_members), 1)
        self.assertEqual(preview.related_members[0][0]["nombre"], "Ana Pérez")
        self.assertEqual(len(preview.related_products), 1)
        self.assertTrue(any("Integrantes GrupLAC" in item for item in preview.diagnostics))

    def test_cvlac_partial_products_are_visible_and_importable(self):
        html = CV + '<p>Producción bibliográfica - Artículo - Publicado en revista especializada</p>' \
            '<blockquote><p>ANA PEREZ,</p><p>"Válido"</p><p>2025,</p></blockquote>' \
            '<p>Producción bibliográfica - Artículo - Publicado en revista especializada</p>' \
            '<blockquote><p>ANA PEREZ,</p><p>"Sin fecha"</p></blockquote>'
        preview = pea.parse_web_page(html, CV_URL)
        self.assertEqual(len(preview.related_products), 1)
        self.assertTrue(any("Productos CvLAC" in item and "Sin fecha" in item for item in preview.diagnostics))
        repo = pea.Repository()
        counts = pea.import_cvlac_preview(repo, preview)
        self.assertEqual((counts["investigadores"], counts["productos"], counts["autorias"]), (1, 1, 1))

    def test_invalid_cvlac_product_preserves_neighbors_and_direct_errors(self):
        def product(title):
            return '<p>Producción bibliográfica - Artículo - Publicado en revista especializada</p>' \
                '<blockquote><p>ANA PEREZ,</p><p>"' + title + '"</p><p>2025,</p></blockquote>'

        html = CV + product("Primero") + product("x" * 100001) + product("Posterior")
        preview = pea.parse_web_page(html, CV_URL)
        self.assertEqual([row["titulo"] for row in preview.related_products], ["Primero", "Posterior"])
        self.assertTrue(any("Productos CvLAC" in item and "tamaño" in item for item in preview.diagnostics))
        with self.assertRaises(pea.DataError):
            pea.parse_cvlac_products(html, CV_URL)

    def test_empty_category_before_name_is_absence_in_a_valid_profile(self):
        preview = pea.parse_web_page('<h1>Hoja de vida</h1><p>Categoría</p><p>Nombre</p><p>Ana Pérez</p>', CV_URL)
        self.assertEqual(preview.suggested_kind, "investigadores")
        self.assertEqual(preview.suggested_row["categoria"], "")
        self.assertEqual(preview.diagnostics, ())

    def test_gruplac_detail_scan_does_not_copy_the_remaining_section(self):
        class NoTailSlices(list):
            def __getitem__(self, index):
                if isinstance(index, slice) and index.start:
                    raise AssertionError("No debe copiar el resto de la sección para cada producto")
                return super().__getitem__(index)

        lines = NoTailSlices(["Artículos publicados"] + [item for number in range(100)
                             for item in (f"{number + 1}.- Artículo: Producto {number}", "2025,")]
                            + ["Libros publicados"])
        with patch.object(pea.VisibleText, "lines", return_value=lines):
            products = pea.parse_gruplac_products("", GROUP_URL)
        self.assertEqual(len(products), 100)

    def test_pdf_download_extracts_once_and_keeps_profile_failure(self):
        class Response:
            headers = Message()
            headers["Content-Type"] = "application/pdf"

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def geturl(self):
                return CV_URL

            def read(self, _limit):
                return b"%PDF-local-fixture"

        with patch.object(pea, "_validate_public_url", side_effect=lambda url: url), \
                patch.object(pea, "_build_public_opener") as opener, \
                patch.object(pea, "extract_pdf_text", return_value="Texto sin perfil") as extract:
            opener.return_value.open.return_value = Response()
            preview = pea.fetch_web_page(CV_URL)
        self.assertEqual(extract.call_count, 1)
        self.assertEqual(preview.format, "PDF de texto")
        self.assertTrue(any("Perfil Scienti PDF" in item for item in preview.diagnostics))

    def test_pdf_parser_reuses_supplied_text_and_keeps_old_signature(self):
        text = "Grupo PDF\nDatos básicos\nClasificación\nA1"
        with patch.object(pea, "extract_pdf_text", return_value=text) as extract:
            kind, row = pea.parse_scienti_pdf(Path("fixture.pdf"), GROUP_URL, text=text)
            self.assertEqual(extract.call_count, 0)
            self.assertEqual((kind, row["nombre"]), ("grupos", "Grupo PDF"))
            self.assertEqual(pea.parse_scienti_pdf(Path("fixture.pdf"), GROUP_URL)[1], row)
            self.assertEqual(extract.call_count, 1)

    def test_unexpected_group_page_is_not_importable_as_a_group(self):
        preview = pea.parse_web_page("<h1>Servicio temporalmente no disponible</h1>", GROUP_URL)
        self.assertIsNone(preview.suggested_kind)
        self.assertTrue(any("Datos básicos" in item for item in preview.diagnostics))

    def test_batch_import_cli_prints_extraction_warnings_and_redacts_urls(self):
        spec = importlib.util.spec_from_file_location("upc_import_diagnostics", ROOT / "scripts/import_upc_dataset.py")
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)
        url = CV_URL + "&token=NO-MOSTRAR#privado"
        partial = pea.parse_web_page(CV, url)._replace(diagnostics=("Productos CvLAC: falta un año válido",))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "datos.csv"
            output = io.StringIO()
            with patch.object(script, "GROUPS", []), patch.object(script, "fetch_web_page", return_value=partial), \
                    patch.object(sys, "argv", ["import_upc_dataset.py", "--data", str(path), "--cvlac", url]), \
                    patch("sys.stdout", output):
                script.main()
            self.assertEqual(len(pea.load_repository(path).rows("investigadores")), 1)
            self.assertIn("EXTRACCIÓN INCOMPLETA", output.getvalue())
            self.assertIn("falta un año válido", output.getvalue())
            self.assertNotIn("NO-MOSTRAR", output.getvalue())
            output = io.StringIO()
            failed = pea.parse_web_page("<h1>Servicio no disponible</h1>", url)
            with patch.object(script, "GROUPS", []), patch.object(script, "fetch_web_page", return_value=failed), \
                    patch.object(sys, "argv", ["import_upc_dataset.py", "--data", str(path), "--cvlac", url]), \
                    patch("sys.stdout", output):
                with self.assertRaises(SystemExit):
                    script.main()
            self.assertIn("cod_rh=42", output.getvalue())
            self.assertNotIn("NO-MOSTRAR", output.getvalue())
            self.assertNotIn("privado", output.getvalue())


class PopulateCategoryTests(unittest.TestCase):
    ROW = {"id": "I-42", "url": CV_URL}

    def test_resolve_distinguishes_found_absent_download_and_unexpected_profile(self):
        absent = pea.parse_web_page(CV, CV_URL)
        found = pea.parse_web_page(CV + '<p>Categoría</p><p>Investigador Junior</p>', CV_URL)
        with patch.object(populate, "fetch_web_page", return_value=found):
            result = populate.resolve(self.ROW)
        self.assertEqual((result.identifier, result.status, result.category), ("I-42", "found", "Investigador Junior"))
        with patch.object(populate, "fetch_web_page", return_value=absent):
            result = populate.resolve(self.ROW)
        self.assertEqual(result.status, "absent")
        self.assertIn("categoría", result.reason)
        with patch.object(populate, "fetch_web_page", side_effect=populate.pea["DataError"]("Descarga agotada")):
            result = populate.resolve(self.ROW)
        self.assertEqual(result.status, "error")
        self.assertIn("Descarga agotada", result.reason)
        with patch.object(populate, "fetch_web_page", return_value=pea.parse_web_page("<h1>Servicio caído</h1>", CV_URL)):
            result = populate.resolve(self.ROW)
        self.assertEqual(result.status, "error")
        self.assertIn("nombre", result.reason)

    def test_resolve_does_not_hide_unexpected_programming_failures(self):
        with patch.object(populate, "fetch_web_page", side_effect=RuntimeError("Error de programación")):
            with self.assertRaisesRegex(RuntimeError, "programación"):
                populate.resolve(self.ROW)

    def test_resolve_rejects_a_different_profile_and_preserves_partial_warnings(self):
        wrong = pea.parse_web_page(CV, CV_URL.replace("=42", "=99"))
        with patch.object(populate, "fetch_web_page", return_value=wrong):
            result = populate.resolve(self.ROW)
        self.assertEqual(result.status, "error")
        self.assertIn("código", result.reason)
        partial = pea.parse_web_page(CV + '<p>Categoría</p><p>Investigador Junior</p>', CV_URL)
        partial = partial._replace(diagnostics=("Productos CvLAC: año no identificado",))
        with patch.object(populate, "fetch_web_page", return_value=partial):
            result = populate.resolve(self.ROW)
        self.assertEqual((result.status, result.category), ("found", "Investigador Junior"))
        self.assertIn("año no identificado", result.reason)
        self.assertEqual(populate.resolve({"id": "I-SIN-URL", "url": ""}).status, "skipped")

    def test_main_keeps_separate_counters_and_reports_failure_ids(self):
        repo = pea.Repository()
        for code in ("1", "2", "3"):
            repo.create("investigadores", {"id": "I-" + code, "nombre": "Persona " + code,
                                           "codigo_cvlac": code, "url": CV_URL.replace("=42", "=" + code)})
        found = pea.parse_web_page(CV + '<p>Categoría</p><p>Investigador Junior</p>', CV_URL.replace("=42", "=1"))
        absent = pea.parse_web_page(CV, CV_URL.replace("=42", "=2"))
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(populate, "load_repository", return_value=repo), \
                patch.object(populate, "save_repository") as save, \
                patch.object(populate, "fetch_web_page", side_effect=[found, absent, populate.pea["DataError"]("Tiempo agotado")]), \
                patch.object(sys, "argv", ["populate_cvlac.py", "--data", str(Path(folder) / "datos.csv"), "--workers", "1"]), \
                patch("sys.stdout", output):
            with self.assertRaises(SystemExit) as exited:
                populate.main()
            self.assertEqual(exited.exception.code, 1)
        self.assertEqual(save.call_count, 1)
        self.assertIn("Actualizados: 1", output.getvalue())
        self.assertIn("sin categoría: 1", output.getvalue())
        self.assertIn("fallos: 1", output.getvalue())
        self.assertIn("I-3", output.getvalue())
        self.assertIn("Tiempo agotado", output.getvalue())


if __name__ == "__main__":
    unittest.main()

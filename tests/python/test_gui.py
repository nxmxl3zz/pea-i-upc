"""Regresiones de flujos Tkinter. Requieren DISPLAY; no alteran data/real."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / "src/python/Taller2_REMR.py"
SPEC = importlib.util.spec_from_file_location("pea_gui_tests", SOURCE)
pea = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pea)


class GuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            probe = subprocess.run([sys.executable, "-c", "import tkinter as tk; r=tk.Tk(); r.destroy()"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=5, text=True)
            if probe.returncode:
                raise RuntimeError((probe.stderr.strip() or "No se pudo abrir la sesión gráfica").splitlines()[-1])
        except Exception as exc:
            raise unittest.SkipTest(f"Sesión Tkinter no disponible: {exc}")
        cls.tk = tk

    def setUp(self):
        self.root = self.tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.repo = self.make_repository()
        if isinstance(self.repo, pea.CppRepository):
            self.addCleanup(self.repo.close)
        self.repo.create("productos", {"id": "P-old", "titulo": "Antes", "anio": "2010"})
        self.repo.create("productos", {"id": "P-new", "titulo": "Ahora", "anio": "2025"})
        self.repo.clear_history()
        self.app = pea.build_gui(self.root, self.repo, load_on_start=False)

    def make_repository(self):
        return pea.Repository()

    def wait_events(self, seconds=0.45):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.root.update()
            time.sleep(0.01)

    def dialog(self):
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, self.tk.Toplevel):
                    return child
                found = walk(child)
                if found is not None:
                    return found
        return walk(self.root)

    def test_custom_years_refresh_without_another_filter(self):
        self.app.period.set("Personalizado")
        self.app.refresh_dashboard()
        self.app.start_year.set("2010")
        self.app.end_year.set("2010")
        self.wait_events()
        self.assertEqual(self.app.current_stats["total"], 1)
        self.assertEqual(self.app.stats_table.get_children(), ("P-old",))
        self.app.start_year.set("2025")
        self.app.end_year.set("2010")
        self.wait_events()
        self.assertIn("Filtro inválido", self.app.filter_error.get())
        self.assertEqual(self.app.current_stats["total"], 1)
        self.app.clear_filters()
        self.assertEqual(self.app.current_stats["total"], 2)
        self.assertEqual(self.app.filter_error.get(), "")

    def test_status_is_visible(self):
        self.app.status.set("Guardado")
        self.assertEqual(str(self.app.status_label.cget("textvariable")), str(self.app.status))

    def test_charts_include_missing_values_and_zero_year_bins(self):
        self.repo.create("productos", {"id": "P-unknown", "titulo": "Sin fecha"})
        self.app.refresh()
        self.assertEqual(self.app.current_stats["total"], 3)
        self.assertEqual(self.app.card_values["undated"].get(), "1")
        self.assertTrue(self.app.year_canvas.find_withtag("year:2011"))
        texts = [self.app.type_canvas.itemcget(item, "text")
                 for item in self.app.type_canvas.find_all()
                 if self.app.type_canvas.type(item) == "text"]
        self.assertIn("Sin dato", texts)
        self.assertIn("3 · 100.0%", texts)

    def test_automatic_validation_drives_cards_rules_and_queue(self):
        self.app.refresh()
        self.assertEqual(self.app.card_values["rejected"].get(), "2")
        rules = [self.app.rules_canvas.itemcget(item, "text") for item in self.app.rules_canvas.find_all()
                 if self.app.rules_canvas.type(item) == "text"]
        self.assertIn(pea.VALIDATION_RULES["autor"], rules)
        self.app.validation.set("Rechazado")
        self.app.refresh_dashboard()
        self.assertEqual(self.app.current_stats["total"], 2)
        self.app.enqueue_rejected()
        self.assertEqual(self.repo.queue_size(), 2)
        motive = self.app.queue_table.item(self.app.queue_table.get_children()[0], "values")[2]
        self.assertIn(pea.VALIDATION_RULES["autor"], motive)
        self.app.enqueue_rejected()
        self.assertEqual(self.repo.queue_size(), 2)

    def test_empty_columns_hide_and_category_stays_in_groups(self):
        self.app.refresh()
        products = self.app.entity_tabs["productos"]
        self.assertNotIn("categoria", products.table["columns"])
        people = self.app.entity_tabs["investigadores"]
        self.assertNotIn("afiliacion", people.table.cget("displaycolumns"))
        self.assertIn("categoria", self.app.entity_tabs["grupos"].table["columns"])
        self.repo.create("investigadores", {"id": "I-af", "nombre": "Con afiliación", "afiliacion": "UPC"})
        self.app.refresh()
        self.assertIn("afiliacion", people.table.cget("displaycolumns"))

    def test_scope_statistics_and_table_share_filters(self):
        self.repo.create("grupos", {"id": "G1", "nombre": "Grupo uno"})
        self.repo.create("grupos_productos", {"grupo_id": "G1", "producto_id": "P-old"})
        self.app.refresh()
        self.app.view.set("Grupo")
        self.app._scope_changed()
        self.assertEqual(self.app.current_stats["total"], 1)
        self.assertEqual(self.app.stats_table.get_children(), ("P-old",))
        self.assertIn("Grupo uno", self.app.context.get())
        self.assertEqual(self.app.card_values["total"].get(), "1")

    def context_sample(self):
        self.repo.create("grupos", {"id": "G1", "nombre": "Primer grupo"})
        self.repo.create("grupos", {"id": "G10", "nombre": "Otro grupo"})
        self.repo.create("investigadores", {"id": "I1", "nombre": "Ana"})
        self.repo.create("membresias", {"grupo_id": "G1", "investigador_id": "I1", "rol": "Líder"})
        self.repo.create("autorias", {"producto_id": "P-old", "investigador_id": "I1"})
        self.repo.create("grupos_productos", {"grupo_id": "G1", "producto_id": "P-old"})
        self.repo.create("planes", {"id": "PL1", "grupo_id": "G1", "nombre": "Plan del primer grupo"})
        self.repo.create("planes", {"id": "PL10", "grupo_id": "G10", "nombre": "Plan ajeno"})
        self.app.refresh()

    def test_details_show_both_ends_and_only_plans_of_exact_group(self):
        self.context_sample()
        group = self.app.open_detail("grupos", "G1")
        self.assertEqual(set(group.link_tabs), {"membresias", "planes", "grupos_productos"})
        self.assertEqual(group.link_tabs["planes"].table.get_children(), ("PL1",))
        self.assertEqual(group.link_tabs["membresias"].table.item("I1", "values")[0], "Ana")
        self.assertEqual(group.statistics["total"], 1)
        person = self.app.open_detail("investigadores", "I1", group)
        self.assertEqual(person.link_tabs["membresias"].table.get_children(), ("G1",))
        self.assertEqual(person.link_tabs["autorias"].table.get_children(), ("P-old",))
        person.destroy()
        product = self.app.open_detail("productos", "P-old", group)
        self.assertEqual(product.link_tabs["autorias"].table.get_children(), ("I1",))
        self.assertEqual(product.link_tabs["grupos_productos"].table.get_children(), ("G1",))
        product.destroy()
        group.show_statistics()
        self.assertEqual(self.app.scope_id.get(), "G1")
        self.assertEqual(self.app.view.get(), "Grupo")

    def test_context_creation_and_inactive_links_remain_visible(self):
        self.context_sample()
        group = self.app.open_detail("grupos", "G1")
        def exercise():
            # El formulario está anidado dentro de la ficha, que también es Toplevel.
            dialog = next(child for child in group.winfo_children() if hasattr(child, "accept"))
            dialog.inputs["nombre"].insert(0, "Plan creado en contexto")
            dialog.accept()
        self.root.after(30, exercise)
        group.link_tabs["planes"].create()
        self.assertEqual(len(group.link_tabs["planes"].items), 2)
        created = next(row for row in self.repo.rows("planes") if row["nombre"] == "Plan creado en contexto")
        self.assertEqual(created["grupo_id"], "G1")
        members = group.link_tabs["membresias"]
        members.table.selection_set("I1")
        members.toggle()
        self.assertEqual(self.repo.get("membresias", ("G1", "I1"))["activo"], "0")
        self.assertIn("Inactivo", members.table.item("I1", "values"))
        members.search.set("Ana")
        members.refresh()
        self.assertEqual(members.table.get_children(), ("I1",))
        self.app.undo()
        self.assertEqual(self.repo.get("membresias", ("G1", "I1"))["activo"], "1")
        group.destroy()

    def test_relationship_search_resolves_names(self):
        self.context_sample()
        tab = self.app.relation_tabs["membresias"]
        tab.search.set("Ana")
        tab.refresh()
        self.assertEqual(len(tab.table.get_children()), 1)
        values = tab.table.item(tab.table.get_children()[0], "values")
        self.assertIn("Ana", values[1])

    def test_older_years_are_grouped_without_losing_products(self):
        cutoff = pea.date.today().year - 20
        self.repo.create("productos", {"id": "P-cutoff", "titulo": "En el corte", "anio": str(cutoff)})
        self.repo.create("productos", {"id": "P-older", "titulo": "Anterior", "anio": "1990"})
        self.app.refresh()
        canvas = self.app.year_canvas
        older = canvas.find_withtag(f"older:{cutoff}")
        self.assertEqual(len(older), 1)
        self.assertIn("count:2", canvas.gettags(older[0]))
        self.assertFalse(canvas.find_withtag("year:1990"))
        self.assertFalse(canvas.find_withtag(f"year:{cutoff}"))
        self.assertEqual(self.app.current_stats["total"], 4)
        self.assertLessEqual(len(canvas.find_withtag("bin")), 22)
        self.app.period.set("Personalizado")
        self.app.start_year.set("1990")
        self.app.end_year.set("1990")
        self.app.refresh_dashboard()
        self.assertEqual(self.app.current_stats["total"], 1)
        self.assertIn("count:1", canvas.gettags(canvas.find_withtag(f"older:{cutoff}")[0]))

    def test_product_opens_complete_detail_without_changing_list(self):
        self.context_sample()
        before = self.app.entity_tabs["productos"].table.get_children()
        self.app.stats_table.selection_set("P-old")
        self.app._open_product(type("Event", (), {"num": None})())
        detail = next(iter(self.app.details))
        self.assertEqual(detail.kind, "productos")
        self.assertIn("Antes", detail.info.get("1.0", "end"))
        self.assertEqual(detail.link_tabs["autorias"].table.get_children(), ("I1",))
        self.assertEqual(detail.link_tabs["grupos_productos"].table.get_children(), ("G1",))
        self.assertEqual(self.app.active_page, "dashboard")
        self.assertEqual(self.app.entity_tabs["productos"].search.get(), "")
        self.assertEqual(self.app.entity_tabs["productos"].table.get_children(), before)
        detail.destroy()

    def test_single_click_opens_product_detail(self):
        self.context_sample()
        self.root.deiconify()
        self.root.update()
        self.app.dashboard_page.scroll_canvas.yview_moveto(1)
        self.root.update()
        table = self.app.stats_table
        x, y, width, height = table.bbox("P-old")
        table.event_generate("<ButtonPress-1>", x=x + 10, y=y + height // 2)
        table.event_generate("<ButtonRelease-1>", x=x + 10, y=y + height // 2)
        self.root.update()
        self.assertEqual(len(self.app.details), 1)
        detail = next(iter(self.app.details))
        self.assertEqual(detail.key, "P-old")
        self.assertEqual(detail.kind, "productos")
        detail.destroy()

    def test_save_copy_and_reopen_preserve_links_queue_and_history(self):
        self.context_sample()
        self.repo.enqueue_review("P-old", "Verificar fuente")
        with tempfile.TemporaryDirectory() as folder:
            with patch("tkinter.filedialog.askdirectory", return_value=folder):
                self.assertTrue(self.app.save())
            self.assertFalse(self.app.repo.dirty)
            self.app.repo.update("productos", "P-old", {"titulo": "Cambio sin guardar"})
            self.app._load(Path(folder))
            self.assertEqual(self.app.repo.get("productos", "P-old")["titulo"], "Antes")
            self.assertIsNotNone(self.app.repo.get("autorias", ("P-old", "I1")))
            self.assertEqual(self.app.repo.queue_front()["producto_id"], "P-old")
            self.assertGreater(self.app.repo.history_size(), 0)
            self.app.undo()
            self.assertEqual(self.app.repo.queue_size(), 0)

    def test_review_validates_observation_and_preserves_fifo_and_undo(self):
        self.repo.enqueue_review("P-new", "Primero")
        self.repo.enqueue_review("P-old", "Segundo")
        self.app.refresh()
        observed = []
        def exercise():
            dialog = self.dialog()
            observed.append(dialog.state_text.get())
            dialog.accept()
            observed.append((dialog.winfo_exists(), dialog.error.get()))
            dialog.observation.insert("1.0", "Comprobado en fuente pública")
            dialog.accept()
        self.root.after(30, exercise)
        self.app.process_queue()
        self.assertIn(pea.VALIDATION_RULES["autor"], observed[0])
        self.assertEqual(observed[1][0], 1)
        self.assertTrue(observed[1][1])
        self.assertEqual(self.repo.get("productos", "P-new")["observacion"], "Comprobado en fuente pública")
        self.assertEqual(self.repo.get("productos", "P-new")["validacion"], "rechazado")
        self.assertEqual(self.repo.queue_front()["producto_id"], "P-old")
        self.app.undo()
        self.assertEqual(self.repo.get("productos", "P-new")["observacion"], "")
        self.assertEqual(self.repo.queue_front()["producto_id"], "P-new")
        self.assertEqual(self.repo.queue_size(), 2)

    def test_csv_type_is_detected_from_headers_and_selected_visually(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "archivo.csv"
            row = pea.clean_row("grupos", {"id": "G-import", "nombre": "Grupo importado"})
            pea._csv_write(path, pea.ENTITY_FIELDS["grupos"], [row])
            selected = []
            def exercise():
                dialog = self.dialog()
                selected.append(dialog.value.get())
                dialog.accept()
            self.root.after(30, exercise)
            with patch("tkinter.messagebox.askyesno", return_value=True), patch("tkinter.messagebox.showinfo"):
                self.app.import_csv_path(path)
            self.assertEqual(selected, ["Grupos"])
            self.assertEqual(self.repo.get("grupos", "G-import")["nombre"], "Grupo importado")

    def test_active_filter_finds_records_and_shows_readable_state(self):
        self.repo.toggle("productos", "P-old")
        self.app.refresh()
        tab = self.app.entity_tabs["productos"]
        tab.state_filter.set("Inactivos")
        tab.refresh()
        self.assertEqual(tab.table.get_children(), ("P-old",))
        self.assertIn("Inactivo", tab.table.item("P-old", "values"))

    def test_invalid_form_keeps_values_and_domain_error_keeps_dialog(self):
        assertions = []
        def exercise():
            dialog = self.dialog()
            try:
                dialog.inputs["titulo"].insert(0, "Valor conservado")
                dialog.inputs["anio"].insert(0, "incorrecto")
                dialog.accept()
                assertions.append((dialog.winfo_exists(), dialog.inputs["titulo"].get(), dialog.error.get()))
                dialog.inputs["anio"].delete(0, "end")
                dialog.inputs["anio"].insert(0, "2025")
                dialog.inputs["id"].delete(0, "end")
                dialog.inputs["id"].insert(0, "P-new")
                dialog.accept()
                assertions.append((dialog.winfo_exists(), dialog.inputs["titulo"].get(), dialog.error.get()))
            finally:
                dialog.destroy()
        self.root.after(30, exercise)
        self.assertFalse(self.app.edit_record("productos"))
        self.assertEqual(len(assertions), 2)
        self.assertEqual(assertions[0][:2], (1, "Valor conservado"))
        self.assertIn("Año inválido", assertions[0][2])
        self.assertEqual(assertions[1][:2], (1, "Valor conservado"))
        self.assertIn("ID duplicado", assertions[1][2])
        self.assertEqual(len(self.repo.rows("productos")), 2)

    def test_picker_reaches_records_beyond_first_page_by_name(self):
        for index in range(125):
            values = {"id": f"I{index:03}", "nombre": f"Persona {index:03}"}
            if isinstance(self.repo, pea.Repository):
                self.repo.create("investigadores", values, remember=False)
            else:
                self.repo.create("investigadores", values)
        def exercise():
            dialog = self.dialog()
            dialog.move(1)
            dialog.table.selection_set("I124")
            dialog.accept()
        self.root.after(30, exercise)
        self.assertEqual(self.app.pick_record("investigadores"), "I124")
        def search():
            dialog = self.dialog()
            dialog.search.set("Persona 124")
            dialog.refresh()
            dialog.table.selection_set("I124")
            dialog.accept()
        self.root.after(30, search)
        self.assertEqual(self.app.pick_record("investigadores"), "I124")

    def test_form_can_commit_and_then_undo(self):
        def exercise():
            dialog = self.dialog()
            dialog.inputs["titulo"].insert(0, "Producto nuevo")
            dialog.accept()
        self.root.after(30, exercise)
        self.assertTrue(self.app.edit_record("productos"))
        self.assertEqual(len(self.repo.rows("productos")), 3)
        self.app.undo()
        self.assertEqual(len(self.repo.rows("productos")), 2)


class CppGuiTest(GuiTest):
    @classmethod
    def setUpClass(cls):
        binary = os.environ.get("PEA_TEST_CPP")
        if not binary or not Path(binary).is_file():
            raise unittest.SkipTest("Defina PEA_TEST_CPP para verificar la interfaz con el motor C++")
        cls.binary = Path(binary)
        super().setUpClass()

    def make_repository(self):
        return pea.CppRepository(self.binary)


if __name__ == "__main__":
    unittest.main()

"""Regresiones de flujos Tkinter. Requieren DISPLAY; no alteran data/."""

import csv
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile
import unittest
from unittest.mock import patch

import fixture_f

SOURCE = Path(__file__).resolve().parents[2] / "src/python/Taller2_REMR.py"
SPEC = importlib.util.spec_from_file_location("pea_gui_tests", SOURCE)
pea = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pea)


def write_legacy_folder(path: Path, groups: list[dict[str, str]]) -> None:
    """Carpeta de la versión 3 (un CSV por tabla), anterior al archivo único."""
    path.mkdir()
    for name, fields in pea.DATA_SECTIONS.items():
        if name == "productos":
            fields = pea.PRODUCT_FIELDS_V4
        rows = {"manifest": [{"version": "3", "guardado": "2026-09-24T00:00:00"}], "grupos": groups}.get(name, [])
        with (path / f"{name}.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


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
        try:
            import customtkinter as ctk
        except ImportError:
            raise unittest.SkipTest("CustomTkinter no instalado: instale requirements.txt")
        cls.tk = tk
        cls.ctk = ctk

    def setUp(self):
        self.root = self.ctk.CTk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.repo = self.make_repository()
        if isinstance(self.repo, pea.CppRepository):
            self.addCleanup(self.repo.close)
        self.repo.create("productos", {"id": "P-old", "titulo": "Antes", "anio": "2010"})
        self.repo.create("productos", {"id": "P-new", "titulo": "Ahora", "anio": "2025"})
        self.repo.clear_history()
        self.app = pea.build_gui(self.root, self.repo, load_on_start=False)
        self.addCleanup(self.cancel_pending_timers)

    def cancel_pending_timers(self):
        """CustomTkinter deja ciclos de seguimiento en la ventana raíz; se cancelan antes de destruirla."""
        for job in self.root.tk.call("after", "info"):
            self.root.tk.call("after", "cancel", job)

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

    def summary_text(self, detail):
        """Texto de las etiquetas del Resumen de una ficha, en orden de creación."""
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, self.ctk.CTkLabel):
                    yield child.cget("text")
                yield from walk(child)
        return "\n".join(walk(detail.summary))

    def test_gui_has_no_tk_message_boxes(self):
        source = SOURCE.read_text(encoding="utf-8")
        gui = source[source.index("def build_gui"):source.index("def main")]
        self.assertNotRegex(gui, r"\b(messagebox|simpledialog)\.")

    def test_dialog_present_is_modal_and_escape_closes(self):
        Dialog = self.app.kit.Dialog
        outer = Dialog(self.root, "Exterior", 320, 160)
        outer.present(wait=False)
        self.assertTrue(outer.winfo_viewable())
        self.assertEqual(str(outer.grab_current()), str(outer))
        inner = Dialog(outer, "Interior", 300, 140)
        inner.present(wait=False)
        self.assertEqual(str(inner.grab_current()), str(inner))
        inner.focus_force()
        self.wait_events(0.1)
        inner.event_generate("<Escape>")
        self.wait_events(0.1)
        self.assertFalse(inner.winfo_exists())
        self.assertEqual(str(outer.grab_current()), str(outer))
        outer.close()
        self.assertFalse(outer.winfo_exists())

    def test_dialog_fits_its_content_from_the_first_one(self):
        heights = []
        def measure():
            dialog = self.app._last_dialog
            self.wait_events(0.15)
            heights.append((dialog.winfo_height(), dialog.winfo_reqheight()))
            dialog.buttons["cancel"].invoke()
        for _ in range(2):
            self.root.after(60, measure)
            self.app.confirm("Eliminar", "¿Eliminar el grupo?\nPuede deshacer este cambio.")
        for height, requested in heights:
            self.assertLessEqual(abs(height - requested), 4, heights)
        self.assertLess(heights[0][0], 260, heights)

    def test_confirm_returns_choice(self):
        answers = []
        for button in ("accept", "cancel"):
            self.root.after(80, lambda name=button: self.app._last_dialog.buttons[name].invoke())
            answers.append(self.app.confirm("Eliminar", "¿Eliminar el registro?"))
        self.root.after(80, lambda: self.app._last_dialog.close())
        answers.append(self.app.confirm("Eliminar", "¿Eliminar el registro?"))
        self.assertEqual(answers, [True, False, False])

    def test_ask_text_and_decide(self):
        def type_and_accept():
            dialog = self.app._last_dialog
            dialog.entry.insert(0, "https://example.org/ficha")
            dialog.buttons["accept"].invoke()
        self.root.after(80, type_and_accept)
        self.assertEqual(self.app.ask_text("Consultar URL", "Pegue una URL pública"), "https://example.org/ficha")
        self.root.after(80, lambda: self.app._last_dialog.buttons["cancel"].invoke())
        self.assertIsNone(self.app.ask_text("Consultar URL", "Pegue una URL pública"))
        self.root.after(80, lambda: self.app._last_dialog.buttons["no"].invoke())
        self.assertIs(self.app.decide("Cambios sin guardar", "¿Guardar cambios?"), False)
        self.root.after(80, lambda: self.app._last_dialog.close())
        self.assertIsNone(self.app.decide("Cambios sin guardar", "¿Guardar cambios?"))

    def test_inform_shows_long_text_scrollable(self):
        text = "\n".join(f"Error {index}" for index in range(30))
        captured = []
        def capture():
            captured.append(self.app._last_dialog.text_widget.get("1.0", "end").strip())
            self.app._last_dialog.buttons["accept"].invoke()
        self.root.after(80, capture)
        self.app.inform("Resultado de importación", text)
        self.assertEqual(captured, [text])

    def test_closing_a_dialog_cancels_its_widget_timers(self):
        def close_long_notice():
            dialog = self.app._last_dialog
            owned = set(dialog.text_widget._tclCommands or ())
            dialog.buttons["accept"].invoke()
            pending = [self.root.tk.call("after", "info", job)[0] for job in self.root.tk.call("after", "info")]
            leftovers.extend(script for script in pending if any(name in str(script) for name in owned))
        leftovers = []
        self.root.after(80, close_long_notice)
        self.app.inform("Resultado", "\n".join(str(index) for index in range(30)))
        self.assertEqual(leftovers, [])

    def make_table(self, columns=("titulo", "anio", "validacion"), **options):
        # Ventana visible y no modal: con una captura modal, Tk no entrega movimientos sintéticos del puntero.
        host = self.ctk.CTkToplevel(self.root)
        try:
            host.wm_attributes("-type", "dialog")
        except self.tk.TclError:
            pass
        host.geometry("720x420")
        host.wait_visibility()
        self.addCleanup(lambda: host.winfo_exists() and host.destroy())
        table = self.app.kit.DataTable(host, columns, headings={name: name.capitalize() for name in columns},
                                       widths={"titulo": 240, "anio": 70, "validacion": 120},
                                       anchors={"anio": "e"}, **options)
        table.pack(fill="both", expand=True)
        self.wait_events(0.15)
        return table

    def test_table_treeview_subset(self):
        table = self.make_table()
        selected = []
        table.on_select(selected.append)
        for key, values in (("a", ("Uno", "2024", "Validado")), ("b", ("Dos", "2025", "Rechazado")),
                            ("c", ("Tres", "2026", "Validado"))):
            self.assertEqual(table.insert("", "end", iid=key, values=values, tags=("stripe",)), key)
        self.assertEqual(table.get_children(), ("a", "b", "c"))
        self.assertEqual(tuple(table.item("b", "values")), ("Dos", "2025", "Rechazado"))
        table.selection_set("b")
        self.assertEqual((table.selection(), selected), (("b",), ["b"]))
        self.assertEqual(table["columns"], ("titulo", "anio", "validacion"))
        table.configure(displaycolumns=("titulo",))
        self.assertEqual(tuple(table.cget("displaycolumns")), ("titulo",))
        table.heading("titulo", text="Nombre")
        self.assertEqual(table.heading("titulo")["text"], "Nombre")
        table.delete("b")
        self.assertEqual((table.get_children(), table.selection()), (("a", "c"), ()))
        with self.assertRaises(self.tk.TclError):
            table.insert("", "end", iid="a", values=("Repetido", "", ""))
        table.delete(*table.get_children())
        self.assertEqual(table.get_children(), ())

    def test_table_open_events(self):
        opened = []
        table = self.make_table()
        table.on_open(opened.append)
        for key in ("a", "b"):
            table.insert("", "end", iid=key, values=(key, "2025", "Validado"))
        table.click_row("a")
        self.assertEqual((opened, table.selection()), ([], ("a",)))
        table.click_row("a", double=True)
        table.selection_set("b")
        table.body.focus_force()
        self.wait_events(0.1)
        table.body.event_generate("<Return>")
        self.wait_events(0.1)
        self.assertEqual(opened, ["a", "b"])
        immediate = self.make_table(open_on_click=True)
        immediate.on_open(opened.append)
        immediate.insert("", "end", iid="z", values=("z", "2025", "Validado"))
        immediate.click_row("z")
        self.assertEqual(opened[-1], "z")

    def test_table_keyboard_moves_selection(self):
        table = self.make_table()
        for index in range(30):
            table.insert("", "end", iid=f"r{index}", values=(f"Fila {index}", "2025", "Validado"))
        table.selection_set("r0")
        table.body.focus_force()
        self.wait_events(0.1)
        for key, expected in (("<Down>", "r1"), ("<End>", "r29"), ("<Up>", "r28"), ("<Home>", "r0"), ("<Next>", None)):
            table.body.event_generate(key)
            self.wait_events(0.05)
            if expected:
                self.assertEqual(table.selection(), (expected,))
        self.assertNotEqual(table.selection(), ("r0",))
        self.assertTrue(table.bbox(table.selection()[0]))

    def test_long_text_is_ellipsized_with_tooltip(self):
        table = self.make_table()
        long_text = "X" * 300
        table.insert("", "end", iid="a", values=(long_text, "2024", "Validado"))
        self.wait_events(0.1)
        item = next(item for item in table.body.find_withtag("cell")
                    if table.body.itemcget(item, "text").startswith("X"))
        self.assertTrue(table.body.itemcget(item, "text").endswith("…"))
        left, _, right, _ = table.body.bbox(item)
        self.assertLessEqual(right - left, table.column_width("titulo"))
        x, y, _, height = table.bbox("a", "titulo")
        table.body.event_generate("<Motion>", x=x + 12, y=y + height // 2)
        self.wait_events(0.8)
        self.assertEqual(table.tooltip_label.cget("text"), long_text)
        table.body.event_generate("<Leave>")
        self.wait_events(0.1)
        self.assertIsNone(table.tooltip)

    def test_table_metrics_follow_widget_scaling(self):
        table = self.make_table()
        for key in ("a", "b"):
            table.insert("", "end", iid=key, values=(key, "2025", "Validado"))
        with patch.object(self.root, "report_callback_exception") as errors:
            try:
                self.ctk.set_widget_scaling(1.5)
                table.redraw()
                self.wait_events(0.15)
                self.assertEqual(table.bbox("b")[1] - table.bbox("a")[1], 51)
            finally:
                self.ctk.set_widget_scaling(1.0)
                self.wait_events(0.15)
            errors.assert_not_called()

    def test_table_refresh_is_fast(self):
        columns = tuple(f"c{index}" for index in range(7))
        table = self.make_table(columns)
        rows = [(f"r{index}", tuple(f"Valor {index}-{column}" for column in range(7))) for index in range(100)]
        timings = []
        for _ in range(5):
            start = time.perf_counter()
            table.delete(*table.get_children())
            for key, values in rows:
                table.insert("", "end", iid=key, values=values)
            table.update_idletasks()
            timings.append(time.perf_counter() - start)
        self.assertLess(sorted(timings)[2], 0.05, timings)

    def test_chip_columns_draw_pills(self):
        table = self.make_table(chips={"validacion": lambda value: "primary" if value == "Validado" else "rejected"})
        for key, state in (("a", "Validado"), ("b", "Rechazado"), ("c", "Validado")):
            table.insert("", "end", iid=key, values=(key, "2025", state))
        self.wait_events(0.1)
        self.assertEqual(len(table.body.find_withtag("chip")), 3)
        # En la fila seleccionada el chip se dibuja sobre la superficie para no perderse en el fondo verde.
        table.selection_set("a")
        fills = [table.body.itemcget(item, "fill") for item in table.body.find_withtag("chip")]
        self.assertIn(self.app.kit.color("surface"), fills)

    def test_table_empty_state_and_wheel(self):
        table = self.make_table()
        table.empty_text = "Sin registros. Cree uno nuevo o cambie la búsqueda."
        table.redraw()
        self.assertEqual([table.body.itemcget(item, "text") for item in table.body.find_withtag("empty")],
                         [table.empty_text])
        for index in range(100):
            table.insert("", "end", iid=f"r{index}", values=(f"Fila {index}", "2025", "Validado"))
        self.wait_events(0.1)
        self.assertEqual(table.body.find_withtag("empty"), ())
        before = table.body.yview()[0]
        table.body.event_generate("<Button-5>")
        self.wait_events(0.1)
        self.assertGreater(table.body.yview()[0], before)

    def test_appearance_switch_recolors_canvases(self):
        fixture_f.populate(self.repo)
        self.app.refresh()
        self.app.period.set("Personalizado")
        self.app.end_year.set("2026")
        self.app.view.set("Grupo")
        self.app._scope_changed("G1")
        table = self.make_table()
        table.insert("", "end", iid="a", values=("Uno", "2025", "Validado"))
        try:
            self.app.set_appearance("dark")
            self.wait_events(0.15)
            track = self.app.indicator_canvas.find_withtag("indicator:track")[0]
            self.assertEqual(self.app.indicator_canvas.itemcget(track, "fill"), pea.DARK_THEME["chart_track"])
            self.assertEqual(self.app.year_canvas.cget("bg"), pea.DARK_THEME["surface"])
            self.assertEqual(table.body.cget("bg"), pea.DARK_THEME["surface"])
            self.assertEqual(self.app.theme, "dark")
        finally:
            self.app.set_appearance("light")
            self.wait_events(0.1)
        self.assertEqual(self.app.year_canvas.cget("bg"), pea.LIGHT_THEME["surface"])

    def test_appearance_switch_after_closing_a_table_dialog(self):
        fixture_f.populate(self.repo)
        self.app.refresh()
        self.app.period.set("Personalizado")
        self.app.end_year.set("2026")
        self.app.view.set("Grupo")
        self.app._scope_changed("G1")
        detail = self.app.show_indicator_details()
        detail.close()
        try:
            self.app.set_appearance("dark")
        finally:
            self.app.set_appearance("light")
        self.assertNotIn(detail.table, self.app.canvases)

    def test_indicator_panel_shows_and_hides(self):
        fixture_f.populate(self.repo)
        result = self.repo.indicator("grupos", "G1", end=2026)
        opened = []
        panel = self.app.kit.IndicatorPanel(self.root, on_details=lambda: opened.append(True))
        panel.show(result, "Grupo uno")
        self.wait_events(0.1)
        self.assertEqual(panel.winfo_manager(), "pack")
        self.assertEqual((panel.value.get(), panel.entity.cget("text")), ("3,53", "Grupo uno"))
        self.assertEqual(len(panel.canvas.find_withtag("indicator:track")), 9)
        self.assertEqual(len(panel.canvas.find_withtag("indicator:fill")),
                         sum(1 for term in (*result["clases"], result["cohesion"], result["cooperacion"])
                             if term["aporte"] > 0))
        chips = [chip.cget("text") for chip in panel.chips]
        self.assertIn("Corte 2026", chips)
        self.assertIn("1 sin categoría", chips)
        self.assertIn("2 grupos activos", panel.note.get())
        panel.details_button.invoke()
        self.assertEqual(opened, [True])
        panel.show(None, "")
        self.assertEqual(panel.winfo_manager(), "")

    def test_pager_labels_and_bounds(self):
        moves = []
        pager = self.app.kit.Pager(self.root, moves.append)
        pager.show(0, 100, 6363)
        self.assertEqual(pager.label.cget("text"), "1–100 de 6.363")
        self.assertEqual((pager.previous.cget("state"), pager.next.cget("state")), ("disabled", "normal"))
        pager.next.invoke()
        self.assertEqual(moves, [1])
        pager.show(6300, 63, 6363)
        self.assertEqual((pager.previous.cget("state"), pager.next.cget("state")), ("normal", "disabled"))
        pager.show(0, 0, 0)
        self.assertEqual(pager.label.cget("text"), "Sin resultados")

    def test_kit_components_use_palette_tokens(self):
        kit = self.app.kit
        self.assertEqual(kit.T["primary"], (pea.LIGHT_THEME["primary"], pea.DARK_THEME["primary"]))
        card = kit.Card(self.root, title="Resumen", stripe="primary")
        self.assertEqual((card.cget("fg_color"), card.cget("border_color")), (kit.T["surface"], kit.T["line"]))
        chip = kit.Chip(self.root, "Validado", "primary")
        chip.set("Rechazado", "rejected")
        self.assertEqual((chip.cget("text"), chip.cget("text_color")), ("Rechazado", kit.T["rejected"]))
        value = self.ctk.StringVar(value="42")
        kpi = kit.Kpi(self.root, "Productos", "primary", value)
        self.assertEqual(str(kpi.value_label.cget("textvariable")), str(value))
        self.assertEqual(kit.button(self.root, "Guardar", lambda: None, variant="primary").cget("fg_color"), kit.T["button"])
        self.assertEqual(kit.button(self.root, "Eliminar", lambda: None, variant="danger").cget("fg_color"), kit.T["rejected"])
        self.assertEqual(kit.color("surface"), pea.LIGHT_THEME["surface"])

    def test_menu_button_dispatches_and_keeps_label(self):
        calls = []
        menu = self.app.kit.MenuButton(self.root, "Archivo", [("Guardar", lambda: calls.append("guardar")),
                                                              ("Salir", lambda: calls.append("salir"))])
        menu.choose("Guardar")
        self.assertEqual(calls, ["guardar"])
        self.assertEqual(menu.get(), "Archivo")

    def test_search_field_debounces_typing(self):
        seen = []
        variable = self.ctk.StringVar()
        field = self.app.kit.SearchField(self.root, variable, lambda: seen.append(variable.get()))
        self.assertEqual((variable.get(), field.get()), ("", ""))
        self.assertEqual(field.hint.winfo_manager(), "place")
        for text in ("a", "an", "ana"):
            variable.set(text)
        self.wait_events(0.45)
        self.assertEqual(seen, ["ana"])
        self.assertEqual(field.hint.winfo_manager(), "")

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

    def test_filters_are_segmented_controls(self):
        self.assertIsInstance(self.app.view_control, self.ctk.CTkSegmentedButton)
        self.assertIsInstance(self.app.validation_control, self.ctk.CTkSegmentedButton)
        self.assertEqual(str(self.app.view_control.cget("variable")), str(self.app.view))
        self.assertEqual(str(self.app.validation_control.cget("variable")), str(self.app.validation))
        self.app.view.set("Grupo")
        self.app.validation.set("Rechazado")
        self.assertEqual(self.app.view_control.get(), "Grupo")
        self.assertEqual(self.app.validation_control.get(), "Rechazado")
        self.assertEqual(self.app._stats_filter[0], "Todos")
        self.app.view_control.cget("command")("Grupo")
        self.assertEqual(self.app._stats_filter[0], "Grupo")
        self.assertEqual(self.app._stats_filter[-1], "rechazado")

    def test_dashboard_table_pages_and_filter_reset(self):
        self.assertIsInstance(self.app.stats_table, self.app.kit.DataTable)
        self.assertEqual(self.app.stats_table["columns"], ("titulo", "anio", "tipologia", "categoria", "validacion"))
        for index in range(101):
            self.repo.create("productos", {"id": f"PAGE-{index:03}", "titulo": f"Página {index}", "anio": "2020"})
        self.app.refresh()
        first = self.app.stats_table.get_children()
        self.assertEqual(len(first), pea.PAGE_SIZE)
        self.app.stats_next.invoke()
        self.assertEqual(self.app.stats_offset, pea.PAGE_SIZE)
        self.assertEqual(len(self.app.stats_table.get_children()), 3)
        self.assertFalse(set(first) & set(self.app.stats_table.get_children()))
        self.assertEqual(self.app.stats_next.cget("state"), "disabled")
        self.app.period.set("Personalizado")
        self.app.start_year.set("2010")
        self.app.end_year.set("2010")
        self.app.refresh_dashboard()
        self.assertEqual(self.app.stats_offset, 0)
        self.assertEqual(self.app.stats_table.get_children(), ("P-old",))
        self.assertEqual(self.app.stats_previous.cget("state"), "disabled")

    def test_graph_tabs_include_filtered_indicator(self):
        self.assertIsInstance(self.app.graph_tabs, self.ctk.CTkTabview)
        for title in ("Por año", "Tendencia", "Por tipología", "Por clase", "Por categoría", "Indicador",
                      "Por validación"):
            self.app.graph_tabs.set(title)
            self.assertEqual(self.app.graph_tabs.get(), title)
        with self.assertRaises(ValueError):
            self.app.graph_tabs.set("Reglas incumplidas")
        fixture_f.populate(self.repo)
        self.app.view.set("Grupo")
        self.app._scope_changed("G1")
        self.assertEqual(len(self.app.graph_indicator_canvas.find_withtag("indicator:track")), 9)
        radar = self.app.graph_profile_canvas.find_withtag("radar:value")
        self.assertEqual(len(radar), 1)
        self.assertEqual(len(self.app.graph_profile_canvas.coords(radar[0])), 18)
        gauge = self.app.graph_profile_canvas.find_withtag("gauge:value")
        result = self.repo.indicator("grupos", "G1")
        self.assertAlmostEqual(float(self.app.graph_profile_canvas.itemcget(gauge[0], "extent")),
                               -180 * result["indicador"] / 10, places=1)
        self.app.clear_filters()
        self.assertFalse(self.app.graph_indicator_canvas.find_withtag("indicator:track"))
        self.assertFalse(self.app.graph_profile_canvas.find_withtag("radar:value"))

    def chart_texts(self, canvas):
        return [canvas.itemcget(item, "text") for item in canvas.find_all() if canvas.type(item) == "text"]

    def test_charts_use_several_kinds(self):
        fixture_f.populate(self.repo)
        self.repo.update("productos", "P1", {"url": "https://example.org/p1", "fuente": "Prueba"})
        self.app.refresh()
        for name in ("trend_canvas", "class_canvas", "category_canvas", "validation_canvas",
                     "dashboard_class_canvas", "dashboard_category_canvas"):
            self.assertIsInstance(getattr(self.app, name), self.app.kit.ChartCanvas, name)
        trend = self.app.trend_canvas
        self.assertEqual(len(trend.find_withtag("trend:line")), 1)
        self.assertEqual(len(trend.find_withtag("trend:average")), 1)
        in_2025 = sum(row["anio"] == "2025" for row in self.repo.rows("productos"))
        self.assertIn(f"count:{in_2025}", trend.gettags(trend.find_withtag("year:2025")[0]))
        classes = self.app.class_canvas
        catalog = {row["codigo"]: row["clase"] for row in self.repo.catalog()}
        expected = {}
        for row in self.repo.rows("productos"):
            name = catalog.get(row["categoria"], "Sin categoría")
            expected[name] = expected.get(name, 0) + 1
        slices = {tag.split(":", 1)[1]: int(next(t for t in classes.gettags(item) if t.startswith("count:"))[6:])
                  for item in classes.find_withtag("donut:slice")
                  for tag in classes.gettags(item) if tag.startswith("slice:")}
        self.assertEqual(slices, expected)
        self.assertIn("10", self.chart_texts(classes))
        cells = self.app.category_canvas.find_withtag("treemap:cell")
        self.assertEqual(len(cells), len({row["categoria"] or "Sin dato" for row in self.repo.rows("productos")}))
        self.assertIn("ART_D", self.chart_texts(self.app.category_canvas))
        self.assertEqual(len(self.app.validation_canvas.find_withtag("donut:slice")), 2)
        self.assertTrue(self.app.dashboard_class_canvas.find_withtag("donut:slice"))
        self.assertTrue(self.app.dashboard_category_canvas.find_withtag("treemap:cell"))
        self.assertTrue(self.app.dashboard_year_canvas.find_withtag("bin"))
        self.assertTrue(self.app.dashboard_type_canvas.find_withtag("bar"))

    def test_dashboard_note_lists_only_rejection_causes(self):
        for key in ("P-old", "P-new"):
            self.repo.delete("productos", key)
        for group in ("G1", "G2"):
            self.repo.create("grupos", {"id": group, "nombre": group})
        for person in ("I1", "I2", "I3"):
            self.repo.create("investigadores", {"id": person, "nombre": person})
        self.repo.create("productos", {"id": "V1", "titulo": "Validado", "anio": "2024", "tipologia": "Artículo",
                                       "url": "https://example.org/v1", "fuente": "Prueba"})
        self.repo.create("grupos_productos", {"grupo_id": "G1", "producto_id": "V1"})
        self.app.refresh()
        self.assertEqual(self.app.card_values["rejected"].get(), "0")
        self.assertEqual(self.app.note.get(), "")
        self.assertEqual(self.app.note_label.winfo_manager(), "")
        self.assertEqual([chip.cget("text") for chip in self.app.institution_chips],
                         ["2 grupos activos", "3 investigadores activos"])

    def test_indicator_panel_draws_gauge(self):
        fixture_f.populate(self.repo)
        self.app.refresh()
        self.app.view.set("Grupo")
        self.app._scope_changed("G1")
        gauge = self.app.indicator_panel.gauge
        self.assertIsInstance(gauge, self.app.kit.ChartCanvas)
        value = self.app.indicator_panel.result["indicador"]
        self.assertAlmostEqual(float(gauge.itemcget(gauge.find_withtag("gauge:value")[0], "extent")),
                               -180 * value / 10, places=1)
        self.assertIn(self.app.indicator_value.get(), self.chart_texts(gauge))

    def test_status_is_visible(self):
        self.app.status.set("Guardado")
        self.assertEqual(str(self.app.status_label.cget("textvariable")), str(self.app.status))

    def test_navigation_marks_active_page(self):
        self.assertEqual(set(self.app.pages), {"dashboard", "graphs", "grupos", "investigadores", "productos",
                                               "planes", "relaciones", "modelo", "cola"})
        self.app.nav_buttons["productos"].invoke()
        self.assertEqual(self.app.active_page, "productos")
        for page, control in self.app.nav_buttons.items():
            self.assertIsInstance(control, self.ctk.CTkButton)
            self.assertEqual(control.cget("fg_color"), self.app.kit.T["sidebar_hover"]
                             if page == "productos" else "transparent")
            self.assertEqual(control.cget("font").cget("weight"), "bold" if page == "productos" else "normal")
        self.assertEqual(self.root.tk.call("winfo", "children", self.app.content)[-1],
                         str(self.app.pages["productos"]))
        self.app.nav_buttons["modelo"].invoke()
        self.assertEqual(self.app.active_page, "modelo")

    def test_header_menu_dispatches_actions(self):
        self.assertEqual(set(self.app.menus), {"archivo", "importar", "editar", "ayuda"})
        with patch.object(self.app, "save_as") as save:
            self.app.menus["archivo"].choose("Guardar como...")
        save.assert_called_once_with()
        self.assertEqual(self.app.menus["archivo"].get(), "Archivo")
        with patch.object(self.app, "import_url") as fetch:
            self.app.menus["importar"].choose("URL pública...")
        fetch.assert_called_once_with()

    def test_queue_badge_counts(self):
        self.assertEqual(self.app.queue_badge.winfo_manager(), "")
        self.app.enqueue_rejected()
        self.assertEqual(self.repo.queue_size(), 2)
        self.assertEqual(self.app.queue_badge.cget("text"), "2")
        self.assertTrue(self.app.queue_badge.winfo_manager())
        self.app.undo()
        self.assertEqual(self.repo.queue_size(), 0)
        self.assertEqual(self.app.queue_badge.winfo_manager(), "")

    def test_shell_controls_and_sidebar_toggle(self):
        for control in (self.app.sidebar, self.app.header, self.app.content):
            self.assertIsInstance(control, self.ctk.CTkFrame)
        self.assertIsInstance(self.app.status_label, self.ctk.CTkLabel)
        self.assertIsInstance(self.app.save_button, self.ctk.CTkButton)
        self.assertIsInstance(self.app.theme_button, self.ctk.CTkSwitch)
        self.assertFalse(self.root.cget("menu"))
        self.app.burger.invoke()
        self.assertEqual(self.app.sidebar.winfo_manager(), "")
        self.assertFalse(self.app.menu_expanded)
        self.app.burger.invoke()
        self.assertEqual(self.app.sidebar.winfo_manager(), "pack")
        self.assertTrue(self.app.menu_expanded)
        try:
            self.app.theme_button.toggle()
            self.assertEqual(self.app.theme, "dark")
        finally:
            self.app.set_appearance("light")

    def test_brand_in_header_and_file_state_in_status_bar(self):
        def inside(widget, container):
            return str(widget).startswith(str(container) + ".")
        def texts(widget):
            for child in widget.winfo_children():
                if isinstance(child, self.ctk.CTkLabel):
                    yield child.cget("text")
                yield from texts(child)
        self.assertTrue(inside(self.app.brand, self.app.header))
        self.assertIn("Universidad Popular del Cesar", list(texts(self.app.header)))
        sidebar_texts = list(texts(self.app.sidebar))
        self.assertNotIn("PEA-i", sidebar_texts)
        self.assertFalse(any(text.startswith("Motor") for text in sidebar_texts))
        for widget in (self.app.workspace_label, self.app.workspace_state):
            self.assertTrue(inside(widget, self.app.status_bar))
        self.assertFalse(isinstance(self.app.sidebar_items, self.ctk.CTkScrollableFrame))

    def test_pagers_and_product_columns_fit_the_window(self):
        fixture_f.populate(self.repo)
        self.app.refresh()
        try:
            self.root.wm_attributes("-type", "dialog")
        except self.tk.TclError:
            pass
        self.root.geometry("1280x850")
        self.root.deiconify()
        self.app._show_page("productos")
        self.wait_events(0.15)
        self.assertEqual(self.app.entity_tabs["productos"].table.hbar.winfo_manager(), "")
        self.root.geometry("1024x680")
        for page in ("grupos", "relaciones", "cola"):
            self.app._show_page(page)
            self.wait_events(0.15)
            pager = {"grupos": lambda: self.app.entity_tabs["grupos"].pager,
                     "relaciones": lambda: self.app.relation_tabs["membresias"].pager,
                     "cola": lambda: self.app.queue_pager}[page]()
            self.assertTrue(pager.winfo_ismapped(), page)

    def test_header_shortcuts_dispatch_actions(self):
        self.root.deiconify()
        self.root.focus_force()
        self.wait_events(0.05)
        for sequence, method in (("<Control-s>", "save"), ("<Control-Shift-S>", "save_as"),
                                  ("<Control-n>", "new_workspace"), ("<Control-z>", "undo")):
            with self.subTest(shortcut=sequence), patch.object(self.app, method) as action:
                self.root.event_generate(sequence)
                self.root.update()
                action.assert_called_once_with()

    def test_startup_loading_overlay_finishes(self):
        self.app.initial_file = Path("datos.csv")
        seen = []
        def load(path):
            seen.append((path, self.app.loading.winfo_manager(), self.app.loading.progress.cget("mode")))
        with patch.object(self.app, "_load", side_effect=load):
            self.app.start_choice()
        self.assertEqual(seen, [(Path("datos.csv"), "place", "indeterminate")])
        self.assertEqual(self.app.loading.winfo_manager(), "")
        with patch.object(self.app, "_load", side_effect=pea.DataError("Error de carga")):
            with self.assertRaisesRegex(pea.DataError, "Error de carga"):
                self.app.start_choice()
        self.assertEqual(self.app.loading.winfo_manager(), "")

    def test_close_cancels_window_timers(self):
        timer = self.root.after(1000, lambda: None)
        with patch.object(self.app, "_may_discard", return_value=True), patch.object(self.root, "destroy") as destroy:
            self.app.close()
        destroy.assert_called_once_with()
        self.assertNotIn(timer, self.root.tk.call("after", "info"))

    def test_header_menus_fit_small_window_and_collapsed_sidebar(self):
        try:
            self.root.wm_attributes("-type", "dialog")
        except self.tk.TclError:
            pass
        self.root.geometry("1024x680")
        self.root.deiconify()
        self.wait_events(0.1)
        self.assertEqual(self.app.header_actions.grid_info()["row"], 1)
        right = self.app.header.winfo_rootx() + self.app.header.winfo_width()
        for control in (*self.app.menus.values(), self.app.save_button):
            self.assertLessEqual(control.winfo_rootx() + control.winfo_width(), right + 1)
        self.app.burger.invoke()
        self.wait_events(0.1)
        self.assertEqual(self.app.header_actions.grid_info()["row"], 0)

    def test_shell_preserves_page_and_chart_wheel_scrolling(self):
        self.root.geometry("1024x680")
        self.root.deiconify()
        self.wait_events(0.1)
        canvas = self.app.dashboard_page.scroll_canvas
        canvas.yview_moveto(0)
        self.app.context_label.event_generate("<Button-5>")
        self.root.update()
        self.assertGreater(canvas.yview()[0], 0)
        self.app.current_stats["por_tipologia"] = {f"Tipo {index}": 1 for index in range(70)}
        self.app._show_page("graphs")
        chart = self.app.type_canvas
        self.app.graph_tabs.set("Por tipología")
        self.wait_events(0.1)
        chart.yview_moveto(0)
        chart.event_generate("<Button-5>")
        self.root.update()
        self.assertGreater(chart.yview()[0], 0)

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
        self.assertIn("3 · 100,0 %", texts)

    def test_automatic_validation_drives_cards_rules_and_queue(self):
        self.app.refresh()
        self.assertEqual(self.app.card_values["rejected"].get(), "2")
        self.assertIn(pea.VALIDATION_RULES["vinculo"].lower(), self.app.note.get())
        self.assertTrue(self.app.note_label.winfo_manager())
        self.app.validation.set("Rechazado")
        self.app.refresh_dashboard()
        self.assertEqual(self.app.current_stats["total"], 2)
        self.app.enqueue_rejected()
        self.assertEqual(self.repo.queue_size(), 2)
        motive = self.app.queue_table.item(self.app.queue_table.get_children()[0], "values")[2]
        self.assertIn(pea.VALIDATION_RULES["vinculo"], motive)
        self.app.enqueue_rejected()
        self.assertEqual(self.repo.queue_size(), 2)

    def test_empty_columns_hide_and_product_category_appears_when_used(self):
        self.app.refresh()
        products = self.app.entity_tabs["productos"]
        self.assertNotIn("categoria", products.table.cget("displaycolumns"))
        self.repo.update("productos", "P-new", {"categoria": "ART_D"})
        self.app.refresh()
        self.assertIn("categoria", products.table.cget("displaycolumns"))
        people = self.app.entity_tabs["investigadores"]
        self.assertNotIn("afiliacion", people.table.cget("displaycolumns"))
        self.assertIn("categoria", self.app.entity_tabs["grupos"].table["columns"])
        self.repo.create("investigadores", {"id": "I-af", "nombre": "Con afiliación", "afiliacion": "UPC"})
        self.app.refresh()
        self.assertIn("afiliacion", people.table.cget("displaycolumns"))

    def test_dashboard_shows_group_indicator(self):
        fixture_f.populate(self.repo)
        self.app.refresh()
        self.app.view.set("Grupo")
        self.app._scope_changed("G1")
        self.app.period.set("Personalizado")
        self.app.end_year.set("2026")
        self.app.refresh_dashboard()
        self.assertIn("3,53", self.app.indicator_value.get())
        self.assertIn("2 grupos activos", self.app.indicator_note.get())
        self.assertEqual(self.app.indicator_panel.winfo_manager(), "pack")
        self.assertEqual(len(self.app.indicator_canvas.find_withtag("indicator:track")), 9)
        self.app.validation.set("Validado")
        self.app.refresh_dashboard()
        self.assertIn("0,00", self.app.indicator_value.get())
        self.app.clear_filters()
        self.assertEqual(self.app.indicator_panel.winfo_manager(), "")

    def test_dashboard_shows_researcher_indicator_and_subtypes(self):
        fixture_f.populate(self.repo)
        self.app.refresh()
        self.app.period.set("Personalizado")
        self.app.end_year.set("2026")
        self.app.view.set("Investigador")
        self.app._scope_changed("I1")
        self.assertIn("1,30", self.app.indicator_value.get())
        self.assertIn("investigadores activos", self.app.indicator_note.get())
        detail = self.app.show_indicator_details()
        self.assertEqual(len(detail.table.get_children()), 2)
        detail.destroy()

    def test_product_form_category_sets_manual_origin(self):
        fixture_f.populate(self.repo)
        self.app.refresh()
        def exercise():
            dialog = self.dialog()
            dialog.inputs["categoria"].set("ART_C — Artículo de investigación C")
            dialog.accept()
        self.root.after(30, exercise)
        self.assertTrue(self.app.edit_record("productos", "P2"))
        product = self.repo.get("productos", "P2")
        self.assertEqual((product["categoria"], product["categoria_origen"]), ("ART_C", "manual"))
        self.app.undo()
        self.assertEqual(self.repo.get("productos", "P2")["categoria"], "ART_D")

    def test_product_form_preserves_estimated_category_when_unchanged(self):
        self.repo.update("productos", "P-new", {"categoria": "ART_D", "categoria_origen": "estimada"})
        def exercise():
            self.dialog().accept()
        self.root.after(30, exercise)
        self.assertTrue(self.app.edit_record("productos", "P-new"))
        self.assertEqual(self.repo.get("productos", "P-new")["categoria_origen"], "estimada")

    def test_cvlac_preview_imports_researcher_products(self):
        fixture = Path(__file__).resolve().parents[1] / "fixtures/cvlac_productos.html"
        url = "https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000494917"
        preview = pea.parse_web_page(fixture.read_text(encoding="utf-8"), url)
        dialog = self.app._show_web_preview(preview)
        self.assertIsInstance(dialog, self.app.kit.Dialog)
        self.assertEqual({name: value.get() for name, value in dialog.detected.items()},
                         {"Productos": "2", "Autorías": "2"})
        self.assertEqual([chip.cget("text") for chip in dialog.category_chips], ["B 1", "FRH_B 1"])
        self.assertEqual(dialog.buttons["import"].cget("text"), "Importar datos detectados")
        self.root.after(30, lambda: self.dialog().accept())
        with patch.object(self.app, "show_import_result") as result, patch.object(self.app, "alert") as errors:
            dialog.buttons["import"].invoke()
        errors.assert_not_called()
        self.assertFalse(dialog.winfo_exists())
        counts, kind, key = result.call_args.args
        self.assertEqual((kind, key, counts["productos"]), ("investigadores", "I-0000494917", 2))
        self.assertIsNotNone(self.repo.get("investigadores", "I-0000494917"))
        self.assertEqual(self.repo.statistics("Investigador", "I-0000494917")["total"], 2)

    def test_category_distribution_and_product_summary(self):
        self.repo.update("productos", "P-new", {"categoria": "ART_D"})
        self.app.refresh()
        labels = [self.app.category_canvas.itemcget(item, "text") for item in self.app.category_canvas.find_all()
                  if self.app.category_canvas.type(item) == "text"]
        self.assertTrue(any(label.upper() == "ART_D" for label in labels))
        detail = self.app.open_detail("productos", "P-new")
        summary = self.summary_text(detail)
        self.assertIn("Valor en puntos", summary)
        self.assertIn("45", summary)
        detail.destroy()

    def test_estimated_category_is_flagged_in_summary(self):
        self.repo.update("productos", "P-old", {"categoria": "ART_D", "categoria_origen": "estimada"})
        self.repo.update("productos", "P-new", {"categoria": "ART_D", "categoria_origen": "manual"})
        hint = "Confirme o cambie la categoría con Editar ficha"
        for key, tone, flagged in (("P-old", "pending", True), ("P-new", "primary", False)):
            with self.subTest(product=key):
                detail = self.app.open_detail("productos", key)
                try:
                    self.assertEqual(detail.tabs.get(), "Resumen")
                    self.assertEqual(detail.category_chip.cget("text"), "ART_D")
                    self.assertEqual(detail.category_chip.cget("text_color"), self.app.kit.T[tone])
                    self.assertEqual(hint in self.summary_text(detail), flagged)
                finally:
                    detail.destroy()

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
        self.assertIsInstance(group, self.app.kit.Dialog)
        self.assertIsInstance(group.tabs, self.ctk.CTkTabview)
        self.assertIs(self.root.grab_current(), group)
        self.assertEqual(set(group.link_tabs), {"membresias", "planes", "grupos_productos"})
        self.assertIsInstance(group.link_tabs["membresias"].table, self.app.kit.DataTable)
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

    def test_context_tab_filters_active_links_and_follows_selection(self):
        self.context_sample()
        self.repo.create("investigadores", {"id": "I2", "nombre": "Beto"})
        self.repo.create("membresias", {"grupo_id": "G1", "investigador_id": "I2", "activo": "0"})
        group = self.app.open_detail("grupos", "G1")
        try:
            members = group.link_tabs["membresias"]
            self.assertIsInstance(members.state_control, self.ctk.CTkSegmentedButton)
            self.assertEqual(str(members.state_control.cget("variable")), str(members.state_filter))
            self.assertEqual(set(members.table.get_children()), {"I1", "I2"})
            self.assertTrue(all(control.cget("state") == "disabled" for control in members.selection_buttons))
            members.table.selection_set("I2")
            self.assertTrue(all(control.cget("state") == "normal" for control in members.selection_buttons))
            self.assertEqual(members.toggle_button.cget("text"), "Activar")
            members.state_filter.set("Activos")
            members.refresh()
            self.assertEqual(members.table.get_children(), ("I1",))
            self.assertTrue(all(control.cget("state") == "disabled" for control in members.selection_buttons))
            members.search.set("Beto")
            members.refresh()
            self.assertEqual(members.table.get_children(), ())
        finally:
            group.destroy()

    def test_detail_indicator_tab_for_group(self):
        fixture_f.populate(self.repo)
        self.app.refresh()
        year = pea.date.today().year
        detail = self.app.open_detail("grupos", "G1", tab="Indicador")
        try:
            self.assertEqual(detail.tabs.get(), "Indicador")
            self.assertEqual(detail.indicator_window.get(), "Completa")
            self.assertEqual(detail.indicator_panel.result, self.repo.indicator("grupos", "G1"))
            detail.indicator_window.set("Últimos 2 años")
            detail.refresh_indicator()
            expected = self.repo.indicator("grupos", "G1", start=year - 1, end=year)
            self.assertNotEqual(expected["indicador"], self.repo.indicator("grupos", "G1")["indicador"])
            self.assertEqual(detail.indicator_panel.result, expected)
            self.assertEqual(detail.indicator_panel.value.get(), f"{expected['indicador']:.2f}".replace(".", ","))
            self.assertEqual(len(detail.indicator_panel.canvas.find_withtag("indicator:track")), 9)
            subtypes = detail.indicator_panel.details_button.invoke()
            self.assertEqual(len(subtypes.table.get_children()), len(expected["subtipos"]))
            subtypes.close()
            self.assertIs(self.root.grab_current(), detail)
        finally:
            detail.destroy()
        self.repo.toggle("grupos", "G2")
        inactive = self.app.open_detail("grupos", "G2", tab="Indicador")
        try:
            self.assertEqual(inactive.indicator_panel.winfo_manager(), "")
            self.assertIn("activos", inactive.indicator_message.cget("text"))
        finally:
            inactive.destroy()
        product = self.app.open_detail("productos", "P1", tab="Indicador")
        self.assertIsNone(product.indicator_panel)
        self.assertEqual(product.tabs.get(), "Resumen")
        product.destroy()

    def test_queue_page_shows_front_card_and_opens_products(self):
        self.assertIsInstance(self.app.queue_table, self.app.kit.DataTable)
        self.assertEqual(self.app.review_button.cget("state"), "disabled")
        self.assertEqual(self.app.queue_reason_chips, [])
        self.app.enqueue_rejected()
        front = self.repo.queue_front()
        self.assertIn(self.app.record("productos", front["producto_id"])["titulo"], self.app.queue_front_label.get())
        self.assertEqual([chip.cget("text") for chip in self.app.queue_reason_chips],
                         [pea.RULE_LABELS[code] for code in pea.auto_reason_codes(front["motivo"])])
        self.assertEqual(self.app.review_button.cget("state"), "normal")
        self.assertEqual(self.app.queue_table.cget("displaycolumns"), ("producto_id", "motivo", "creado"))
        self.app.queue_table.click_row(front["id"], double=True)
        detail = next(iter(self.app.details))
        self.assertEqual((detail.kind, detail.key), ("productos", front["producto_id"]))
        detail.destroy()

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
        self.assertIn("Antes", self.summary_text(detail))
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
        table.click_row("P-old")
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
            path = Path(folder) / "datos.csv"
            with patch("tkinter.filedialog.asksaveasfilename", return_value=str(path)):
                self.assertTrue(self.app.save())
            self.assertFalse(self.app.repo.dirty)
            self.assertEqual(self.app.data_file, path)
            self.assertEqual(self.app.save_button.cget("text"), "Guardar")
            self.assertEqual(self.app.workspace_state.cget("text"), "Guardado")
            self.app.repo.update("productos", "P-old", {"titulo": "Cambio sin guardar"})
            self.app.refresh()
            self.assertEqual(self.app.workspace_state.cget("text"), "Cambios sin guardar")
            self.app._load(path)
            self.assertEqual(self.app.data_file, path)
            self.assertIn("datos.csv", self.app.workspace.get())
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
            self.assertIsInstance(dialog, self.app.kit.Dialog)
            self.assertIsInstance(dialog.observation, self.ctk.CTkTextbox)
            self.assertEqual([chip.cget("text") for chip in dialog.reason_chips], ["Primero"])
            self.assertEqual(dialog.validation_chip.cget("text"), "Rechazado")
            observed.append(dialog.state_text.get())
            dialog.accept()
            observed.append((dialog.winfo_exists(), dialog.error.get()))
            dialog.observation.insert("1.0", "Comprobado en fuente pública")
            dialog.accept()
        self.root.after(30, exercise)
        self.app.process_queue()
        self.assertIn(pea.VALIDATION_RULES["vinculo"], observed[0])
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
            with patch.object(self.app, "confirm", return_value=True) as preview, patch.object(self.app, "inform"):
                self.app.import_csv_path(path)
            self.assertEqual(selected, ["Grupos"])
            self.assertEqual(self.repo.get("grupos", "G-import")["nombre"], "Grupo importado")
            self.assertIn("Aceptables: 1", preview.call_args.args[1])
            self.assertEqual((preview.call_args.kwargs["accept"], preview.call_args.kwargs["cancel"]),
                             ("Importar aceptables", "Cancelar"))

    def test_csv_import_is_saved_to_open_file(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder) / "datos.csv"
            with patch("tkinter.filedialog.asksaveasfilename", return_value=str(data)):
                self.assertTrue(self.app.save())
            source = Path(folder) / "archivo.csv"
            row = pea.clean_row("grupos", {"id": "G-import", "nombre": "Grupo importado"})
            pea._csv_write(source, pea.ENTITY_FIELDS["grupos"], [row])
            self.root.after(30, lambda: self.dialog().accept())
            with patch.object(self.app, "confirm", return_value=True), patch.object(self.app, "inform"):
                self.app.import_csv_path(source)
            self.assertFalse(self.app.repo.dirty)
            self.assertIn("datos.csv", self.app.status.get())
            self.assertEqual(pea.load_repository(data).get("grupos", "G-import")["nombre"], "Grupo importado")

    def test_import_without_file_stays_pending(self):
        self.assertIsNone(self.app.data_file)
        self.repo.create("grupos", {"id": "G-import", "nombre": "Grupo importado"})
        with patch("tkinter.filedialog.asksaveasfilename") as dialog:
            self.app._keep_import("Importación lista.")
        dialog.assert_not_called()
        self.assertTrue(self.app.repo.dirty)
        self.assertIn("Guarde", self.app.status.get())

    def test_url_dialog_examples_fill_entry(self):
        seen = []
        def exercise():
            dialog = self.dialog()
            try:
                self.assertIsInstance(dialog, self.app.kit.UrlDialog)
                for example in ("Ejemplo GrupLAC", "Ejemplo CvLAC"):
                    dialog.examples[example].invoke()
                    seen.append(dialog.entry.get())
            finally:
                dialog.close()
        self.root.after(30, exercise)
        self.assertIsNone(self.app.kit.UrlDialog(self.root, self.app).result)
        self.assertEqual(seen, [
            "https://scienti.minciencias.gov.co/gruplac/jsp/visualiza/visualizagr.jsp?nro=00000000002099",
            "https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000494917"])

    def test_url_import_consults_inside_dialog_and_opens_preview(self):
        fixture = Path(__file__).resolve().parents[1] / "fixtures/cvlac_productos.html"
        url = "https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000494917"
        preview = pea.parse_web_page(fixture.read_text(encoding="utf-8"), url)
        checks = []
        def retry():
            dialog = self.dialog()
            checks.append((dialog.winfo_exists(), dialog.error.get(), dialog.progress.winfo_manager()))
            dialog.consult.invoke()
        def exercise():
            dialog = self.dialog()
            dialog.entry.insert(0, url)
            dialog.consult.invoke()
            checks.append((dialog.progress.winfo_manager(), dialog.consult.cget("state")))
            self.root.after(400, retry)
        self.root.after(30, exercise)
        with patch.object(pea, "fetch_web_page", side_effect=[pea.DataError("Sin conexión"), preview]) as fetch:
            self.app.import_url()
        self.assertEqual(checks[0], ("pack", "disabled"))
        self.assertEqual(checks[1], (1, "Sin conexión", ""))
        self.assertEqual([call.args[0] for call in fetch.call_args_list], [url, url])
        shown = self.app._last_dialog
        try:
            self.assertEqual(shown.title(), "Vista previa de URL pública")
            self.assertEqual(shown.detected["Productos"].get(), "2")
        finally:
            shown.close()
        self.assertFalse(self.app._url_busy)

    def test_import_result_opens_indicator(self):
        url = "https://scienti.minciencias.gov.co/gruplac/jsp/visualiza/visualizagr.jsp?nro=123"
        html = """<h1>Grupo de prueba</h1><h2>Datos básicos</h2>
        <h2>Integrantes del grupo</h2><table>
        <tr><th>Nombre</th><th>Vinculación</th><th>Horas</th><th>Inicio - Fin</th></tr>
        <tr><td>1.- Ana Pérez</td><td>Investigador</td><td>20</td><td>2020/1 - Actual</td></tr>
        </table>
        <h2>Artículos publicados</h2>
        <p>1.- Publicado en revista especializada: Estudio verificable</p>
        <p>Colombia, Revista X, 2024 vol:2, DOI:10.1000/uno</p>
        <p>Autores: Ana Perez</p>"""
        preview = pea.parse_web_page(html, url)
        counts = pea.import_gruplac_preview(self.repo, preview)
        group_id = preview.suggested_row["id"]
        self.app.refresh()
        result = self.app.show_import_result(counts, "grupos", group_id)
        self.assertIsInstance(result, self.app.kit.Dialog)
        self.assertEqual(result.table.item("productos", "values"), ("Productos", "1"))
        self.assertEqual(result.table.item("investigadores", "values"), ("Investigadores", "1"))
        result.indicator_button.invoke()
        self.assertFalse(result.winfo_exists())
        detail = next(iter(self.app.details))
        try:
            self.assertEqual((detail.kind, detail.key, detail.tabs.get()), ("grupos", group_id, "Indicador"))
            self.assertEqual(detail.indicator_panel.result, self.repo.indicator("grupos", group_id))
        finally:
            detail.destroy()
        product = self.app.show_import_result(counts, "productos", "P-old")
        self.assertEqual(product.indicator_button.cget("state"), "disabled")
        product.close()

    def test_about_dialog_shows_engine_file_and_counts(self):
        self.repo.enqueue_review("P-old", "Verificar")
        self.app.refresh()
        for opener in (self.app._show_about, self.app._show_status):
            with self.subTest(opener=opener.__name__):
                dialog = opener()
                try:
                    self.assertIsInstance(dialog, self.app.kit.Dialog)
                    facts = dialog.facts
                    self.assertEqual(facts["Motor de datos"], self.app.backend_name)
                    self.assertEqual(facts["Archivo"], "Sin archivo (Guardar como crea uno)")
                    self.assertEqual((facts["Esquema de datos"], facts["Protocolo C++"]), ("5", "4"))
                    self.assertEqual((facts["Productos"], facts["Grupos"], facts["Cola de revisión"]), ("2", "0", "1"))
                finally:
                    dialog.close()

    def test_legacy_folder_save_asks_for_file(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "anterior"
            write_legacy_folder(folder, [{"id": "G-OLD", "nombre": "Grupo anterior"}])
            self.app._load(folder / "manifest.csv")
            self.assertIsNone(self.app.data_file)
            self.assertEqual(self.app.repo.get("grupos", "G-OLD")["nombre"], "Grupo anterior")
            before = sorted(item.name for item in folder.iterdir())
            target = Path(temp) / "convertido.csv"
            with patch("tkinter.filedialog.asksaveasfilename", return_value=str(target)) as dialog:
                self.assertTrue(self.app.save())
            dialog.assert_called_once()
            self.assertEqual(sorted(item.name for item in folder.iterdir()), before)
            self.assertEqual(self.app.data_file, target)
            self.assertIsNotNone(pea.load_repository(target).get("grupos", "G-OLD"))

    def test_corrupt_file_offers_previous_save(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "datos.csv"
            with patch("tkinter.filedialog.asksaveasfilename", return_value=str(path)):
                self.assertTrue(self.app.save())
            self.repo.update("productos", "P-old", {"titulo": "Segunda versión"})
            self.assertTrue(self.app.save())
            path.write_text("archivo dañado", encoding="utf-8")
            with patch.object(self.app, "confirm", return_value=True):
                self.app._load(path)
            self.assertIsNone(self.app.data_file)
            self.assertEqual(self.app.repo.get("productos", "P-old")["titulo"], "Antes")

    def test_active_filter_finds_records_and_shows_readable_state(self):
        self.repo.toggle("productos", "P-old")
        self.app.refresh()
        tab = self.app.entity_tabs["productos"]
        tab.state_filter.set("Inactivos")
        tab.refresh()
        self.assertEqual(tab.table.get_children(), ("P-old",))
        self.assertIn("Inactivo", tab.table.item("P-old", "values"))

    def test_selection_bar_follows_row_state(self):
        tab = self.app.entity_tabs["productos"]
        self.assertIsInstance(tab.table, self.app.kit.DataTable)
        self.assertIsInstance(tab.state_control, self.ctk.CTkSegmentedButton)
        self.assertEqual(str(tab.state_control.cget("variable")), str(tab.state_filter))
        self.assertTrue(all(control.cget("state") == "disabled" for control in tab.selection_buttons))
        self.repo.toggle("productos", "P-old")
        self.app.refresh()
        tab.table.selection_set("P-old")
        self.assertTrue(all(control.cget("state") == "normal" for control in tab.selection_buttons))
        self.assertEqual(tab.toggle_button.cget("text"), "Activar")
        tab.table.selection_set(())
        self.assertTrue(all(control.cget("state") == "disabled" for control in tab.selection_buttons))
        tab.table.selection_set("P-old")
        tab.toggle_button.invoke()
        self.assertEqual(self.repo.get("productos", "P-old")["activo"], "1")
        self.assertEqual(tab.toggle_button.cget("text"), "Desactivar")
        tab.search.set("Sin coincidencias")
        tab.refresh()
        self.assertTrue(all(control.cget("state") == "disabled" for control in tab.selection_buttons))

    def test_estimated_category_chip_uses_product_origin(self):
        self.repo.update("productos", "P-old", {"categoria": "ART_D", "categoria_origen": "estimada"})
        self.repo.update("productos", "P-new", {"categoria": "ART_D", "categoria_origen": "manual"})
        self.app.refresh()
        table = self.app.entity_tabs["productos"].table
        self.assertEqual(table.cell_tone("P-old", "categoria"), "pending")
        self.assertEqual(table.cell_tone("P-new", "categoria"), "primary")
        self.assertIn("Estimada por tipología", table.cell_tooltip("P-old", "categoria"))

    def test_populated_pages_follow_dpi_changes(self):
        for key in ("P-old", "P-new"):
            self.repo.delete("productos", key)
        fixture_f.populate(self.repo)
        self.app.refresh()
        try:
            self.root.wm_attributes("-type", "dialog")
        except self.tk.TclError:
            pass
        self.root.geometry("1024x680")
        self.root.deiconify()
        self.app._show_page("modelo")
        self.wait_events(0.05)
        with patch.object(self.root, "report_callback_exception") as errors:
            try:
                for factor in (1.25, 1.5):
                    self.ctk.set_widget_scaling(factor)
                    self.ctk.set_window_scaling(factor)
                    self.root.geometry("1024x680")
                    self.wait_events(0.1)
                    self.assertFalse(self.app.stats_table.hbar.winfo_manager())
                    self.assertEqual(len(self.app.model_table.get_children()), 169)
            finally:
                self.ctk.set_widget_scaling(1.0)
                self.ctk.set_window_scaling(1.0)
                self.wait_events(0.05)
            errors.assert_not_called()

    def test_category_picker_filters_by_class(self):
        checks = []
        def exercise():
            dialog = self.dialog()
            try:
                self.assertIsInstance(dialog, self.app.kit.Dialog)
                dialog.class_filter.set("DPC")
                dialog.refresh()
                checks.append(len(dialog.table.get_children()))
                dialog.class_filter.set("Todas")
                dialog.search.set("tesis")
                dialog.refresh()
                checks.append(set(dialog.table.get_children()))
                dialog.table.selection_set("TD_A")
                dialog.search.set("Sin coincidencias")
                dialog.refresh()
                self.assertEqual(dialog.choose.cget("state"), "disabled")
                dialog.search.set("tesis")
                dialog.refresh()
                dialog.table.selection_set("TD_A")
                dialog.accept()
            finally:
                if dialog.winfo_exists():
                    dialog.close()
        self.root.after(30, exercise)
        picker = self.app.kit.CategoryPicker(self.root, self.app)
        self.assertEqual(checks[0], 46)
        self.assertTrue({"TD_A", "TD_B"} <= checks[1])
        self.assertEqual(picker.result, "TD_A")

    def test_model_page_lists_catalog_and_formula(self):
        self.assertIsInstance(self.app.model_table, self.app.kit.DataTable)
        self.assertEqual(len(self.app.model_table.get_children()), 169)
        self.assertIn("3,7·Nc.Top", self.app.model_formula.cget("text"))
        self.assertIn("ln(n / periodo + 1)", self.app.model_definitions.cget("text"))

    def test_category_picker_clear_and_cancel_are_distinct(self):
        self.root.after(30, lambda: self.dialog().clear())
        self.assertEqual(self.app.kit.CategoryPicker(self.root, self.app, "ART_D").result, "")
        self.root.after(30, lambda: self.dialog().close())
        self.assertIsNone(self.app.kit.CategoryPicker(self.root, self.app, "ART_D").result)

    def test_nested_category_picker_returns_to_form(self):
        checks = []
        def exercise():
            form = self.dialog()
            try:
                def choose():
                    picker = self.app._last_dialog
                    picker.table.click_row("ART_C", double=True)
                self.root.after(30, choose)
                form.inputs["categoria"].select()
                checks.append((form.inputs["categoria"].get(), self.root.grab_current() is form))
                form.accept()
            finally:
                if form.winfo_exists():
                    form.close()
        self.root.after(30, exercise)
        with patch.object(self.root, "report_callback_exception") as errors:
            self.assertTrue(self.app.edit_record("productos", "P-new"))
        errors.assert_not_called()
        self.assertEqual(checks, [("ART_C", True)])
        self.assertEqual(self.repo.get("productos", "P-new")["categoria"], "ART_C")

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

    def test_all_record_forms_preserve_references_and_locked_keys(self):
        self.repo.create("grupos", {"id": "FORM-G", "nombre": "Grupo de formulario"})
        self.repo.create("investigadores", {"id": "FORM-I", "nombre": "Persona de formulario"})
        self.repo.create("planes", {"id": "FORM-L", "grupo_id": "FORM-G", "nombre": "Plan"})
        self.repo.create("membresias", {"grupo_id": "FORM-G", "investigador_id": "FORM-I"})
        self.repo.create("autorias", {"producto_id": "P-old", "investigador_id": "FORM-I"})
        self.repo.create("grupos_productos", {"grupo_id": "FORM-G", "producto_id": "P-old"})
        for kind, key in (("grupos", "FORM-G"), ("investigadores", "FORM-I"), ("productos", "P-old"),
                          ("planes", "FORM-L"), ("membresias", ("FORM-G", "FORM-I")),
                          ("autorias", ("P-old", "FORM-I")), ("grupos_productos", ("FORM-G", "P-old"))):
            before = self.repo.get(kind, key)
            checks = []
            def exercise():
                dialog = self.dialog()
                try:
                    self.assertIsInstance(dialog, self.app.kit.Dialog)
                    self.assertIsInstance(dialog.inputs["activo"], self.ctk.CTkSegmentedButton)
                    for field, control in dialog.inputs.items():
                        if field.endswith("_id"):
                            self.assertEqual(control.get(), before[field])
                            if kind in pea.RELATION_ENDS:
                                self.assertEqual(control.button.cget("state"), "disabled")
                        if field == "id":
                            self.assertEqual(control.cget("state"), "readonly")
                    dialog.accept()
                    checks.append(dialog.result is not None)
                finally:
                    if dialog.winfo_exists():
                        dialog.close()
            with self.subTest(kind=kind):
                self.root.after(30, exercise)
                self.assertTrue(self.app.edit_record(kind, key))
                self.assertEqual(checks, [True])
                self.assertEqual(self.repo.get(kind, key), before)


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

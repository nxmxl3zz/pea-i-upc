"""Regresiones de persistencia, importación y comunicación del bloque 1–6."""

import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pea_fixes", ROOT / "src/python/Taller2_REMR.py")
pea = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pea)


def profile(products=40):
    return pea.WebPreview(
        "https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=77",
        "HTML", "Perfil de prueba", (), {}, "investigadores",
        pea.clean_row("investigadores", {"id": "I-source", "nombre": "Ana Gómez", "codigo_cvlac": "77"}),
        related_products=tuple(pea.clean_row("productos", {
            "id": f"P-{i}", "titulo": f"Producto {i}", "anio": "2025",
            "doi": f"10.1234/fixes.{i}", "categoria": "ART_D", "categoria_origen": "estimada",
        }) for i in range(products)),
    )


class RepositoryFixes:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pea-fixes-test-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.repo = self.make_repository()

    def test_web_import_is_one_undo_and_preserves_previous_history(self):
        self.repo.create("grupos", {"id": "G-before", "nombre": "Anterior"})
        counts = pea.import_cvlac_preview(self.repo, profile())
        self.assertEqual((counts["productos"], counts["autorias"], counts["errors"]), (40, 40, []))
        self.assertEqual(self.repo.history_size(), 2)
        self.assertTrue(self.repo.undo())
        self.assertEqual(self.repo.page("productos", limit=0)["total"], 0)
        self.assertEqual(self.repo.page("autorias", limit=0)["total"], 0)
        self.assertEqual(self.repo.page("investigadores", limit=0)["total"], 0)
        self.assertIsNotNone(self.repo.get("grupos", "G-before"))
        self.assertTrue(self.repo.undo())
        self.assertIsNone(self.repo.get("grupos", "G-before"))

    def test_web_batch_roundtrips_between_engines(self):
        pea.import_cvlac_preview(self.repo, profile())
        path = self.folder / "batch.csv"
        if isinstance(self.repo, pea.CppRepository):
            self.repo.save(path)
        else:
            pea.save_repository(self.repo, path)
        saved = pea.load_repository(path)
        self.assertEqual(saved.history_size(), 1)
        self.assertTrue(saved.undo())
        self.assertEqual(sum(saved.page(kind, limit=0)["total"] for kind in pea.ALL_FIELDS), 0)
        if os.environ.get("PEA_TEST_CPP"):
            with self.subTest(reader="cpp"):
                native = pea.CppRepository(Path(os.environ["PEA_TEST_CPP"]))
                try:
                    native.load(path)
                    self.assertTrue(native.undo())
                    self.assertEqual(sum(native.page(kind, limit=0)["total"] for kind in pea.ALL_FIELDS), 0)
                finally:
                    native.close()

    def install_delta(self, changes):
        path = self.folder / "history.csv"
        if isinstance(self.repo, pea.CppRepository):
            self.repo.save(path)
            saved = pea.load_repository(path)
        else:
            saved = self.repo
        saved.history.clear()
        saved.history.push(json.dumps({"__undo": changes}, ensure_ascii=False, separators=(",", ":")))
        pea.save_repository(saved, path)
        if isinstance(self.repo, pea.CppRepository):
            self.repo.load(path)
        else:
            self.repo = pea.load_repository(path)

    def state(self):
        return ({kind: self.repo.rows(kind) for kind in pea.ALL_FIELDS},
                self.repo.queue_rows(), self.repo.dirty, self.repo.history_size())

    def test_invalid_delta_preserves_rows_queue_order_and_dirty_state(self):
        self.repo.create("investigadores", {"id": "I", "nombre": "Ana"})
        for i in range(3):
            self.repo.create("productos", {"id": f"P{i}", "titulo": f"Producto {i}"})
            self.repo.create("autorias", {"producto_id": f"P{i}", "investigador_id": "I"})
            self.repo.enqueue_review(f"P{i}", "Revisar")
        middle_job = self.repo.queue_rows()[1]["id"]
        self.install_delta([
            {"__op": "queue_remove", "__kind": "", "id": middle_job},
            {"__op": "delete", "__kind": "autorias", "producto_id": "P1", "investigador_id": "I"},
            {"__op": "delete", "__kind": "grupos", "id": "NO-EXISTE"},
        ])
        before = self.state()
        related = self.repo.related("autorias", "I", "right")
        with self.assertRaises(pea.DataError):
            self.repo.undo()
        self.assertEqual(self.state(), before)
        self.assertEqual(self.repo.related("autorias", "I", "right"), related)

    def test_delta_external_identity_uses_effective_previous_changes(self):
        self.repo.create("investigadores", {"id": "I1", "nombre": "Ana", "codigo_cvlac": "A"})
        self.repo.create("investigadores", {"id": "I2", "nombre": "Luis", "codigo_cvlac": "B"})
        first = self.repo.get("investigadores", "I1").copy()
        second = self.repo.get("investigadores", "I2").copy()
        self.install_delta([
            {**first, "codigo_cvlac": "C", "__op": "replace", "__kind": "investigadores"},
            {**second, "codigo_cvlac": "C", "__op": "replace", "__kind": "investigadores"},
        ])
        before = self.state()
        with self.assertRaises(pea.DataError):
            self.repo.undo()
        self.assertEqual(self.state(), before)
        self.install_delta([
            {**first, "codigo_cvlac": "", "__op": "replace", "__kind": "investigadores"},
            {**second, "codigo_cvlac": "A", "__op": "replace", "__kind": "investigadores"},
        ])
        self.assertTrue(self.repo.undo())
        self.assertEqual(self.repo.get("investigadores", "I2")["codigo_cvlac"], "A")

    def test_undo_keeps_products_with_invalid_doi_available_for_review(self):
        self.repo.create("productos", {"id": "P1", "titulo": "Uno", "doi": "https://doi.org/"})
        self.repo.create("productos", {"id": "P2", "titulo": "Dos"})
        self.repo.update("productos", "P1", {"observacion": "Cambio"})
        self.assertTrue(self.repo.undo())
        self.assertEqual(self.repo.get("productos", "P1")["observacion"], "")
        self.assertEqual(self.repo.get("productos", "P1")["validacion"], "rechazado")
        self.repo.update("productos", "P2", {"doi": "https://doi.org/"})
        self.assertIsNone(self.repo.find_external("productos", "https://doi.org/"))
        with self.repo.batch():
            self.repo.update("productos", "P1", {"observacion": "Uno"})
            self.repo.update("productos", "P2", {"observacion": "Dos"})
        self.assertTrue(self.repo.undo())

    def test_batch_keeps_valid_work_undoable_after_exception(self):
        with self.assertRaisesRegex(pea.DataError, "interrumpida"):
            with self.repo.batch():
                self.repo.create("grupos", {"id": "G", "nombre": "Grupo"})
                for blocked in (self.repo.undo, self.repo.clear_history):
                    with self.assertRaises(pea.DataError):
                        blocked()
                with self.assertRaises(pea.DataError):
                    if isinstance(self.repo, pea.CppRepository):
                        self.repo.save(self.folder / "forbidden.csv")
                    else:
                        pea.save_repository(self.repo, self.folder / "forbidden.csv")
                self.assertFalse((self.folder / "forbidden.csv").exists())
                raise pea.DataError("Importación interrumpida")
        self.assertEqual(self.repo.history_size(), 1)
        self.assertTrue(self.repo.undo())
        self.assertIsNone(self.repo.get("grupos", "G"))

    def test_partial_import_keeps_valid_rows_in_one_action(self):
        preview = profile(2)
        preview = preview._replace(related_products=(preview.related_products[0],
                                                    {**preview.related_products[1], "anio": "1800"}))
        counts = pea.import_cvlac_preview(self.repo, preview)
        self.assertEqual((counts["productos"], counts["autorias"], len(counts["errors"])), (1, 1, 1))
        self.assertEqual(self.repo.history_size(), 1)
        self.assertTrue(self.repo.undo())
        self.assertEqual(self.repo.page("investigadores", limit=0)["total"], 0)
        self.assertEqual(self.repo.page("productos", limit=0)["total"], 0)

    def test_cvlac_resolves_existing_person_and_doi(self):
        self.repo.create("investigadores", {"id": "I-manual", "nombre": "Antes", "codigo_cvlac": "77"})
        self.repo.create("productos", {"id": "P-manual", "titulo": "Producto 0", "anio": "2025",
                                      "doi": "https://doi.org/10.1234/FIXES.0", "categoria": "ART_A1"})
        self.repo.clear_history()
        counts = pea.import_cvlac_preview(self.repo, profile(1))
        self.assertEqual(counts["errors"], [])
        self.assertEqual(self.repo.page("investigadores", limit=0)["total"], 1)
        self.assertEqual(self.repo.page("productos", limit=0)["total"], 1)
        self.assertIsNotNone(self.repo.get("autorias", ("P-manual", "I-manual")))
        self.assertEqual(self.repo.get("productos", "P-manual")["categoria_origen"], "manual")
        self.assertEqual(self.repo.get("productos", "P-manual")["categoria"], "ART_A1")
        history = self.repo.history_size()
        repeated = pea.import_cvlac_preview(self.repo, profile(1))
        self.assertEqual((repeated["errors"], repeated["actualizados"], repeated["autorias"]), ([], 0, 0))
        self.assertEqual(self.repo.history_size(), history)
        self.assertTrue(self.repo.undo())
        self.assertEqual(self.repo.get("investigadores", "I-manual")["nombre"], "Antes")
        self.assertIsNone(self.repo.get("autorias", ("P-manual", "I-manual")))

    def test_gruplac_remaps_every_relation_to_canonical_ids(self):
        self.repo.create("grupos", {"id": "G-manual", "nombre": "Grupo anterior", "codigo_gruplac": "42"})
        self.repo.create("investigadores", {"id": "I-manual", "nombre": "Antes", "codigo_cvlac": "77"})
        self.repo.create("productos", {"id": "P-manual", "titulo": "Producto 0", "anio": "2025",
                                      "doi": "10.1234/fixes.0", "categoria": "ART_A1"})
        self.repo.clear_history()
        person = profile(1).suggested_row
        preview = profile(1)._replace(
            suggested_kind="grupos",
            suggested_row=pea.clean_row("grupos", {"id": "G-source", "nombre": "Grupo nuevo", "codigo_gruplac": "42"}),
            related_members=((person, {"grupo_id": "G-source", "investigador_id": "I-source", "rol": "Integrante"}),),
            related_plan={"id": "PL-source", "grupo_id": "G-source", "nombre": "Plan"},
            related_authorships=({"producto_id": "P-0", "investigador_id": "I-source"},),
        )
        counts = pea.import_gruplac_preview(self.repo, preview)
        self.assertEqual(counts["errors"], [])
        for kind in pea.ALL_FIELDS:
            self.assertEqual(self.repo.page(kind, limit=0)["total"], 1, kind)
        self.assertEqual(self.repo.get("planes", "PL-source")["grupo_id"], "G-manual")
        for kind, pair in (("membresias", ("G-manual", "I-manual")),
                           ("autorias", ("P-manual", "I-manual")),
                           ("grupos_productos", ("G-manual", "P-manual"))):
            self.assertIsNotNone(self.repo.get(kind, pair))
        self.assertTrue(self.repo.undo())
        self.assertEqual(self.repo.get("grupos", "G-manual")["nombre"], "Grupo anterior")
        self.assertEqual(self.repo.page("planes", limit=0)["total"], 0)

    def test_conflicting_source_id_does_not_overwrite_other_product(self):
        self.repo.create("productos", {"id": "P-0", "titulo": "Otro producto", "doi": "10.1234/other"})
        self.repo.create("productos", {"id": "P-canonical", "titulo": "Producto 0", "anio": "2025",
                                      "doi": "10.1234/fixes.0"})
        counts = pea.import_cvlac_preview(self.repo, profile(1))
        self.assertEqual(len(counts["errors"]), 1)
        self.assertEqual(self.repo.get("productos", "P-0")["titulo"], "Otro producto")
        self.assertEqual(self.repo.page("autorias", limit=0)["total"], 0)

    def test_unicode_and_multiple_word_search(self):
        self.repo.create("investigadores", {"id": "I", "nombre": "Ana Gómez Ñúñez Straße Σίσυφος"})
        for query in ("GÓMEZ", "ÑÚÑEZ", "STRASSE", "ΣΊΣΥΦΟΣ", "I ANA"):
            self.assertEqual(self.repo.page("investigadores", query=query)["total"], 1, query)

    def test_only_canonical_ascii_years_and_dates_are_accepted(self):
        for values in ({"anio": "2_025"}, {"anio": "+2025"}, {"anio": "٢٠٢٥"},
                       {"fecha": "20250312"}, {"fecha": "2025-W10-3"}):
            with self.subTest(values=values), self.assertRaises(pea.DataError):
                self.repo.create("productos", {"id": "P-bad", "titulo": "Prueba", **values})
        row = self.repo.create("productos", {"id": "P-good", "titulo": "Prueba", "fecha": "2025-03-12"})
        self.assertEqual(row["anio"], "2025")

    def test_author_order_and_field_limits_match_both_engines(self):
        self.repo.create("investigadores", {"id": "I", "nombre": "Ana"})
        self.repo.create("productos", {"id": "P", "titulo": "Producto"})
        for order in ("²", "١", "+1", "9223372036854775808", "0"):
            with self.subTest(order=order), self.assertRaises(pea.DataError):
                self.repo.create("autorias", {"producto_id": "P", "investigador_id": "I", "orden": order})
        self.repo.create("autorias", {"producto_id": "P", "investigador_id": "I", "orden": "0001"})
        with self.assertRaises(pea.DataError):
            self.repo.create("grupos", {"id": "G", "nombre": "ñ" * 50001})
        self.repo.create("grupos", {"id": "G", "nombre": "ñ" * 50000})

    def test_csv_rejects_duplicate_headers_and_unclosed_quotes_without_mutation(self):
        fields = pea.ALL_FIELDS["grupos"]
        path = self.folder / "bad.csv"
        with path.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow([*fields, "nombre"])
            values = {"id": "G", "nombre": "Original", "activo": "1"}
            writer.writerow([*[values.get(field, "") for field in fields], "Sobrescrito"])
        for mode in ("duplicate", "unclosed", "bare_quote", "blank_row"):
            if mode == "unclosed":
                path.write_text(",".join(fields) + "\n" + ",".join(["G", "Prueba", *([""] * (len(fields) - 3)), '"1']))
            elif mode == "bare_quote":
                path.write_text(",".join(fields) + "\n" + ",".join(["G", 'Una "cita"', *([""] * (len(fields) - 2))]) + "\n")
            elif mode == "blank_row":
                path.write_text(",".join(fields) + "\n\n")
            with self.subTest(mode=mode), self.assertRaises(pea.DataError):
                if isinstance(self.repo, pea.CppRepository):
                    self.repo.import_csv(path, "grupos")
                else:
                    pea.merge_csv(self.repo, path, "grupos")
            self.assertEqual(self.repo.page("grupos", limit=0)["total"], 0)
            self.assertEqual(self.repo.history_size(), 0)


class PythonFixes(RepositoryFixes, unittest.TestCase):
    def make_repository(self):
        return pea.Repository()

    def test_old_large_snapshot_can_be_reopened_and_undone(self):
        for i in range(500):
            self.repo.create("productos", {"id": f"P{i}", "titulo": "Título " * 40}, remember=False)
        self.repo.history.push(self.repo.snapshot())
        self.repo.update("productos", "P0", {"observacion": "Cambio"}, remember=False)
        path = self.folder / "legacy.csv"
        pea.save_repository(self.repo, path)
        saved = pea.load_repository(path)
        self.assertEqual(saved.get("productos", "P0")["observacion"], "Cambio")
        self.assertTrue(saved.undo())
        self.assertEqual(saved.get("productos", "P0")["observacion"], "")

    def test_edit_history_size_does_not_grow_with_unrelated_data(self):
        for i in range(500):
            self.repo.create("productos", {"id": f"P{i}", "titulo": "Título " * 40}, remember=False)
        self.repo.update("productos", "P0", {"observacion": "Cambio"})
        self.assertLess(len(self.repo.history.peek().encode()), 5000)
        self.assertTrue(self.repo.undo())
        self.assertEqual(self.repo.get("productos", "P0")["observacion"], "")

    def test_history_limit_rejects_edit_before_mutation(self):
        self.repo.create("productos", {"id": "P", "titulo": "Producto"}, remember=False)
        before = self.state()
        with patch.object(pea, "MAX_HISTORY_BYTES", 64), self.assertRaises(pea.DataError):
            self.repo.update("productos", "P", {"observacion": "Cambio"})
        self.assertEqual(self.state(), before)


@unittest.skipUnless(os.environ.get("PEA_TEST_CPP"), "Defina PEA_TEST_CPP para probar el motor C++")
class CppFixes(RepositoryFixes, unittest.TestCase):
    def make_repository(self):
        repo = pea.CppRepository(Path(os.environ["PEA_TEST_CPP"]))
        self.addCleanup(repo.close)
        return repo

    def test_large_cpp_batch_can_be_loaded_by_python(self):
        source = self.folder / "groups.csv"
        with source.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=pea.ALL_FIELDS["grupos"])
            writer.writeheader()
            for i in range(3000):
                writer.writerow({"id": f"G-{i}", "nombre": f"Grupo {i}"})
        self.assertEqual(self.repo.import_csv(source, "grupos"), (3000, []))
        path = self.folder / "batch.csv"
        self.repo.save(path)
        saved = pea.load_repository(path)
        self.assertTrue(saved.undo())
        self.assertEqual(saved.page("grupos", limit=0)["total"], 0)


class CommunicationFixes(unittest.TestCase):
    def fake_binary(self, folder, blocked_action, behavior="time.sleep(20)", *, stop_reading=False):
        path = Path(folder) / "backend"
        path.write_text(
            f"#!{sys.executable}\nimport json,os,sys,time\n"
            "for line in sys.stdin:\n"
            " q=json.loads(line)\n"
            f" if q['action']=={blocked_action!r}:\n"
            + "".join(f"  {line}\n" for line in behavior.splitlines())
            +
            f" result={{'backend':'cpp','protocol':{pea.CPP_PROTOCOL!r}}} if q['action']=='ping' else None\n"
            " print(json.dumps({'ok':True,'result':result,'state':{'dirty':False,'history_size':0,'queue_size':0}}),flush=True)\n"
            + (" if q['action']=='ping':time.sleep(20)\n" if stop_reading else "")
            +
            " if q['action']=='shutdown':break\n"
        )
        path.chmod(0o700)
        return path

    @unittest.skipIf(os.name == "nt", "El backend de prueba usa un shebang POSIX")
    def test_stalled_backend_response_has_deadline_and_releases_resources(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = self.fake_binary(folder, "summary")
            repo = pea.CppRepository(binary, timeout=0.15)
            try:
                started = time.monotonic()
                with self.assertRaisesRegex(pea.DataError, "tiempo|plazo"):
                    repo.summary()
                self.assertLess(time.monotonic() - started, 2)
                self.assertIsNotNone(repo.process.poll())
                with self.assertRaises(pea.DataError):
                    repo.summary()
            finally:
                repo.close()
                repo.close()
            self.assertTrue(all(s.closed for s in (repo.process.stdin, repo.process.stdout, repo.process.stderr)))

    @unittest.skipIf(os.name == "nt", "El backend de prueba usa un shebang POSIX")
    def test_stalled_shutdown_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = pea.CppRepository(self.fake_binary(folder, "shutdown"), timeout=0.15)
            started = time.monotonic()
            repo.close()
            self.assertLess(time.monotonic() - started, 2)
            self.assertIsNotNone(repo.process.poll())

    @unittest.skipIf(os.name == "nt", "El backend de prueba usa un shebang POSIX")
    def test_stalled_write_does_not_leak_streams_or_retry_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = pea.CppRepository(self.fake_binary(folder, "unused", stop_reading=True), timeout=0.15)
            try:
                started = time.monotonic()
                with self.assertRaises(pea.DataError):
                    repo._request("create", values="x" * 1_000_000)
                self.assertLess(time.monotonic() - started, 2)
                self.assertIsNotNone(repo.process.poll())
            finally:
                repo.close()
            self.assertTrue(all(s.closed for s in (repo.process.stdin, repo.process.stdout, repo.process.stderr)))

    @unittest.skipUnless(hasattr(os, "fork"), "La prueba crea un descendiente POSIX")
    def test_descendant_holding_stdout_cannot_block_deadline(self):
        with tempfile.TemporaryDirectory() as folder:
            pidfile = Path(folder) / "child.pid"
            behavior = ("pid=os.fork()\n"
                        "if pid==0:\n time.sleep(20)\n os._exit(0)\n"
                        f"open({str(pidfile)!r},'w').write(str(pid))\n"
                        "time.sleep(20)")
            repo = pea.CppRepository(self.fake_binary(folder, "summary", behavior), timeout=0.15)
            try:
                started = time.monotonic()
                with self.assertRaises(pea.DataError):
                    repo.summary()
                self.assertLess(time.monotonic() - started, 2)
            finally:
                if pidfile.exists():
                    os.kill(int(pidfile.read_text()), 9)
                repo.close()
                repo._worker.join(timeout=1)
            self.assertTrue(all(s.closed for s in (repo.process.stdin, repo.process.stdout, repo.process.stderr)))

    @unittest.skipIf(os.name == "nt", "El backend de prueba usa un shebang POSIX")
    def test_waiting_for_busy_backend_does_not_kill_it(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = pea.CppRepository(self.fake_binary(folder, "unused"), timeout=0.15)
            try:
                repo._request_lock.acquire()
                try:
                    with self.assertRaisesRegex(pea.DataError, "ocupado"):
                        repo.summary()
                    self.assertIsNone(repo.process.poll())
                finally:
                    repo._request_lock.release()
                repo.summary()
            finally:
                repo.close()

    @unittest.skipIf(os.name == "nt", "El backend de prueba usa un shebang POSIX")
    def test_invalid_protocol_closes_backend_and_business_error_keeps_it_alive(self):
        with tempfile.TemporaryDirectory() as folder:
            for behavior, closes in (("print('not json',flush=True)\ncontinue", True),
                                     ("print(json.dumps({'ok':False,'error':'Dato inválido',"
                                      "'state':{'dirty':False,'history_size':0,'queue_size':0}}),flush=True)\ncontinue", False)):
                with self.subTest(closes=closes):
                    repo = pea.CppRepository(self.fake_binary(folder, "summary", behavior), timeout=0.15)
                    try:
                        with self.assertRaises(pea.DataError):
                            repo.summary()
                        self.assertEqual(repo.process.poll() is not None, closes)
                    finally:
                        repo.close()

    @unittest.skipIf(os.name == "nt", "El backend de prueba usa un shebang POSIX")
    def test_stalled_handshake_releases_process_and_streams(self):
        with tempfile.TemporaryDirectory() as folder:
            opened = []
            popen = subprocess.Popen

            def start(*args, **kwargs):
                process = popen(*args, **kwargs)
                opened.append(process)
                return process

            with patch.object(pea.subprocess, "Popen", side_effect=start), self.assertRaises(pea.DataError):
                pea.CppRepository(self.fake_binary(folder, "ping"), timeout=0.15)
            self.assertEqual(len(opened), 1)
            self.assertIsNotNone(opened[0].poll())
            self.assertTrue(all(s.closed for s in (opened[0].stdin, opened[0].stdout, opened[0].stderr)))

    @unittest.skipIf(os.name == "nt", "El backend de prueba usa un shebang POSIX")
    def test_backend_failure_aborts_web_import_and_batch_finalization(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = pea.CppRepository(self.fake_binary(folder, "create"), timeout=0.15)
            try:
                with self.assertRaises(pea.BackendError):
                    pea.import_cvlac_preview(repo, profile(1))
            finally:
                repo.close()
            repo = pea.CppRepository(self.fake_binary(folder, "unused"), timeout=0.15)
            try:
                with self.assertRaises(pea.BackendError):
                    with repo.batch():
                        repo.process.kill()
                        repo.process.wait(timeout=1)
            finally:
                repo.close()


if __name__ == "__main__":
    unittest.main()

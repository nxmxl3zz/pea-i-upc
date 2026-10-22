"""Regresiones de filtros, identidades y población del bloque 7–11."""

import csv
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pea_backend_cleanup", ROOT / "src/python/Taller2_REMR.py")
pea = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pea)
FIXTURE_SPEC = importlib.util.spec_from_file_location("cleanup_fixture", ROOT / "tests/python/fixture_f.py")
fixture = importlib.util.module_from_spec(FIXTURE_SPEC)
FIXTURE_SPEC.loader.exec_module(fixture)


class BackendBehavior:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pea-backend-cleanup-")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.repo = self.make_repository()

    def populate_links(self):
        for key, name in (("G1", "Energía"), ("G2", "Salud")):
            self.repo.create("grupos", {"id": key, "nombre": name})
        for index in range(9):
            self.repo.create("investigadores", {"id": f"I{index}", "nombre": f"Gómez {index}",
                                                "activo": "0" if index == 4 else "1"})
            self.repo.create("membresias", {"grupo_id": "G1", "investigador_id": f"I{index}",
                                          "rol": "Director" if index % 3 == 0 else "Miembro",
                                          "activo": "1" if index % 2 == 0 else "0"})
            self.repo.create("planes", {"id": f"PL{index}", "grupo_id": "G1" if index % 2 == 0 else "G2",
                                       "nombre": f"Plan {index}", "activo": "1" if index % 3 == 0 else "0"})

    def test_active_filter_counts_before_pagination_and_preserves_order(self):
        self.populate_links()
        for active in ("", "0", "1"):
            expected = [row for row in self.repo.rows("investigadores") if not active or row["activo"] == active]
            for offset, limit in ((0, 2), (2, 3), (100, 4), (0, 0)):
                self.assertEqual(self.repo.page("investigadores", offset, limit, active=active),
                                 {"rows": expected[offset:offset + limit], "total": len(expected)})

    def test_plans_group_and_active_filters_compose_with_query(self):
        self.populate_links()
        expected = [row for row in self.repo.rows("planes")
                    if row["grupo_id"] == "G1" and row["activo"] == "1"]
        self.assertEqual(self.repo.page("planes", 1, 1, "PLAN", active="1", group_id="G1"),
                         {"rows": expected[1:2], "total": len(expected)})
        self.assertEqual(self.repo.page("planes", group_id="missing")["total"], 0)

    def test_relation_page_searches_both_endpoints_and_link_fields(self):
        self.populate_links()
        all_links = self.repo.rows("membresias")
        expected = [row for row in all_links if row["activo"] == "1"]
        result = self.repo.page("membresias", 1, 2, "ENERGÍA", active="1", include_references=True)
        self.assertEqual(result["rows"], expected[1:3])
        self.assertEqual(result["total"], len(expected))
        self.assertEqual(result["references"], {"grupos": [self.repo.get("grupos", "G1")],
                         "investigadores": [self.repo.get("investigadores", row["investigador_id"])
                                            for row in expected[1:3]]})
        self.assertEqual(self.repo.page("membresias", query="GÓMEZ 4", include_references=True)["rows"],
                         [self.repo.get("membresias", ("G1", "I4"))])
        self.assertEqual(self.repo.page("membresias", query="director", include_references=True)["total"], 3)
        self.assertEqual(self.repo.page("membresias", query="GÓMEZ")["total"], 0)

    def test_related_search_filters_before_slicing_in_chain_order(self):
        self.populate_links()
        expected = [row for row in self.repo.related("membresias", "G1", "left") if row["activo"] == "1"]
        self.assertEqual(self.repo.related_page("membresias", "G1", "left", 1, 2, True, "GÓMEZ"),
                         {"rows": expected[1:3], "total": len(expected)})
        self.assertEqual(self.repo.related_page("membresias", "I0", "right", query="ENERGÍA")["total"], 1)
        self.assertEqual(self.repo.related_page("membresias", "G1", "left", query="director")["total"], 3)
        self.assertEqual(self.repo.related_page("membresias", "G1", "left", query="Salud")["total"], 0)

    def test_reference_payload_only_contains_returned_page_and_preserves_default_shape(self):
        self.populate_links()
        page = self.repo.related_page("membresias", "G1", "left", 2, 2, include_references=True)
        self.assertEqual(set(page["references"]), {"investigadores"})
        self.assertEqual([row["id"] for row in page["references"]["investigadores"]],
                         [row["investigador_id"] for row in page["rows"]])
        empty = self.repo.related_page("membresias", "G1", "left", query="missing", include_references=True)
        self.assertEqual(empty, {"rows": [], "total": 0, "references": {"investigadores": []}})
        self.assertEqual(set(self.repo.page("membresias")), {"rows", "total"})
        self.assertEqual(set(self.repo.related_page("membresias", "G1", "left")), {"rows", "total"})

    def test_invalid_filter_and_side_rejected_without_mutation(self):
        self.populate_links()
        before = self.repo.history_size()
        for call in (lambda: self.repo.page("grupos", active="si"),
                     lambda: self.repo.page("grupos", group_id="G1"),
                     lambda: self.repo.page("grupos", include_references=True),
                     lambda: self.repo.related_page("membresias", "G1", "invalid"),
                     lambda: self.repo.related("membresias", "G1", "invalid")):
            with self.assertRaises(pea.DataError):
                call()
        self.assertEqual(self.repo.history_size(), before)

    def test_external_identities_follow_update_delete_undo_and_load(self):
        for kind, field, base in (("grupos", "codigo_gruplac", {"nombre": "Grupo"}),
                                  ("investigadores", "codigo_cvlac", {"nombre": "Persona"}),
                                  ("productos", "doi", {"titulo": "Producto"})):
            with self.subTest(kind=kind):
                prefix = "https://doi.org/" if kind == "productos" else ""
                old, new = "10.1234/old" if prefix else "old", "10.1234/new" if prefix else "new"
                self.repo.create(kind, {"id": kind, **base, field: prefix + old.upper()})
                self.assertEqual(self.repo.find_external(kind, old)["id"], kind)
                self.repo.update(kind, kind, {field: new})
                self.assertIsNone(self.repo.find_external(kind, old))
                self.assertEqual(self.repo.find_external(kind, prefix + new.upper())["id"], kind)
                with self.assertRaises(pea.DataError):
                    self.repo.create(kind, {"id": kind + "-duplicate", **base, field: new})
                self.assertTrue(self.repo.undo())
                self.assertIsNone(self.repo.find_external(kind, new))
                self.assertEqual(self.repo.find_external(kind, old)["id"], kind)
                self.repo.delete(kind, kind)
                self.assertIsNone(self.repo.find_external(kind, old))
                self.assertTrue(self.repo.undo())
                path = self.folder / f"{kind}.csv"
                if isinstance(self.repo, pea.CppRepository):
                    self.repo.save(path)
                    self.repo.load(path)
                else:
                    pea.save_repository(self.repo, path)
                    self.repo = pea.load_repository(path)
                self.assertEqual(self.repo.find_external(kind, old)["id"], kind)
        self.repo.create("productos", {"id": "empty-doi", "titulo": "Sin DOI", "doi": "https://doi.org/"})
        self.assertIsNone(self.repo.find_external("productos", "https://doi.org/"))

    def test_population_cache_keys_and_mutations_keep_cross_engine_parity(self):
        fixture.populate(self.repo)
        for options in ({"end": 2026}, {"start": 2025, "end": 2026}, {"end": 2024},
                        {"end": 2026, "status": "rechazado"}, {"end": 2026, "status": "validado"}):
            self.assert_population_matches_fresh(options)
        for kind, key, changes in (("productos", "P1", {"categoria": "ART_A1"}),
                                    ("grupos", "G2", {"activo": "0"}),
                                    ("investigadores", "I2", {"activo": "0"}),
                                    ("membresias", ("G1", "I2"), {"activo": "0"}),
                                    ("autorias", ("P1", "I2"), {"activo": "0"}),
                                    ("grupos_productos", ("G1", "P1"), {"activo": "0"})):
            self.repo.update(kind, key, changes)
            self.assert_population_matches_fresh({"end": 2026})
            self.assertTrue(self.repo.undo())
            self.assert_population_matches_fresh({"end": 2026})

    def assert_population_matches_fresh(self, options):
        fresh = pea.Repository()
        for kind in pea.ALL_FIELDS:
            for row in self.repo.rows(kind):
                fresh.create(kind, row, remember=False)
        for kind, key in (("grupos", "G1"), ("investigadores", "I1"), ("investigadores", "I3")):
            self.assertEqual(self.repo.indicator(kind, key, **options), fresh.indicator(kind, key, **options))


class PythonBackendFixes(BackendBehavior, unittest.TestCase):
    def make_repository(self):
        return pea.Repository()

    def test_identity_checks_and_resolution_do_not_scan_entity_lists(self):
        for kind, field, base in (("grupos", "codigo_gruplac", {"nombre": "Grupo"}),
                                  ("investigadores", "codigo_cvlac", {"nombre": "Persona"}),
                                  ("productos", "doi", {"titulo": "Producto"})):
            self.repo.create(kind, {"id": kind, **base, field: "unique"})
        with patch.object(pea.DoublyLinkedList, "__iter__", side_effect=AssertionError("Escaneo de entidades")):
            for kind, field, base in (("grupos", "codigo_gruplac", {"nombre": "Grupo"}),
                                      ("investigadores", "codigo_cvlac", {"nombre": "Persona"}),
                                      ("productos", "doi", {"titulo": "Producto"})):
                self.assertEqual(self.repo.find_external(kind, "UNIQUE")["id"], kind)
                self.repo.create(kind, {"id": kind + "-2", **base, field: "other"}, remember=False)
                self.repo.update(kind, kind, {field: "changed"}, remember=False)
                with self.assertRaises(pea.DataError):
                    self.repo.create(kind, {"id": kind + "-duplicate", **base, field: "CHANGED"})

    def test_population_maxima_are_reused_for_other_ids_and_invalidated_without_history(self):
        fixture.populate(self.repo)
        with patch.object(self.repo, "_indicator_raw", wraps=self.repo._indicator_raw) as raw:
            self.repo.indicator("investigadores", "I1", end=2026)
            self.assertEqual(raw.call_count, 3)
            self.repo.indicator("investigadores", "I3", end=2026)
            self.assertEqual(raw.call_count, 4)
            self.repo.update("productos", "P4", {"categoria": "ART_A1"}, remember=False)
            self.repo.indicator("investigadores", "I1", end=2026)
            self.assertEqual(raw.call_count, 7)
        self.assert_population_matches_fresh({"end": 2026})

    def test_legacy_restore_rebuilds_external_indexes_and_population(self):
        fixture.populate(self.repo)
        self.repo.update("investigadores", "I1", {"codigo_cvlac": "before"})
        snapshot = self.repo.snapshot()
        expected = self.repo.indicator("investigadores", "I1", end=2026)
        self.repo.update("investigadores", "I1", {"codigo_cvlac": "after"})
        self.repo.update("productos", "P1", {"categoria": "ART_A1"})
        self.repo.history.push(snapshot)
        self.assertTrue(self.repo.undo())
        self.assertIsNone(self.repo.find_external("investigadores", "after"))
        self.assertEqual(self.repo.find_external("investigadores", "before")["id"], "I1")
        self.assertEqual(self.repo.indicator("investigadores", "I1", end=2026), expected)


@unittest.skipUnless(os.environ.get("PEA_TEST_CPP"), "PEA_TEST_CPP no configurado")
class CppBackendFixes(BackendBehavior, unittest.TestCase):
    def make_repository(self):
        repo = pea.CppRepository(Path(os.environ["PEA_TEST_CPP"]))
        self.addCleanup(repo.close)
        return repo


class HeaderProbe(unittest.TestCase):
    def test_native_header_probe_stops_after_first_complete_record(self):
        with tempfile.TemporaryDirectory(prefix="pea-header-cleanup-") as temporary:
            folder = Path(temporary)
            path = folder / "data.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                csv.writer(stream).writerow(pea.ENTITY_FIELDS["productos"])
                stream.write('"comilla sin cerrar')
            harness = folder / "probe.cpp"
            harness.write_text('#define main pea_original_main\n#include "' +
                               str(ROOT / "src/cpp/Taller2_REMR.cpp") + '"\n#undef main\n' +
                               'int main(int argc,char**argv) { (void)argc; try {' +
                               'if (!pea::headerMatches(argv[1],pea::FIELDS.at("productos"))) return 2;' +
                               'try { pea::readCsvEach(argv[1],pea::FIELDS.at("productos"),' +
                               '[](pea::Row,std::size_t){}); return 3; } catch(const pea::DataError&) {}' +
                               'return 0; } catch(const pea::DataError&) { return 4; }}\n', encoding="utf-8")
            compiled = subprocess.run(["g++", "-std=c++17", "-O0", str(harness), "-o", str(folder / "probe")],
                                      capture_output=True, text=True, timeout=120)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(folder / "probe"), str(path)], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr.decode())


if __name__ == "__main__":
    unittest.main()

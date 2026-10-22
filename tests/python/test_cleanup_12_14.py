"""Contratos de CSV, contadores y compilación automática del bloque 12–14."""

import csv
import importlib.util
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[2] / "src/python/Taller2_REMR.py"
SPEC = importlib.util.spec_from_file_location("pea_cleanup_12_14", SOURCE)
pea = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pea)


class AutomaticBuildTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pea-auto-build-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ("CMakeLists.txt", "src/cpp/Taller2_REMR.cpp"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            content = ((SOURCE.parents[2] / name).read_text(encoding="utf-8") if name == "CMakeLists.txt"
                       else "int main() { return 0; }\n")
            path.write_text(content, encoding="utf-8")
        module = self.root / "src/python/Taller2_REMR.py"
        self.filename = patch.object(pea, "__file__", str(module))
        self.filename.start()
        self.addCleanup(self.filename.stop)

    def build(self, relative_binary):
        calls = []

        def run(command, **_options):
            calls.append(command)
            if "--build" in command:
                binary = self.root / relative_binary
                binary.parent.mkdir(parents=True, exist_ok=True)
                binary.write_bytes(b"backend fixture")
            return subprocess.CompletedProcess(command, 0, "")

        with patch.object(pea.shutil, "which", return_value="/tools/cmake"), \
                patch.object(pea.subprocess, "run", side_effect=run):
            binary = pea.cpp_executable()
        return binary, calls

    @unittest.skipUnless(pea.os.name == "posix" and pea.shutil.which("cmake") and pea.shutil.which("make")
                         and pea.shutil.which("c++"), "Requiere CMake y compilador C++ en POSIX")
    def test_single_configuration_defaults_to_optimized_release(self):
        build = self.root / "configured"
        result = subprocess.run(["cmake", "-S", str(self.root), "-B", str(build), "-G", "Unix Makefiles"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("CMAKE_BUILD_TYPE:STRING=Release", (build / "CMakeCache.txt").read_text())
        flags = (build / "CMakeFiles/pea_cpp.dir/flags.make").read_text()
        self.assertIn("-O3", flags)
        self.assertIn("-DNDEBUG", flags)

    def test_fresh_native_build_finds_default_output(self):
        binary, calls = self.build("build/default/pea_cpp")
        self.assertEqual(binary, self.root / "build/default/pea_cpp")
        self.assertEqual(len(calls), 2)

    def test_native_multi_configuration_build_finds_release_output(self):
        binary, calls = self.build("build/default/Release/pea_cpp")
        self.assertEqual(binary, self.root / "build/default/Release/pea_cpp")
        self.assertEqual(calls[1][-2:], ["--config", "Release"])

    def test_mingw_keeps_its_generator_and_release_build(self):
        with patch.object(pea, "os", SimpleNamespace(name="nt")), \
                patch.object(pea, "bundled_windows_cpp", return_value=None):
            binary, calls = self.build("build/mingw/pea_cpp.exe")
        self.assertEqual(binary, self.root / "build/mingw/pea_cpp.exe")
        self.assertEqual(calls[0][-2:], ["-G", "MinGW Makefiles"])
        self.assertEqual(calls[1][-2:], ["--config", "Release"])

    def test_explicit_binary_never_runs_cmake(self):
        binary = self.root / "explicit-backend"
        binary.write_bytes(b"fixture")
        with patch.object(pea.subprocess, "run") as run:
            self.assertEqual(pea.cpp_executable(binary), binary.resolve())
        run.assert_not_called()

    def test_current_existing_binary_never_runs_cmake(self):
        binary = self.root / "build/pea_cpp"
        binary.parent.mkdir()
        binary.write_bytes(b"fixture")
        with patch.object(pea.subprocess, "run") as run:
            self.assertEqual(pea.cpp_executable(), binary)
        run.assert_not_called()

    def test_missing_cmake_is_an_explicit_error(self):
        with patch.object(pea.shutil, "which", return_value=None), \
                patch.object(pea.subprocess, "run") as run:
            with self.assertRaisesRegex(pea.DataError, "CMake no está instalado"):
                pea.cpp_executable()
        run.assert_not_called()

    def test_configure_failure_preserves_the_diagnostic(self):
        result = subprocess.CompletedProcess([], 1, "generador no disponible")
        with patch.object(pea.shutil, "which", return_value="/tools/cmake"), \
                patch.object(pea.subprocess, "run", return_value=result) as run:
            with self.assertRaisesRegex(pea.DataError, "generador no disponible"):
                pea.cpp_executable()
        self.assertEqual(run.call_count, 1)


class CsvAndImportContractTest(unittest.TestCase):
    @staticmethod
    def first_row(path):
        with path.open(encoding="utf-8", newline="") as stream:
            return next(csv.DictReader(stream))

    def test_storage_and_spreadsheet_keep_different_apostrophe_policies(self):
        repo = pea.Repository()
        repo.create("grupos", {"id": "G", "nombre": "'literal",
                               "descripcion": '=SUM(1,2)\n"línea", ñ'})
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            flat = folder / "storage.csv"
            pea._csv_write(flat, pea.ENTITY_FIELDS["grupos"], repo.rows("grupos"))
            pea.export_repository_spreadsheet(repo, folder / "excel")
            storage = self.first_row(flat)
            spreadsheet = self.first_row(folder / "excel/grupos.csv")
        self.assertEqual(storage["nombre"], "''literal")
        self.assertEqual(spreadsheet["nombre"], "'literal")
        self.assertEqual(storage["descripcion"], '\'=SUM(1,2)\n"línea", ñ')
        self.assertEqual(spreadsheet["descripcion"], storage["descripcion"])

    def test_exports_synchronize_each_completed_file(self):
        repo = pea.Repository()
        with tempfile.TemporaryDirectory() as temporary, patch.object(pea.os, "fsync") as sync:
            pea.export_repository_spreadsheet(repo, Path(temporary))
        self.assertEqual(sync.call_count, 1 + len(pea.ALL_FIELDS))

    def test_flat_writer_propagates_sync_failure(self):
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(pea.os, "fsync", side_effect=OSError("sin espacio")):
            with self.assertRaisesRegex(OSError, "sin espacio"):
                pea._csv_write(Path(temporary) / "flat.csv", ("id",), [{"id": "G"}])

    def test_failed_save_preserves_file_backup_history_and_dirty(self):
        repo = pea.Repository()
        repo.create("grupos", {"id": "G", "nombre": "Primero"})
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "datos.csv"
            pea.save_repository(repo, path)
            repo.update("grupos", "G", {"nombre": "Segundo"})
            pea.save_repository(repo, path)
            repo.update("grupos", "G", {"nombre": "Sin guardar"})
            before, backup = path.read_bytes(), pea.backup_of(path).read_bytes()
            history = list(repo.history)
            with patch.object(pea.os, "fsync", side_effect=OSError("disco lleno")):
                with self.assertRaisesRegex(OSError, "disco lleno"):
                    pea.save_repository(repo, path)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(pea.backup_of(path).read_bytes(), backup)
            self.assertEqual(list(repo.history), history)
            self.assertTrue(repo.dirty)
            self.assertEqual(pea.load_repository(path).get("grupos", "G")["nombre"], "Segundo")
            self.assertFalse(list(path.parent.glob("*.tmp")))

    def test_group_and_person_import_results_have_independent_counters_and_errors(self):
        repo = pea.Repository()
        group_url = "https://scienti.minciencias.gov.co/gruplac/jsp/visualiza/visualizagr.jsp?nro=123"
        person_url = "https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=456"
        group = pea.parse_web_page("<h1>Grupo</h1><h2>Datos básicos</h2>", group_url)
        invalid = pea.clean_row("productos", {"id": "P", "titulo": "Producto", "anio": "2025"})
        invalid["anio"] = "1800"
        first = pea.import_gruplac_preview(repo, group._replace(related_products=(invalid,)))
        person = pea.parse_web_page("<h1>Hoja de vida</h1><p>Nombre</p><p>Ana Pérez</p>", person_url)
        second = pea.import_cvlac_preview(repo, person)
        self.assertEqual((first["grupos"], len(first["errors"])), (1, 1))
        self.assertEqual((second["grupos"], second["investigadores"], second["errors"]), (0, 1, []))
        self.assertEqual(set(first), set(second))
        self.assertIsNot(first["errors"], second["errors"])


if __name__ == "__main__":
    unittest.main()

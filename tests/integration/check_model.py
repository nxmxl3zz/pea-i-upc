"""Comprueba el catálogo 2024, las categorías y la persistencia compartida de ambos motores."""

import csv
import importlib.util
import math
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pea", ROOT / "src/python/Taller2_REMR.py")
pea = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pea)
FIXTURE_SPEC = importlib.util.spec_from_file_location("fixture_f", ROOT / "tests/python/fixture_f.py")
fixture_f = importlib.util.module_from_spec(FIXTURE_SPEC)
FIXTURE_SPEC.loader.exec_module(fixture_f)


def assert_result_equal(actual, expected, path="result") -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys(), path
        for key in expected:
            assert_result_equal(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), path
        for index, item in enumerate(expected):
            assert_result_equal(actual[index], item, f"{path}[{index}]")
    elif isinstance(expected, float):
        assert math.isclose(actual, expected, rel_tol=0, abs_tol=1e-9), (path, actual, expected)
    else:
        assert actual == expected, (path, actual, expected)


def check_indicator(cpp, folder: Path) -> None:
    python = pea.Repository()
    fixture_f.populate(python)
    path = folder / "fixture_f.csv"
    pea.save_repository(python, path)
    cpp.load(path)
    assert_result_equal(cpp._request("indicator", kind="grupos", key="G1", end="2026"),
                        python.indicator("grupos", "G1", end=2026))
    entities = (("grupos", "G1"), ("grupos", "G2"), *(('investigadores', key) for key in ("I1", "I2", "I3")))
    for kind, key in entities:
        for options in ({"end": 2026}, {"start": 2025, "end": 2026}, {"end": 2024},
                        {"end": 2026, "status": "validado"}, {"end": 2026, "status": "rechazado"}):
            assert_result_equal(cpp.indicator(kind, key, **options), python.indicator(kind, key, **options))
    for kind, key in (("autorias", ("P1", "I2")), ("membresias", ("G2", "I1")),
                       ("investigadores", "I2"), ("productos", "P8"), ("grupos", "G2")):
        cpp.toggle(kind, key)
        python.toggle(kind, key)
        assert_result_equal(cpp.indicator("grupos", "G1", end=2026), python.indicator("grupos", "G1", end=2026))
        assert_result_equal(cpp.indicator("investigadores", "I1", end=2026),
                            python.indicator("investigadores", "I1", end=2026))
        assert cpp.undo() and python.undo()
    cpp.load(ROOT / "data/pea_upc.csv")
    python = pea.load_repository(ROOT / "data/pea_upc.csv")
    for kind, key in (("grupos", "G-00000000002099"), ("investigadores", "I-0000494917")):
        for options in ({"end": 2026}, {"start": 2025, "end": 2026}):
            assert_result_equal(cpp.indicator(kind, key, **options), python.indicator(kind, key, **options))


def check_categories(cpp, python) -> None:
    for repo in (python, cpp):
        repo.create("productos", {"id": "P-MAN", "titulo": "Categoría manual", "categoria": "ART_A1"})
        repo.create("productos", {"id": "P-EST", "titulo": "Categoría estimada", "categoria": "ART_D",
                                  "categoria_origen": "estimada"})
    for changes, origin in (({"observacion": "nota"}, "estimada"),
                            ({"categoria": " ART_D "}, "estimada"),
                            ({"categoria": "ART_C"}, "manual"),
                            ({"categoria": ""}, ""),
                            ({"categoria_origen": "manual"}, ""),
                            ({"categoria": "ART_D", "categoria_origen": "estimada"}, "estimada")):
        assert cpp.update("productos", "P-EST", changes) == python.update("productos", "P-EST", changes)
        assert cpp.get("productos", "P-EST")["categoria_origen"] == origin
    assert cpp.statistics() == python.statistics()
    cpp.update("productos", "P-EST", {"categoria": "ART_C"})
    assert cpp.undo()
    assert cpp.get("productos", "P-EST") == python.get("productos", "P-EST")


def check_persistence(cpp, python, folder: Path) -> None:
    path = folder / "datos.csv"
    pea.save_repository(python, path)
    cpp.load(path)
    assert cpp.rows("productos") == python.rows("productos")
    # Las instantáneas completas de Python se pueden deshacer en C++.
    assert cpp.undo() and python.undo()
    assert cpp.rows("productos") == python.rows("productos")
    cpp.update("productos", "P-MAN", {"observacion": "Edición desde C++"})
    cpp.save(path)
    manifest = [row for section, _, row in pea.read_data_sections(path) if section == "manifest"]
    assert manifest[0]["version"] == "5"
    restored = pea.load_repository(path)
    assert restored.rows("productos") == cpp.rows("productos")
    # Los deltas de C++ se pueden deshacer en Python sin perder la categoría.
    assert restored.undo() and cpp.undo()
    assert restored.rows("productos") == cpp.rows("productos")
    assert restored.get("productos", "P-MAN")["categoria"] == "ART_A1"

    cpp.load(ROOT / "tests/fixtures/v4_con_historial.csv")
    product = cpp.get("productos", "P1")
    assert (product["categoria"], product["categoria_origen"], product["observacion"]) == ("", "", "nota")
    assert cpp.undo()
    assert cpp.get("productos", "P1")["observacion"] == ""
    cpp.save(path)
    upgraded = pea.load_repository(path)
    assert upgraded.get("productos", "P1") == cpp.get("productos", "P1")
    assert upgraded.undo() and cpp.undo()
    assert upgraded.rows("productos") == cpp.rows("productos")


def check_csv_headers(cpp, folder: Path) -> None:
    for fields in (pea.PRODUCT_FIELDS_V4, pea.ENTITY_FIELDS["productos"]):
        for quoting in (csv.QUOTE_MINIMAL, csv.QUOTE_ALL):
            cpp.reset()
            path = folder / "importacion.csv"
            row = {"id": "P-CSV", "titulo": "Importación con encabezado anterior o actual"}
            if "categoria" in fields:
                row.update(categoria="ART_D", categoria_origen="estimada")
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=tuple(reversed(fields)), quoting=quoting)
                writer.writeheader()
                writer.writerow(row)
            assert cpp.preview_csv(path, "productos") == (1, 1, [])
            assert cpp.rows("productos") == []
            assert cpp.import_csv(path, "productos") == (1, [])
            expected = pea.Repository().create("productos", row)
            assert cpp.get("productos", "P-CSV") == expected
            assert cpp.undo() and cpp.rows("productos") == []


def check_indicator_console(binary: Path, folder: Path) -> None:
    python = pea.Repository()
    fixture_f.populate(python)
    path = folder / "console_f.csv"
    pea.save_repository(python, path)
    for keys, expected in (("12\n1\nG1\n4\n\n2026\n\n0\n", "Ind. = 3.5319"),
                            ("12\n2\nI1\n4\n\n2026\n\n0\n", "Ind. = 1.3000"),
                            ("12\n3\n0\n", "ART_A2")):
        run = subprocess.run([str(binary), "--data", str(path)], input=keys, text=True,
                             capture_output=True, check=True, timeout=20, cwd=ROOT)
        assert expected in run.stdout, run.stdout[-3000:]
        if "ART_A2" == expected:
            assert "550" in run.stdout
    detail = subprocess.run([str(binary), "--data", str(path)], input="3\n2\nP1\n0\n0\n", text=True,
                            capture_output=True, check=True, timeout=20, cwd=ROOT)
    assert "Peso relativo: 9" in detail.stdout and "Valor en puntos: 45" in detail.stdout


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python3 tests/integration/check_model.py build/pea_cpp")
    cpp = pea.CppRepository(Path(sys.argv[1]).resolve())
    try:
        catalog = cpp.catalog()
        assert catalog == pea.Repository().catalog()
        assert cpp._request("ping") == {"backend": "cpp", "protocol": "4"}
        for row in catalog:
            assert isinstance(row["ventana"], int)
            assert all(isinstance(row[field], float) for field in ("peso_alta", "peso_relativo", "peso_global"))
        python = pea.Repository()
        check_categories(cpp, python)
        with tempfile.TemporaryDirectory(prefix="pea-model-") as folder:
            check_persistence(cpp, python, Path(folder))
            check_csv_headers(cpp, Path(folder))
            check_indicator(cpp, Path(folder))
            check_indicator_console(Path(sys.argv[1]).resolve(), Path(folder))
    finally:
        cpp.close()
    print("Modelo 2024 compartido: catálogo, categorías, esquema v5 e historial v4 correctos.")


if __name__ == "__main__":
    main()

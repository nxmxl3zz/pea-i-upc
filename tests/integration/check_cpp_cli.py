"""Recorre los menus C++ con datos nuevos y comprueba los CSV desde Python."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pea", ROOT / "src/python/Taller2_REMR.py")
pea = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pea)


def values(kind: str, entries: dict[str, str]) -> list[str]:
    return [entries.get(name, "") for name in pea.ALL_FIELDS[kind]]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python3 tests/integration/check_cpp_cli.py build/pea_cpp")
    binary = Path(sys.argv[1]).resolve()
    if not binary.is_file():
        raise SystemExit(f"No existe el ejecutable: {binary}")
    with tempfile.TemporaryDirectory(prefix="pea-cpp-cli-") as folder:
        actions = ["1"]  # iniciar vacio
        for main_option, kind, fields in (
            ("1", "grupos", {"id": "G-CLI", "nombre": "Grupo de consola"}),
            ("2", "investigadores", {"id": "I-CLI", "nombre": "Persona de consola"}),
            ("3", "productos", {"id": "P-CLI", "titulo": "Producto de consola", "anio": "2025"}),
            ("4", "planes", {"id": "PL-CLI", "grupo_id": "G-CLI", "nombre": "Plan de consola"}),
        ):
            actions += [main_option, "3", *values(kind, fields), "0"]
        actions += ["5"]
        for relation_option, kind, fields in (
            ("1", "membresias", {"grupo_id": "G-CLI", "investigador_id": "I-CLI", "rol": "Lider"}),
            ("2", "autorias", {"producto_id": "P-CLI", "investigador_id": "I-CLI", "orden": "1"}),
            ("3", "grupos_productos", {"grupo_id": "G-CLI", "producto_id": "P-CLI"}),
        ):
            actions += [relation_option, "3", *values(kind, fields), "0"]
        actions += ["0", "7", "2", "G-CLI", "4", "2025", "2025", "", "", "11", folder, "0"]
        run = subprocess.run(
            [str(binary)], input="\n".join(actions) + "\n", text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=ROOT, timeout=20, check=True,
        )
        assert "Productos unicos: 1" in run.stdout, run.stdout[-3000:]
        saved = pea.load_repository(Path(folder))
        assert len(saved.rows("grupos")) == 1
        assert len(saved.rows("investigadores")) == 1
        assert len(saved.rows("productos")) == 1
        assert len(saved.rows("planes")) == 1
        assert saved.statistics(view="Grupo", selected_id="G-CLI")["total"] == 1
        assert saved.statistics(view="Investigador", selected_id="I-CLI")["total"] == 1
        assert saved.get("membresias", ("G-CLI", "I-CLI")) is not None
    print("Menus C++ correctos: alta, relaciones, estadisticas y guardado.")


if __name__ == "__main__":
    main()

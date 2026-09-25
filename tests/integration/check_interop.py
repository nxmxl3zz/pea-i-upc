"""Verifica intercambios C++ -> Python -> C++ de CSV, cola e historial."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "python" / "Taller2_REMR.py"
SPEC = importlib.util.spec_from_file_location("pea", SOURCE)
pea = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pea)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python3 tests/integration/check_interop.py build/pea_cpp")
    binary = Path(sys.argv[1]).resolve()
    if not binary.is_file():
        raise SystemExit(f"No existe el ejecutable: {binary}")
    with tempfile.TemporaryDirectory(prefix="pea-interop-") as folder:
        path = Path(folder)
        first = subprocess.run(
            [str(binary), "--demo"],
            input=f"8\n3\nvalidado\nVerificado por C++\n0\n11\n{path}\n0\n",
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=ROOT, timeout=20, check=True,
        )
        assert "Procesado P-DEMO-2" in first.stdout
        python_repo = pea.load_repository(path)
        assert python_repo.get("productos", "P-DEMO-2")["validacion"] == "validado"
        assert python_repo.queue.peek()["producto_id"] == "P-DEMO-3"
        assert python_repo.history.length == 1
        assert python_repo.undo()
        assert python_repo.queue.peek()["producto_id"] == "P-DEMO-2"
        assert python_repo.get("productos", "P-DEMO-2")["validacion"] == "pendiente"
        python_repo = pea.load_repository(path)

        python_repo.update(
            "productos", "P-DEMO-1",
            {"categoria": "Revisada en Python", "observacion": "Nueva razón en Python"},
        )
        pea.save_repository(python_repo, path)
        second = subprocess.run(
            [str(binary), "--data-dir", str(path)],
            input="9\n11\n0\n",
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=ROOT, timeout=20, check=True,
        )
        assert "Ultima accion deshecha" in second.stdout
        after = pea.load_repository(path)
        assert after.get("productos", "P-DEMO-1")["categoria"] == "Ejemplo A"
        assert after.get("productos", "P-DEMO-2")["validacion"] == "validado"
        assert after.history.length == 1

        third = subprocess.run(
            [str(binary), "--data-dir", str(path)],
            input="9\n11\n0\n",
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=ROOT, timeout=20, check=True,
        )
        assert "Ultima accion deshecha" in third.stdout
        restored = pea.load_repository(path)
        assert restored.get("productos", "P-DEMO-2")["validacion"] == "pendiente"
        assert restored.queue.peek()["producto_id"] == "P-DEMO-2"
        assert restored.queue.length == 2
    print("Interoperabilidad C++/Python correcta: CSV, cola e historial.")


if __name__ == "__main__":
    main()

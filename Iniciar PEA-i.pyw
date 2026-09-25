"""Abre PEA-i sin mostrar una consola en Windows."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "src/python/Taller2_REMR.py"),
                   run_name="__main__")

"""Genera el backend portátil de Windows incluido en el repositorio."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (ROOT / "CMakeLists.txt", ROOT / "src/cpp/Taller2_REMR.cpp")
OUTPUT = ROOT / "bin/windows/pea_cpp.exe"
FINGERPRINT = ROOT / "bin/windows/pea_cpp.source-sha256"
INTEGRITY = ROOT / "bin/windows/pea_cpp.exe.sha256"


def source_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in SOURCES:
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def main() -> None:
    compiler = shutil.which("x86_64-w64-mingw32-g++")
    if compiler is None and os.name == "nt":
        compiler = shutil.which("g++")
    if compiler is None:
        raise SystemExit("Se necesita x86_64-w64-mingw32-g++ o g++ de 64 bits en Windows")
    target = subprocess.check_output([compiler, "-dumpmachine"], text=True).strip().lower()
    if "x86_64" not in target or "mingw" not in target:
        raise SystemExit(f"El compilador no genera ejecutables Windows de 64 bits: {target}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pea-win-", dir=OUTPUT.parent) as folder:
        temporary = Path(folder) / OUTPUT.name
        subprocess.run(
            [compiler, "-std=c++17", "-O2", "-static", "-static-libgcc",
             "-static-libstdc++", "-Wall", "-Wextra", "-Wpedantic",
             str(SOURCES[1]), "-o", str(temporary)],
            cwd=ROOT, check=True,
        )
        strip = (shutil.which("x86_64-w64-mingw32-strip")
                 if "x86_64-w64-mingw32" in compiler else shutil.which("strip"))
        if strip:
            subprocess.run([strip, str(temporary)], check=True)
        temporary.replace(OUTPUT)
    FINGERPRINT.write_text(source_fingerprint() + "\n", encoding="ascii")
    INTEGRITY.write_text(hashlib.sha256(OUTPUT.read_bytes()).hexdigest() + "\n", encoding="ascii")
    print(f"Backend Windows listo: {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

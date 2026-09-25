"""Prueba reproducible de carga del backend C++; no toca los datos del proyecto.

Ejemplo: python3 tests/performance/stress_backend.py build/pea_cpp \
    --products 225000 --people 9000 --links 225000 --memory-mb 1536
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pea", ROOT / "src/python/Taller2_REMR.py")
pea = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pea)


def make_data(directory: Path, products: int, people: int, links: int, jobs: int) -> None:
    with (directory / "manifest.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("version", "guardado"))
        writer.writeheader()
        writer.writerow({"version": "1", "guardado": "2026-09-24"})
    for kind, fields in pea.ALL_FIELDS.items():
        with (directory / f"{kind}.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            if kind == "investigadores":
                for index in range(people):
                    writer.writerow({"id": f"I-{index:07d}", "nombre": f"Persona {index}",
                                     "codigo_cvlac": f"CV-{index:07d}", "activo": "1"})
            elif kind == "productos":
                for index in range(products):
                    writer.writerow({"id": f"P-{index:07d}", "titulo": f"Producto {index}",
                                     "anio": "2025", "doi": f"10.1234/{index:07d}",
                                     "validacion": "pendiente", "activo": "1"})
            elif kind == "autorias":
                for index in range(links):
                    writer.writerow({"producto_id": f"P-{index % products:07d}",
                                     "investigador_id": f"I-{(index // products + index % products) % people:07d}",
                                     "activo": "1"})
    for kind, fields in (("cola_validacion", ("id", "producto_id", "motivo", "creado")),
                         ("historial", ("orden", "snapshot"))):
        with (directory / f"{kind}.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            if kind == "cola_validacion":
                for index in range(jobs):
                    writer.writerow({"id": f"Q-{index:07d}", "producto_id": f"P-{index:07d}",
                                     "motivo": "Prueba de carga", "creado": "2026-09-24T00:00:00"})


class Backend:
    def __init__(self, binary: Path, memory_mb: int, timeout: int):
        def limit_memory() -> None:
            if os.name == "posix":
                import resource
                size = memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (size, size))

        self.timeout = timeout
        self.reader = ThreadPoolExecutor(max_workers=1) if os.name != "posix" else None
        self.process = subprocess.Popen(
            [str(binary), "--api"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
            preexec_fn=limit_memory if os.name == "posix" else None,
        )

    def request(self, action: str, **fields: str):
        assert self.process.stdin and self.process.stdout
        self.process.stdin.write(json.dumps({"action": action, **fields}, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        if self.reader is None:
            ready, _, _ = select.select([self.process.stdout], [], [], self.timeout)
            if not ready:
                raise TimeoutError(f"{action} tardó más de {self.timeout} segundos")
            line = self.process.stdout.readline()
        else:
            try:
                line = self.reader.submit(self.process.stdout.readline).result(timeout=self.timeout)
            except TimeoutError as exc:
                raise TimeoutError(f"{action} tardó más de {self.timeout} segundos") from exc
        if not line:
            raise RuntimeError(f"Backend terminó en {action}: {self.process.stderr.read()}")
        response = json.loads(line)
        if not response["ok"]:
            raise RuntimeError(f"{action}: {response['error']}")
        return response["result"]

    def peak_kib(self) -> int | None:
        status = Path(f"/proc/{self.process.pid}/status")
        if status.exists():
            for line in status.read_text().splitlines():
                if line.startswith("VmHWM:"):
                    return int(line.split()[1])
        return None

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.request("shutdown")
                self.process.wait(timeout=3)
            except (OSError, RuntimeError, TimeoutError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait()
        if self.reader is not None:
            self.reader.shutdown(wait=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--products", type=int, default=20000)
    parser.add_argument("--people", type=int, default=1000)
    parser.add_argument("--links", type=int, default=20000)
    parser.add_argument("--jobs", type=int, default=0, help="Trabajos pendientes en la cola")
    parser.add_argument("--memory-mb", type=int, default=768)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--edits", type=int, default=30, help="Ediciones consecutivas con deshacer")
    parser.add_argument("--check-import", action="store_true", help="También importar y deshacer el CSV de productos")
    args = parser.parse_args()
    if min(args.products, args.people, args.memory_mb, args.timeout) < 1 or min(args.links, args.edits, args.jobs) < 0:
        parser.error("Los tamaños y límites deben ser positivos")
    if args.jobs > args.products:
        parser.error("--jobs no puede superar --products")
    if args.links > args.products * args.people:
        parser.error("--links supera las parejas únicas posibles")
    binary = args.binary.resolve()
    if not binary.is_file():
        parser.error(f"No existe {binary}")
    with tempfile.TemporaryDirectory(prefix="pea-stress-") as folder:
        data = Path(folder) / "input"
        data.mkdir()
        started = time.perf_counter()
        make_data(data, args.products, args.people, args.links, args.jobs)
        print(f"CSV generados en {time.perf_counter() - started:.2f} s", flush=True)
        backend = Backend(binary, args.memory_mb, args.timeout)
        try:
            started = time.perf_counter()
            backend.request("load", path=str(data))
            print(f"Carga: {time.perf_counter() - started:.2f} s; pico: {backend.peak_kib()} KiB", flush=True)
            page = backend.request("page", kind="productos", offset=str(max(0, args.products - 100)), limit="100")
            assert page["total"] == args.products and 1 <= len(page["rows"]) <= 100
            stats = backend.request("statistics", view="Todos", selected="", limit="100")
            assert stats["total"] == args.products and len(stats["productos"]) == min(100, args.products)
            summary = backend.request("summary")
            assert summary["active_people"] == args.people
            assert backend.request("queue_page", limit="1")["total"] == args.jobs
            backend.request("create", kind="productos", values=json.dumps(
                {"id": "P-STRESS-NEW", "titulo": "Creado en prueba", "doi": "10.1234/stress-new"}))
            assert backend.request("undo") is True
            assert backend.request("get", kind="productos", key="P-STRESS-NEW") is None
            started = time.perf_counter()
            for index in range(args.edits):
                backend.request("update", kind="productos", key="P-0000000",
                                values=json.dumps({"titulo": f"Editado {index}"}))
            for _ in range(args.edits):
                assert backend.request("undo") is True
            assert backend.request("get", kind="productos", key="P-0000000")["titulo"] == "Producto 0"
            print(f"{args.edits} ediciones y deshacer: {time.perf_counter() - started:.2f} s; "
                  f"pico: {backend.peak_kib()} KiB", flush=True)
            saved = Path(folder) / "saved"
            started = time.perf_counter()
            backend.request("save", path=str(saved))
            print(f"Guardado: {time.perf_counter() - started:.2f} s; pico: {backend.peak_kib()} KiB", flush=True)
        finally:
            backend.close()
        reopened = Backend(binary, args.memory_mb, args.timeout)
        try:
            started = time.perf_counter()
            reopened.request("load", path=str(saved))
            assert reopened.request("statistics", view="Todos", selected="", limit="1")["total"] == args.products
            assert reopened.request("queue_page", limit="1")["total"] == args.jobs
            print(f"Reapertura: {time.perf_counter() - started:.2f} s; pico: {reopened.peak_kib()} KiB", flush=True)
        finally:
            reopened.close()
        if args.check_import:
            importer = Backend(binary, args.memory_mb, args.timeout)
            try:
                source = data / "productos.csv"
                started = time.perf_counter()
                preview = importer.request("preview_csv", kind="productos", path=str(source))
                assert preview["accepted"] == args.products
                imported = importer.request("import_csv", kind="productos", path=str(source))
                assert imported["accepted"] == args.products
                assert importer.request("undo") is True
                assert importer.request("page", kind="productos", limit="1")["total"] == 0
                print(f"Vista previa, importación y deshacer: {time.perf_counter() - started:.2f} s; "
                      f"pico: {importer.peak_kib()} KiB", flush=True)
            finally:
                importer.close()


if __name__ == "__main__":
    main()

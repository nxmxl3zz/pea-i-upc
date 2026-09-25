"""Rellena la categoría CvLAC de los investigadores desde sus fichas individuales.

La importación de UPC solo descargó las fichas GrupLAC de los grupos; la
categoría del investigador ("Investigador Junior/Senior/Asociado...") vive en su
ficha CvLAC. Este script visita cada URL CvLAC ya registrada y copia el campo
"categoria". La afiliación y el contacto no aparecen en la ficha CvLAC pública,
así que quedan intactos (vacíos).
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
pea = runpy.run_path(str(ROOT / "src" / "python" / "Taller2_REMR.py"))

fetch_web_page = pea["fetch_web_page"]
read_csv = pea["_csv_read"]
write_csv = pea["_csv_write"]
fields = pea["ALL_FIELDS"]["investigadores"]


def resolve(row: dict[str, str]) -> tuple[str, str]:
    url = row["url"].strip()
    if not url:
        return row["id"], ""
    try:
        preview = fetch_web_page(url)
    except Exception:
        return row["id"], ""
    if preview.suggested_kind == "investigadores" and preview.suggested_row:
        return row["id"], preview.suggested_row.get("categoria", "").strip()
    return row["id"], ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Rellenar categoría CvLAC de investigadores")
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "real" / "investigadores.csv")
    parser.add_argument("--limit", type=int, help="Máximo de perfiles a consultar (pruebas)")
    parser.add_argument("--workers", type=int, default=6, help="Descargas simultáneas")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit debe ser positivo")
    if args.workers < 1 or args.workers > 16:
        parser.error("--workers debe estar entre 1 y 16")

    path = args.input
    rows = read_csv(path, fields, encoded=True)

    pending = [row for row in rows if not row["categoria"].strip() and row["url"].strip()]
    if args.limit:
        pending = pending[: args.limit]
    print(f"Perfiles por consultar: {len(pending)} de {len(rows)}", flush=True)

    updated = 0
    failures = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(resolve, row): row for row in pending}
        for index, future in enumerate(as_completed(futures), start=1):
            row = futures[future]
            _, categoria = future.result()
            if categoria:
                row["categoria"] = categoria
                updated += 1
            else:
                failures += 1
            if index % 100 == 0:
                print(f"[{index}/{len(pending)}] actualizados={updated} sin-categoría/fallos={failures}", flush=True)

    if updated:
        temporary = path.with_name(path.name + ".tmp")
        try:
            write_csv(temporary, fields, rows)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"\nActualizados: {updated} | sin categoría o fallo: {failures}", flush=True)


if __name__ == "__main__":
    main()

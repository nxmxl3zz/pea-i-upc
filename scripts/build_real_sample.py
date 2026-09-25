"""Rebuild data/real from the two public Scienti URLs in the assignment.

For repeatable offline review, pass --group-html and --researcher-html with
previously downloaded HTML files from those exact URLs.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import runpy


ROOT = Path(__file__).resolve().parents[1]
pea = runpy.run_path(str(ROOT / "src" / "python" / "Taller2_REMR.py"))
GROUP_URL = "https://scienti.minciencias.gov.co/gruplac/jsp/visualiza/visualizagr.jsp?nro=00000000002099"
RESEARCHER_URL = "https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000494917"


def preview(url: str, cached_html: Path | None):
    if cached_html is None:
        return pea["fetch_web_page"](url)
    raw = cached_html.read_bytes()
    match = re.search(rb"charset\s*=\s*['\"]?([A-Za-z0-9_-]+)", raw[:5000], re.IGNORECASE)
    charset = match.group(1).decode("ascii") if match else "utf-8"
    return pea["parse_web_page"](raw.decode(charset), url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear muestra UPC desde fichas públicas de Scienti")
    parser.add_argument("--group-html", type=Path, help="HTML GrupLAC ya descargado")
    parser.add_argument("--researcher-html", type=Path, help="HTML CvLAC ya descargado")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "sample_scienti", help="Carpeta CSV de salida")
    args = parser.parse_args()
    group_page = preview(GROUP_URL, args.group_html)
    researcher_page = preview(RESEARCHER_URL, args.researcher_html)
    if group_page.suggested_kind != "grupos" or researcher_page.suggested_kind != "investigadores":
        parser.error("Una de las fichas públicas no se pudo identificar")
    if not group_page.related_members or not group_page.related_products:
        parser.error("La ficha GrupLAC no contiene el censo o los productos esperados")

    repo = pea["Repository"]()
    group = group_page.suggested_row
    researcher = researcher_page.suggested_row
    repo.create("grupos", group, remember=False)
    member_ids = {person["id"] for person, _ in group_page.related_members}
    if researcher["id"] not in member_ids:
        parser.error("El perfil CvLAC no figura en el censo del grupo")
    for person, _ in group_page.related_members:
        if person["id"] == researcher["id"]:
            roster_source = person["fuente"]
            person = {**person, **{key: value for key, value in researcher.items() if value}}
            person["fuente"] = f"{roster_source}; {researcher['fuente']}"
        repo.create("investigadores", person, remember=False)
    if group_page.related_plan:
        repo.create("planes", group_page.related_plan, remember=False)
    for _, membership in group_page.related_members:
        repo.create("membresias", membership, remember=False)
    for product in group_page.related_products:
        repo.create("productos", product, remember=False)
        repo.create("grupos_productos", {
            "grupo_id": group["id"], "producto_id": product["id"],
            "origen": "GrupLAC: producto listado en la ficha",
        }, remember=False)
    for authorship in group_page.related_authorships:
        repo.create("autorias", authorship, remember=False)
    pea["save_repository"](repo, args.output)
    print(f"Guardado en {args.output}: {len(repo.rows('investigadores'))} investigadores, "
          f"{len(repo.rows('membresias'))} membresías, {len(repo.rows('planes'))} planes, "
          f"{len(repo.rows('productos'))} productos y {len(repo.rows('autorias'))} autorías")


if __name__ == "__main__":
    main()

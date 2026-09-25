"""Importa el conjunto completo de grupos de la Universidad Popular del Cesar.

Enumeración obtenida de la búsqueda pública "Ciencia y Tecnología para Todos"
(busquedaGrupoXInstitucionGrupos.do?codInst=947), Convocatoria 957 de 2024.
Cada grupo se descarga desde su ficha GrupLAC pública y se incorpora con el
mismo motor de importación que usa la interfaz (import_gruplac_preview), pero
con el historial desactivado para que la carga masiva no sea cuadrática.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
pea = runpy.run_path(str(ROOT / "src" / "python" / "Taller2_REMR.py"))

DataError = pea["DataError"]
Repository = pea["Repository"]
clean_row = pea["clean_row"]
fetch_web_page = pea["fetch_web_page"]
save_repository = pea["save_repository"]

GROUP_URL = "https://scienti.minciencias.gov.co/gruplac/jsp/visualiza/visualizagr.jsp?nro={nro}"

# (nro, nombre) de los 66 grupos UPC, Convocatoria 957 de 2024.
GROUPS: list[tuple[str, str]] = [
    ('00000000020734', 'Sierra Nevada de Santa Marta'),
    ('00000000001901', 'Grupo de investigacion ZooBios.'),
    ('00000000016636', 'GESTIÓN EN INVESTIGACIÓN,  PRODUCCIÓN Y TRANSFORMACIÓN AGROINDUSTRIAL (GIPTA)'),
    ('00000000024291', 'Investiguemos en Instrumentación Quirúrgica (INVIQ)'),
    ('00000000024297', 'Ars Scribendi: investigación en estudios literarios y pedagógicos'),
    ('00000000024259', 'Grupo de Investigación en Producción Sostenible de las Ciencias Agropecuarias'),
    ('00000000018873', 'SALUD Y BIENESTAR PARA EL SER HUMANO EN SU ENTORNO (SBSHE)'),
    ('00000000017356', 'Grupo de Investigación Educativa en Ciencias Naturales y Matemática ECINAMA'),
    ('00000000023954', 'MUEVETE_UPECISTA'),
    ('00000000018949', 'GESTIÓN AMBIENTAL Y TERRITORIOS SOSTENIBLES  (GE&TES)'),
    ('00000000020417', 'GRUPO DE INVESTIGACION BUTERAMA'),
    ('00000000016202', 'Grupo de Investigación en Matemática Educativa- DELTA'),
    ('00000000023779', 'Acepciones del Derecho y la Administración Pública'),
    ('00000000024331', 'Lecturas del territorio'),
    ('00000000018897', 'PEDAGOGÍA Y EDUCACIÓN EN SALUD (PES)'),
    ('00000000002497', 'GILEHKA'),
    ('00000000017409', 'DSP-ASIC BUILDER GROUP'),
    ('00000000018931', 'CEGOSA Cuidado de Enfermería y Gestión en Organizaciones y Servicios de Salud'),
    ('00000000022105', 'CENTRO DE INVESTIGACIÓN MUSICAL DEL CESAR'),
    ('00000000003161', 'Grupo de Optimización Agroindustrial'),
    ('00000000003202', 'FACEUPC'),
    ('00000000017413', 'GRESBIOCA'),
    ('00000000017566', 'DIDACINNOVACIONCN'),
    ('00000000017467', 'ESTUDIOS SOCIALES EN EL DEPARTAMENTO DEL CESAR'),
    ('00000000023784', 'EKONOLAB'),
    ('00000000023299', 'Grupo de Investigación en Tributación, Ciencias Contables e Información Financiera (TRICOFI)'),
    ('00000000002093', 'Grupo de óptica e informática'),
    ('00000000023799', 'Grupo de Optoelectrónica y Procesamiento de Señales (OPSE)'),
    ('00000000023785', 'Tecnología, educación, salud,  Instrumentación e inclusión y sociedad TESIS'),
    ('00000000017478', 'Biotecnología y Genotoxicidad Ambiental - BiotecGen'),
    ('00000000001883', 'POTENCIALIDAD DIALÓGICA'),
    ('00000000017462', 'Grupo de investigación de desarrollo social y salud GIDESA'),
    ('00000000016815', 'Grupo de investigación literaria  Luis Mizar'),
    ('00000000011723', 'Grupo Interdisciplinario de Investigación en Evaluación'),
    ('00000000023768', 'POLITES (Grupo de investigación socio-jurídico del programa de Derecho UPC)'),
    ('00000000002521', 'Grupo de Energías Ambiente y Biotecnología (GEAB)'),
    ('00000000005792', 'DESAFIO BIOMEDICO Y BIOTECNOLOGICO (DESBIOTEC)'),
    ('00000000015173', 'GINTICS'),
    ('00000000014398', 'CÁTEDRA CARRILLO LUQUEZ'),
    ('00000000017408', 'GRUPO DE INVESTIGACIÓN ARGOS'),
    ('00000000002397', 'Microbiología agrícola y ambiental'),
    ('00000000005564', 'ESTUDIOS SANITARIOS Y AMBIENTALES - E.S.A.'),
    ('00000000009744', 'Grupo de investigación FASAPROIN (facultad de salud con proyección investigativa)'),
    ('00000000009022', 'CINBIOS'),
    ('00000000000900', 'GRUPO INTERDISCIPLINARIO ESTUDIO DEL PENSAMIENTO NUMERICO, POLÍTICAS PÚBLICAS DE CIENCIA Y TECNOLOGÍA, PRODUCCIÓN AGRARIA, MEDIO AMBIENTE, Y PROBLEMATICA DE LA EDUCACION LATINOAMERICANA Y DEL CARIBE'),
    ('00000000020413', 'GIDEATIC Grupo de Investigación en Desarrollo y Aplicación de Tecnologías de Información y la Comunicación'),
    ('00000000018778', 'CISATEC-LINE'),
    ('00000000017497', 'OBSERVATORIO DE DESARROLLO ECONÓMICO DEL CESAR - ODECE'),
    ('00000000003915', 'GUATAPURI (Grupo de Investigación y estudios socioculturales)'),
    ('00000000020415', 'ECONFI'),
    ('00000000015180', 'Grupo de Investigacion en Biotecnologia, Ingenieria y Salud'),
    ('00000000002099', 'GRUPO DE INVESTIGACION EN SISTEMAS Y COMPUTACIÓN -GISICO-'),
    ('00000000007152', 'CREANDO CIENCIAS "CRECI"'),
    ('00000000014742', 'TC-Psi'),
    ('00000000001307', 'Grupo de Espectroscopia  Optica y Laser'),
    ('00000000018935', 'Mente Lila'),
    ('00000000002668', 'AITICE'),
    ('00000000003639', 'GIELEHLA'),
    ('00000000017498', 'Investigarte'),
    ('00000000002681', 'PARASITOLOGIA - AGROECOLOGIA MILENIO'),
    ('00000000024277', 'EQUIPO DE INVESTIGACIÓN EN DESARROLLO Y GESTIÓN AVANZADA (EIDGA)'),
    ('00000000022006', 'GRUPO INTERDISCIPLINARIO ORGANIZACION SOCIEDAD, EDUCACION Y CULTURA PARA LA PAZ'),
    ('00000000001727', '(BIAT) BIOTECNOLOGIA E INNOVACION AGROINDUSTRIAL TROPICAL'),
    ('00000000017495', 'APOLO INFINITO'),
    ('00000000002103', 'CONTROL DE CALIDAD DE LOS PROCESOS EN SALUD'),
    ('00000000024231', 'Grupo de Investigación de aplicación de las TIC en la educación y sector productivo'),
]


def import_group(repo: Repository, preview) -> dict:
    """Equivalente a import_gruplac_preview, pero con historial desactivado.

    El motor de la interfaz registra un snapshot completo en cada alta para
    poder deshacer; en una carga masiva eso es cuadrático, así que aquí se
    repite la misma lógica de fusión llamando a create(..., remember=False).
    """
    if preview.suggested_kind != "grupos" or not preview.suggested_row:
        raise DataError("La ficha no contiene un grupo")
    source_group = preview.suggested_row
    group = clean_row("grupos", source_group)
    if group["codigo_gruplac"] != source_group["codigo_gruplac"]:
        raise DataError("El código GrupLAC revisado no coincide con la fuente")
    group_id = group["id"]
    counts = {kind: 0 for kind in (
        "grupos", "investigadores", "membresias", "planes", "productos", "grupos_productos", "autorias")}
    counts["existentes"] = 0
    counts["errors"] = []

    def add(kind: str, row: dict, key) -> bool:
        existing = repo.get(kind, key)
        if existing is not None:
            if kind == "grupos" and existing["codigo_gruplac"] != source_group["codigo_gruplac"]:
                counts["errors"].append(f"{kind} {key}: ID ocupado por otro grupo")
                return False
            if kind == "investigadores" and existing["codigo_cvlac"] != row["codigo_cvlac"]:
                counts["errors"].append(f"{kind} {key}: ID ocupado por otro perfil")
                return False
            if kind == "productos" and (existing["titulo"] != row["titulo"] or existing["anio"] != row["anio"]):
                counts["errors"].append(f"{kind} {key}: ID ocupado por otro producto")
                return False
            counts["existentes"] += 1
            return True
        try:
            repo.create(kind, row, remember=False)
        except (DataError, OSError, ValueError) as exc:
            counts["errors"].append(f"{kind} {key}: {exc}")
            return False
        counts[kind] += 1
        return True

    if not add("grupos", group, group_id):
        return counts
    available_people = set()
    for person, _ in preview.related_members:
        if add("investigadores", person, person["id"]):
            available_people.add(person["id"])
    if preview.related_plan:
        add("planes", {**preview.related_plan, "grupo_id": group_id}, preview.related_plan["id"])
    for person, membership in preview.related_members:
        if person["id"] in available_people:
            add("membresias", {**membership, "grupo_id": group_id}, (group_id, person["id"]))
    available_products = set()
    for product in preview.related_products:
        if add("productos", product, product["id"]):
            available_products.add(product["id"])
    for product in preview.related_products:
        if product["id"] in available_products:
            add("grupos_productos", {
                "grupo_id": group_id, "producto_id": product["id"],
                "origen": "GrupLAC: producto listado en la ficha",
            }, (group_id, product["id"]))
    for authorship in preview.related_authorships:
        product_id, researcher_id = authorship["producto_id"], authorship["investigador_id"]
        if product_id in available_products and researcher_id in available_people:
            add("autorias", authorship, (product_id, researcher_id))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Importar los 66 grupos UPC desde sus fichas GrupLAC")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "real",
                        help="Carpeta CSV de salida")
    parser.add_argument("--limit", type=int, help="Máximo de grupos a importar (para pruebas)")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit debe ser positivo")
    if args.limit and args.output.resolve() == (ROOT / "data" / "real").resolve():
        parser.error("--limit requiere --output para no reemplazar el conjunto completo")

    repo = Repository()
    totals = {kind: 0 for kind in ("grupos", "investigadores", "membresias", "planes",
                                   "productos", "grupos_productos", "autorias")}
    failures: list[tuple[str, str]] = []
    for index, (nro, name) in enumerate(GROUPS[:args.limit] if args.limit else GROUPS, start=1):
        url = GROUP_URL.format(nro=nro)
        try:
            preview = fetch_web_page(url)
            counts = import_group(repo, preview)
        except (DataError, OSError, ValueError) as exc:
            failures.append((name, str(exc)))
            print(f"[{index:2d}/{len(GROUPS)}] FALLO  {name}: {exc}")
            continue
        for kind in totals:
            totals[kind] += counts[kind]
        print(f"[{index:2d}/{len(GROUPS)}] OK     {name}  "
              f"(investigadores +{counts['investigadores']}, productos +{counts['productos']})")
        if counts["errors"]:
            for error in counts["errors"][:5]:
                print(f"          - {error}")
            failures.append((name, f"{len(counts['errors'])} registros o vínculos rechazados"))

    if failures:
        print(f"\n{len(failures)} grupo(s) con importación incompleta; no se reemplazó {args.output}:")
        for name, reason in failures:
            print(f"  - {name}: {reason}")
        raise SystemExit(1)

    save_repository(repo, args.output)
    print(f"\nGuardado en {args.output}:")
    for kind in ("grupos", "investigadores", "membresias", "planes",
                 "productos", "grupos_productos", "autorias"):
        print(f"  {kind}: {totals[kind]}")


if __name__ == "__main__":
    main()

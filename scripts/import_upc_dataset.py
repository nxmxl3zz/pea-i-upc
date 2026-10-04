"""Actualiza el archivo de datos con los grupos de la Universidad Popular del Cesar.

Enumeración obtenida de la búsqueda pública "Ciencia y Tecnología para Todos"
(busquedaGrupoXInstitucionGrupos.do?codInst=947), Convocatoria 957 de 2024.
Cada grupo se descarga desde su ficha GrupLAC pública y se fusiona en el archivo
existente con el mismo motor de importación que usa la interfaz
(import_gruplac_preview): agrega lo nuevo, actualiza lo que la fuente cambió y no
borra nada. El historial se desactiva para que la carga masiva no sea cuadrática.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
pea = runpy.run_path(str(ROOT / "src" / "python" / "Taller2_REMR.py"))

DataError = pea["DataError"]
Repository = pea["Repository"]
fetch_web_page = pea["fetch_web_page"]
import_gruplac_preview = pea["import_gruplac_preview"]
load_repository = pea["load_repository"]
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Actualizar el archivo de datos con los 66 grupos UPC de GrupLAC")
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "pea_upc.csv",
                        help="Archivo de datos que se actualiza (se crea si no existe)")
    parser.add_argument("--limit", type=int, help="Máximo de grupos a consultar (para pruebas)")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit debe ser positivo")

    repo = load_repository(args.data) if args.data.exists() else Repository()
    kinds = ("grupos", "investigadores", "membresias", "planes", "productos", "grupos_productos", "autorias")
    added = {kind: 0 for kind in kinds}
    updated = 0
    failures: list[tuple[str, str]] = []
    selected = GROUPS[:args.limit] if args.limit else GROUPS
    for index, (nro, name) in enumerate(selected, start=1):
        url = GROUP_URL.format(nro=nro)
        try:
            preview = fetch_web_page(url)
            counts = import_gruplac_preview(repo, preview, remember=False)
        except (DataError, OSError, ValueError) as exc:
            failures.append((name, str(exc)))
            print(f"[{index:2d}/{len(selected)}] FALLO  {name}: {exc}")
            continue
        for kind in kinds:
            added[kind] += counts[kind]
        updated += counts["actualizados"]
        print(f"[{index:2d}/{len(selected)}] OK     {name}  (nuevos: {sum(counts[kind] for kind in kinds)}, "
              f"actualizados: {counts['actualizados']})")
        if counts["errors"]:
            for error in counts["errors"][:5]:
                print(f"          - {error}")
            failures.append((name, f"{len(counts['errors'])} registros o vínculos rechazados"))

    # Fusionar nunca borra: los grupos que fallaron conservan sus datos anteriores.
    if updated or any(added.values()) or not args.data.exists():
        save_repository(repo, args.data)
    print(f"\nArchivo {args.data}: {updated} registros actualizados; nuevos:")
    for kind in kinds:
        print(f"  {kind}: {added[kind]}")
    if failures:
        print(f"\n{len(failures)} grupo(s) con importación incompleta (se conservan sus datos anteriores):")
        for name, reason in failures:
            print(f"  - {name}: {reason}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

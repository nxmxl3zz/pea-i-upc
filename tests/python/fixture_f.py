"""Fixture F del modelo 2024, compartida por las pruebas de ambos motores."""


def populate(repo) -> None:
    for group_id, created in (("G1", "2010-01-01"), ("G2", "2025-03-01")):
        repo.create("grupos", {"id": group_id, "nombre": group_id, "fecha_creacion": created})
    for researcher_id in ("I1", "I2", "I3"):
        repo.create("investigadores", {"id": researcher_id, "nombre": researcher_id})
    for group_id, researcher_id in (("G1", "I1"), ("G1", "I2"), ("G2", "I3"), ("G2", "I1")):
        repo.create("membresias", {"grupo_id": group_id, "investigador_id": researcher_id})
    for product_id, year, category, authors, group_id in (
        ("P1", "2025", "ART_D", ("I1", "I2"), "G1"),
        ("P2", "2024", "ART_D", ("I1",), "G1"),
        ("P3", "2021", "LIB_B", ("I2",), "G1"),
        ("P4", "2026", "ART_D", ("I3",), "G2"),
        ("P5", "2019", "SF", ("I1",), "G1"),
        ("P6", "2025", "", ("I1",), "G1"),
        ("P7", "2023", "WP", ("I3",), "G2"),
        ("P8", "2025", "WP", ("I1",), "G1"),
    ):
        repo.create("productos", {"id": product_id, "titulo": product_id, "anio": year,
                                  "tipologia": "Prueba", "categoria": category})
        for researcher_id in authors:
            repo.create("autorias", {"producto_id": product_id, "investigador_id": researcher_id})
        repo.create("grupos_productos", {"grupo_id": group_id, "producto_id": product_id})

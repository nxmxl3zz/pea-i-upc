"""Comprueba que Tkinter puede delegar operaciones reales al proceso C++."""

import importlib.util
import csv
from pathlib import Path
import sys
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pea", ROOT / "src/python/Taller2_REMR.py")
pea = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pea)


def write_folder(repo, path: Path, version: str) -> None:
    """Carpeta anterior al archivo único, con un CSV por tabla como en las versiones 1 a 3."""
    path.mkdir(parents=True, exist_ok=True)
    tables = {"manifest": [{"version": version, "guardado": "2026-09-24T00:00:00"}],
              **{kind: repo.rows(kind) for kind in pea.ALL_FIELDS},
              "cola_validacion": list(repo.queue), "historial": []}
    for name, rows in tables.items():
        fields = pea.DATA_SECTIONS[name]
        with (path / f"{name}.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(fields)
            writer.writerows([pea._storage_cell(row.get(field, "")) for field in fields] for row in rows)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python3 tests/integration/check_backend.py build/pea_cpp")
    binary = Path(sys.argv[1]).resolve()
    backend = pea.CppRepository(binary)
    fixture = tempfile.TemporaryDirectory(prefix="pea-backend-fixture-")
    try:
        demo = Path(fixture.name) / "demo.csv"
        subprocess.run([sys.executable, str(ROOT / "scripts/build_demo.py"),
                        "--output", str(demo)], check=True, capture_output=True, text=True)
        backend.load(demo)
        assert backend.statistics()["total"] == 4
        assert backend.page("productos", limit=2)["total"] == 4
        assert len(backend.page("productos", limit=2)["rows"]) == 2
        assert backend.summary()["active_people"] == 3
        assert backend.statistics(start=2025, end=2026)["total"] == 2
        assert len(backend.related("grupos_productos", "G-DEMO-1", "left")) == 3
        assert backend.queue_size() == 2
        assert backend.queue_front()["producto_id"] == "P-DEMO-2"
        assert backend.suggest_id("productos").startswith("P-")

        assert backend.statistics(limit=0)["por_validacion"] == {"validado": 3, "rechazado": 1}
        assert backend.statistics(status="rechazado", limit=0)["por_regla"] == {"fuente": 1}
        done = backend.process_review("Aprobado desde Tkinter")
        assert done["validacion"] == "validado"
        assert backend.get("productos", "P-DEMO-2")["observacion"] == "Aprobado desde Tkinter"
        assert backend.queue_size() == 1
        assert backend.undo()
        assert backend.get("productos", "P-DEMO-2")["observacion"] == ""
        assert backend.queue_size() == 2
        assert backend.enqueue_rejected() == 1 and backend.queue_size() == 3
        assert backend.undo() and backend.queue_size() == 2

        backend.reset()
        backend.create("grupos", {"id": "G-B", "nombre": "Grupo interfaz"})
        backend.create("investigadores", {"id": "I-B", "nombre": "Investigadora"})
        backend.create("productos", {"id": "P-B", "titulo": "Acción, línea\nsegunda", "anio": "2025"})
        backend.create("membresias", {"grupo_id": "G-B", "investigador_id": "I-B", "rol": "Líder"})
        backend.create("autorias", {"producto_id": "P-B", "investigador_id": "I-B"})
        backend.create("grupos_productos", {"grupo_id": "G-B", "producto_id": "P-B"})
        assert backend.statistics("Grupo", "G-B")["total"] == 1
        assert backend.statistics("Investigador", "I-B")["total"] == 1
        backend.toggle("grupos_productos", ("G-B", "P-B"))
        assert backend.statistics("Grupo", "G-B")["total"] == 0
        backend.toggle("grupos_productos", ("G-B", "P-B"))
        assert backend.get("productos", "P-B")["titulo"] == "Acción, línea\nsegunda"
        assert backend.product_issues("P-B") == ["tipologia", "fuente"]
        assert backend.field_usage("productos")["doi"] == 0
        backend.update("productos", "P-B", {"tipologia": "Artículo", "doi": "10.1234/interfaz"})
        assert backend.get("productos", "P-B")["validacion"] == "validado"
        assert backend.undo() and backend.get("productos", "P-B")["validacion"] == "rechazado"
        try:
            backend.delete("grupos", "G-B")
            raise AssertionError("C++ permitió borrar un grupo con vínculos")
        except pea.DataError:
            pass
        with tempfile.TemporaryDirectory(prefix="pea-backend-") as folder:
            path = Path(folder)
            source = path / "importar.csv"
            with source.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=pea.ALL_FIELDS["productos"])
                writer.writeheader()
                writer.writerow({"id": "P-IMP", "titulo": "Importado", "anio": "2026"})
                writer.writerow({"id": "P-B", "titulo": "Duplicado", "anio": "2026"})
            total, accepted, errors = backend.preview_csv(source, "productos")
            assert (total, accepted, len(errors)) == (2, 1, 1)
            imported, errors = backend.import_csv(source, "productos")
            assert imported == 1 and len(errors) == 1
            assert backend.get("productos", "P-IMP") is not None
            assert backend.undo() and backend.get("productos", "P-IMP") is None
            malformed = path / "malformado.csv"
            with malformed.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=pea.ALL_FIELDS["productos"])
                writer.writeheader()
                writer.writerow({"id": "P-SHOULD-NOT-LOAD", "titulo": "Primera fila válida"})
                stream.write('P-BROKEN,"comilla sin cerrar')
            try:
                backend.import_csv(malformed, "productos")
                raise AssertionError("C++ permitió CSV malformado")
            except pea.DataError:
                pass
            assert backend.get("productos", "P-SHOULD-NOT-LOAD") is None
            invalid_utf8 = path / "codificacion.csv"
            invalid_utf8.write_bytes(
                (",".join(pea.ALL_FIELDS["productos"]) + "\nP-BAD,\xff\n").encode("latin-1"))
            try:
                backend.preview_csv(invalid_utf8, "productos")
                raise AssertionError("C++ permitió un CSV sin UTF-8 válido")
            except pea.DataError:
                pass
            data = path / "datos.csv"
            backend.save(data)
            assert not backend.dirty
            assert sorted(item.name for item in path.iterdir()) == ["codificacion.csv", "datos.csv",
                                                                     "importar.csv", "malformado.csv"]
            loaded = pea.load_repository(data)
            assert loaded.statistics(view="Grupo", selected_id="G-B")["total"] == 1
            assert loaded.get("productos", "P-B")["titulo"] == "Acción, línea\nsegunda"
            backend.update("productos", "P-B", {"observacion": "Revisada"})
            assert backend.history_size() > 0
            backend.save(data)
            assert (path / ".backup" / "datos.csv").is_file()
            reopened = pea.CppRepository(binary)
            python_with_cpp_history = pea.load_repository(data)
            assert python_with_cpp_history.undo()
            assert python_with_cpp_history.get("productos", "P-B")["observacion"] == ""
            try:
                reopened.load(data)
                assert reopened.get("productos", "P-B")["observacion"] == "Revisada"
                assert reopened.undo()
                assert reopened.get("productos", "P-B")["observacion"] == ""
            finally:
                reopened.close()
            backend.create("productos", {"id": "P-FORMULA", "titulo": "=1+1"})
            backend.save(data)
            with data.open(encoding="utf-8", newline="") as stream:
                stored = {record[0]: record for record in csv.reader(stream)}
            assert stored["P-FORMULA"][1] == "'=1+1"
            python_repo = pea.load_repository(data)
            assert python_repo.get("productos", "P-FORMULA")["titulo"] == "=1+1"
            pea.save_repository(python_repo, data)
            backend.load(data)
            assert backend.get("productos", "P-FORMULA")["titulo"] == "=1+1"
    finally:
        backend.close()
        fixture.cleanup()
    assert backend.process.poll() is not None
    with tempfile.TemporaryDirectory(prefix="pea-legacy-") as folder:
        path = Path(folder)
        old = pea.Repository()
        old.create("grupos", {"id": "G-OLD", "nombre": "Grupo anterior"}, remember=False)
        old.create("productos", {"id": "P-OLD", "titulo": "Producto anterior"}, remember=False)
        write_folder(old, path, "1")
        groups = pea._csv_read(path / "grupos.csv", pea.ENTITY_FIELDS["grupos"], encoded=True)
        with (path / "grupos.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=("id", "nombre", "sigla", *pea.ENTITY_FIELDS["grupos"][2:]))
            writer.writeheader()
            writer.writerows(groups)
        products = pea._csv_read(path / "productos.csv", pea.ENTITY_FIELDS["productos"], encoded=True)
        with (path / "productos.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=tuple(
                field for field in pea.ENTITY_FIELDS["productos"] if field != "validacion"), extrasaction="ignore")
            writer.writeheader()
            writer.writerows(products)
        (path / "cola_validacion.csv").unlink()
        legacy = pea.CppRepository(binary)
        try:
            legacy.load(path)
            assert legacy.get("productos", "P-OLD")["validacion"] == "rechazado"
            assert legacy.product_issues("P-OLD") == ["anio", "tipologia", "autor", "grupo", "fuente"]
            converted = path / "datos.csv"
            legacy.save(converted)
            assert pea.load_repository(converted).get("grupos", "G-OLD")["nombre"] == "Grupo anterior"
            legacy.load(path / "manifest.csv")
            assert legacy.get("productos", "P-OLD")["validacion"] == "rechazado"
        finally:
            legacy.close()
    with tempfile.TemporaryDirectory(prefix="pea-v2-") as folder:
        path = Path(folder)
        old = pea.Repository()
        old.create("productos", {"id": "P-V2", "titulo": "Producto v2"}, remember=False)
        write_folder(old, path, "2")
        products = pea._csv_read(path / "productos.csv", pea.ENTITY_FIELDS["productos"], encoded=True)
        products[0].update(categoria="B", validacion="pendiente")
        with (path / "productos.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=(*pea.ENTITY_FIELDS["productos"][:6], "categoria",
                                                        *pea.ENTITY_FIELDS["productos"][6:]))
            writer.writeheader()
            writer.writerows(products)
        upgraded = pea.CppRepository(binary)
        try:
            upgraded.load(path)
            expected = pea.load_repository(path).get("productos", "P-V2")
            assert upgraded.get("productos", "P-V2") == expected
            assert expected["observacion"] == "Categoría registrada antes de la versión 3: B"
        finally:
            upgraded.close()
    print("Backend C++ conectado: CRUD, estadísticas, validación, cola, deshacer y CSV.")


if __name__ == "__main__":
    main()

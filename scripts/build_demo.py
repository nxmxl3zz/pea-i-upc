"""Recrea el conjunto ficticio de demostración."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "python" / "Taller2_REMR.py"
SPEC = importlib.util.spec_from_file_location("pea", SOURCE)
pea = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pea)

repo = pea.Repository()
source = "Demostración ficticia; no representa registros de la UPC ni de Scienti"
for row in (
    {"id": "G-DEMO-1", "nombre": "Grupo demostrativo de sistemas", "sigla": "GDS", "categoria": "Ejemplo A", "unidad": "Ingeniería", "objetivos": "Estudiar sistemas de información", "fuente": source},
    {"id": "G-DEMO-2", "nombre": "Grupo demostrativo ambiental", "sigla": "GDA", "categoria": "Ejemplo B", "unidad": "Ciencias", "objetivos": "Estudiar el ambiente", "fuente": source},
):
    repo.create("grupos", row, remember=False)
for row in (
    {"id": "I-DEMO-1", "nombre": "Ana Ejemplo", "afiliacion": "Ficticia", "fuente": source},
    {"id": "I-DEMO-2", "nombre": "Bruno Ejemplo", "afiliacion": "Ficticia", "fuente": source},
    {"id": "I-DEMO-3", "nombre": "Carla Ejemplo", "afiliacion": "Ficticia", "fuente": source},
):
    repo.create("investigadores", row, remember=False)
for row in (
    {"id": "P-DEMO-1", "titulo": "Análisis de redes de prueba", "anio": "2026", "familia": "Nuevo conocimiento", "tipologia": "Artículo", "categoria": "Ejemplo A", "validacion": "validado", "observacion": "Validación de demostración", "fuente": source},
    {"id": "P-DEMO-2", "titulo": "Herramienta educativa de prueba", "anio": "2025", "familia": "Desarrollo tecnológico", "tipologia": "Software", "categoria": "Ejemplo B", "fuente": source},
    {"id": "P-DEMO-3", "titulo": "Libro de muestra, tomo 1", "anio": "2023", "familia": "Nuevo conocimiento", "tipologia": "Libro", "categoria": "Ejemplo B", "fuente": source},
    {"id": "P-DEMO-4", "titulo": "Informe histórico de ejemplo", "anio": "2021", "familia": "Apropiación social", "tipologia": "Informe", "categoria": "Sin categoría", "validacion": "rechazado", "observacion": "Caso ficticio para filtro", "fuente": source},
):
    repo.create("productos", row, remember=False)
for row in (
    {"id": "PL-DEMO-1", "grupo_id": "G-DEMO-1", "nombre": "Plan de sistemas", "inicio": "2025-01-01", "fin": "2027-12-31", "objetivo": "Desarrollar herramientas", "indicador": "Productos publicados", "meta": "3", "actividad": "Investigar y divulgar"},
    {"id": "PL-DEMO-2", "grupo_id": "G-DEMO-2", "nombre": "Plan ambiental", "inicio": "2024-01-01", "fin": "2028-12-31", "objetivo": "Medir impacto ambiental", "indicador": "Informes", "meta": "2", "actividad": "Recolección de datos"},
):
    repo.create("planes", row, remember=False)
for row in (
    {"grupo_id": "G-DEMO-1", "investigador_id": "I-DEMO-1", "rol": "Líder"},
    {"grupo_id": "G-DEMO-1", "investigador_id": "I-DEMO-2", "rol": "Integrante"},
    {"grupo_id": "G-DEMO-2", "investigador_id": "I-DEMO-2", "rol": "Líder"},
    {"grupo_id": "G-DEMO-2", "investigador_id": "I-DEMO-3", "rol": "Integrante"},
):
    repo.create("membresias", row, remember=False)
for row in (
    {"producto_id": "P-DEMO-1", "investigador_id": "I-DEMO-1", "orden": "1"},
    {"producto_id": "P-DEMO-1", "investigador_id": "I-DEMO-2", "orden": "2"},
    {"producto_id": "P-DEMO-2", "investigador_id": "I-DEMO-2", "orden": "1"},
    {"producto_id": "P-DEMO-3", "investigador_id": "I-DEMO-3", "orden": "1"},
    {"producto_id": "P-DEMO-4", "investigador_id": "I-DEMO-1", "orden": "1"},
):
    repo.create("autorias", row, remember=False)
for row in (
    {"grupo_id": "G-DEMO-1", "producto_id": "P-DEMO-1", "origen": source},
    {"grupo_id": "G-DEMO-2", "producto_id": "P-DEMO-1", "origen": source},
    {"grupo_id": "G-DEMO-1", "producto_id": "P-DEMO-2", "origen": source},
    {"grupo_id": "G-DEMO-2", "producto_id": "P-DEMO-3", "origen": source},
    {"grupo_id": "G-DEMO-1", "producto_id": "P-DEMO-4", "origen": source},
):
    repo.create("grupos_productos", row, remember=False)
repo.queue.enqueue({"id": "Q-DEMO-1", "producto_id": "P-DEMO-2", "motivo": "Revisar categoría", "creado": "2026-09-24T09:00:00"})
repo.queue.enqueue({"id": "Q-DEMO-2", "producto_id": "P-DEMO-3", "motivo": "Verificar fuente", "creado": "2026-09-24T09:05:00"})
pea.save_repository(repo, ROOT / "data" / "demo")
print("Demostración creada: 2 grupos, 3 investigadores, 4 productos, 2 revisiones")

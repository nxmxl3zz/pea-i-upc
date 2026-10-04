"""PEA-i UPC: interfaz Tkinter conectada al backend C++.

Ejecutar: python src/python/Taller2_REMR.py [--data ARCHIVO]
Sin --data se abre data/pea_upc.csv, el archivo único con todos los datos.
Con --python-backend se usa la implementación Python independiente de estructuras enlazadas.
La lógica de datos puede probarse sin un servidor gráfico.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime
import hashlib
from html.parser import HTMLParser
import http.client
import io
import ipaddress
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import socket
import subprocess
import tempfile
import threading
from typing import Any, Callable, Iterator, NamedTuple
import unicodedata
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import (HTTPRedirectHandler, HTTPHandler, HTTPSHandler,
                            ProxyHandler, Request, build_opener)
import uuid
import zipfile


# Versión 4: un solo archivo con todas las tablas. Las versiones 1 a 3 eran carpetas con
# un CSV por tabla; se pueden abrir y se guardan como archivo único.
SCHEMA_VERSION = "4"
FOLDER_VERSIONS = ("1", "2", "3")
ENTITY_FIELDS = {
    "grupos": ("id", "nombre", "codigo_gruplac", "fecha_creacion", "unidad", "responsable", "categoria", "descripcion", "objetivos", "mision", "vision", "lineas", "url", "fuente", "activo"),
    "investigadores": ("id", "nombre", "codigo_cvlac", "afiliacion", "categoria", "contacto", "url", "fuente", "activo"),
    "productos": ("id", "titulo", "anio", "fecha", "familia", "tipologia", "validacion", "observacion", "doi", "url", "fuente", "activo"),
    "planes": ("id", "grupo_id", "nombre", "inicio", "fin", "objetivo", "indicador", "meta", "actividad", "activo"),
}
RELATION_FIELDS = {
    "membresias": ("grupo_id", "investigador_id", "rol", "inicio", "fin", "activo"),
    "autorias": ("producto_id", "investigador_id", "orden", "rol", "activo"),
    "grupos_productos": ("grupo_id", "producto_id", "origen", "activo"),
}
RELATION_ENDS = {
    "membresias": ("grupo_id", "investigador_id", "grupos", "investigadores"),
    "autorias": ("producto_id", "investigador_id", "productos", "investigadores"),
    "grupos_productos": ("grupo_id", "producto_id", "grupos", "productos"),
}
ALL_FIELDS = {**ENTITY_FIELDS, **RELATION_FIELDS}
MANIFEST_FIELDS = ("version", "guardado")
QUEUE_FIELDS = ("id", "producto_id", "motivo", "creado")
HISTORY_FIELDS = ("orden", "snapshot")
# Secciones del archivo único en el orden de lectura: cada relación aparece después de
# las entidades que enlaza, así que puede crearse en cuanto se lee.
DATA_SECTIONS = {"manifest": MANIFEST_FIELDS, **ALL_FIELDS,
                 "cola_validacion": QUEUE_FIELDS, "historial": HISTORY_FIELDS}
PAGE_SIZE = 100
REQUIRED = {
    "grupos": ("id", "nombre"), "investigadores": ("id", "nombre"),
    "productos": ("id", "titulo"), "planes": ("id", "grupo_id", "nombre"),
}
LABELS = {
    "id": "ID", "nombre": "Nombre", "codigo_gruplac": "Código GrupLAC",
    "fecha_creacion": "Fecha de creación", "unidad": "Unidad académica", "responsable": "Responsable",
    "categoria": "Categoría", "descripcion": "Descripción", "objetivos": "Objetivos",
    "mision": "Misión", "vision": "Visión", "lineas": "Líneas", "url": "URL",
    "fuente": "Fuente", "activo": "Activo", "codigo_cvlac": "Código CvLAC",
    "afiliacion": "Afiliación", "contacto": "Contacto público", "titulo": "Título",
    "anio": "Año", "fecha": "Fecha", "familia": "Familia", "tipologia": "Tipología",
    "validacion": "Validación", "observacion": "Observación", "doi": "DOI",
    "grupo_id": "Grupo (ID)", "investigador_id": "Investigador (ID)",
    "producto_id": "Producto (ID)", "inicio": "Inicio", "fin": "Fin",
    "objetivo": "Objetivo", "indicador": "Indicador", "meta": "Meta",
    "actividad": "Actividad", "rol": "Rol", "orden": "Orden",
    "origen": "Origen de asociación",
}
# Validación automática de productos. El orden de los códigos es parte del contrato
# con el backend C++: ambos motores devuelven las mismas reglas en el mismo orden.
VALIDATION_RULES = {
    "anio": "Sin año de publicación",
    "tipologia": "Sin tipología",
    "autor": "Sin autor activo registrado",
    "grupo": "Sin grupo activo asociado",
    "doi": "DOI con formato inválido",
    "fuente": "Sin fuente verificable (URL o DOI)",
}
VALIDATION_STATES = ("validado", "rechazado")
# Motivo de cola generado por la validación: "reglas:" seguido de códigos separados por comas.
AUTO_REASON_PREFIX = "reglas:"
LONG_FIELDS = {"descripcion", "objetivos", "mision", "vision", "lineas", "observacion", "objetivo", "indicador", "meta", "actividad", "fuente"}
MAX_FIELD_LEN = 100_000
MAX_CSV_ROWS = 500_000
MAX_PDF_TEXT = 5_000_000
MAX_PDF_MEMORY = 512 * 1024 * 1024
PDF_TIMEOUT = 25
MAX_LOCAL_FILE = 32 * 1024 * 1024
MAX_ARCHIVE_UNPACKED = 128 * 1024 * 1024
DEFAULT_DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "pea_upc.csv"


class DataError(ValueError):
    """Dato inválido o relación que rompería la integridad."""


class ListNode:
    def __init__(self, value: dict[str, str]):
        self.value = value
        self.prev: ListNode | None = None
        self.next: ListNode | None = None


class DoublyLinkedList:
    """Lista fuente de verdad para entidades; índices auxiliares no la reemplazan."""

    def __init__(self) -> None:
        self.head: ListNode | None = None
        self.tail: ListNode | None = None
        self.length = 0
        self.by_id: dict[str, ListNode] = {}

    def append(self, value: dict[str, str]) -> None:
        key = value["id"]
        if key in self.by_id:
            raise DataError(f"ID duplicado: {key}")
        node = ListNode(value)
        node.prev = self.tail
        if self.tail:
            self.tail.next = node
        else:
            self.head = node
        self.tail = node
        self.by_id[key] = node
        self.length += 1

    def get(self, key: str) -> dict[str, str] | None:
        node = self.by_id.get(key)
        return node.value if node else None

    def remove(self, key: str) -> dict[str, str]:
        node = self.by_id.pop(key, None)
        if node is None:
            raise DataError(f"No existe ID {key}")
        if node.prev:
            node.prev.next = node.next
        else:
            self.head = node.next
        if node.next:
            node.next.prev = node.prev
        else:
            self.tail = node.prev
        self.length -= 1
        return node.value

    def __iter__(self) -> Iterator[dict[str, str]]:
        node = self.head
        while node:
            yield node.value
            node = node.next

    def backwards(self) -> Iterator[dict[str, str]]:
        node = self.tail
        while node:
            yield node.value
            node = node.prev


class RelationNode:
    def __init__(self, left: str, right: str, value: dict[str, str]):
        self.left = left
        self.right = right
        self.value = value
        self.next_left: RelationNode | None = None
        self.next_right: RelationNode | None = None


class MultiList:
    """Cada vínculo pertenece simultáneamente a dos cadenas de recorrido."""

    def __init__(self, left_field: str, right_field: str) -> None:
        self.left_field = left_field
        self.right_field = right_field
        self.left_heads: dict[str, RelationNode] = {}
        self.right_heads: dict[str, RelationNode] = {}
        self.by_pair: dict[tuple[str, str], RelationNode] = {}

    def add(self, row: dict[str, str]) -> None:
        left, right = row[self.left_field], row[self.right_field]
        pair = (left, right)
        if pair in self.by_pair:
            raise DataError(f"Relación duplicada: {left} / {right}")
        node = RelationNode(left, right, row)
        node.next_left = self.left_heads.get(left)
        node.next_right = self.right_heads.get(right)
        self.left_heads[left] = node
        self.right_heads[right] = node
        self.by_pair[pair] = node

    def get(self, left: str, right: str) -> dict[str, str] | None:
        node = self.by_pair.get((left, right))
        return node.value if node else None

    def by_left(self, left: str) -> Iterator[dict[str, str]]:
        node = self.left_heads.get(left)
        while node:
            yield node.value
            node = node.next_left

    def by_right(self, right: str) -> Iterator[dict[str, str]]:
        node = self.right_heads.get(right)
        while node:
            yield node.value
            node = node.next_right

    def remove(self, left: str, right: str) -> dict[str, str]:
        node = self.by_pair.pop((left, right), None)
        if not node:
            raise DataError("No existe esa relación")
        previous = None
        current = self.left_heads[left]
        while current is not node:
            previous, current = current, current.next_left
        if previous:
            previous.next_left = node.next_left
        elif node.next_left:
            self.left_heads[left] = node.next_left
        else:
            del self.left_heads[left]
        previous = None
        current = self.right_heads[right]
        while current is not node:
            previous, current = current, current.next_right
        if previous:
            previous.next_right = node.next_right
        elif node.next_right:
            self.right_heads[right] = node.next_right
        else:
            del self.right_heads[right]
        return node.value

    def __iter__(self) -> Iterator[dict[str, str]]:
        for left in self.left_heads:
            yield from self.by_left(left)


class StackNode:
    def __init__(self, value: str, next_node: StackNode | None = None):
        self.value, self.next = value, next_node


class LinkedStack:
    def __init__(self, limit: int = 30) -> None:
        self.top: StackNode | None = None
        self.length = 0
        self.limit = limit

    def push(self, value: str) -> None:
        self.top = StackNode(value, self.top)
        self.length += 1
        if self.length > self.limit:
            node = self.top
            for _ in range(self.limit - 1):
                node = node.next  # type: ignore[assignment]
            node.next = None
            self.length = self.limit

    def peek(self) -> str | None:
        return self.top.value if self.top else None

    def pop(self) -> str | None:
        if not self.top:
            return None
        value = self.top.value
        self.top = self.top.next
        self.length -= 1
        return value

    def clear(self) -> None:
        self.top, self.length = None, 0

    def __iter__(self) -> Iterator[str]:
        node = self.top
        while node:
            yield node.value
            node = node.next


class QueueNode:
    def __init__(self, value: dict[str, str]):
        self.value = value
        self.next: QueueNode | None = None


class LinkedQueue:
    def __init__(self) -> None:
        self.front: QueueNode | None = None
        self.rear: QueueNode | None = None
        self.length = 0

    def enqueue(self, value: dict[str, str]) -> None:
        node = QueueNode(value)
        if self.rear:
            self.rear.next = node
        else:
            self.front = node
        self.rear = node
        self.length += 1

    def prepend(self, value: dict[str, str]) -> None:
        node = QueueNode(value)
        node.next = self.front
        self.front = node
        if self.rear is None:
            self.rear = node
        self.length += 1

    def remove(self, job_id: str) -> None:
        previous = None
        node = self.front
        while node and node.value["id"] != job_id:
            previous, node = node, node.next
        if node is None:
            raise DataError("Trabajo de cola no encontrado")
        if previous:
            previous.next = node.next
        else:
            self.front = node.next
        if self.rear is node:
            self.rear = previous
        self.length -= 1

    def peek(self) -> dict[str, str] | None:
        return self.front.value if self.front else None

    def dequeue(self) -> dict[str, str] | None:
        if not self.front:
            return None
        value = self.front.value
        self.front = self.front.next
        if not self.front:
            self.rear = None
        self.length -= 1
        return value

    def clear(self) -> None:
        self.front, self.rear, self.length = None, None, 0

    def __iter__(self) -> Iterator[dict[str, str]]:
        node = self.front
        while node:
            yield node.value
            node = node.next


def clean_row(kind: str, values: dict[str, Any]) -> dict[str, str]:
    if kind not in ALL_FIELDS:
        raise DataError(f"Tipo desconocido: {kind}")
    extra = set(values) - set(ALL_FIELDS[kind])
    if extra:
        raise DataError(f"Columnas desconocidas: {', '.join(sorted(extra))}")
    row = {field: str(values.get(field, "") or "").strip() for field in ALL_FIELDS[kind]}
    row["activo"] = row["activo"] or "1"
    if row["activo"] not in ("0", "1"):
        raise DataError("Activo debe ser 0 o 1")
    for field in REQUIRED.get(kind, ()):
        if not row[field]:
            raise DataError(f"Falta {LABELS[field]}")
    for field in ALL_FIELDS[kind]:
        if field.endswith("_id") and not row[field]:
            raise DataError(f"Falta {LABELS[field]}")
    if kind == "productos":
        if row["fecha"] and not row["anio"]:
            row["anio"] = row["fecha"][:4]
        if row["anio"]:
            try:
                year = int(row["anio"])
            except ValueError as exc:
                raise DataError("Año inválido") from exc
            if not 1900 <= year <= date.today().year + 1:
                raise DataError("Año fuera de rango")
    if kind == "productos":
        # El repositorio recalcula este campo; aquí solo se admite un valor conocido.
        # «pendiente» procede de carpetas anteriores a la validación automática.
        row["validacion"] = row["validacion"] or "rechazado"
        if row["validacion"] not in (*VALIDATION_STATES, "pendiente"):
            raise DataError("Validación: validado o rechazado")
    if kind == "autorias" and row["orden"]:
        if not row["orden"].isdigit() or int(row["orden"]) < 1:
            raise DataError("Orden de autor debe ser positivo")
    for field in ("fecha", "fecha_creacion", "inicio", "fin"):
        if field in row and row[field]:
            try:
                date.fromisoformat(row[field])
            except ValueError as exc:
                raise DataError(f"{LABELS[field]} debe ser AAAA-MM-DD") from exc
    if kind == "productos" and row["fecha"] and row["anio"]:
        if row["fecha"][:4] != row["anio"]:
            raise DataError("El año y la fecha del producto no coinciden")
    if kind in ("planes", "membresias") and row["inicio"] and row["fin"]:
        if row["inicio"] > row["fin"]:
            raise DataError("La fecha final precede la inicial")
    for field, value in row.items():
        if len(value) > MAX_FIELD_LEN:
            raise DataError(f"El campo {LABELS.get(field, field)} supera el tamaño permitido")
    return row


def _legacy_row(kind: str, values: dict[str, str]) -> dict[str, str]:
    """Adapta filas de las versiones 1 y 2 sin alterar los datos persistidos de origen."""
    row = values.copy()
    if kind == "grupos":
        row.pop("sigla", None)
    if kind == "productos":
        row.setdefault("validacion", "pendiente")
        # La versión 3 retira la categoría de producto; un valor escrito a mano se conserva en la observación.
        category = (row.pop("categoria", "") or "").strip()
        if category:
            note = f"Categoría registrada antes de la versión 3: {category}"
            row["observacion"] = f"{row.get('observacion', '').strip()}\n{note}".strip()
    return row


def _doi_text(value: str) -> str:
    text = value.strip().lower()
    return text[len("https://doi.org/"):] if text.startswith("https://doi.org/") else text


def _valid_doi(doi: str) -> bool:
    """10.NNNN/sufijo sin espacios; se evalúa igual que en C++ (sin expresiones regulares)."""
    if not doi.startswith("10."):
        return False
    prefix, slash, suffix = doi[3:].partition("/")
    return (bool(slash) and 4 <= len(prefix) <= 9 and prefix.isascii() and prefix.isdigit()
            and bool(suffix) and not any(ch in " \t\n\r\f\v" for ch in suffix))


def _verifiable_url(url: str) -> bool:
    text = url.strip().lower()
    return any(text.startswith(scheme) and len(text) > len(scheme) for scheme in ("http://", "https://"))


def auto_reason_codes(reason: str) -> list[str] | None:
    """Códigos de reglas de un motivo generado automáticamente; None si el motivo es manual."""
    if not reason.startswith(AUTO_REASON_PREFIX):
        return None
    return [code for code in reason[len(AUTO_REASON_PREFIX):].split(",") if code in VALIDATION_RULES]


class Repository:
    """Operaciones del dominio. Las entidades viven en listas; relaciones en multilistas."""

    def __init__(self) -> None:
        self.entities = {name: DoublyLinkedList() for name in ENTITY_FIELDS}
        self.relations = {
            name: MultiList(ends[0], ends[1]) for name, ends in RELATION_ENDS.items()
        }
        self.history = LinkedStack()
        self.queue = LinkedQueue()
        self.issues: dict[str, tuple[str, ...]] = {}
        self.dirty = False

    def rows(self, kind: str) -> list[dict[str, str]]:
        source = self.entities.get(kind) or self.relations.get(kind)
        if source is None:
            raise DataError(f"Tipo desconocido: {kind}")
        rows = [row.copy() for row in source]
        if kind in RELATION_ENDS:
            left, right = RELATION_ENDS[kind][:2]
            rows.sort(key=lambda row: (row[left], row[right]))
        return rows

    def page(self, kind: str, offset: int = 0, limit: int = PAGE_SIZE,
             query: str = "") -> dict[str, Any]:
        source = self.entities.get(kind) or self.relations.get(kind)
        if source is None:
            raise DataError(f"Tipo desconocido: {kind}")
        needle = query.casefold().strip()
        rows = (row for row in source if not needle or needle in " ".join(row.values()).casefold())
        if kind in RELATION_ENDS:
            left, right = RELATION_ENDS[kind][:2]
            matches = sorted(rows, key=lambda row: (row[left], row[right]))
            return {"rows": [row.copy() for row in matches[offset:offset + limit]], "total": len(matches)}
        page_rows = []
        total = 0
        for row in rows:
            if offset <= total < offset + limit:
                page_rows.append(row.copy())
            total += 1
        return {"rows": page_rows, "total": total}

    def summary(self) -> dict[str, Any]:
        return {"active_groups": sum(row["activo"] == "1" for row in self.entities["grupos"]),
                "active_people": sum(row["activo"] == "1" for row in self.entities["investigadores"])}

    def field_usage(self, kind: str) -> dict[str, int]:
        """Registros con valor por campo; la interfaz oculta columnas que nadie ha llenado."""
        source = self.entities.get(kind) or self.relations.get(kind)
        if source is None:
            raise DataError(f"Tipo desconocido: {kind}")
        usage = dict.fromkeys(ALL_FIELDS[kind], 0)
        for row in source:
            for field, value in row.items():
                if value:
                    usage[field] += 1
        return usage

    # Validación automática: un producto es «validado» si cumple todas las reglas.
    # Depende de sus vínculos, así que se recalcula al cambiar el producto, sus
    # autorías o grupos, o el estado de un investigador o grupo enlazado.
    def _rule_failures(self, product: dict[str, str]) -> tuple[str, ...]:
        failed = []
        if not product["anio"]:
            failed.append("anio")
        if not product["tipologia"]:
            failed.append("tipologia")
        if not any(link["activo"] == "1" and (person := self.get("investigadores", link["investigador_id"]))
                   and person["activo"] == "1" for link in self.relations["autorias"].by_left(product["id"])):
            failed.append("autor")
        if not any(link["activo"] == "1" and (group := self.get("grupos", link["grupo_id"]))
                   and group["activo"] == "1" for link in self.relations["grupos_productos"].by_right(product["id"])):
            failed.append("grupo")
        doi = _doi_text(product["doi"])
        if doi and not _valid_doi(doi):
            failed.append("doi")
        if not _verifiable_url(product["url"]) and not (doi and _valid_doi(doi)):
            failed.append("fuente")
        return tuple(failed)

    def _revalidate(self, product_ids: Any) -> None:
        for product_id in set(product_ids):
            product = self.get("productos", product_id)
            if product is None:
                self.issues.pop(product_id, None)
                continue
            failed = self._rule_failures(product)
            self.issues[product_id] = failed
            product["validacion"] = "rechazado" if failed else "validado"

    def _affected_products(self, kind: str, row: dict[str, str]) -> list[str]:
        if kind == "productos":
            return [row["id"]]
        if kind in ("autorias", "grupos_productos"):
            return [row["producto_id"]]
        if kind == "investigadores":
            return [link["producto_id"] for link in self.relations["autorias"].by_right(row["id"])]
        if kind == "grupos":
            return [link["producto_id"] for link in self.relations["grupos_productos"].by_left(row["id"])]
        return []

    def product_issues(self, product_id: str) -> list[str]:
        if self.get("productos", product_id) is None:
            raise DataError("Producto inexistente")
        return list(self.issues.get(product_id, ()))

    def get(self, kind: str, key: str | tuple[str, str]) -> dict[str, str] | None:
        if kind in ENTITY_FIELDS:
            return self.entities[kind].get(str(key))
        if kind in RELATION_FIELDS and isinstance(key, tuple):
            return self.relations[kind].get(*key)
        return None

    def related(self, kind: str, key: str, side: str) -> list[dict[str, str]]:
        relation = self.relations[kind]
        return list(relation.by_left(key) if side == "left" else relation.by_right(key))

    def related_page(self, kind: str, key: str, side: str, offset: int = 0,
                     limit: int = PAGE_SIZE, active_only: bool = False) -> dict[str, Any]:
        relation = self.relations[kind]
        source = relation.by_left(key) if side == "left" else relation.by_right(key)
        rows = []
        total = 0
        for row in source:
            if active_only and row["activo"] != "1":
                continue
            if offset <= total < offset + limit:
                rows.append(row.copy())
            total += 1
        return {"rows": rows, "total": total}

    def history_size(self) -> int:
        return self.history.length

    def suggest_id(self, kind: str) -> str:
        return new_id({"grupos": "G", "investigadores": "I",
                       "productos": "P", "planes": "PL"}[kind])

    def snapshot(self) -> str:
        state = {kind: self.rows(kind) for kind in ALL_FIELDS}
        state["cola_validacion"] = [job.copy() for job in self.queue]
        return json.dumps(state, ensure_ascii=False, separators=(",", ":"))

    def _restore(self, snapshot: str) -> None:
        state = json.loads(snapshot)
        fresh = Repository()
        for kind in ENTITY_FIELDS:
            for row in state[kind]:
                fresh.create(kind, _legacy_row(kind, row), remember=False)
        for kind in RELATION_FIELDS:
            for row in state[kind]:
                fresh.create(kind, row, remember=False)
        for job in state.get("cola_validacion", []):
            fresh._validate_job(job)
            fresh.queue.enqueue(job)
        self.entities, self.relations, self.queue = fresh.entities, fresh.relations, fresh.queue
        self.issues = fresh.issues
        self.dirty = True

    def _remember(self) -> None:
        self.history.push(self.snapshot())
        self.dirty = True

    @staticmethod
    def _decode_delta(snapshot: str) -> list[dict[str, str]] | None:
        state = json.loads(snapshot)
        if "__undo" not in state:
            return None
        if set(state) != {"__undo"} or not isinstance(state["__undo"], list) or not state["__undo"]:
            raise DataError("Historial de cambios inválido")
        for change in state["__undo"]:
            if not isinstance(change, dict):
                raise DataError("Historial de cambios inválido")
            op, kind = change.get("__op"), change.get("__kind")
            if op == "queue_remove":
                if not change.get("id"):
                    raise DataError("Historial de cola inválido")
            elif op == "queue_prepend":
                if not {"id", "producto_id", "motivo", "creado"} <= set(change):
                    raise DataError("Historial de cola inválido")
            elif op in ("create", "replace") and kind in ALL_FIELDS:
                clean_row(kind, _legacy_row(kind, {key: value for key, value in change.items()
                                                   if not key.startswith("__")}))
            elif op == "delete" and kind in ALL_FIELDS:
                keys = ("id",) if kind in ENTITY_FIELDS else RELATION_ENDS[kind][:2]
                if any(not change.get(key) for key in keys):
                    raise DataError("Historial sin clave")
            else:
                raise DataError("Operación de historial desconocida")
        return state["__undo"]

    def _apply_delta(self, changes: list[dict[str, str]]) -> None:
        for change in changes:
            op, kind = change["__op"], change["__kind"]
            if op == "queue_remove":
                self.queue.remove(change["id"])
            elif op == "queue_prepend":
                job = {name: change[name] for name in QUEUE_FIELDS}
                self._validate_job(job)
                self.queue.prepend(job)
            else:
                row = _legacy_row(kind, {key: value for key, value in change.items()
                                         if not key.startswith("__")})
                key = row["id"] if kind in ENTITY_FIELDS else tuple(row[name] for name in RELATION_ENDS[kind][:2])
                if op == "delete":
                    self.delete(kind, key, remember=False)
                elif op == "create":
                    self.create(kind, row, remember=False)
                else:
                    current = self.get(kind, key)
                    if current is None:
                        raise DataError("Registro de historial no encontrado")
                    current.update(row)
                    self._revalidate(self._affected_products(kind, current))
        self.dirty = True

    def undo(self) -> bool:
        previous = self.history.peek()
        if previous is None:
            return False
        changes = self._decode_delta(previous)
        if changes is None:
            self._restore(previous)
        else:
            self._apply_delta(changes)
        self.history.pop()
        return True

    def clear_history(self) -> None:
        self.history.clear()
        self.dirty = True

    def _check_links(self, kind: str, row: dict[str, str]) -> None:
        if kind == "planes" and not self.get("grupos", row["grupo_id"]):
            raise DataError("El grupo del plan no existe")
        if kind in RELATION_ENDS:
            left, right, left_kind, right_kind = RELATION_ENDS[kind]
            if not self.get(left_kind, row[left]) or not self.get(right_kind, row[right]):
                raise DataError("La relación apunta a una entidad inexistente")

    def _unique_external(self, kind: str, row: dict[str, str], old_id: str = "") -> None:
        field = {"grupos": "codigo_gruplac", "investigadores": "codigo_cvlac", "productos": "doi"}.get(kind)
        if not field or not row[field]:
            return
        normalized = row[field].strip().lower().removeprefix("https://doi.org/") if field == "doi" else row[field].strip().lower()
        for existing in self.entities[kind]:
            if existing["id"] == old_id or not existing[field]:
                continue
            candidate = existing[field].strip().lower().removeprefix("https://doi.org/") if field == "doi" else existing[field].strip().lower()
            if candidate == normalized:
                raise DataError(f"{LABELS[field]} ya registrado en {existing['id']}")

    def create(self, kind: str, values: dict[str, Any], remember: bool = True) -> dict[str, str]:
        row = clean_row(kind, values)
        self._check_links(kind, row)
        if kind in ENTITY_FIELDS:
            self._unique_external(kind, row)
            if self.get(kind, row["id"]):
                raise DataError("ID duplicado")
        else:
            left, right = RELATION_ENDS[kind][:2]
            if self.get(kind, (row[left], row[right])):
                raise DataError("Relación duplicada")
        if remember:
            self._remember()
        if kind in ENTITY_FIELDS:
            self.entities[kind].append(row)
        else:
            self.relations[kind].add(row)
        self._revalidate(self._affected_products(kind, row))
        return row

    def update(self, kind: str, key: str | tuple[str, str], values: dict[str, Any], remember: bool = True) -> dict[str, str]:
        current = self.get(kind, key)
        if current is None:
            raise DataError("Registro no encontrado")
        updated = clean_row(kind, {**current, **values})
        fixed = ("id",) if kind in ENTITY_FIELDS else RELATION_ENDS[kind][:2]
        if any(updated[field] != current[field] for field in fixed):
            raise DataError("Los identificadores son estables; cree otra relación si cambian")
        self._check_links(kind, updated)
        if kind in ENTITY_FIELDS:
            self._unique_external(kind, updated, current["id"])
        if remember:
            self._remember()
        current.update(updated)
        self._revalidate(self._affected_products(kind, current))
        return current

    def delete(self, kind: str, key: str | tuple[str, str], remember: bool = True) -> None:
        row = self.get(kind, key)
        if not row:
            raise DataError("Registro no encontrado")
        if kind in ENTITY_FIELDS:
            if kind == "grupos" and any(p["grupo_id"] == key for p in self.entities["planes"]):
                raise DataError("El grupo tiene planes; elimínelos o desactívelo")
            for rel_kind, (left, right, left_kind, right_kind) in RELATION_ENDS.items():
                field = left if kind == left_kind else right if kind == right_kind else None
                if field and any(rel[field] == key for rel in self.relations[rel_kind]):
                    raise DataError("Hay relaciones asociadas; elimínelas o desactive el registro")
            if kind == "productos" and any(job["producto_id"] == key for job in self.queue):
                raise DataError("Hay revisiones pendientes para el producto")
        if remember:
            self._remember()
        affected = self._affected_products(kind, row)
        if kind in ENTITY_FIELDS:
            self.entities[kind].remove(str(key))
        else:
            self.relations[kind].remove(*key)
        self._revalidate(affected)

    def toggle(self, kind: str, key: str | tuple[str, str]) -> None:
        row = self.get(kind, key)
        if not row:
            raise DataError("Registro no encontrado")
        self.update(kind, key, {"activo": "0" if row["activo"] == "1" else "1"})

    def product_scope(self, view: str = "Todos", selected_id: str = "") -> list[dict[str, str]]:
        if view == "Grupo":
            ids = {r["producto_id"] for r in self.relations["grupos_productos"].by_left(selected_id) if r["activo"] == "1"} if selected_id else set()
        elif view == "Investigador":
            ids = {r["producto_id"] for r in self.relations["autorias"].by_right(selected_id) if r["activo"] == "1"} if selected_id else set()
        elif view == "Producto":
            ids = {selected_id} if selected_id else set()
        else:
            ids = None
        return [p for p in self.entities["productos"] if p["activo"] == "1" and (ids is None or p["id"] in ids)]

    def statistics(self, view: str = "Todos", selected_id: str = "", start: int | None = None,
                   end: int | None = None, status: str = "",
                   offset: int = 0, limit: int | None = None) -> dict[str, Any]:
        # Hipercubo lógico: cada producto es un hecho; grupo e investigador llegan
        # por multilistas, y año, tipología y validación son dimensiones.
        # La vista elige grupo/investigador/producto; los filtros recortan el conjunto
        # y estos conteos se calculan bajo demanda. No hay cubo OLAP materializado
        # ni filtro simultáneo por grupo e investigador.
        if view not in ("Todos", "Grupo", "Investigador", "Producto"):
            raise DataError("Vista desconocida")
        if start is not None and end is not None and start > end:
            raise DataError("El año inicial supera al final")
        if status and status not in VALIDATION_STATES:
            raise DataError("Validación: validado o rechazado")
        products = []
        total = 0
        tallies: dict[str, dict[str, int]] = {name: {} for name in ("anio", "tipologia", "validacion")}
        rules: dict[str, int] = {}
        for row in self.product_scope(view, selected_id):
            year = int(row["anio"]) if row["anio"] else None
            if start is not None and (year is None or year < start):
                continue
            if end is not None and (year is None or year > end):
                continue
            if status and row["validacion"] != status:
                continue
            if total >= offset and (limit is None or len(products) < limit):
                products.append(row.copy())
            total += 1
            for name, counts in tallies.items():
                key = row[name] or "Sin dato"
                counts[key] = counts.get(key, 0) + 1
            for code in self.issues.get(row["id"], ()):
                rules[code] = rules.get(code, 0) + 1
        return {"productos": products, "total": total,
                "por_anio": tallies["anio"], "por_tipologia": tallies["tipologia"],
                "por_validacion": tallies["validacion"], "por_regla": rules}


    def queue_rows(self) -> list[dict[str, str]]:
        return list(self.queue)
    def queue_page(self, offset: int = 0, limit: int = PAGE_SIZE) -> dict[str, Any]:
        rows = []
        for index, job in enumerate(self.queue):
            if offset <= index < offset + limit:
                rows.append(job.copy())
            if index >= offset + limit:
                break
        return {"rows": rows, "total": self.queue.length}
    def queue_front(self) -> dict[str, str] | None:
        return self.queue.peek()
    def queue_size(self) -> int:
        return self.queue.length
    def _validate_job(self, job: dict[str, str]) -> None:
        if set(job) != {"id", "producto_id", "motivo", "creado"}:
            raise DataError("Formato inválido de la cola")
        if not self.get("productos", job["producto_id"]):
            raise DataError("La cola referencia un producto inexistente")
        if not job["id"] or not job["creado"]:
            raise DataError("Trabajo de cola incompleto")
    @staticmethod
    def _new_job(product_id: str, reason: str) -> dict[str, str]:
        return {"id": uuid.uuid4().hex[:12], "producto_id": product_id,
                "motivo": reason.strip(), "creado": datetime.now().isoformat(timespec="seconds")}
    def enqueue_review(self, product_id: str, reason: str) -> None:
        if not self.get("productos", product_id):
            raise DataError("Producto inexistente")
        if any(job["producto_id"] == product_id for job in self.queue):
            raise DataError("El producto ya está en la cola")
        self._remember()
        self.queue.enqueue(self._new_job(product_id, reason))
    def enqueue_rejected(self) -> int:
        """Encola los productos activos rechazados que aún no esperan revisión (una acción)."""
        queued = {job["producto_id"] for job in self.queue}
        targets = [row["id"] for row in self.entities["productos"]
                   if row["activo"] == "1" and row["validacion"] == "rechazado" and row["id"] not in queued]
        if targets:
            self._remember()
            for product_id in targets:
                self.queue.enqueue(self._new_job(product_id, AUTO_REASON_PREFIX + ",".join(self.issues.get(product_id, ()))))
        return len(targets)
    def process_review(self, observation: str) -> dict[str, str]:
        """Cierra la revisión del frente con una nota; la validación sigue siendo automática."""
        job = self.queue.peek()
        if not job:
            raise DataError("La cola está vacía")
        if not observation.strip():
            raise DataError("Debe registrar una observación")
        current = self.get("productos", job["producto_id"])
        if current is None:
            raise DataError("El producto ya no existe")
        clean_row("productos", {**current, "observacion": observation})
        self._remember()
        self.update("productos", job["producto_id"], {"observacion": observation}, remember=False)
        self.queue.dequeue()
        return {**job, "validacion": current["validacion"]}
    def discard_review(self) -> dict[str, str]:
        if not self.queue.peek():
            raise DataError("La cola está vacía")
        self._remember()
        return self.queue.dequeue()  # type: ignore[return-value]

def _storage_cell(value: str) -> str:
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r", "'")) else value


def _csv_read(path: Path, fields: tuple[str, ...], *, version: str = SCHEMA_VERSION,
              encoded: bool = False) -> list[dict[str, str]]:
    # La versión 3 ya tiene los campos actuales; solo 1 y 2 necesitan adaptarse.
    legacy = version in ("1", "2")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        actual = set(reader.fieldnames or ())
        expected = set(fields)
        # v1: grupos con «sigla» y productos sin «validacion»; v1 y v2: productos con «categoria».
        old_groups = version == "1" and path.stem == "grupos" and actual == expected | {"sigla"}
        old_products = legacy and path.stem == "productos" and (
            actual == expected | {"categoria"}
            or (version == "1" and actual in ((expected | {"categoria"}) - {"validacion"},
                                              expected - {"validacion"})))
        if reader.fieldnames is None or not (actual == expected or old_groups or old_products):
            raise DataError(f"Encabezados incorrectos en {path.name}; se esperan: {', '.join(fields)}")
        rows = []
        for number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise DataError(f"Fila {number} malformada en {path.name}")
            if len(rows) >= MAX_CSV_ROWS:
                raise DataError(f"Demasiadas filas en {path.name}")
            if encoded:
                row = {key: value[1:] if value.startswith("'") else value for key, value in row.items()}
            rows.append(_legacy_row(path.stem, row) if legacy else row)
        return rows


def _csv_write(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _storage_cell(row.get(field, "")) for field in fields})
        stream.flush()
        os.fsync(stream.fileno())


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _check_local_file(path: Path, *, archive: bool = False) -> None:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise DataError(f"No se puede abrir el archivo: {exc}") from exc
    if size > MAX_LOCAL_FILE:
        raise DataError("El archivo supera 32 MB")
    if archive:
        try:
            with zipfile.ZipFile(path) as package:
                members = package.infolist()
                if len(members) > 10_000 or sum(item.file_size for item in members) > MAX_ARCHIVE_UNPACKED:
                    raise DataError("El documento comprimido supera los límites de extracción")
        except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError) as exc:
            raise DataError("El archivo no es un documento Office válido") from exc


def _xlsx_to_csv(source: Path, target: Path) -> Path:
    """Convierte la primera hoja de un .xlsx a CSV respetando los límites de importación."""
    _check_local_file(source, archive=True)
    try:
        import openpyxl
    except ImportError as exc:
        raise DataError("Para importar Excel instale openpyxl (pip install openpyxl)") from exc
    try:
        workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    except Exception as exc:
        raise DataError(f"No se pudo leer el Excel: {exc}") from exc
    try:
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        header = next(rows, None)
        header_cells = [_cell_text(cell) for cell in (header or ())]
        if not any(header_cells):
            raise DataError("El Excel no tiene encabezados")
        if any(not name for name in header_cells):
            raise DataError("El Excel tiene columnas sin encabezado")
        if any(len(name) > MAX_FIELD_LEN for name in header_cells):
            raise DataError("El Excel tiene un encabezado demasiado largo")
        with target.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(header_cells)
            count = 1
            for record in rows:
                count += 1
                if count > MAX_CSV_ROWS:
                    raise DataError("El Excel tiene demasiadas filas")
                cells = [_cell_text(cell) for cell in record]
                if any(len(cell) > MAX_FIELD_LEN for cell in cells):
                    raise DataError("El Excel tiene un valor demasiado largo")
                writer.writerow(cells)
    except DataError:
        raise
    except Exception as exc:
        raise DataError(f"No se pudo leer el Excel: {exc}") from exc
    finally:
        workbook.close()
    return target


def _neutralize_cell(value: str) -> str:
    if value and value[0] in "=+-@\t\r":
        return "'" + value
    return value


def _csv_write_safe(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _neutralize_cell(row.get(field, "")) for field in fields})
        stream.flush()
        os.fsync(stream.fileno())


def export_repository_spreadsheet(repo: Repository | CppRepository, directory: Path) -> None:
    """Exporta los datos neutralizados para abrirlos en hojas de cálculo sin fórmulas."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    _csv_write_safe(directory / "manifest.csv", MANIFEST_FIELDS,
                    [{"version": SCHEMA_VERSION, "guardado": datetime.now().isoformat(timespec="seconds")}])
    for kind, fields in ALL_FIELDS.items():
        _csv_write_safe(directory / f"{kind}.csv", fields, repo.rows(kind))


def is_folder_data(path: Path) -> bool:
    """Carpeta de las versiones 1 a 3, indicada por la carpeta o por su manifest.csv."""
    path = Path(path)
    return path.is_dir() or path.name == "manifest.csv"


def backup_of(path: Path) -> Path:
    """Copia del guardado anterior: .backup junto al archivo (o dentro de una carpeta anterior)."""
    path = Path(path)
    if is_folder_data(path):
        return (path if path.is_dir() else path.parent) / ".backup"
    return path.parent / ".backup" / path.name


def save_repository(repo: Repository, path: Path) -> None:
    """Escribe el archivo único en un temporal y lo sustituye de una vez; conserva la copia anterior."""
    path = Path(path)
    if path.is_dir():
        raise DataError("Indique un archivo .csv, no una carpeta")
    path.parent.mkdir(parents=True, exist_ok=True)
    tables = {"manifest": [{"version": SCHEMA_VERSION, "guardado": datetime.now().isoformat(timespec="seconds")}],
              **{kind: repo.rows(kind) for kind in ALL_FIELDS},
              "cola_validacion": list(repo.queue),
              "historial": [{"orden": str(index), "snapshot": state} for index, state in enumerate(repo.history)]}
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            for section, fields in DATA_SECTIONS.items():
                writer.writerow([f"#{section}"])
                writer.writerow(fields)
                writer.writerows([_storage_cell(row.get(field, "")) for field in fields] for row in tables[section])
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            backup = backup_of(path)
            backup.parent.mkdir(exist_ok=True)
            shutil.copy2(path, backup)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    repo.dirty = False


def read_data_sections(path: Path) -> Iterator[tuple[str, int, dict[str, str]]]:
    """Recorre el archivo único en orden y entrega (sección, línea, fila).

    Cada sección empieza con una fila de una sola celda «#nombre», sigue su encabezado y
    luego sus filas hasta la siguiente marca. Ninguna tabla tiene una sola columna, así que
    una fila de datos nunca se confunde con una marca.
    """
    path = Path(path)
    expected = iter(DATA_SECTIONS)
    section, header, count, previous = "", None, 0, 0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        for record in reader:
            line, previous = previous + 1, reader.line_num
            where = f"{path.name}, línea {line}"
            if not record or record == [""]:
                continue
            if len(record) == 1 and record[0].startswith("#"):
                if section and header is None:
                    raise DataError(f"{where}: falta el encabezado de la sección #{section}")
                wanted = next(expected, None)
                if wanted is None:
                    raise DataError(f"{where}: sección sobrante {record[0]}")
                if record[0] != f"#{wanted}":
                    raise DataError(f"{where}: se esperaba la sección #{wanted}")
                section, header, count = wanted, None, 0
                continue
            if not section:
                raise DataError(f"{where}: el archivo debe comenzar con #manifest")
            if header is None:
                fields = DATA_SECTIONS[section]
                if len(record) != len(fields) or set(record) != set(fields):
                    raise DataError(f"{where}: encabezados incorrectos en #{section}; se esperan: {', '.join(fields)}")
                header = record
                continue
            if len(record) != len(header):
                raise DataError(f"{where}: fila malformada en #{section}")
            count += 1
            if count > MAX_CSV_ROWS:
                raise DataError(f"{where}: demasiadas filas en #{section}")
            yield section, line, {name: value[1:] if value.startswith("'") else value
                                  for name, value in zip(header, record)}
    missing = next(expected, None)
    if missing is not None:
        raise DataError(f"{path.name}: falta la sección #{missing}")
    if header is None:
        raise DataError(f"{path.name}: falta el encabezado de la sección #{section}")


def _load_history(repo: Repository, entries: list[dict[str, str]]) -> None:
    for entry in reversed(entries):
        # Cada snapshot se verifica antes de incorporarlo al historial.
        validator = Repository()
        try:
            if validator._decode_delta(entry["snapshot"]) is None:
                validator._restore(entry["snapshot"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DataError("Historial dañado") from exc
        repo.history.push(entry["snapshot"])


def _load_file(path: Path) -> Repository:
    """Crea los registros a medida que los lee: las entidades llegan antes que sus relaciones."""
    repo = Repository()
    manifests = 0
    job_ids: set[str] = set()
    history: list[dict[str, str]] = []
    for section, line, row in read_data_sections(path):
        try:
            if section == "manifest":
                manifests += 1
                if manifests > 1:
                    raise DataError("Manifest con más de una fila")
                if row["version"] != SCHEMA_VERSION:
                    raise DataError("Versión de datos incompatible")
            elif section in ALL_FIELDS:
                repo.create(section, row, remember=False)
            elif section == "cola_validacion":
                repo._validate_job(row)
                if row["id"] in job_ids:
                    raise DataError(f"Trabajo de cola duplicado: {row['id']}")
                job_ids.add(row["id"])
                repo.queue.enqueue(row)
            else:
                history.append(row)
        except DataError as exc:
            raise DataError(f"{path.name}, línea {line} (#{section}): {exc}") from exc
    if manifests != 1:
        raise DataError(f"{path.name}: falta la fila de #manifest")
    _load_history(repo, history)
    repo.dirty = False
    return repo


def _load_folder(directory: Path) -> Repository:
    """Carpeta de las versiones 1 a 3 (un CSV por tabla); se guarda luego como archivo único."""
    manifest = _csv_read(directory / "manifest.csv", MANIFEST_FIELDS, encoded=True)
    if len(manifest) != 1 or manifest[0]["version"] not in FOLDER_VERSIONS:
        raise DataError("Versión de datos incompatible")
    version = manifest[0]["version"]
    legacy = version == "1"
    repo = Repository()
    for kind in ENTITY_FIELDS:
        for number, row in enumerate(_csv_read(directory / f"{kind}.csv", ENTITY_FIELDS[kind],
                                               version=version, encoded=not legacy), start=2):
            try:
                repo.create(kind, row, remember=False)
            except DataError as exc:
                raise DataError(f"{kind}.csv, fila {number}: {exc}") from exc
    for kind in RELATION_FIELDS:
        for number, row in enumerate(_csv_read(directory / f"{kind}.csv", RELATION_FIELDS[kind],
                                               encoded=not legacy), start=2):
            try:
                repo.create(kind, row, remember=False)
            except DataError as exc:
                raise DataError(f"{kind}.csv, fila {number}: {exc}") from exc
    job_ids: set[str] = set()
    queue_path = directory / "cola_validacion.csv"
    if not queue_path.exists() and not legacy:
        raise DataError("Falta cola_validacion.csv")
    jobs = _csv_read(queue_path, QUEUE_FIELDS, encoded=not legacy) if queue_path.exists() else []
    for job in jobs:
        repo._validate_job(job)
        if job["id"] in job_ids:
            raise DataError(f"Trabajo de cola duplicado: {job['id']}")
        job_ids.add(job["id"])
        repo.queue.enqueue(job)
    _load_history(repo, _csv_read(directory / "historial.csv", HISTORY_FIELDS, encoded=not legacy))
    repo.dirty = False
    return repo


def load_repository(path: Path) -> Repository:
    """Abre el archivo único o, para convertirla, una carpeta anterior (o su manifest.csv)."""
    path = Path(path)
    if is_folder_data(path):
        return _load_folder(path if path.is_dir() else path.parent)
    return _load_file(path)


def merge_csv(repo: Repository, path: Path, kind: str) -> tuple[int, list[str]]:
    """Importa filas válidas en lote y conserva una sola acción para deshacer."""
    if kind not in ALL_FIELDS:
        raise DataError("Tipo de CSV desconocido")
    rows = _csv_read(Path(path), ALL_FIELDS[kind])
    before = repo.snapshot()
    accepted, errors = 0, []
    for number, row in enumerate(rows, start=2):
        try:
            repo.create(kind, row, remember=False)
            accepted += 1
        except DataError as exc:
            errors.append(f"Fila {number}: {exc}")
    if accepted:
        repo.history.push(before)
        repo.dirty = True
    return accepted, errors


def preview_csv_merge(repo: Repository, path: Path, kind: str) -> tuple[int, int, list[str]]:
    """Comprueba en una copia todos los aciertos/rechazos antes de mutar datos."""
    if kind not in ALL_FIELDS:
        raise DataError("Tipo de CSV desconocido")
    rows = _csv_read(Path(path), ALL_FIELDS[kind])
    staged = Repository()
    staged._restore(repo.snapshot())
    accepted, errors = 0, []
    for number, row in enumerate(rows, start=2):
        try:
            staged.create(kind, row, remember=False)
            accepted += 1
        except DataError as exc:
            errors.append(f"Fila {number}: {exc}")
    return len(rows), accepted, errors


def bundled_windows_cpp(root: Path) -> Path | None:
    """Usa el binario incluido solo si coincide con las fuentes y con su huella propia."""
    binary = root / "bin" / "windows" / "pea_cpp.exe"
    fingerprint = binary.with_suffix(".source-sha256")
    integrity = root / "bin" / "windows" / "pea_cpp.exe.sha256"
    if not binary.is_file() or not fingerprint.is_file() or not integrity.is_file():
        return None
    try:
        digest = hashlib.sha256()
        for source in (root / "CMakeLists.txt", root / "src/cpp/Taller2_REMR.cpp"):
            digest.update(source.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(source.read_bytes().replace(b"\r\n", b"\n"))
        if fingerprint.read_text(encoding="ascii").strip() != digest.hexdigest():
            return None
        binary_digest = hashlib.sha256(binary.read_bytes()).hexdigest()
        if integrity.read_text(encoding="ascii").strip() != binary_digest:
            return None
        return binary
    except (OSError, UnicodeError):
        pass
    return None


def cpp_executable(explicit: Path | None = None) -> Path:
    """Localiza o compila el ejecutable que atiende a la interfaz Tkinter."""
    root = Path(__file__).resolve().parents[2]
    if explicit is not None:
        binary = Path(explicit).expanduser().resolve()
        if not binary.is_file():
            raise DataError(f"No existe el backend C++: {binary}")
        return binary
    candidates = [root / "build" / "mingw" / "pea_cpp.exe",
                  root / "build" / "default" / "Release" / "pea_cpp.exe",
                  root / "build" / "default" / "pea_cpp.exe",
                  root / "build" / "Release" / "pea_cpp.exe",
                  root / "build" / "pea_cpp.exe",
                  root / "build" / "pea_cpp"]
    available = [item for item in candidates if item.is_file()]
    binary = max(available, key=lambda item: item.stat().st_mtime) if available else None
    newest_source = max((root / "CMakeLists.txt").stat().st_mtime,
                        (root / "src" / "cpp" / "Taller2_REMR.cpp").stat().st_mtime)
    if binary is not None and binary.stat().st_mtime >= newest_source:
        return binary
    if os.name == "nt":
        bundled = bundled_windows_cpp(root)
        if bundled is not None:
            return bundled
    if binary is None or binary.stat().st_mtime < newest_source:
        if shutil.which("cmake") is None:
            raise DataError("CMake no está instalado. Instálelo para compilar el backend C++.")
        mingw = bool(os.name == "nt" and shutil.which("g++") and shutil.which("mingw32-make"))
        build_dir = root / "build" / ("mingw" if mingw else "default")
        configure = ["cmake", "-S", str(root), "-B", str(build_dir)]
        if mingw:
            configure += ["-G", "MinGW Makefiles"]
        for command in (configure, ["cmake", "--build", str(build_dir), "--config", "Release"]):
            try:
                completed = subprocess.run(command, cwd=root, text=True, encoding="utf-8",
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           check=False)
            except OSError as exc:
                raise DataError(f"No se pudo iniciar CMake: {exc}") from exc
            if completed.returncode:
                raise DataError("No se pudo compilar el backend C++:\n" + completed.stdout[-3000:])
        available = [item for item in candidates if item.is_file()]
        binary = max(available, key=lambda item: item.stat().st_mtime) if available else None
    if binary is None:
        raise DataError("CMake terminó sin generar pea_cpp; revise la carpeta build.")
    return binary


CPP_PROTOCOL = "3"


class CppRepository:
    """Adaptador local: Tkinter envía operaciones y el proceso C++ conserva el estado."""

    def __init__(self, binary: Path | None = None) -> None:
        executable = cpp_executable(binary)
        root = Path(__file__).resolve().parents[2]
        try:
            self.process = subprocess.Popen(
                [str(executable), "--api"], cwd=root,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", bufsize=1,
            )
        except OSError as exc:
            raise DataError(f"No se pudo iniciar el backend C++: {exc}") from exc
        self.dirty = False
        self._history_size = 0
        self._queue_size = 0
        try:
            hello = self._request("ping")
            if hello != {"backend": "cpp", "protocol": CPP_PROTOCOL}:
                raise DataError("El backend C++ usa un protocolo incompatible")
        except Exception:
            self.close()
            raise

    def _request(self, action: str, **fields: str) -> Any:
        if self.process.poll() is not None:
            detail = self.process.stderr.read().strip() if self.process.stderr else ""
            raise DataError("El backend C++ se cerró" + (f": {detail}" if detail else ""))
        assert self.process.stdin is not None and self.process.stdout is not None
        request = {"action": action, **fields}
        try:
            self.process.stdin.write(json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline()
        except (OSError, UnicodeError) as exc:
            raise DataError(f"No se pudo comunicar con el backend C++: {exc}") from exc
        if not line:
            detail = self.process.stderr.read().strip() if self.process.stderr else ""
            raise DataError("El backend C++ no respondió" + (f": {detail}" if detail else ""))
        try:
            response = json.loads(line)
            state = response["state"]
            self.dirty = bool(state["dirty"])
            self._history_size = int(state["history_size"])
            self._queue_size = int(state["queue_size"])
            if not response["ok"]:
                raise DataError(response["error"])
            return response["result"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise DataError("Respuesta inválida del backend C++") from exc

    @staticmethod
    def _keys(key: str | tuple[str, str]) -> dict[str, str]:
        return {"key": key[0], "second": key[1]} if isinstance(key, tuple) else {"key": key, "second": ""}

    def rows(self, kind: str) -> list[dict[str, str]]:
        return self._request("rows", kind=kind)

    def page(self, kind: str, offset: int = 0, limit: int = PAGE_SIZE,
             query: str = "") -> dict[str, Any]:
        return self._request("page", kind=kind, offset=str(offset), limit=str(limit), query=query)

    def summary(self) -> dict[str, Any]:
        return self._request("summary")

    def field_usage(self, kind: str) -> dict[str, int]:
        return self._request("field_usage", kind=kind)

    def product_issues(self, product_id: str) -> list[str]:
        return self._request("product_issues", key=product_id)

    def get(self, kind: str, key: str | tuple[str, str]) -> dict[str, str] | None:
        return self._request("get", kind=kind, **self._keys(key))

    def related(self, kind: str, key: str, side: str) -> list[dict[str, str]]:
        return self._request("related", kind=kind, key=key, side=side)

    def related_page(self, kind: str, key: str, side: str, offset: int = 0,
                     limit: int = PAGE_SIZE, active_only: bool = False) -> dict[str, Any]:
        return self._request("related_page", kind=kind, key=key, side=side,
                             offset=str(offset), limit=str(limit), active="1" if active_only else "0")

    def create(self, kind: str, values: dict[str, str]) -> dict[str, str]:
        return self._request("create", kind=kind, values=json.dumps(values, ensure_ascii=False))

    def update(self, kind: str, key: str | tuple[str, str], values: dict[str, str]) -> dict[str, str]:
        return self._request("update", kind=kind, values=json.dumps(values, ensure_ascii=False),
                             **self._keys(key))

    def delete(self, kind: str, key: str | tuple[str, str]) -> None:
        self._request("delete", kind=kind, **self._keys(key))

    def toggle(self, kind: str, key: str | tuple[str, str]) -> None:
        self._request("toggle", kind=kind, **self._keys(key))

    def statistics(self, view: str = "Todos", selected_id: str = "", start: int | None = None,
                   end: int | None = None, status: str = "",
                   offset: int = 0, limit: int = PAGE_SIZE) -> dict[str, Any]:
        return self._request("statistics", view=view, selected=selected_id,
                             start="" if start is None else str(start),
                             end="" if end is None else str(end),
                             status=status, offset=str(offset), limit=str(limit))

    def history_size(self) -> int:
        return self._history_size

    def suggest_id(self, kind: str) -> str:
        return self._request("new_id", kind=kind)

    def undo(self) -> bool:
        return self._request("undo")

    def clear_history(self) -> None:
        self._request("clear_history")

    def reset(self) -> None:
        self._request("reset")

    def load(self, path: Path) -> None:
        self._request("load", path=str(Path(path).resolve()))

    def save(self, path: Path) -> None:
        self._request("save", path=str(Path(path).resolve()))

    def preview_csv(self, path: Path, kind: str) -> tuple[int, int, list[str]]:
        result = self._request("preview_csv", path=str(Path(path).resolve()), kind=kind)
        return result["total"], result["accepted"], result["errors"]

    def import_csv(self, path: Path, kind: str) -> tuple[int, list[str]]:
        result = self._request("import_csv", path=str(Path(path).resolve()), kind=kind)
        return result["accepted"], result["errors"]

    def queue_rows(self) -> list[dict[str, str]]:
        return self._request("queue_rows")
    def queue_page(self, offset: int = 0, limit: int = PAGE_SIZE) -> dict[str, Any]:
        return self._request("queue_page", offset=str(offset), limit=str(limit))
    def queue_front(self) -> dict[str, str] | None:
        return self._request("queue_front")
    def queue_size(self) -> int:
        return self._queue_size
    def enqueue_review(self, product_id: str, reason: str) -> None:
        self._request("enqueue_review", product_id=product_id, reason=reason)
    def enqueue_rejected(self) -> int:
        return self._request("enqueue_rejected")
    def process_review(self, observation: str) -> dict[str, str]:
        return self._request("process_review", observation=observation)
    def discard_review(self) -> dict[str, str]:
        return self._request("discard_review")

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self._request("shutdown")
                self.process.wait(timeout=2)
            except (DataError, OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream is not None:
                stream.close()


class VisibleText(HTMLParser):
    BLOCKS = {"tr", "td", "th", "h1", "h2", "h3", "h4", "p", "li", "br", "div", "section", "article", "title"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.suppressed += 1
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.suppressed = max(0, self.suppressed - 1)
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.suppressed:
            self.parts.append(data)

    def lines(self) -> list[str]:
        return [re.sub(r"\s+", " ", part).strip() for part in "".join(self.parts).splitlines() if part.strip()]


class LinkedTableRows(HTMLParser):
    """Conserva celdas y enlaces de tablas HTML para distinguir nombres de códigos CvLAC."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[tuple[str, str]]] = []
        self._row: list[tuple[str, str]] | None = None
        self._cell: list[str] | None = None
        self._href = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._href = ""
        elif tag == "a" and self._cell is not None:
            self._href = dict(attrs).get("href") or self._href

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None:
            if self._row is not None:
                self._row.append((re.sub(r"\s+", " ", "".join(self._cell)).strip(), self._href))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


class WebPreview(NamedTuple):
    url: str
    format: str
    title: str
    lines: tuple[str, ...]
    metadata: dict[str, str]
    suggested_kind: str | None = None
    suggested_row: dict[str, str] | None = None
    csv_bytes: bytes | None = None
    tables: tuple[tuple[tuple[str, ...], ...], ...] = ()
    related_products: tuple[dict[str, str], ...] = ()
    related_members: tuple[tuple[dict[str, str], dict[str, str]], ...] = ()
    related_plan: dict[str, str] | None = None
    related_authorships: tuple[dict[str, str], ...] = ()


class GrupLACProduct(NamedTuple):
    row: dict[str, str]
    authors: tuple[str, ...]
    section: str


class PageText(VisibleText):
    """Recoge texto visible y metadatos explícitos, sin interpretar el tema del sitio."""

    META_KEYS = {
        "description", "og:description", "og:title", "twitter:title", "author", "date", "article:published_time",
        "citation_title", "citation_doi", "citation_date", "citation_publication_date",
        "citation_author", "citation_journal_title", "dc.title", "dc.date",
    }

    def __init__(self) -> None:
        super().__init__()
        self.metadata: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.heading_parts: list[str] = []
        self._title = False
        self._heading = False
        self._json_ld = False
        self._json_parts: list[str] = []
        self.schemas: list[dict[str, Any]] = []
        self.tables: list[tuple[tuple[str, ...], ...]] = []
        self._table_level = 0
        self._table_rows: list[tuple[str, ...]] = []
        self._table_row: list[str] | None = None
        self._table_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "meta":
            key = (attributes.get("name") or attributes.get("property") or "").casefold()
            value = (attributes.get("content") or "").strip()
            if key in self.META_KEYS and value and key not in self.metadata:
                self.metadata[key] = value[:1000]
        if tag == "title":
            self._title = True
        if tag == "h1" and not self.heading_parts:
            self._heading = True
        if tag == "script" and attributes.get("type", "").casefold() == "application/ld+json":
            self._json_ld = True
            self._json_parts = []
        if tag == "table":
            self._table_level += 1
            if self._table_level == 1:
                self._table_rows = []
        elif self._table_level == 1 and tag == "tr":
            self._table_row = []
        elif self._table_level == 1 and tag in ("td", "th") and self._table_row is not None:
            self._table_cell = []
        super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._json_ld:
            self._json_ld = False
            try:
                schema = json.loads("".join(self._json_parts))
            except (ValueError, TypeError, RecursionError):
                schema = None
            self._collect_schema(schema)
        if tag == "title":
            self._title = False
        if tag == "h1":
            self._heading = False
        if self._table_level == 1 and tag in ("td", "th") and self._table_cell is not None:
            if self._table_row is not None and len(self._table_row) < 30:
                self._table_row.append(re.sub(r"\s+", " ", "".join(self._table_cell)).strip()[:500])
            self._table_cell = None
        elif self._table_level == 1 and tag == "tr" and self._table_row is not None:
            if self._table_row and len(self._table_rows) < 100:
                self._table_rows.append(tuple(self._table_row))
            self._table_row = None
        if tag == "table" and self._table_level:
            if self._table_level == 1 and self._table_rows and len(self.tables) < 5:
                self.tables.append(tuple(self._table_rows))
            self._table_level -= 1
        super().handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._json_ld:
            self._json_parts.append(data)
        if self._title:
            self.title_parts.append(data)
        if self._heading:
            self.heading_parts.append(data)
        if self._table_cell is not None:
            self._table_cell.append(data)
        super().handle_data(data)

    def _collect_schema(self, item: Any, depth: int = 0) -> None:
        if depth > 64:
            return
        if isinstance(item, list):
            for value in item:
                self._collect_schema(value, depth + 1)
        elif isinstance(item, dict):
            if isinstance(item.get("@graph"), list):
                self._collect_schema(item["@graph"], depth + 1)
            if "@type" in item:
                self.schemas.append(item)


def _web_source(url: str) -> str:
    return f"{urlparse(url).hostname}, consultado {date.today().isoformat()}"


def _redact_url(url: str, keep_params: tuple[str, ...] = ("nro", "cod_rh")) -> str:
    """Elimina parámetros de consulta sensibles; conserva solo los necesarios para reabrir."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return url
    params = parse_qs(parsed.query)
    kept = {key: params[key][0] for key in keep_params if key in params}
    query = urlencode(sorted(kept.items()))
    return parsed._replace(query=query, fragment="").geturl()


def _publication_year(value: str) -> str:
    match = re.search(r"(?<!\d)(?:19|20)\d{2}(?!\d)", value)
    if match and 1900 <= int(match.group()) <= date.today().year + 1:
        return match.group()
    return ""


def _is_scholarly_article(item: dict[str, Any]) -> bool:
    declared = item.get("@type")
    types = [declared] if isinstance(declared, str) else declared if isinstance(declared, list) else []
    return any(isinstance(value, str) and value.rsplit("/", 1)[-1] == "ScholarlyArticle" for value in types)


def parse_web_page(text: str, url: str, format: str = "HTML") -> WebPreview:
    """Previsualiza cualquier página de texto; solo propone campos con etiquetas fiables."""
    metadata: dict[str, str] = {}
    suggestion: tuple[str, dict[str, str]] | None = None
    tables: tuple[tuple[tuple[str, ...], ...], ...] = ()
    related_products: tuple[dict[str, str], ...] = ()
    related_members: tuple[tuple[dict[str, str], dict[str, str]], ...] = ()
    related_plan: dict[str, str] | None = None
    related_authorships: tuple[dict[str, str], ...] = ()
    if format == "HTML":
        parser = PageText()
        parser.feed(text)
        lines = parser.lines()
        metadata = parser.metadata.copy()
        tables = tuple(parser.tables)
        if tables:
            metadata["Tablas HTML"] = str(len(tables))
        title = re.sub(r"\s+", " ", "".join(parser.title_parts)).strip()
        heading = re.sub(r"\s+", " ", "".join(parser.heading_parts)).strip()
        title = title or metadata.get("og:title", "") or metadata.get("twitter:title", "") or heading or metadata.get("citation_title", "")
        if urlparse(url).hostname == "scienti.minciencias.gov.co":
            try:
                suggestion = parse_scienti_html(text, url)
                if suggestion[0] == "grupos":
                    members = parse_gruplac_members(text, url)
                    products = parse_gruplac_products(text, url)
                    related_members = tuple(members)
                    related_products = tuple(item.row for item in products)
                    related_plan = parse_gruplac_plan(text, url, suggestion[1]["objetivos"])
                    related_authorships = tuple(match_gruplac_authors(products, members))
            except DataError:
                pass
        if suggestion is None:
            article = next((item for item in parser.schemas if _is_scholarly_article(item)), None)
            article_title = metadata.get("citation_title", "")
            if article and not article_title and isinstance(article.get("headline") or article.get("name"), str):
                article_title = article.get("headline") or article.get("name")
            if article_title:
                published = metadata.get("citation_publication_date") or metadata.get("citation_date") or (
                    article.get("datePublished", "") if article else "")
                doi = metadata.get("citation_doi") or (article.get("doi", "") if article else "")
                if article:
                    for key, value in (("schema.org: título", article_title),
                                       ("schema.org: fecha", published), ("schema.org: DOI", doi)):
                        if value and key not in metadata:
                            metadata[key] = str(value)[:1000]
                row = {"id": new_id("P"), "titulo": article_title, "anio": _publication_year(str(published)),
                       "doi": str(doi) if isinstance(doi, str) else "", "url": _redact_url(url), "fuente": _web_source(url)}
                suggestion = ("productos", row)
        if not title:
            title = lines[0] if lines else urlparse(url).hostname or url
    elif format == "CSV":
        reader = csv.reader(io.StringIO(text))
        try:
            columns = next(reader)
        except StopIteration:
            columns = []
        metadata["Columnas CSV"] = ", ".join(columns[:30]) or "Archivo vacío"
        lines = [f"Encabezados: {metadata['Columnas CSV']}"]
        for index, row in enumerate(reader, start=1):
            if index > 100:
                lines.append("… Vista previa limitada a 100 filas")
                break
            lines.append(f"Fila {index}: " + " | ".join(row[:30]))
        title = "CSV: " + (urlparse(url).path.rsplit("/", 1)[-1] or urlparse(url).hostname or url)
    else:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = lines[0][:200] if lines else urlparse(url).path.rsplit("/", 1)[-1] or url
    if not lines and not metadata:
        lines = ["No se encontró texto legible en la respuesta. El sitio podría requerir JavaScript o acceso especial."]
    if suggestion:
        kind, row = suggestion
    else:
        kind, row = None, None
    return WebPreview(url, format, title[:250], tuple(lines[:300]), metadata, kind, row, None, tables,
                      related_products, related_members, related_plan, related_authorships)


def _resolve_public_addrs(host: str, port: int) -> list[str]:
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, ValueError) as exc:
        raise DataError(f"No se pudo resolver el sitio: {exc}") from exc
    resolved: list[str] = []
    for item in addresses:
        address = ipaddress.ip_address(item[4][0])
        if not address.is_global:
            raise DataError("No se permiten direcciones locales o privadas")
        if item[4][0] not in resolved:
            resolved.append(item[4][0])
    if not resolved:
        raise DataError("No se pudo resolver el sitio")
    return resolved


def _validate_public_url(url: str) -> str:
    try:
        parsed = urlparse(url.strip())
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise DataError("URL inválida") from exc
    if parsed.scheme not in ("http", "https") or not host or parsed.username or parsed.password:
        raise DataError("Indique una URL pública HTTP o HTTPS, sin usuario ni contraseña")
    if host.casefold() == "localhost" or host.casefold().endswith((".localhost", ".local")):
        raise DataError("No se permiten direcciones locales o privadas")
    if port is not None and port not in (80, 443):
        raise DataError("Solo se permiten los puertos 80 y 443")
    try:
        literal_address = ipaddress.ip_address(host)
    except ValueError:
        literal_address = None
    if literal_address is not None and not literal_address.is_global:
        raise DataError("No se permiten direcciones locales o privadas")
    _resolve_public_addrs(host, port or (443 if parsed.scheme == "https" else 80))
    return url.strip()


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def connect(self) -> None:
        address = _resolve_public_addrs(self.host, self.port)[0]
        self.sock = socket.create_connection((address, self.port), self.timeout, self.source_address)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self) -> None:
        address = _resolve_public_addrs(self.host, self.port)[0]
        self.sock = socket.create_connection((address, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self._tunnel()
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self._tunnel_host or self.host)


class _PinnedHTTPHandler(HTTPHandler):
    def http_open(self, req: Request) -> Any:
        return self.do_open(_PinnedHTTPConnection, req)


class _PinnedHTTPSHandler(HTTPSHandler):
    def https_open(self, req: Request) -> Any:
        return self.do_open(_PinnedHTTPSConnection, req, context=self._context)


class PublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> Request | None:
        _validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_public_opener() -> Any:
    return build_opener(ProxyHandler({}), _PinnedHTTPHandler(),
                        _PinnedHTTPSHandler(), PublicRedirects())


def fetch_web_page(url: str) -> WebPreview:
    """Descarga una sola URL pública y previsualiza HTML, texto, CSV o PDF de texto."""
    url = _validate_public_url(url)
    request = Request(url, headers={"User-Agent": "PEA-i-UPC/1.0 (academic project)",
                                    "Accept": "text/html,text/plain,text/csv,application/pdf;q=0.9,*/*;q=0.1"})
    try:
        opener = _build_public_opener()
        with opener.open(request, timeout=15) as response:
            final_url = _validate_public_url(response.geturl())
            content_type = response.headers.get_content_type().casefold()
            charset = response.headers.get_content_charset()
            content = response.read(8_000_001)
    except (OSError, TimeoutError) as exc:
        raise DataError(f"No se pudo descargar la URL: {exc}") from exc
    if len(content) > 8_000_000:
        raise DataError("La respuesta supera 8 MB; use un archivo CSV local")
    if content.startswith(b"%PDF") or content_type == "application/pdf":
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "pagina.pdf"
            path.write_bytes(content)
            preview = parse_web_page(extract_pdf_text(path), final_url, "PDF de texto")
            if urlparse(final_url).hostname == "scienti.minciencias.gov.co":
                try:
                    kind, row = parse_scienti_pdf(path, final_url)
                    preview = preview._replace(suggested_kind=kind, suggested_row=row)
                except DataError:
                    pass
            return preview
    csv_file = content_type in ("text/csv", "application/csv", "application/vnd.ms-excel") or urlparse(final_url).path.lower().endswith(".csv")
    html_file = content_type in ("text/html", "application/xhtml+xml") or content[:500].lstrip().lower().startswith((b"<!doctype html", b"<html"))
    if not (csv_file or html_file or content_type.startswith("text/")):
        raise DataError(f"Formato web no legible: {content_type}")
    if not charset and html_file:
        match = re.search(rb"charset\s*=\s*['\"]?([A-Za-z0-9_-]+)", content[:5000], re.IGNORECASE)
        charset = match.group(1).decode("ascii") if match else None
    try:
        decoded = content.decode(charset or "utf-8-sig", errors="replace")
    except LookupError as exc:
        raise DataError(f"Codificación desconocida: {charset}") from exc
    preview = parse_web_page(decoded, final_url, "CSV" if csv_file else "HTML" if html_file else "Texto")
    return preview._replace(csv_bytes=content) if csv_file else preview


def chart_values(values: dict[str, int]) -> dict[str, int]:
    """Los campos sin valor cuentan en el total, pero no forman una barra de datos."""
    return {key: value for key, value in values.items() if key.strip().casefold() != "sin dato" and value > 0}


_GRUPLAC_LEVELS = ("A1", "A", "B", "C", "D", "Reconocido")


def _gruplac_category(value: str) -> str:
    """Reduce el texto de 'Clasificación' a un nivel válido (A1..D, Reconocido) o vacío."""
    token = value.split(" ")[0].strip()
    return token if token in _GRUPLAC_LEVELS else ""


def parse_scienti_html(html: str, url: str) -> tuple[str, dict[str, str]]:
    """Extrae campos identificables; evita atribuir productos a un perfil ambiguo."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "scienti.minciencias.gov.co":
        raise DataError("Solo se admiten URL públicas HTTPS de Scienti Minciencias")
    parser = VisibleText()
    parser.feed(html)
    lines = parser.lines()
    if not lines:
        raise DataError("La página no contiene texto legible")
    code = parse_qs(parsed.query)
    if "/gruplac/" in parsed.path and code.get("nro"):
        candidates = [line for line in lines if line.lower() not in ("gruplac - plataforma scienti - colombia", "datos básicos")]
        name = next((line for line in candidates if line in lines[:15] and len(line) > 2 and not line.lower().startswith(("inicio", "menú", "buscar"))), "")
        if not name:
            raise DataError("No se identificó el nombre del grupo")
        text = "\n".join(lines)
        def after(label: str) -> str:
            match = re.search(rf"(?im)^{re.escape(label)}\s*(?:[:|])?\s*(.+)$", text)
            if match:
                return match.group(1).strip()
            try:
                index = next(i for i, line in enumerate(lines) if line.casefold() == label.casefold())
                return lines[index + 1] if index + 1 < len(lines) else ""
            except StopIteration:
                return ""
        def block(label: str, stop: str) -> str:
            try:
                first = next(i for i, line in enumerate(lines) if line.casefold().startswith(label.casefold()))
            except StopIteration:
                return ""
            collected = [lines[first].split(":", 1)[1].strip()] if ":" in lines[first] else []
            for line in lines[first + 1:]:
                if line.casefold().startswith(stop.casefold()):
                    break
                collected.append(line)
            return "\n".join(part for part in collected if part)
        formed = after("Año y mes de formación")
        group = {
            "id": f"G-{code['nro'][0]}", "nombre": name,
            "codigo_gruplac": code["nro"][0], "responsable": after("Líder"),
            "categoria": _gruplac_category(after("Clasificación")),
            "descripcion": block("Estado del arte", "Objetivos"),
            "objetivos": block("Objetivos", "Retos"),
            "vision": after("Visión"),
            "lineas": block("Líneas de investigación declaradas por el grupo", "Integrantes del grupo"),
            "url": _redact_url(url), "fuente": f"Scienti, consultado {date.today().isoformat()}; formación: {formed}",
        }
        return "grupos", clean_row("grupos", group)
    if "/cvlac/" in parsed.path and code.get("cod_rh"):
        text = "\n".join(lines)
        match = re.search(r"(?im)^Nombre\s+([^\n]+)$", text)
        if not match:
            raise DataError("No se identificó el nombre del investigador")
        name = match.group(1).strip()
        category = ""
        for index, line in enumerate(lines):
            if line.casefold() == "categoría" and index + 1 < len(lines):
                category = lines[index + 1].split(" con vigencia")[0].strip()
                break
        if not category:
            found = re.search(r"Categoría Investigador\s+([^\n]+)", text, re.IGNORECASE)
            category = found.group(1).split(" con vigencia")[0].strip() if found else ""
        researcher = {
            "id": f"I-{code['cod_rh'][0]}", "nombre": name,
            "codigo_cvlac": code["cod_rh"][0],
            "categoria": category,
            "url": _redact_url(url), "fuente": f"Scienti, consultado {date.today().isoformat()}",
        }
        return "investigadores", clean_row("investigadores", researcher)
    raise DataError("La URL debe ser una ficha GrupLAC o CvLAC con su código")


def _require_gruplac_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "scienti.minciencias.gov.co" or "/gruplac/" not in parsed.path:
        raise DataError("La fuente debe ser una ficha GrupLAC HTTPS")
    code = parse_qs(parsed.query).get("nro", [""])[0]
    if not code:
        raise DataError("La ficha GrupLAC no tiene código de grupo")
    return code


def _name_key(value: str) -> str:
    plain = "".join(char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", plain).casefold().strip()


def parse_gruplac_members(html: str, url: str) -> list[tuple[dict[str, str], dict[str, str]]]:
    """Importa el censo explícito; conserva meses textuales sin inventar un día ISO."""
    code = _require_gruplac_url(url)
    parser = LinkedTableRows()
    parser.feed(html)
    first = next((i + 1 for i, row in enumerate(parser.rows)
                  if len(row) >= 4 and _name_key(row[0][0]) == "nombre"
                  and _name_key(row[1][0]) == "vinculacion"
                  and "inicio" in _name_key(row[3][0])), None)
    if first is None:
        return []
    members: list[tuple[dict[str, str], dict[str, str]]] = []
    seen: set[str] = set()
    for row in parser.rows[first:]:
        if len(row) < 4:
            if members:
                break
            continue
        match = re.match(r"^\d+\.-\s*(.+)$", row[0][0])
        if not match:
            if members:
                break
            continue
        name = match.group(1).strip()
        href = row[0][1]
        profile = urlparse(href)
        profile_code = ""
        if profile.scheme == "https" and profile.hostname == "scienti.minciencias.gov.co" and "/cvlac/" in profile.path:
            profile_code = parse_qs(profile.query).get("cod_rh", [""])[0]
        person_id = ("I-" + profile_code) if profile_code else (
            "I-GR-" + hashlib.sha1((code + "|" + _name_key(name)).encode("utf-8")).hexdigest()[:12].upper())
        if person_id in seen:
            continue
        seen.add(person_id)
        period = row[3][0].strip()
        role = row[1][0].strip() or "Integrante"
        ended = bool(re.search(r"\s-\s(?:19|20)\d{2}/\d{1,2}\s*$", period))
        person = clean_row("investigadores", {
            "id": person_id, "nombre": name, "codigo_cvlac": profile_code,
            "url": _redact_url(href) if profile_code else _redact_url(url),
            "fuente": f"GrupLAC, censo de integrantes, consultado {date.today().isoformat()}; vinculación: {period}",
        })
        membership = clean_row("membresias", {
            "grupo_id": "G-" + code, "investigador_id": person_id,
            "rol": f"{role} · {period}" if period else role,
            "activo": "0" if ended else "1",
        })
        members.append((person, membership))
    return members


def parse_gruplac_plan(html: str, url: str, objectives: str = "") -> dict[str, str] | None:
    code = _require_gruplac_url(url)
    parser = VisibleText()
    parser.feed(html)
    lines = parser.lines()
    try:
        first = lines.index("Plan Estratégico") + 1
    except ValueError:
        return None
    last = next((i for i in range(first, len(lines)) if lines[i].startswith("Estado del arte")), first)
    activities = "\n".join(lines[first:last]).strip()
    if not activities and not objectives:
        return None
    return clean_row("planes", {
        "id": "PL-" + code, "grupo_id": "G-" + code, "nombre": "Plan Estratégico",
        "objetivo": objectives, "actividad": activities,
    })


GRUPLAC_SECTIONS = (
    ("Artículos publicados", "Libros publicados", "Producción bibliográfica"),
    ("Libros publicados", "Capítulos de libro publicados", "Producción bibliográfica"),
    ("Capítulos de libro publicados", "Documentos de trabajo", "Producción bibliográfica"),
    ("Documentos de trabajo", "Otra publicación divulgativa", "Producción bibliográfica"),
    ("Otra publicación divulgativa", "Otros artículos publicados", "Producción bibliográfica"),
    ("Otros artículos publicados", "Libros de formación", "Producción bibliográfica"),
    ("Libros de formación", "Libros de divulgación y/o Compilación de divulgación", "Producción bibliográfica"),
    ("Otros Libros publicados", "Traducciones", "Producción bibliográfica"),
    ("Otros productos tecnológicos", "Prototipos", "Producción técnica y tecnológica"),
    ("Softwares", "Empresas de base tecnológica", "Producción técnica y tecnológica"),
    ("Empresas de base tecnológica", "APROPIACIÓN SOCIAL Y DIVULGACIÓN PÚBLICA DE LA CIENCIA", "Producción técnica y tecnológica"),
)


def parse_gruplac_products(html: str, url: str) -> list[GrupLACProduct]:
    """Extrae secciones con tipo, título y año explícitos; une fichas repetidas por DOI o título."""
    _require_gruplac_url(url)
    parser = VisibleText()
    parser.feed(html)
    lines = parser.lines()
    by_identity: dict[str, GrupLACProduct] = {}
    for section, stop, family in GRUPLAC_SECTIONS:
        try:
            first = lines.index(section) + 1
        except ValueError:
            continue
        last = next((i for i in range(first, len(lines)) if lines[i] == stop), len(lines))
        for index in range(first, last):
            match = re.match(r"^\d+\.-\s*([^:]+?)\s*:\s*(.+)$", lines[index])
            if not match:
                continue
            kind, title = match.group(1).strip(), match.group(2).strip()
            if not title:
                continue
            details: list[str] = []
            authors: list[str] = []
            for line in lines[index + 1:min(index + 16, last)]:
                if re.match(r"^\d+\.-\s", line):
                    break
                if line.startswith("Autores:"):
                    authors.extend(name.strip() for name in line[8:].split(",") if name.strip())
                    break
                details.append(line)
            detail = " ".join(details)
            year_match = re.search(r"(?<![\d-])((?:19|20)\d{2})(?=\s*(?:[,.;]|vol:|$))", detail)
            if not year_match or not _publication_year(year_match.group(1)):
                continue
            year = year_match.group(1)
            doi_match = re.search(r"\bDOI:\s*(10\.\S+)", detail, re.IGNORECASE)
            doi = doi_match.group(1).rstrip(".,;)") if doi_match else ""
            identity = "doi:" + doi.casefold() if doi else "title:" + _name_key(title) + "|" + year
            if not doi and section != "Artículos publicados":
                identity += "|" + _name_key(kind)
            previous = by_identity.get(identity)
            if previous:
                combined = list(previous.authors)
                known = {_name_key(name) for name in combined}
                for name in authors:
                    if _name_key(name) not in known:
                        combined.append(name)
                        known.add(_name_key(name))
                by_identity[identity] = previous._replace(authors=tuple(combined))
                continue
            stable_id = "P-GR-" + hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12].upper()
            row = clean_row("productos", {
                "id": stable_id, "titulo": title, "anio": year,
                "familia": family, "tipologia": kind,
                "doi": doi, "url": _redact_url(url),
                "fuente": f"GrupLAC, sección {section}, consultado {date.today().isoformat()}",
            })
            by_identity[identity] = GrupLACProduct(row, tuple(authors), section)
    return list(by_identity.values())


def parse_gruplac_articles(html: str, url: str) -> list[dict[str, str]]:
    """Compatibilidad: artículos de revista de la sección propia de GrupLAC."""
    return [entry.row for entry in parse_gruplac_products(html, url) if entry.section == "Artículos publicados"]


def match_gruplac_authors(products: list[GrupLACProduct],
                          members: list[tuple[dict[str, str], dict[str, str]]]) -> list[dict[str, str]]:
    by_name = {_name_key(person["nombre"]): person["id"] for person, _ in members}
    relations: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for product in products:
        for author in product.authors:
            researcher_id = by_name.get(_name_key(author))
            pair = (product.row["id"], researcher_id or "")
            if not researcher_id or pair in seen:
                continue
            seen.add(pair)
            relations.append(clean_row("autorias", {"producto_id": pair[0], "investigador_id": pair[1],
                                                   "rol": "Autor listado en GrupLAC"}))
    return relations


# Campos que una ficha GrupLAC vuelve a traer al importarla de nuevo; solo esos se actualizan,
# y solo con valores no vacíos. Las claves, la validación calculada, la observación de revisión
# y la URL de un producto (cambia según el grupo consultado) nunca se reemplazan.
REFRESH_FIELDS = {
    "grupos": ("nombre", "responsable", "categoria", "descripcion", "objetivos", "vision", "lineas", "url"),
    "investigadores": ("nombre", "categoria", "url"),
    "planes": ("nombre", "objetivo", "actividad"),
    "productos": ("familia", "tipologia"),
    "membresias": ("rol", "activo"),
}


def import_gruplac_preview(repository: Repository | CppRepository, preview: WebPreview,
                           reviewed_group: dict[str, str] | None = None, *,
                           remember: bool = True) -> dict[str, Any]:
    """Incorpora una ficha: crea lo nuevo y actualiza lo existente con lo que diga la fuente.

    remember=False (solo con Repository) omite el historial de deshacer en cargas masivas.
    """
    if preview.suggested_kind != "grupos" or not preview.suggested_row:
        raise DataError("La vista previa no contiene una ficha de grupo")
    source_group = preview.suggested_row
    group = clean_row("grupos", reviewed_group or source_group)
    if group["codigo_gruplac"] != source_group["codigo_gruplac"]:
        raise DataError("El código GrupLAC revisado no coincide con la fuente")
    group_id = group["id"]
    counts: dict[str, Any] = {kind: 0 for kind in (
        "grupos", "investigadores", "membresias", "planes", "productos", "grupos_productos", "autorias")}
    counts["existentes"] = counts["actualizados"] = 0
    counts["errors"] = []
    extra: dict[str, Any] = {} if remember else {"remember": False}

    def add(kind: str, row: dict[str, str], key: str | tuple[str, str]) -> bool:
        existing = repository.get(kind, key)
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
            changes = {name: row[name] for name in REFRESH_FIELDS.get(kind, ())
                       if row.get(name) and row[name] != existing.get(name, "")}
            if not changes:
                counts["existentes"] += 1
                return True
            # La fecha de consulta cambia en cada descarga: la fuente solo se renueva con el contenido.
            if row.get("fuente"):
                changes["fuente"] = row["fuente"]
            try:
                repository.update(kind, key, changes, **extra)
            except (DataError, OSError, ValueError) as exc:
                counts["errors"].append(f"{kind} {key}: {exc}")
                return True
            counts["actualizados"] += 1
            return True
        try:
            repository.create(kind, row, **extra)
        except (DataError, OSError, ValueError) as exc:
            counts["errors"].append(f"{kind} {key}: {exc}")
            return False
        counts[kind] += 1
        return True

    if not add("grupos", group, group_id):
        return counts
    available_people: set[str] = set()
    for person, _ in preview.related_members:
        if add("investigadores", person, person["id"]):
            available_people.add(person["id"])
    if preview.related_plan:
        plan = {**preview.related_plan, "grupo_id": group_id}
        add("planes", plan, plan["id"])
    for person, membership in preview.related_members:
        if person["id"] in available_people:
            row = {**membership, "grupo_id": group_id}
            add("membresias", row, (group_id, person["id"]))
    available_products: set[str] = set()
    for product in preview.related_products:
        if add("productos", product, product["id"]):
            available_products.add(product["id"])
    for product in preview.related_products:
        if product["id"] in available_products:
            row = {"grupo_id": group_id, "producto_id": product["id"],
                   "origen": "GrupLAC: producto listado en la ficha"}
            add("grupos_productos", row, (group_id, product["id"]))
    for authorship in preview.related_authorships:
        product_id, researcher_id = authorship["producto_id"], authorship["investigador_id"]
        if product_id in available_products and researcher_id in available_people:
            add("autorias", authorship, (product_id, researcher_id))
    return counts


def extract_docx_html(path: Path) -> str:
    """Convierte un .docx a fragmento HTML con mammoth (instalación opcional)."""
    _check_local_file(path, archive=True)
    try:
        import mammoth
    except ImportError as exc:
        raise DataError("Para importar Word instale mammoth (pip install mammoth)") from exc
    try:
        with path.open("rb") as stream:
            html = mammoth.convert_to_html(stream).value
            if len(html) > MAX_PDF_TEXT:
                raise DataError("El documento Word produce demasiado texto")
            return html
    except DataError:
        raise
    except Exception as exc:
        raise DataError(f"No se pudo leer el documento Word: {exc}") from exc


def extract_pdf_text(path: Path) -> str:
    """Admite PDF de texto si pdftotext (Poppler) está instalado."""
    _check_local_file(path)
    if shutil.which("pdftotext") is None:
        raise DataError("Para importar PDF instale Poppler (pdftotext) o use CSV")

    def limit_resources() -> None:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (MAX_PDF_MEMORY, MAX_PDF_MEMORY))
        resource.setrlimit(resource.RLIMIT_CPU, (PDF_TIMEOUT, PDF_TIMEOUT))

    try:
        process = subprocess.Popen(
            ["pdftotext", "-layout", str(path), "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            start_new_session=(os.name != "nt"),
            preexec_fn=limit_resources if os.name != "nt" else None,
        )
    except (OSError, ValueError) as exc:
        raise DataError(f"No se pudo leer el PDF: {exc}") from exc
    chunks: list[str] = []
    failures: list[Exception] = []

    def collect() -> None:
        total = 0
        try:
            assert process.stdout is not None
            while chunk := process.stdout.read(65536):
                total += len(chunk)
                if total > MAX_PDF_TEXT:
                    raise DataError("El PDF produce demasiado texto")
                chunks.append(chunk)
        except (OSError, UnicodeError, DataError) as exc:
            failures.append(exc)

    reader = threading.Thread(target=collect, daemon=True)
    reader.start()
    reader.join(PDF_TIMEOUT)
    if reader.is_alive() or failures:
        process.kill()
        process.wait()
        reader.join(timeout=1)
        if process.stdout is not None:
            process.stdout.close()
        if reader.is_alive():
            raise DataError("Se agotó el tiempo al leer el PDF")
        if failures:
            raise DataError(f"No se pudo leer el PDF: {failures[0]}") from failures[0]
        raise DataError("Se agotó el tiempo al leer el PDF")
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise DataError("Se agotó el tiempo al leer el PDF") from exc
    finally:
        if process.stdout is not None:
            process.stdout.close()
    if process.returncode != 0:
        raise DataError("No se pudo leer el PDF")
    text = "".join(chunks)
    if not text.strip():
        raise DataError("El PDF no contiene texto seleccionable; requiere OCR")
    return text


def parse_scienti_pdf(path: Path, source_url: str) -> tuple[str, dict[str, str]]:
    """Procesa PDFs impresos de GrupLAC/CvLAC con URL original conocida."""
    text = extract_pdf_text(path)
    # El exportador PDF presenta texto en bloques; reutilizamos la misma extracción
    # de campos, con saltos de línea preservados para no inventar asociaciones.
    from html import escape
    html = "<p>" + "</p><p>".join(escape(line) for line in text.splitlines()) + "</p>"
    return parse_scienti_html(html, source_url)


def new_id(prefix: str) -> str:
    return prefix + "-" + uuid.uuid4().hex[:8].upper()


def open_gui_repository(*, python_backend: bool = False,
                        cpp_binary: Path | None = None) -> tuple[Repository | CppRepository, str]:
    """Abre el motor disponible y devuelve un aviso si se usó el respaldo Python."""
    if python_backend:
        return Repository(), ""
    try:
        return CppRepository(cpp_binary), ""
    except DataError as exc:
        if cpp_binary is not None:
            raise
        return Repository(), str(exc).splitlines()[0]


def build_gui(root: Any, repository: Repository | CppRepository,
              data_file: Path | None = None, *, load_on_start: bool = True) -> Any:
    """Construye la ventana; permite verificar sus flujos con un repositorio aislado."""
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import filedialog, messagebox, simpledialog, ttk

    available_fonts = set(tkfont.families(root))

    def first_font(*names: str) -> str | None:
        return next((name for name in names if name in available_fonts), None)

    BODY_FONT = first_font("Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans") or "TkDefaultFont"
    STRONG_FONT = first_font("Segoe UI Semibold", "Segoe UI Variable Text Semibold")
    FIGURE_FONT = first_font("Bahnschrift SemiBold", "Bahnschrift", "Inter Display")

    def font(size: int, weight: str = "normal") -> tuple[Any, ...]:
        """weight: normal, strong (títulos) o figure (cifras)."""
        if weight == "figure" and FIGURE_FONT:
            return (FIGURE_FONT, size) if "Bahnschrift" in FIGURE_FONT else (FIGURE_FONT, size, "bold")
        if weight != "normal":
            return (STRONG_FONT, size) if STRONG_FONT else (BODY_FONT, size, "bold")
        return (BODY_FONT, size)

    # Campos, menús y diálogos estándar usan las fuentes con nombre de Tk.
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
        try:
            tkfont.nametofont(name, root=root).configure(family=BODY_FONT, size=10)
        except tk.TclError:
            pass

    SIDEBAR_WIDTH = 196
    PAGE_PADDING = (24, 18, 24, 14)

    TITLES = {"grupos": "Grupos", "investigadores": "Investigadores", "productos": "Productos",
              "planes": "Planes", "membresias": "Integrantes", "autorias": "Autorías",
              "grupos_productos": "Grupos y productos"}

    def record_name(row: dict[str, str]) -> str:
        return row.get("nombre") or row.get("titulo") or row["id"]

    def display_value(field: str, value: str) -> str:
        if field == "activo":
            return "Activo" if value == "1" else "Inactivo"
        if field == "validacion":
            return value.capitalize()
        return value or "Sin dato"

    def reason_text(reason: str, short: bool = False) -> str:
        codes = auto_reason_codes(reason)
        if codes is None:
            return reason or "Sin motivo registrado"
        rules = "; ".join(VALIDATION_RULES[code] for code in codes) or "rechazado"
        return rules if short else "Validación automática: " + rules

    def cell_value(field: str, value: str) -> str:
        """Texto de una celda de tabla: una línea y un guion discreto para lo vacío."""
        return " ".join(display_value(field, value).split()) if value or field == "activo" else "—"

    def show_columns(table: ttk.Treeview, columns: tuple[str, ...], usage: dict[str, int],
                     keep: tuple[str, ...] = ()) -> None:
        """Oculta las columnas que ningún registro ha llenado; reaparecen al tener datos."""
        shown = [name for name in columns
                 if name in keep or name.startswith("_") or usage.get(name, 1) > 0]
        if tuple(table.cget("displaycolumns")) != tuple(shown):
            table.configure(displaycolumns=shown)

    def place_dialog(dialog: tk.Toplevel, parent: tk.Misc, width: int, height: int) -> None:
        host = parent.winfo_toplevel()
        dialog.transient(host)
        width = min(width, host.winfo_screenwidth() - 60)
        height = min(height, host.winfo_screenheight() - 100)
        x = max(0, min(host.winfo_rootx() + (host.winfo_width() - width) // 2,
                       host.winfo_screenwidth() - width))
        y = max(0, min(host.winfo_rooty() + (host.winfo_height() - height) // 2,
                       host.winfo_screenheight() - height))
        dialog.geometry(f"{width}x{height}+{x}+{y}")

    def text_field(parent: tk.Misc, **options: Any) -> tk.Text:
        """tk.Text con el aspecto de los campos ttk del tema activo."""
        style = ttk.Style()
        return tk.Text(parent, wrap="word", font=font(10), relief="flat", borderwidth=0, padx=7, pady=5,
                       background=style.lookup("TEntry", "fieldbackground"),
                       foreground=style.lookup("TEntry", "foreground"),
                       insertbackground=style.lookup("TEntry", "foreground"),
                       selectbackground=style.lookup(".", "selectbackground"),
                       highlightthickness=1, highlightbackground=style.lookup("TEntry", "bordercolor"),
                       highlightcolor=style.lookup(".", "focuscolor"), **options)

    class AutoScrollbar(ttk.Scrollbar):
        """Solo ocupa espacio cuando el contenido no cabe (requiere grid)."""
        def grid(self, **options: Any) -> None:
            self._grid_options = options
            self._shown = True
            super().grid(**options)

        def set(self, first: Any, last: Any) -> None:
            needed = not (float(first) <= 0.0 and float(last) >= 1.0)
            if needed != getattr(self, "_shown", True) and hasattr(self, "_grid_options"):
                if needed:
                    super().grid(**self._grid_options)
                else:
                    self.grid_remove()
                self._shown = needed
            super().set(first, last)

    class ScrolledPage(ttk.Frame):
        def __init__(self, parent: tk.Misc):
            super().__init__(parent)
            self.columnconfigure(0, weight=1)
            self.rowconfigure(0, weight=1)
            self.scroll_canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
            scroll = AutoScrollbar(self, command=self.scroll_canvas.yview, style="Page.Vertical.TScrollbar")
            self.scroll_canvas.configure(yscrollcommand=scroll.set)
            self.scroll_canvas.grid(row=0, column=0, sticky="nsew")
            scroll.grid(row=0, column=1, sticky="ns")
            self.body = ttk.Frame(self.scroll_canvas, padding=PAGE_PADDING)
            window = self.scroll_canvas.create_window((0, 0), window=self.body, anchor="nw")
            self.body.bind("<Configure>", lambda _e: self.scroll_canvas.configure(
                scrollregion=self.scroll_canvas.bbox("all")))
            self.scroll_canvas.bind("<Configure>", lambda event: self.scroll_canvas.itemconfigure(
                window, width=event.width))

    class ChoiceDialog(tk.Toplevel):
        def __init__(self, parent: tk.Misc, title: str, prompt: str,
                     options: dict[str, str], default: str = ""):
            super().__init__(parent)
            self.title(title)
            place_dialog(self, parent, 530, 220)
            self.minsize(400, 200)
            self.result: str | None = None
            self.options = options
            self.columnconfigure(0, weight=1)
            ttk.Label(self, text=prompt, wraplength=480, padding=12).grid(row=0, column=0, sticky="ew")
            self.value = tk.StringVar(value=next((label for label, value in options.items() if value == default), next(iter(options))))
            self.box = ttk.Combobox(self, textvariable=self.value, values=list(options), state="readonly")
            self.box.grid(row=1, column=0, sticky="ew", padx=12)
            footer = ttk.Frame(self, padding=12)
            footer.grid(row=2, column=0, sticky="ew")
            ttk.Button(footer, text="Continuar", style="Accent.TButton", command=self.accept).pack(side="right")
            ttk.Button(footer, text="Cancelar", command=self.destroy).pack(side="right", padx=6)
            self.bind("<Escape>", lambda _e: self.destroy())
            self.bind("<Return>", lambda _e: self.accept())
            previous = self.grab_current()
            self.grab_set()
            self.box.focus_set()
            self.wait_window()
            if previous is not None and previous.winfo_exists():
                previous.grab_set()

        def accept(self) -> None:
            self.result = self.options[self.value.get()]
            self.destroy()

    class RecordPicker(tk.Toplevel):
        """Consulta paginada: el límite por página no limita las opciones disponibles."""
        def __init__(self, parent: tk.Misc, repo: Repository | CppRepository,
                     kind: str, current: str = ""):
            super().__init__(parent)
            self.title("Seleccionar " + TITLES[kind].lower())
            place_dialog(self, parent, 740, 530)
            self.minsize(500, 350)
            self.repo, self.kind = repo, kind
            self.result: str | None = None
            self.offset = 0
            self._timer: str | None = None
            self.search = tk.StringVar()
            self.columnconfigure(0, weight=1)
            self.rowconfigure(1, weight=1)
            top = ttk.Frame(self, padding=12)
            top.grid(row=0, column=0, sticky="ew")
            top.columnconfigure(1, weight=1)
            ttk.Label(top, text="Buscar nombre o ID").grid(row=0, column=0, padx=(0, 10))
            self.search_entry = ttk.Entry(top, textvariable=self.search)
            self.search_entry.grid(row=0, column=1, sticky="ew")
            self.search.trace_add("write", self._search_changed)
            body = ttk.Frame(self, padding=(12, 0))
            body.grid(row=1, column=0, sticky="nsew")
            body.columnconfigure(0, weight=1)
            body.rowconfigure(0, weight=1)
            self.table = ttk.Treeview(body, columns=("nombre", "id", "activo"),
                                      show="headings", selectmode="browse")
            for field, title, width in (("nombre", "Nombre / título", 380), ("id", "ID", 180),
                                         ("activo", "Estado", 90)):
                self.table.heading(field, anchor="w", text=title)
                self.table.column(field, width=width, minwidth=80)
            scroll = AutoScrollbar(body, command=self.table.yview)
            self.table.configure(yscrollcommand=scroll.set)
            self.table.grid(row=0, column=0, sticky="nsew")
            scroll.grid(row=0, column=1, sticky="ns")
            footer = ttk.Frame(self, padding=12)
            footer.grid(row=2, column=0, sticky="ew")
            pager = ttk.Frame(footer)
            pager.pack(fill="x", pady=(0, 6))
            self.previous = ttk.Button(pager, text="Anterior", command=lambda: self.move(-1))
            self.previous.pack(side="left")
            self.count = tk.StringVar()
            ttk.Label(pager, textvariable=self.count).pack(side="left", padx=10)
            self.next = ttk.Button(pager, text="Siguiente", command=lambda: self.move(1))
            self.next.pack(side="left")
            self.choose = ttk.Button(footer, text="Seleccionar", style="Accent.TButton", command=self.accept)
            self.choose.pack(side="right")
            ttk.Button(footer, text="Cancelar", command=self.destroy).pack(side="right", padx=6)
            self.table.bind("<<TreeviewSelect>>", lambda _e: self.choose.configure(
                state="normal" if self.table.selection() else "disabled"))
            self.table.bind("<Double-1>", lambda _e: self.accept())
            self.table.bind("<Return>", lambda _e: self.accept())
            self.bind("<Escape>", lambda _e: self.destroy())
            self.refresh()
            if current and self.table.exists(current):
                self.table.selection_set(current)
            previous_grab = self.grab_current()
            self.grab_set()
            self.search_entry.focus_set()
            self.wait_window()
            if previous_grab is not None and previous_grab.winfo_exists():
                previous_grab.grab_set()

        def _search_changed(self, *_: Any) -> None:
            if self._timer:
                self.after_cancel(self._timer)
            self.offset = 0
            self._timer = self.after(200, self.refresh)

        def refresh(self) -> None:
            if self._timer:
                self.after_cancel(self._timer)
                self._timer = None
            page = self.repo.page(self.kind, self.offset, PAGE_SIZE, self.search.get())
            self.table.delete(*self.table.get_children())
            for row in page["rows"]:
                self.table.insert("", "end", iid=row["id"],
                                  values=(record_name(row), row["id"], display_value("activo", row["activo"])))
            first = self.offset + 1 if page["total"] else 0
            self.count.set(f"{first}–{self.offset + len(page['rows'])} de {page['total']}")
            self.previous.configure(state="normal" if self.offset else "disabled")
            self.next.configure(state="normal" if self.offset + PAGE_SIZE < page["total"] else "disabled")
            self.choose.configure(state="disabled")

        def move(self, direction: int) -> None:
            self.offset = max(0, self.offset + direction * PAGE_SIZE)
            self.refresh()

        def accept(self) -> None:
            selected = self.table.selection()
            if selected:
                self.result = selected[0]
                self.destroy()

        def destroy(self) -> None:
            if self._timer:
                self.after_cancel(self._timer)
                self._timer = None
            super().destroy()

    class ReferenceInput(ttk.Frame):
        def __init__(self, parent: tk.Misc, repo: Repository | CppRepository, kind: str, value: str = "",
                     variable: tk.StringVar | None = None, command: Callable[[], Any] | None = None,
                     style: str = "TFrame"):
            super().__init__(parent, style=style)
            self.repo, self.kind, self.command = repo, kind, command
            self.value = variable if variable is not None else tk.StringVar()
            self.label = tk.StringVar()
            self._trace = self.value.trace_add("write", lambda *_: self._update_label())
            self.columnconfigure(0, weight=1)
            self.entry = ttk.Entry(self, textvariable=self.label, state="readonly")
            self.entry.grid(row=0, column=0, sticky="ew")
            self.button = ttk.Button(self, text="Elegir…", command=self.select)
            self.button.grid(row=0, column=1, padx=(6, 0))
            self.set(value)

        def get(self) -> str:
            return self.value.get()

        def set(self, value: str) -> None:
            self.value.set(value)

        def _update_label(self) -> None:
            value = self.value.get()
            row = self.repo.get(self.kind, value) if value else None
            self.label.set(f"{record_name(row)} · {value}" if row else value)

        def select(self) -> None:
            picker = RecordPicker(self, self.repo, self.kind, self.get())
            if picker.result:
                self.set(picker.result)
                if self.command:
                    self.command()

        def set_enabled(self, enabled: bool) -> None:
            self.button.configure(state="normal" if enabled else "disabled")

        def destroy(self) -> None:
            self.value.trace_remove("write", self._trace)
            super().destroy()

    class RecordDialog(tk.Toplevel):
        def __init__(self, parent: tk.Misc, kind: str, initial: dict[str, str] | None = None,
                     suggested_id: str = "", external: bool = False,
                     repo: Repository | CppRepository | None = None,
                     on_save: Callable[[dict[str, str]], Any] | None = None,
                     is_new: bool = False, locked_fields: tuple[str, ...] = ()):
            super().__init__(parent)
            self.title(("Revisar " if external else "Crear " if is_new or initial is None else "Editar ")
                       + TITLES[kind].lower())
            place_dialog(self, parent, 760, 650)
            self.resizable(True, True)
            self.minsize(540, 420)
            self.result: dict[str, str] | None = None
            self.kind, self.on_save = kind, on_save
            self.inputs: dict[str, Any] = {}
            self.error = tk.StringVar()
            self.columnconfigure(0, weight=1)
            self.rowconfigure(0, weight=1)
            canvas = tk.Canvas(self, highlightthickness=0, background=ttk.Style().lookup("TFrame", "background"))
            self.scroll_canvas = canvas
            scrollbar = AutoScrollbar(self, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")
            body = ttk.Frame(canvas, padding=(18, 12))
            window = canvas.create_window((0, 0), window=body, anchor="nw")
            body.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
            body.columnconfigure(1, weight=1)
            sections = {
                "grupos": (("Identificación", ("id", "nombre", "codigo_gruplac", "fecha_creacion", "unidad", "responsable", "categoria", "activo")),
                           ("Perfil de investigación", ("descripcion", "objetivos", "mision", "vision", "lineas")),
                           ("Procedencia", ("url", "fuente"))),
                "investigadores": (("Información personal pública", ("id", "nombre", "afiliacion", "contacto", "activo")),
                                    ("Clasificación", ("codigo_cvlac", "categoria")), ("Procedencia", ("url", "fuente"))),
                "productos": (("Producto", ("id", "titulo", "anio", "fecha", "doi", "activo")),
                               ("Clasificación y revisión", ("familia", "tipologia", "observacion")),
                               ("Procedencia", ("url", "fuente"))),
                "planes": (("Plan del grupo", ("id", "grupo_id", "nombre", "inicio", "fin", "activo")),
                            ("Objetivos y actividades", ("objetivo", "indicador", "meta", "actividad"))),
            }.get(kind, (("Asociación", ALL_FIELDS[kind]),))
            fields = [field for _, group in sections for field in group]
            headings = {group[0]: title for title, group in sections}
            index = 0
            for field in fields:
                if field in headings:
                    ttk.Label(body, text=headings[field], style="Section.TLabel").grid(
                        row=index, column=0, columnspan=2, sticky="w", padx=4, pady=(10, 6))
                    index += 1
                required = field in REQUIRED.get(kind, ()) or field.endswith("_id")
                label = LABELS.get(field, field).replace(" (ID)", "") + (" *" if required else "")
                ttk.Label(body, text=label).grid(row=index, column=0, sticky="nw", padx=4, pady=6)
                value = initial.get(field, "") if initial else ""
                if field == "activo" and not initial:
                    value = "1"
                if field == "id" and not value:
                    value = suggested_id
                if field in LONG_FIELDS:
                    widget = text_field(body, height=3, width=40)
                    widget.insert("1.0", value)
                elif field == "activo":
                    widget = ttk.Combobox(body, values=("Activo", "Inactivo"), state="readonly", width=30)
                    widget.set(display_value(field, value or "1"))
                elif field.endswith("_id") and repo is not None:
                    ref_kind = {"grupo_id": "grupos", "investigador_id": "investigadores", "producto_id": "productos"}[field]
                    widget = ReferenceInput(body, repo, ref_kind, value)
                else:
                    widget = ttk.Entry(body, width=40)
                    widget.insert(0, value)
                widget.grid(row=index, column=1, sticky="ew", padx=4, pady=3)
                stable = initial and not external and not is_new and (field == "id" or field in RELATION_ENDS.get(kind, ())[:2])
                if stable or field in locked_fields:
                    if isinstance(widget, ReferenceInput):
                        widget.set_enabled(False)
                    else:
                        widget.configure(state="readonly")
                self.inputs[field] = widget
                index += 1
            help_text = "* Campo obligatorio. Fechas: AAAA-MM-DD. Ctrl+Enter guarda."
            if kind == "productos":
                help_text += ("\nLa validación es automática y se recalcula al guardar: requiere año, tipología, "
                              "un autor y un grupo activos, y una URL o un DOI válido.")
            ttk.Label(body, text=help_text, style="Muted.TLabel", wraplength=500).grid(
                row=index, column=0, columnspan=2, sticky="w", pady=8)
            footer = ttk.Frame(self, padding=12)
            footer.grid(row=1, column=0, columnspan=2, sticky="ew")
            footer.columnconfigure(0, weight=1)
            self.error_label = ttk.Label(footer, textvariable=self.error, style="Error.TLabel", wraplength=600)
            self.error_label.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
            ttk.Button(footer, text="Guardar", style="Accent.TButton", command=self.accept).grid(row=1, column=1)
            ttk.Button(footer, text="Cancelar", command=self.destroy).grid(row=1, column=0, sticky="e", padx=8)
            self.bind("<Escape>", lambda _event: self.destroy())
            self.bind("<Control-Return>", lambda _event: self.accept())
            self.error_label.bind("<Configure>", lambda event: self.error_label.configure(wraplength=max(220, event.width - 10)))
            previous_grab = self.grab_current()
            self.grab_set()
            focus = self.inputs.get("nombre") or self.inputs.get("titulo")
            if focus is not None:
                focus.focus_set()
            self.wait_window()
            if previous_grab is not None and previous_grab.winfo_exists():
                previous_grab.grab_set()

        def accept(self) -> None:
            result = {}
            for field, widget in self.inputs.items():
                if isinstance(widget, tk.Text):
                    result[field] = widget.get("1.0", "end-1c").strip()
                else:
                    result[field] = widget.get().strip()
                if field == "activo":
                    result[field] = "1" if result[field] == "Activo" else "0"
            try:
                result = clean_row(self.kind, result)
                if self.on_save:
                    self.on_save(result)
            except (DataError, OSError, ValueError) as exc:
                self.error.set(str(exc))
                return
            self.result = result
            self.destroy()

    class ReviewDialog(tk.Toplevel):
        """Revisión del frente de la cola: corregir el producto y cerrar con una nota."""
        def __init__(self, parent: tk.Misc, app: "App", job: dict[str, str]):
            super().__init__(parent)
            self.title("Revisar siguiente producto")
            place_dialog(self, parent, 680, 540)
            self.minsize(480, 420)
            self.app, self.job = app, job
            self.result: dict[str, str] | None = None
            self.columnconfigure(0, weight=1)
            self.rowconfigure(5, weight=1)
            product = app.repo.get("productos", job["producto_id"])
            ttk.Label(self, text=record_name(product), style="Title.TLabel", wraplength=620,
                      padding=(18, 16, 18, 4)).grid(row=0, column=0, sticky="ew")
            ttk.Label(self, text="Motivo: " + reason_text(job["motivo"]), style="Muted.TLabel", wraplength=620,
                      padding=(18, 0)).grid(row=1, column=0, sticky="ew")
            state = ttk.Frame(self, style="Card.TFrame", padding=(14, 10))
            state.grid(row=2, column=0, sticky="ew", padx=18, pady=12)
            state.columnconfigure(0, weight=1)
            self.state_text = tk.StringVar()
            self.state_label = ttk.Label(state, textvariable=self.state_text, style="Card.TLabel",
                                         wraplength=520, justify="left")
            self.state_label.grid(row=0, column=0, sticky="ew")
            ttk.Button(state, text="Editar producto", command=self.edit_product).grid(row=0, column=1, sticky="ne", padx=(10, 0))
            ttk.Label(self, text="Nota de la revisión *", padding=(18, 0)).grid(row=4, column=0, sticky="w")
            self.observation = text_field(self, height=5, width=40)
            self.observation.grid(row=5, column=0, sticky="nsew", padx=18, pady=6)
            self.error = tk.StringVar()
            ttk.Label(self, textvariable=self.error, style="Error.TLabel", wraplength=620,
                      padding=(18, 0)).grid(row=6, column=0, sticky="ew")
            footer = ttk.Frame(self, padding=(18, 12))
            footer.grid(row=7, column=0, sticky="ew")
            ttk.Button(footer, text="Ver ficha", command=lambda: app.open_detail("productos", product["id"], self)).pack(side="left")
            ttk.Button(footer, text="Cerrar revisión", style="Accent.TButton", command=self.accept).pack(side="right")
            ttk.Button(footer, text="Cancelar", command=self.destroy).pack(side="right", padx=6)
            self._update_state()
            self.bind("<Escape>", lambda _e: self.destroy())
            self.bind("<Control-Return>", lambda _e: self.accept())
            previous = self.grab_current()
            self.grab_set()
            self.observation.focus_set()
            self.wait_window()
            if previous is not None and previous.winfo_exists():
                previous.grab_set()

        def _update_state(self) -> None:
            product = self.app.repo.get("productos", self.job["producto_id"])
            issues = self.app.repo.product_issues(self.job["producto_id"])
            if product["validacion"] == "validado":
                self.state_text.set("Validado: el producto cumple todas las reglas.")
                self.state_label.configure(style="Card.TLabel")
            else:
                self.state_text.set("Rechazado. Corrija el producto o explique en la nota por qué no es posible:\n"
                                    + "\n".join("• " + VALIDATION_RULES[code] for code in issues))
                self.state_label.configure(style="Rejected.Card.TLabel")

        def edit_product(self) -> None:
            self.app.edit_record("productos", key=self.job["producto_id"], parent=self)
            self._update_state()

        def accept(self) -> None:
            try:
                self.result = self.app.repo.process_review(self.observation.get("1.0", "end-1c"))
            except (DataError, OSError, ValueError) as exc:
                self.error.set(str(exc))
                return
            self.destroy()

    class EntityTab(ttk.Frame):
        def __init__(self, parent: tk.Misc, app: "App", kind: str):
            super().__init__(parent, padding=PAGE_PADDING)
            self.app, self.kind = app, kind
            self.search = tk.StringVar()
            self.state_filter = tk.StringVar(value="Todos")
            self.offset = 0
            self._search_timer: str | None = None
            heading = ttk.Frame(self)
            heading.pack(fill="x", pady=(0, 14))
            ttk.Label(heading, text=TITLES[kind], style="Heading.TLabel").pack(side="left")
            ttk.Button(heading, text="Nuevo", style="Accent.TButton", command=self.create).pack(side="right")
            toolbar = ttk.Frame(self)
            toolbar.pack(fill="x")
            ttk.Label(toolbar, text="Buscar", style="Muted.TLabel").pack(side="left")
            ttk.Entry(toolbar, textvariable=self.search, width=20).pack(side="left", padx=8, fill="x", expand=True)
            state_box = ttk.Combobox(toolbar, textvariable=self.state_filter, values=("Todos", "Activos", "Inactivos"),
                                    state="readonly", width=10)
            state_box.pack(side="left")
            state_box.bind("<<ComboboxSelected>>", lambda _e: self._search_changed())
            self.search.trace_add("write", lambda *_: self._search_changed())
            actions = ttk.Frame(self)
            actions.pack(fill="x", pady=(10, 0))
            self.selection_buttons = []
            for label, action in (("Abrir ficha", self.open_detail), ("Editar", self.edit),
                                  ("Desactivar", self.toggle), ("Eliminar", self.delete)):
                button = ttk.Button(actions, text=label, command=action,
                                    style="Danger.TButton" if label == "Eliminar" else "TButton")
                button.pack(side="left", padx=(0, 6))
                self.selection_buttons.append(button)
                if label == "Desactivar":
                    self.toggle_button = button
            # La categoría solo se muestra en el módulo de grupos. Las columnas sin datos se ocultan al refrescar.
            visible = {
                "grupos": ("nombre", "categoria", "responsable", "activo", "id"),
                "investigadores": ("nombre", "afiliacion", "contacto", "activo", "id"),
                "productos": ("titulo", "anio", "tipologia", "validacion", "activo", "id"),
                "planes": ("grupo_id", "nombre", "objetivo", "inicio", "fin", "activo", "id"),
            }[kind]
            table_frame = ttk.Frame(self)
            table_frame.pack(fill="both", expand=True, pady=(10, 0))
            table_frame.columnconfigure(0, weight=1)
            table_frame.rowconfigure(0, weight=1)
            self.table = ttk.Treeview(table_frame, columns=visible, show="headings", selectmode="browse", height=14)
            self.table.tag_configure("stripe", background=self.app.colors["stripe"])
            for field in visible:
                self.table.heading(field, anchor="w", text="Estado" if field == "activo" else LABELS[field].replace(" (ID)", ""))
                width = (360 if field == "objetivo" else 300 if field in ("titulo", "nombre", "grupo_id") else
                         220 if field in ("responsable", "tipologia", "afiliacion") else
                         180 if field in ("id", "contacto") else 110)
                self.table.column(field, width=width, minwidth=65, stretch=True)
            table_y = AutoScrollbar(table_frame, orient="vertical", command=self.table.yview)
            table_x = AutoScrollbar(table_frame, orient="horizontal", command=self.table.xview)
            self.table.configure(yscrollcommand=table_y.set, xscrollcommand=table_x.set)
            self.table.grid(row=0, column=0, sticky="nsew")
            table_y.grid(row=0, column=1, sticky="ns")
            table_x.grid(row=1, column=0, sticky="ew")
            if kind == "productos":
                self.table.bind("<ButtonRelease-1>", lambda event: self.open_detail() if self.table.identify_row(event.y) else None)
            else:
                self.table.bind("<Double-1>", lambda _event: self.open_detail())
            self.table.bind("<Return>", lambda _event: self.open_detail())
            self.table.bind("<<TreeviewSelect>>", lambda _event: self._selection_changed())
            self.empty_state = ttk.Label(table_frame, text="Sin registros. Cree uno nuevo o cambie la búsqueda.",
                                          style="Muted.TLabel", wraplength=400)
            pager = ttk.Frame(self, padding=(0, 10, 0, 0))
            pager.pack(side="bottom", fill="x", before=table_frame)
            self.previous = ttk.Button(pager, text="Anterior", command=lambda: self._move(-1))
            self.previous.pack(side="left")
            self.page_label = tk.StringVar()
            ttk.Label(pager, textvariable=self.page_label).pack(side="left", padx=10)
            self.next = ttk.Button(pager, text="Siguiente", command=lambda: self._move(1))
            self.next.pack(side="left")
            if kind in ("grupos", "investigadores"):
                ttk.Button(pager, text="Consultar fuente", command=self.open_source).pack(side="right")
            self.visible = visible

        def selected(self) -> str | None:
            selection = self.table.selection()
            return selection[0] if selection else None

        def _selection_changed(self) -> None:
            key = self.selected()
            for button in self.selection_buttons:
                button.configure(state="normal" if key else "disabled")
            row = self.app.record(self.kind, key) if key else None
            self.toggle_button.configure(text="Activar" if row and row["activo"] == "0" else "Desactivar")

        def _search_changed(self) -> None:
            self.offset = 0
            if self._search_timer is not None:
                self.after_cancel(self._search_timer)
            self._search_timer = self.after(250, self._perform_search)

        def _perform_search(self) -> None:
            self._search_timer = None
            self.refresh()

        def _move(self, direction: int) -> None:
            self.offset = max(0, self.offset + direction * PAGE_SIZE)
            self.refresh()

        def refresh(self) -> None:
            if self._search_timer is not None:
                self.after_cancel(self._search_timer)
                self._search_timer = None
            current = self.selected()
            self.table.delete(*self.table.get_children())
            page = self.app.entity_page(self.kind, self.offset, self.search.get(), self.state_filter.get())
            if self.offset and self.offset >= page["total"]:
                self.offset = max(0, (page["total"] - 1) // PAGE_SIZE * PAGE_SIZE)
                page = self.app.entity_page(self.kind, self.offset, self.search.get(), self.state_filter.get())
            for index, row in enumerate(page["rows"]):
                self.app._record_cache[(self.kind, row["id"])] = row
                values = [self.app.reference_label("grupos", row[field]) if field == "grupo_id" else cell_value(field, row[field])
                          for field in self.visible]
                self.table.insert("", "end", iid=row["id"], values=values,
                                  tags=("stripe",) if index % 2 else ())
            self.page_label.set(f"{self.offset + 1 if page['total'] else 0}–{self.offset + len(page['rows'])} de {page['total']}")
            show_columns(self.table, self.visible, self.app.usage(self.kind), keep=("nombre", "titulo", "activo", "id"))
            if current and self.table.exists(current):
                self.table.selection_set(current)
            self._selection_changed()
            self.previous.configure(state="normal" if self.offset else "disabled")
            self.next.configure(state="normal" if self.offset + PAGE_SIZE < page["total"] else "disabled")
            if page["total"]:
                self.empty_state.place_forget()
            else:
                self.empty_state.place(relx=0.5, rely=0.45, anchor="center")

        def open_detail(self) -> None:
            key = self.selected()
            if key:
                self.app.open_detail(self.kind, key, self)

        def create(self) -> None:
            self.app.edit_record(self.kind, parent=self)

        def edit(self) -> None:
            key = self.selected()
            if not key:
                return
            self.app.edit_record(self.kind, key=key, parent=self)

        def open_source(self) -> None:
            key = self.selected()
            if key:
                row = self.app.repo.get(self.kind, key)
                if row and row["url"]:
                    self.app.import_url(row["url"])
                else:
                    messagebox.showinfo("Sin fuente", "Este registro no tiene URL de origen", parent=self)

        def toggle(self) -> None:
            key = self.selected()
            if key:
                self.app.mutate(lambda: self.app.repo.toggle(self.kind, key))

        def delete(self) -> None:
            key = self.selected()
            row = self.app.record(self.kind, key) if key else None
            if row and messagebox.askyesno("Eliminar", f"¿Eliminar {record_name(row)} definitivamente?\nPuede deshacer este cambio antes de vaciar el historial.", parent=self):
                self.app.mutate(lambda: self.app.repo.delete(self.kind, key))

        def restyle(self) -> None:
            self.table.tag_configure("stripe", background=self.app.colors["stripe"])

    class RelationTab(ttk.Frame):
        def __init__(self, parent: tk.Misc, app: "App", kind: str):
            super().__init__(parent, padding=(14, 14, 14, 10))
            self.app, self.kind = app, kind
            self.offset = 0
            self.search = tk.StringVar()
            self._search_timer: str | None = None
            search_bar = ttk.Frame(self)
            search_bar.pack(fill="x", pady=(0, 10))
            ttk.Label(search_bar, text="Buscar nombres, IDs o datos del vínculo", style="Muted.TLabel").pack(side="left")
            ttk.Entry(search_bar, textvariable=self.search, width=30).pack(side="left", padx=8, fill="x", expand=True)
            ttk.Button(search_bar, text="Vincular", style="Accent.TButton", command=self.create).pack(side="right", padx=(8, 0))
            self.search.trace_add("write", self._search_changed)
            actions = ttk.Frame(self)
            actions.pack(fill="x")
            for label, action in (("Editar", self.edit),
                                  ("Activar/desactivar", self.toggle), ("Desvincular", self.delete)):
                ttk.Button(actions, text=label, command=action,
                           style="Danger.TButton" if label == "Desvincular" else "TButton").pack(side="left", padx=(0, 6))
            self.fields = RELATION_FIELDS[kind]
            table_frame = ttk.Frame(self)
            table_frame.pack(fill="both", expand=True, pady=10)
            table_frame.columnconfigure(0, weight=1)
            table_frame.rowconfigure(0, weight=1)
            self.table = ttk.Treeview(table_frame, columns=self.fields, show="headings", selectmode="browse")
            self.table.tag_configure("stripe", background=self.app.colors["stripe"])
            for field in self.fields:
                self.table.heading(field, anchor="w", text=LABELS.get(field, field).replace(" (ID)", ""))
                self.table.column(field, width=260 if field.endswith("_id") else 130)
            table_y = AutoScrollbar(table_frame, orient="vertical", command=self.table.yview)
            table_x = AutoScrollbar(table_frame, orient="horizontal", command=self.table.xview)
            self.table.configure(yscrollcommand=table_y.set, xscrollcommand=table_x.set)
            self.table.grid(row=0, column=0, sticky="nsew")
            table_y.grid(row=0, column=1, sticky="ns")
            table_x.grid(row=1, column=0, sticky="ew")
            pager = ttk.Frame(self)
            pager.pack(fill="x")
            ttk.Button(pager, text="Anterior", command=lambda: self._move(-1)).pack(side="left")
            self.page_label = tk.StringVar()
            ttk.Label(pager, textvariable=self.page_label).pack(side="left", padx=10)
            ttk.Button(pager, text="Siguiente", command=lambda: self._move(1)).pack(side="left")

        def _search_changed(self, *_: Any) -> None:
            self.offset = 0
            if self._search_timer:
                self.after_cancel(self._search_timer)
            self._search_timer = self.after(250, self.refresh)

        def _move(self, direction: int) -> None:
            self.offset = max(0, self.offset + direction * PAGE_SIZE)
            self.refresh()

        def selected(self) -> tuple[str, str] | None:
            selection = self.table.selection()
            if not selection:
                return None
            return tuple(json.loads(selection[0]))  # type: ignore[return-value]

        def refresh(self) -> None:
            if self._search_timer:
                self.after_cancel(self._search_timer)
                self._search_timer = None
            current = self.table.selection()
            self.table.delete(*self.table.get_children())
            left, right = RELATION_ENDS[self.kind][:2]
            page = self.app.relationship_page(self.kind, self.offset, self.search.get())
            if self.offset and self.offset >= page["total"]:
                self.offset = max(0, (page["total"] - 1) // PAGE_SIZE * PAGE_SIZE)
                page = self.app.relationship_page(self.kind, self.offset, self.search.get())
            left_kind, right_kind = RELATION_ENDS[self.kind][2:]
            for index, row in enumerate(page["rows"]):
                pair = json.dumps((row[left], row[right]))
                values = [self.app.reference_label(left_kind if field == left else right_kind, row[field])
                          if field in (left, right) else cell_value(field, row[field]) for field in self.fields]
                self.table.insert("", "end", iid=pair, values=values,
                                  tags=("stripe",) if index % 2 else ())
            self.page_label.set(f"{self.offset + 1 if page['total'] else 0}–{self.offset + len(page['rows'])} de {page['total']}")
            show_columns(self.table, self.fields, self.app.usage(self.kind), keep=(left, right, "activo"))
            if current and self.table.exists(current[0]):
                self.table.selection_set(current[0])

        def create(self) -> None:
            self.app.edit_record(self.kind, parent=self)

        def edit(self) -> None:
            key = self.selected()
            if not key:
                return
            self.app.edit_record(self.kind, key=key, parent=self)

        def toggle(self) -> None:
            key = self.selected()
            if key:
                self.app.mutate(lambda: self.app.repo.toggle(self.kind, key))

        def delete(self) -> None:
            key = self.selected()
            if key and messagebox.askyesno("Desvincular", "¿Eliminar esta relación?", parent=self):
                self.app.mutate(lambda: self.app.repo.delete(self.kind, key))

        def restyle(self) -> None:
            self.table.tag_configure("stripe", background=self.app.colors["stripe"])

    class ContextTab(ttk.Frame):
        def __init__(self, parent: tk.Misc, detail: "DetailDialog", source: str, side: str,
                     target_kind: str, columns: tuple[str, ...]):
            super().__init__(parent, padding=10)
            self.detail, self.app = detail, detail.app
            self.source, self.side, self.target_kind = source, side, target_kind
            self.columns = columns
            self.offset = 0
            self.search = tk.StringVar()
            self._timer: str | None = None
            self.items: dict[str, tuple[dict[str, str], dict[str, str]]] = {}
            toolbar = ttk.Frame(self)
            toolbar.pack(fill="x", pady=(0, 5))
            ttk.Label(toolbar, text="Buscar").pack(side="left")
            ttk.Entry(toolbar, textvariable=self.search, width=25).pack(side="left", padx=6)
            self.search.trace_add("write", self._search_changed)
            ttk.Button(toolbar, text="Nuevo plan" if source == "planes" else "Vincular…",
                       style="Accent.TButton", command=self.create).pack(side="right")
            actions = ttk.Frame(self)
            actions.pack(fill="x", pady=(0, 6))
            self.selection_buttons = []
            for label, command in (("Abrir ficha", self.open_record), ("Editar registro", self.edit_record),
                                    ("Editar vínculo" if source != "planes" else "Editar plan", self.edit_link),
                                    ("Activar/desactivar", self.toggle),
                                    ("Desvincular" if source != "planes" else "Eliminar plan", self.delete)):
                if source == "planes" and label == "Editar registro":
                    continue
                button = ttk.Button(actions, text=label, command=command,
                                    style="Danger.TButton" if label in ("Desvincular", "Eliminar plan") else "TButton")
                button.pack(side="left", padx=(0, 6))
                self.selection_buttons.append(button)
            frame = ttk.Frame(self)
            frame.pack(fill="both", expand=True)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
            self.table = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
            for field in columns:
                label = {"_link_active": "Vínculo", "_record_active": "Registro"}.get(field, LABELS.get(field, field))
                self.table.heading(field, anchor="w", text=label)
                self.table.column(field, width=270 if field in ("nombre", "titulo") else 120, minwidth=70)
            yscroll = AutoScrollbar(frame, command=self.table.yview)
            xscroll = AutoScrollbar(frame, orient="horizontal", command=self.table.xview)
            self.table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
            self.table.grid(row=0, column=0, sticky="nsew")
            yscroll.grid(row=0, column=1, sticky="ns")
            xscroll.grid(row=1, column=0, sticky="ew")
            self.table.bind("<<TreeviewSelect>>", lambda _e: self._selection_changed())
            if target_kind == "productos":
                self.table.bind("<ButtonRelease-1>", lambda event: self.open_record() if self.table.identify_row(event.y) else None)
            else:
                self.table.bind("<Double-1>", lambda _e: self.open_record())
            self.table.bind("<Return>", lambda _e: self.open_record())
            pager = ttk.Frame(self)
            pager.pack(side="bottom", fill="x", pady=(5, 0), before=frame)
            self.previous = ttk.Button(pager, text="Anterior", command=lambda: self.move(-1))
            self.previous.pack(side="left")
            self.count = tk.StringVar()
            ttk.Label(pager, textvariable=self.count).pack(side="left", padx=8)
            self.next = ttk.Button(pager, text="Siguiente", command=lambda: self.move(1))
            self.next.pack(side="left")

        def _search_changed(self, *_: Any) -> None:
            if self._timer:
                self.after_cancel(self._timer)
            self.offset = 0
            self._timer = self.after(250, self.refresh)

        def move(self, direction: int) -> None:
            self.offset = max(0, self.offset + direction * PAGE_SIZE)
            self.refresh()

        def selected(self) -> tuple[dict[str, str], dict[str, str]] | None:
            selected = self.table.selection()
            return self.items.get(selected[0]) if selected else None

        def _selection_changed(self) -> None:
            state = "normal" if self.selected() else "disabled"
            for button in self.selection_buttons:
                button.configure(state=state)

        def refresh(self) -> None:
            if self._timer:
                self.after_cancel(self._timer)
                self._timer = None
            selected = self.table.selection()
            page = self.detail.page_for(self, self.offset, self.search.get())
            if self.offset and self.offset >= page["total"]:
                self.offset = max(0, (page["total"] - 1) // PAGE_SIZE * PAGE_SIZE)
                page = self.detail.page_for(self, self.offset, self.search.get())
            self.items.clear()
            self.table.delete(*self.table.get_children())
            self.table.tag_configure("stripe", background=self.app.colors["stripe"])
            for index, (row, link) in enumerate(page["rows"]):
                self.items[row["id"]] = (row, link)
                combined = {**row, **link, "_link_active": link["activo"], "_record_active": row["activo"]}
                values = [cell_value("activo" if field.startswith("_") else field, combined.get(field, ""))
                          for field in self.columns]
                self.table.insert("", "end", iid=row["id"], values=values, tags=("stripe",) if index % 2 else ())
            if selected and self.table.exists(selected[0]):
                self.table.selection_set(selected[0])
            self._selection_changed()
            usage = {**self.app.usage(self.target_kind), **self.app.usage(self.source)}
            show_columns(self.table, self.columns, usage, keep=("nombre", "titulo"))
            first = self.offset + 1 if page["total"] else 0
            self.count.set(f"{first}–{self.offset + len(page['rows'])} de {page['total']}" if page["total"] else "Sin datos asociados")
            self.previous.configure(state="normal" if self.offset else "disabled")
            self.next.configure(state="normal" if self.offset + PAGE_SIZE < page["total"] else "disabled")

        def create(self) -> None:
            field = "grupo_id" if self.source == "planes" else RELATION_ENDS[self.source][0 if self.side == "left" else 1]
            self.app.edit_record(self.source, defaults={field: self.detail.key}, parent=self.detail, locked_fields=(field,))

        def edit_link(self) -> None:
            item = self.selected()
            if item:
                row, link = item
                key = row["id"] if self.source == "planes" else tuple(link[field] for field in RELATION_ENDS[self.source][:2])
                self.app.edit_record(self.source, key=key, parent=self.detail)

        def edit_record(self) -> None:
            item = self.selected()
            if item:
                self.app.edit_record(self.target_kind, key=item[0]["id"], parent=self.detail)

        def open_record(self) -> None:
            item = self.selected()
            if item:
                self.app.open_detail(self.target_kind, item[0]["id"], self.detail)

        def toggle(self) -> None:
            item = self.selected()
            if item:
                row, link = item
                key = row["id"] if self.source == "planes" else tuple(link[field] for field in RELATION_ENDS[self.source][:2])
                self.app.mutate(lambda: self.app.repo.toggle(self.source, key))

        def delete(self) -> None:
            item = self.selected()
            if item and messagebox.askyesno("Eliminar asociación" if self.source != "planes" else "Eliminar plan",
                                            f"¿Eliminar {record_name(item[0])} de esta ficha?", parent=self.detail):
                row, link = item
                key = row["id"] if self.source == "planes" else tuple(link[field] for field in RELATION_ENDS[self.source][:2])
                self.app.mutate(lambda: self.app.repo.delete(self.source, key))

        def destroy(self) -> None:
            if self._timer:
                self.after_cancel(self._timer)
                self._timer = None
            super().destroy()

    class DetailDialog(tk.Toplevel):
        def __init__(self, parent: tk.Misc, app: "App", kind: str, key: str):
            super().__init__(parent)
            self.app, self.kind, self.key = app, kind, key
            self.title("Ficha · " + TITLES[kind])
            place_dialog(self, parent, 1000, 670)
            self.minsize(700, 480)
            self.columnconfigure(0, weight=1)
            self.rowconfigure(1, weight=1)
            header = ttk.Frame(self, padding=(20, 16, 20, 12))
            header.grid(row=0, column=0, sticky="ew")
            header.columnconfigure(0, weight=1)
            self.heading = tk.StringVar()
            ttk.Label(header, textvariable=self.heading, style="Title.TLabel", wraplength=700).grid(row=0, column=0, sticky="w")
            ttk.Button(header, text="Editar ficha", style="Accent.TButton", command=lambda: app.edit_record(
                kind, key=key, parent=self)).grid(row=0, column=1, padx=(12, 0))
            self.notebook = ttk.Notebook(self)
            self.notebook.grid(row=1, column=0, sticky="nsew", padx=20)
            information = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(information, text="Resumen")
            self.info = tk.Text(information, wrap="word", font=font(10), state="disabled",
                                padx=18, pady=10, borderwidth=0, relief="flat", highlightthickness=1)
            scroll = ttk.Scrollbar(information, command=self.info.yview)
            self.info.configure(yscrollcommand=scroll.set)
            self.info.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")
            # Categorías solo dentro de los grupos: la del grupo y la de sus integrantes.
            specifications = {
                "grupos": (("Integrantes", "membresias", "left", "investigadores", ("nombre", "categoria", "rol", "inicio", "fin", "_link_active", "_record_active")),
                           ("Planes", "planes", "left", "planes", ("nombre", "inicio", "fin", "objetivo", "_record_active")),
                           ("Productos", "grupos_productos", "left", "productos", ("titulo", "anio", "tipologia", "validacion", "_link_active", "_record_active"))),
                "investigadores": (("Grupos", "membresias", "right", "grupos", ("nombre", "rol", "inicio", "fin", "_link_active", "_record_active")),
                                    ("Productos", "autorias", "right", "productos", ("titulo", "anio", "tipologia", "validacion", "orden", "rol", "_link_active", "_record_active"))),
                "productos": (("Autores", "autorias", "left", "investigadores", ("nombre", "orden", "rol", "_link_active", "_record_active")),
                               ("Grupos", "grupos_productos", "right", "grupos", ("nombre", "origen", "_link_active", "_record_active"))),
                "planes": (),
            }
            self.link_tabs = {}
            for title, source, side, target, columns in specifications[kind]:
                tab = ContextTab(self.notebook, self, source, side, target, columns)
                self.link_tabs[source] = tab
                self.notebook.add(tab, text=title)
            self.stats_canvas = None
            if kind != "planes":
                stats = ttk.Frame(self.notebook, padding=10)
                self.notebook.add(stats, text="Estadísticas")
                self.stats_note = tk.StringVar()
                ttk.Label(stats, textvariable=self.stats_note, wraplength=800).pack(fill="x", pady=(0, 6))
                panel, self.stats_canvas = app._chart_panel(stats, 280)
                panel.pack(fill="both", expand=True)
                self.stats_canvas.bind("<Configure>", lambda _e: self._draw_statistics())
                ttk.Button(stats, text="Explorar en Dashboard con filtros", command=self.show_statistics).pack(anchor="e", pady=6)
            footer = ttk.Frame(self, padding=(20, 12))
            footer.grid(row=2, column=0, sticky="ew")
            if kind == "productos":
                ttk.Button(footer, text="Enviar a revisión", command=lambda: app.enqueue(key, parent=self)).pack(side="left")
            elif kind == "planes":
                ttk.Button(footer, text="Abrir grupo", command=lambda: app.open_detail(
                    "grupos", app.repo.get(kind, key)["grupo_id"], self)).pack(side="left")
            self.source_button = ttk.Button(footer, text="Consultar fuente", command=self.open_source)
            if kind != "planes":
                self.source_button.pack(side="left", padx=6)
            ttk.Button(footer, text="Cerrar", command=self.destroy).pack(side="right")
            self.bind("<Escape>", lambda _e: self.destroy())
            self._previous_grab = self.grab_current()
            self.refresh()
            app.details.add(self)
            self.grab_set()

        def page_for(self, tab: ContextTab, offset: int, query: str) -> dict[str, Any]:
            needle = query.strip().casefold()
            if tab.source != "planes" and not needle:
                page = self.app.repo.related_page(tab.source, self.key, tab.side, offset, PAGE_SIZE)
                field = RELATION_ENDS[tab.source][1 if tab.side == "left" else 0]
                return {"total": page["total"], "rows": [(self.app.record(tab.target_kind, link[field]), link) for link in page["rows"]]}
            total = 0
            rows = []
            position = 0
            while True:
                page = (self.app.repo.page("planes", position, PAGE_SIZE) if tab.source == "planes" else
                        self.app.repo.related_page(tab.source, self.key, tab.side, position, PAGE_SIZE))
                for link in page["rows"]:
                    if tab.source == "planes":
                        if link["grupo_id"] != self.key:
                            continue
                        row = link
                    else:
                        field = RELATION_ENDS[tab.source][1 if tab.side == "left" else 0]
                        row = self.app.record(tab.target_kind, link[field])
                    if needle and needle not in " ".join((*row.values(), *link.values())).casefold():
                        continue
                    if offset <= total < offset + PAGE_SIZE:
                        rows.append((row, link))
                    total += 1
                position += len(page["rows"])
                if not page["rows"] or position >= page["total"]:
                    break
            return {"total": total, "rows": rows}

        def refresh(self) -> None:
            row = self.app.repo.get(self.kind, self.key)
            if row is None:
                self.destroy()
                return
            self.heading.set(f"{record_name(row)} · {display_value('activo', row['activo'])}")
            colors = self.app.colors
            self.info.configure(state="normal", background=colors["surface"], foreground=colors["ink"],
                                selectbackground=colors["primary_soft"], highlightbackground=colors["line"])
            self.info.tag_configure("label", font=font(9, "strong"), foreground=colors["muted"], spacing1=12)
            self.info.tag_configure("value", font=font(10), foreground=colors["ink"], spacing1=2, lmargin1=0)
            self.info.tag_configure("missing", font=font(9), foreground=colors["muted"], spacing1=16)
            self.info.tag_configure("issue", font=font(10), foreground=colors["rejected"], spacing1=2)
            self.info.delete("1.0", "end")
            # Solo campos con datos; los vacíos se resumen en una línea. La categoría de
            # un investigador se consulta desde los integrantes de su grupo.
            hidden = {"investigadores": {"categoria"}}.get(self.kind, set())
            missing = []
            first = True
            for field in ENTITY_FIELDS[self.kind]:
                if field in hidden:
                    continue
                if field != "validacion" and not row[field]:
                    missing.append(LABELS[field])
                    continue
                self.info.insert("end", ("" if first else "\n") + LABELS[field] + "\n", "label")
                first = False
                if field == "validacion":
                    issues = self.app.repo.product_issues(self.key)
                    self.info.insert("end", "Validado: cumple todas las reglas" if not issues else "Rechazado", "value")
                    for code in issues:
                        self.info.insert("end", "\n• " + VALIDATION_RULES[code], "issue")
                else:
                    self.info.insert("end", display_value(field, row[field]), "value")
            if missing:
                self.info.insert("end", "\nSin registrar: " + ", ".join(missing), "missing")
            self.info.configure(state="disabled")
            self.source_button.configure(state="normal" if row.get("url") else "disabled")
            for tab in self.link_tabs.values():
                tab.refresh()
            if self.stats_canvas is not None:
                self.statistics = self.app.repo.statistics({"grupos": "Grupo", "investigadores": "Investigador", "productos": "Producto"}[self.kind], self.key, limit=0)
                self.stats_note.set(f"{self.statistics['total']} productos activos únicos de esta ficha · Todos los años. Los vínculos inactivos se excluyen.")
                self._draw_statistics()

        def _draw_statistics(self) -> None:
            if self.stats_canvas is not None and hasattr(self, "statistics"):
                self.stats_canvas.configure(bg=self.app.colors["surface"])
                self.app._draw_histogram(self.stats_canvas, self.statistics["por_anio"])

        def show_statistics(self) -> None:
            kind, key = self.kind, self.key
            self.destroy()
            self.app.view.set({"grupos": "Grupo", "investigadores": "Investigador", "productos": "Producto"}[kind])
            self.app._scope_changed(key)
            self.app._show_page("dashboard")

        def open_source(self) -> None:
            row = self.app.repo.get(self.kind, self.key)
            self.destroy()
            self.app.import_url(row["url"])

        def destroy(self) -> None:
            self.app.details.discard(self)
            previous = getattr(self, "_previous_grab", None)
            super().destroy()
            if previous is not None and previous.winfo_exists():
                previous.grab_set()

    # «Sierra y sabana»: verde institucional UPC; el amarillo solo marca lo pendiente.
    LIGHT_THEME = {
        "page": "#f3f6f3", "surface": "#ffffff", "field": "#ffffff",
        "sidebar": "#163a2e", "sidebar_fg": "#e3ece7", "sidebar_muted": "#a9c2b6",
        "sidebar_hover": "#1f4a3b", "ink": "#1c2a24", "muted": "#5b6c64",
        "line": "#dce4df", "line_strong": "#c3cfc8", "hover": "#eaf0ec",
        "primary": "#1e6b50", "primary_hover": "#185a43", "primary_pressed": "#124636",
        "on_primary": "#ffffff", "primary_soft": "#dcefe5", "stripe": "#f7faf8",
        "thumb": "#c3cfc8", "thumb_active": "#9fb0a7",
        "chart_grid": "#e7ece9", "chart_track": "#eef3f0", "chart_older": "#8fb8a5",
        "pending": "#bb7e0e", "rejected": "#b5472f", "unknown": "#87938d",
        "error": "#b42318",
    }

    DARK_THEME = {
        "page": "#111714", "surface": "#18201c", "field": "#1d2621",
        "sidebar": "#0b100e", "sidebar_fg": "#e3ece7", "sidebar_muted": "#8fa79b",
        "sidebar_hover": "#16201b", "ink": "#e3ece7", "muted": "#94a69d",
        "line": "#28332e", "line_strong": "#3a4842", "hover": "#222c27",
        "primary": "#4db38c", "primary_hover": "#2f8a68", "primary_pressed": "#236b51",
        "on_primary": "#ffffff", "primary_soft": "#1f3a30", "stripe": "#1b241f",
        "thumb": "#34423b", "thumb_active": "#4a5b52",
        "chart_grid": "#232d28", "chart_track": "#202a25", "chart_older": "#3f7d65",
        "pending": "#e6b04a", "rejected": "#e07a62", "unknown": "#7d8c85",
        "error": "#ffb4ab",
    }
    # Botón primario: en oscuro el verde claro sirve para trazos, no como fondo de texto blanco.
    DARK_THEME["button"] = "#2a7a5c"
    LIGHT_THEME["button"] = LIGHT_THEME["primary"]
    STATUS_COLORS = {"validado": "primary", "rechazado": "rejected", "Sin dato": "unknown"}

    class App:
        def __init__(self, root: tk.Tk, initial_file: Path | None,
                     repository: Repository | CppRepository):
            self.root = root
            self.repo = repository
            self.backend_name = "C++" if isinstance(repository, CppRepository) else "Python"
            self.theme = "light"
            # Archivo donde se guarda; None si los datos aún no tienen uno (vacío, carpeta anterior o copia).
            self.data_file: Path | None = None
            self.initial_file = initial_file
            self._url_busy = False
            self.details: set[DetailDialog] = set()
            self._record_cache: dict[tuple[str, str], dict[str, str]] = {}
            self._usage_cache: dict[str, dict[str, int]] = {}
            self._year_timer: str | None = None
            self.status = tk.StringVar(value="Iniciando PEA-i…")
            self.workspace = tk.StringVar()
            self.workspace_caption = "Espacio vacío"
            self.root.title("PEA-i UPC — Investigación")
            self.root.geometry("1280x850")
            self.root.minsize(900, 620)
            self._apply_theme("light")
            self._menu()
            # El lateral ocupa toda la altura; cabecera y estado pertenecen al contenido.
            self.sidebar = ttk.Frame(root, style="Sidebar.TFrame", width=SIDEBAR_WIDTH)
            self.sidebar.pack(side="left", fill="y")
            self.sidebar.pack_propagate(False)
            main = ttk.Frame(root)
            main.pack(side="left", fill="both", expand=True)
            workspace_bar = ttk.Frame(main, style="Header.TFrame", padding=(24, 10, 16, 10))
            workspace_bar.pack(side="top", fill="x")
            workspace_bar.columnconfigure(0, weight=1)
            self.workspace_label = ttk.Label(workspace_bar, textvariable=self.workspace, style="Header.TLabel")
            self.workspace_label.grid(row=0, column=0, sticky="w")
            self.save_button = ttk.Button(workspace_bar, text="Guardar como…", style="Accent.TButton", command=self.save)
            self.save_button.grid(row=0, column=1, padx=(8, 0))
            workspace_bar.bind("<Configure>", lambda event: self.workspace_label.configure(wraplength=max(200, event.width - 180)))
            ttk.Frame(main, style="Rule.TFrame", height=1).pack(side="top", fill="x")
            self.status_label = ttk.Label(main, textvariable=self.status, style="Status.TLabel",
                                          padding=(24, 7), anchor="w", justify="left")
            self.status_label.pack(side="bottom", fill="x")
            ttk.Frame(main, style="Rule.TFrame", height=1).pack(side="bottom", fill="x")
            main.bind("<Configure>", lambda event: self.status_label.configure(wraplength=max(200, event.width - 48)))
            self.menu_expanded = True
            brand_row = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
            brand_row.pack(fill="x", padx=10, pady=(14, 0))
            self.burger = ttk.Button(brand_row, text="☰", width=2,
                                     style="Burger.TButton", command=self._toggle_menu)
            self.burger.pack(side="left")
            self.brand = ttk.Label(brand_row, text="PEA-i", style="Brand.TLabel")
            self.brand.pack(side="left", padx=(4, 0))
            self.sidebar_items = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
            self.sidebar_items.pack(fill="both", expand=True)
            ttk.Label(self.sidebar_items, text="Universidad Popular del Cesar", style="SidebarCaption.TLabel",
                      padding=(22, 2, 12, 6), wraplength=SIDEBAR_WIDTH - 34).pack(anchor="w")
            self.content = ttk.Frame(main)
            self.content.pack(side="top", fill="both", expand=True)
            self.content.rowconfigure(0, weight=1)
            self.content.columnconfigure(0, weight=1)

            self.pages: dict[str, tk.Widget] = {}
            self.dashboard = ttk.Frame(self.content)
            self._build_dashboard()
            self.graphs = ttk.Frame(self.content, padding=PAGE_PADDING)
            self._build_graphs()
            self.entity_tabs: dict[str, EntityTab] = {}
            for kind in ("grupos", "investigadores", "productos", "planes"):
                self.entity_tabs[kind] = EntityTab(self.content, self, kind)
            relations_host = ttk.Frame(self.content, padding=PAGE_PADDING)
            ttk.Label(relations_host, text="Relaciones", style="Heading.TLabel").pack(anchor="w")
            ttk.Label(relations_host, text="Vínculos entre investigadores, grupos y productos.",
                      style="Muted.TLabel").pack(anchor="w", pady=(2, 12))
            relations = ttk.Notebook(relations_host)
            relations.pack(fill="both", expand=True)
            self.relation_tabs: dict[str, RelationTab] = {}
            for kind, title in (("membresias", "Integrantes"), ("autorias", "Autorías"),
                                ("grupos_productos", "Grupos / productos")):
                tab = RelationTab(relations, self, kind)
                self.relation_tabs[kind] = tab
                relations.add(tab, text=title)
            self.queue_tab = ttk.Frame(self.content, padding=PAGE_PADDING)
            self._build_queue()

            self.nav_buttons = {}
            for group, items in (
                    ("Análisis", (("dashboard", "Dashboard", self.dashboard),
                                  ("graphs", "Gráficos", self.graphs))),
                    ("Registros", (("grupos", "Grupos", self.entity_tabs["grupos"]),
                                   ("investigadores", "Investigadores", self.entity_tabs["investigadores"]),
                                   ("productos", "Productos", self.entity_tabs["productos"]),
                                   ("planes", "Planes", self.entity_tabs["planes"]),
                                   ("relaciones", "Relaciones", relations_host))),
                    ("Seguimiento", (("cola", "Cola de revisión", self.queue_tab),))):
                ttk.Label(self.sidebar_items, text=group, style="NavGroup.TLabel",
                          padding=(22, 14, 0, 4)).pack(anchor="w")
                for page_id, title, page in items:
                    self.pages[page_id] = page
                    # Sin margen derecho: el elemento activo se une al contenido como una pestaña.
                    button = ttk.Button(self.sidebar_items, text=title, style="Nav.TButton",
                                        command=lambda p=page_id: self._show_page(p))
                    button.pack(fill="x", padx=(10, 0), pady=1)
                    self.nav_buttons[page_id] = button
            self.theme_button = ttk.Button(self.sidebar_items, text="Modo oscuro", style="SidebarGhost.TButton",
                                           command=self._toggle_theme)
            self.theme_button.pack(side="bottom", fill="x", padx=12, pady=14)
            for page in self.pages.values():
                page.grid(row=0, column=0, sticky="nsew")

            self.refresh()
            self._show_page("dashboard")
            self.root.protocol("WM_DELETE_WINDOW", self.close)
            self._startup_timer = self.root.after(80, self.start_choice) if load_on_start else None
            self.root.bind("<Destroy>", self._destroyed, add="+")
            self.root.bind_all("<MouseWheel>", self._wheel)
            self.root.bind_all("<Button-4>", self._wheel)
            self.root.bind_all("<Button-5>", self._wheel)

        def _destroyed(self, event: tk.Event) -> None:
            if event.widget is self.root:
                for timer in (self._year_timer, self._startup_timer):
                    if timer:
                        self.root.after_cancel(timer)
                for tab in (*self.entity_tabs.values(), *self.relation_tabs.values()):
                    if tab._search_timer:
                        self.root.after_cancel(tab._search_timer)

        def _show_page(self, page_id: str) -> None:
            self.active_page = page_id
            for key, button in self.nav_buttons.items():
                button.configure(style="Selected.Nav.TButton" if key == page_id else "Nav.TButton")
            self.pages[page_id].tkraise()
            if page_id == "graphs":
                self._redraw_charts()

        def _wheel(self, event: tk.Event) -> str | None:
            widget = event.widget
            if isinstance(widget, (tk.Text, ttk.Treeview, ttk.Combobox)):
                return None
            units = -1 if getattr(event, "num", None) == 4 else 1 if getattr(event, "num", None) == 5 else (
                -int(event.delta / 120) if abs(event.delta) >= 120 else -1 if event.delta > 0 else 1)
            while widget is not None:
                if isinstance(widget, tk.Canvas) and widget.cget("yscrollcommand"):
                    bbox = widget.bbox("all")
                    if bbox and bbox[3] - bbox[1] > widget.winfo_height():
                        widget.yview_scroll(units, "units")
                        return "break"
                canvas = getattr(widget, "scroll_canvas", None)
                if canvas is not None:
                    bbox = canvas.bbox("all")
                    if bbox and bbox[3] - bbox[1] > canvas.winfo_height():
                        canvas.yview_scroll(units, "units")
                        return "break"
                widget = getattr(widget, "master", None)
            return None

        def _toggle_menu(self) -> None:
            if self.menu_expanded:
                self.sidebar_items.pack_forget()
                self.brand.pack_forget()
                self.sidebar.configure(width=56)
            else:
                self.brand.pack(side="left", padx=(4, 0))
                self.sidebar_items.pack(fill="both", expand=True)
                self.sidebar.configure(width=SIDEBAR_WIDTH)
            self.menu_expanded = not self.menu_expanded

        def _show_status(self) -> None:
            messagebox.showinfo("Estado de datos", self.status.get(), parent=self.root)

        def _apply_theme(self, theme: str) -> None:
            style = ttk.Style()
            if "clam" in style.theme_names():
                style.theme_use("clam")
            colors = LIGHT_THEME if theme == "light" else DARK_THEME
            self.theme = theme
            self.colors = colors
            c = colors

            def flat(name: str, background: str, border: str | None = None, **options: Any) -> None:
                """clam dibuja biseles con light/darkcolor; igualarlos al fondo deja el control plano."""
                style.configure(name, background=background, bordercolor=border or background,
                                lightcolor=background, darkcolor=background, **options)

            self.root.configure(background=c["page"])
            for pattern, value in (("*Toplevel.background", c["page"]),
                                   ("*TCombobox*Listbox.background", c["surface"]),
                                   ("*TCombobox*Listbox.foreground", c["ink"]),
                                   ("*TCombobox*Listbox.selectBackground", c["primary_soft"]),
                                   ("*TCombobox*Listbox.selectForeground", c["ink"]),
                                   ("*TCombobox*Listbox.font", font(10))):
                self.root.option_add(pattern, value)
            style.configure(".", font=font(10), background=c["page"], foreground=c["ink"],
                            troughcolor=c["page"], focuscolor=c["primary"], selectbackground=c["primary_soft"],
                            selectforeground=c["ink"], insertcolor=c["ink"])
            style.configure("TFrame", background=c["page"])
            style.configure("TLabel", background=c["page"], foreground=c["ink"])
            style.configure("Muted.TLabel", foreground=c["muted"])
            style.configure("Error.TLabel", foreground=c["error"])
            style.configure("Heading.TLabel", font=font(20, "strong"), foreground=c["ink"])
            style.configure("Section.TLabel", font=font(12, "strong"), foreground=c["ink"])
            style.configure("Title.TLabel", font=font(15, "strong"), foreground=c["ink"])
            style.configure("Rule.TFrame", background=c["line"])
            # Tarjetas: superficie blanca con borde fino; sus hijos usan *.Card.* para no mostrar el fondo de página.
            flat("Card.TFrame", c["surface"], c["line"], borderwidth=1, relief="solid")
            style.configure("CardBody.TFrame", background=c["surface"])
            style.configure("Card.TLabel", background=c["surface"], foreground=c["ink"])
            style.configure("Muted.Card.TLabel", background=c["surface"], foreground=c["muted"], font=font(9))
            style.configure("Error.Card.TLabel", background=c["surface"], foreground=c["error"])
            style.configure("Rejected.Card.TLabel", background=c["surface"], foreground=c["rejected"])
            style.configure("CardValue.TLabel", background=c["surface"], foreground=c["ink"], font=font(24, "figure"))
            style.configure("CardCaption.TLabel", background=c["surface"], foreground=c["muted"], font=font(9))
            for tone in ("sidebar", "primary", "pending", "rejected", "unknown"):
                style.configure(f"{tone}.Stripe.TFrame", background=c[tone] if tone != "sidebar" else c["ink"])
            style.configure("Header.TFrame", background=c["surface"])
            style.configure("Header.TLabel", background=c["surface"], foreground=c["muted"], font=font(9))
            style.configure("Dirty.Header.TLabel", background=c["surface"], foreground=c["pending"], font=font(9, "strong"))
            style.configure("Status.TLabel", background=c["page"], foreground=c["muted"], font=font(9))
            # Lateral
            style.configure("Sidebar.TFrame", background=c["sidebar"])
            style.configure("Brand.TLabel", background=c["sidebar"], foreground=c["sidebar_fg"], font=font(16, "figure"))
            style.configure("SidebarCaption.TLabel", background=c["sidebar"], foreground=c["sidebar_muted"], font=font(9))
            style.configure("NavGroup.TLabel", background=c["sidebar"], foreground=c["sidebar_muted"], font=font(9))
            flat("Nav.TButton", c["sidebar"], foreground=c["sidebar_fg"], anchor="w", padding=(12, 7),
                 font=font(10), relief="flat", focuscolor=c["sidebar"])
            style.map("Nav.TButton", background=[("pressed", c["sidebar_hover"]), ("active", c["sidebar_hover"])],
                      lightcolor=[("active", c["sidebar_hover"])], darkcolor=[("active", c["sidebar_hover"])],
                      bordercolor=[("active", c["sidebar_hover"])], foreground=[("active", c["sidebar_fg"])])
            # Activo: toma el color de la página y se une al contenido.
            flat("Selected.Nav.TButton", c["page"], foreground=c["primary"], font=font(10, "strong"),
                 focuscolor=c["page"])
            style.map("Selected.Nav.TButton", background=[("active", c["page"]), ("pressed", c["page"])],
                      lightcolor=[("active", c["page"])], darkcolor=[("active", c["page"])],
                      bordercolor=[("active", c["page"])], foreground=[("active", c["primary"])])
            flat("Burger.TButton", c["sidebar"], foreground=c["sidebar_fg"], padding=(8, 2), font=font(15),
                 relief="flat", focuscolor=c["sidebar"])
            style.map("Burger.TButton", background=[("active", c["sidebar_hover"])],
                      lightcolor=[("active", c["sidebar_hover"])], darkcolor=[("active", c["sidebar_hover"])],
                      bordercolor=[("active", c["sidebar_hover"])], foreground=[("active", c["sidebar_fg"])])
            flat("SidebarGhost.TButton", c["sidebar"], c["sidebar_hover"], foreground=c["sidebar_muted"],
                 padding=(10, 6), font=font(9), focuscolor=c["sidebar"])
            style.map("SidebarGhost.TButton", background=[("active", c["sidebar_hover"])],
                      lightcolor=[("active", c["sidebar_hover"])], darkcolor=[("active", c["sidebar_hover"])],
                      foreground=[("active", c["sidebar_fg"])])
            # Botones: secundarios con borde visible en ambos temas.
            flat("TButton", c["surface"], c["line_strong"], foreground=c["ink"], padding=(12, 6), relief="solid", width=-6)
            style.map("TButton", background=[("disabled", c["page"]), ("pressed", c["line"]), ("active", c["hover"])],
                      lightcolor=[("disabled", c["page"]), ("pressed", c["line"]), ("active", c["hover"])],
                      darkcolor=[("disabled", c["page"]), ("pressed", c["line"]), ("active", c["hover"])],
                      bordercolor=[("disabled", c["line"]), ("active", c["primary"])],
                      foreground=[("disabled", c["unknown"])])
            flat("Accent.TButton", c["button"], foreground=c["on_primary"], padding=(14, 7), font=font(10, "strong"))
            style.map("Accent.TButton", background=[("disabled", c["line"]), ("pressed", c["primary_pressed"]), ("active", c["primary_hover"])],
                      lightcolor=[("pressed", c["primary_pressed"]), ("active", c["primary_hover"])],
                      darkcolor=[("pressed", c["primary_pressed"]), ("active", c["primary_hover"])],
                      bordercolor=[("pressed", c["primary_pressed"]), ("active", c["primary_hover"])],
                      foreground=[("disabled", c["muted"]), ("active", c["on_primary"])])
            flat("Danger.TButton", c["surface"], c["line_strong"], foreground=c["rejected"], padding=(12, 6))
            style.map("Danger.TButton", background=[("disabled", c["page"]), ("active", c["hover"])],
                      lightcolor=[("disabled", c["page"]), ("active", c["hover"])],
                      darkcolor=[("disabled", c["page"]), ("active", c["hover"])],
                      bordercolor=[("disabled", c["line"]), ("active", c["rejected"])],
                      foreground=[("disabled", c["unknown"])])
            # Campos con anillo de foco.
            for name in ("TEntry", "TCombobox"):
                style.configure(name, fieldbackground=c["field"], foreground=c["ink"], bordercolor=c["line_strong"],
                                lightcolor=c["field"], darkcolor=c["field"], padding=(7, 5), arrowcolor=c["muted"],
                                background=c["field"], insertcolor=c["ink"])
                # Una entrada de solo lectura se distingue de una editable; una lista desplegable no.
                readonly = c["page"] if name == "TEntry" else c["field"]
                style.map(name, bordercolor=[("focus", c["primary"])], lightcolor=[("focus", c["primary"])],
                          fieldbackground=[("disabled", c["page"]), ("readonly", readonly)],
                          foreground=[("disabled", c["muted"]), ("readonly", c["ink"])],
                          background=[("active", c["hover"]), ("pressed", c["line"])],
                          arrowcolor=[("disabled", c["line_strong"]), ("active", c["primary"])],
                          selectbackground=[("readonly", c["field"]), ("!focus", c["field"])],
                          selectforeground=[("readonly", c["ink"]), ("!focus", c["ink"])])
            # Barras de desplazamiento finas, sin flechas.
            for orient, sticky in (("Vertical", "ns"), ("Horizontal", "ew")):
                style.layout(f"{orient}.TScrollbar", [(f"{orient}.Scrollbar.trough", {"sticky": sticky, "children": [
                    (f"{orient}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
                # Casi todas viven en tablas y tarjetas; la de la página usa el fondo de página.
                flat(f"{orient}.TScrollbar", c["thumb"], troughcolor=c["surface"], gripcount=0,
                     arrowsize=9, width=9, relief="flat", borderwidth=0)
                style.configure(f"{orient}.TScrollbar", troughcolor=c["surface"], bordercolor=c["surface"])
                style.map(f"{orient}.TScrollbar", background=[("active", c["thumb_active"]), ("pressed", c["thumb_active"])],
                          lightcolor=[("active", c["thumb_active"])], darkcolor=[("active", c["thumb_active"])])
            style.configure("Page.Vertical.TScrollbar", troughcolor=c["page"], bordercolor=c["page"])
            # Pestañas planas.
            style.configure("TNotebook", background=c["page"], bordercolor=c["line"], lightcolor=c["page"],
                            darkcolor=c["page"], borderwidth=0, tabmargins=(0, 0, 0, 0))
            flat("TNotebook.Tab", c["page"], c["line"], foreground=c["muted"], padding=(16, 8))
            style.map("TNotebook.Tab", background=[("selected", c["surface"]), ("active", c["hover"])],
                      lightcolor=[("selected", c["surface"]), ("active", c["hover"])],
                      darkcolor=[("selected", c["surface"]), ("active", c["hover"])],
                      foreground=[("selected", c["primary"]), ("active", c["ink"])],
                      font=[("selected", font(10, "strong"))], padding=[("selected", (16, 8))],
                      expand=[("selected", (0, 0, 0, 0))])
            style.configure("TLabelframe", background=c["page"], bordercolor=c["line"], relief="solid")
            style.configure("TLabelframe.Label", background=c["page"], foreground=c["ink"], font=font(10, "strong"))
            style.configure("TSeparator", background=c["line"])
            # Tablas: encabezados alineados a la izquierda, selección tenue.
            flat("Treeview", c["surface"], c["line"], fieldbackground=c["surface"], foreground=c["ink"],
                 rowheight=30, borderwidth=1)
            style.map("Treeview", background=[("selected", c["primary_soft"])],
                      foreground=[("selected", c["ink"])])
            flat("Treeview.Heading", c["surface"], c["line"], foreground=c["muted"], relief="flat",
                 padding=(8, 7), font=font(9, "strong"))
            style.map("Treeview.Heading", background=[("active", c["hover"])],
                      lightcolor=[("active", c["hover"])], darkcolor=[("active", c["hover"])])
            for menu in getattr(self, "_menus", ()):
                menu.configure(background=c["surface"], foreground=c["ink"],
                               activebackground=c["primary_soft"], activeforeground=c["ink"],
                               borderwidth=0, font=font(10))
            self._restyle_widgets()

        def _toggle_theme(self) -> None:
            self._apply_theme("dark" if self.theme == "light" else "light")
            self.theme_button.configure(text="Modo claro" if self.theme == "dark" else "Modo oscuro")

        def _restyle_widgets(self) -> None:
            colors = self.colors
            for name in ("year_canvas", "type_canvas", "validation_canvas", "rules_canvas",
                         "dashboard_year_canvas", "dashboard_type_canvas"):
                canvas = getattr(self, name, None)
                if canvas is not None:
                    canvas.configure(bg=colors["surface"])
            for name in ("stats_table",):
                table = getattr(self, name, None)
                if table is not None:
                    table.tag_configure("stripe", background=colors["stripe"])
            for tab in getattr(self, "entity_tabs", {}).values():
                tab.restyle()
            for tab in getattr(self, "relation_tabs", {}).values():
                tab.restyle()
            if hasattr(self, "dashboard_page"):
                self.dashboard_page.scroll_canvas.configure(bg=colors["page"])
            if hasattr(self, "queue_table"):
                self.queue_table.tag_configure("stripe", background=colors["stripe"])
            if hasattr(self, "current_stats"):
                self._redraw_charts()
            for detail in tuple(getattr(self, "details", ())):
                detail.refresh()

        def _menu(self) -> None:
            menu = tk.Menu(self.root)
            files = tk.Menu(menu, tearoff=False)
            for label, command in (("Iniciar vacío", self.new_workspace),
                                   ("Abrir archivo de datos...", self.open_file),
                                   ("Abrir datos UPC", self.open_default),
                                   ("Guardar", self.save), ("Guardar como...", self.save_as),
                                   ("Exportar para hoja de cálculo...", self.export_spreadsheet),
                                   ("Salir", self.close)):
                files.add_command(label=label, command=command)
            menu.add_cascade(label="Archivo", menu=files)
            imports = tk.Menu(menu, tearoff=False)
            for label, command in (("Hoja de cálculo (CSV/Excel)...", self.import_csv),
                                   ("URL pública...", self.import_url),
                                   ("PDF de texto GrupLAC/CvLAC...", self.import_pdf),
                                   ("Documento Word...", self.import_docx)):
                imports.add_command(label=label, command=command)
            menu.add_cascade(label="Importar", menu=imports)
            edit = tk.Menu(menu, tearoff=False)
            edit.add_command(label="Deshacer", command=self.undo, accelerator="Ctrl+Z")
            edit.add_command(label="Vaciar historial", command=self.clear_history)
            menu.add_cascade(label="Editar", menu=edit)
            help_menu = tk.Menu(menu, tearoff=False)
            help_menu.add_command(label="Estado de datos", command=self._show_status)
            help_menu.add_command(label="Acerca de PEA-i", command=lambda: messagebox.showinfo(
                "Acerca de PEA-i", f"Programa Estadístico de Análisis de Investigación\n"
                f"Universidad Popular del Cesar\nMotor de datos: {self.backend_name}", parent=self.root))
            menu.add_cascade(label="Ayuda", menu=help_menu)
            self._menus = (menu, files, imports, edit, help_menu)
            def shortcut(action: Callable[[], Any]) -> Callable[[Any], str]:
                def invoke(_event: Any) -> str:
                    action()
                    return "break"
                return invoke
            self.root.bind("<Control-z>", shortcut(self.undo))
            self.root.bind("<Control-s>", shortcut(self.save))
            self.root.bind("<Control-Shift-S>", shortcut(self.save_as))
            self.root.bind("<Control-n>", shortcut(self.new_workspace))
            self.root.config(menu=menu)

        def _build_dashboard(self) -> None:
            self.dashboard_page = ScrolledPage(self.dashboard)
            self.dashboard_page.pack(fill="both", expand=True)
            body = self.dashboard_page.body
            ttk.Label(body, text="Panorama de investigación", style="Heading.TLabel").pack(anchor="w")
            self.context = tk.StringVar()
            self.context_label = ttk.Label(body, textvariable=self.context, style="Muted.TLabel", wraplength=700)
            self.context_label.pack(fill="x", pady=(2, 14))
            filters = ttk.Frame(body, style="Card.TFrame", padding=(12, 10, 12, 12))
            filters.pack(fill="x", pady=(0, 14))
            for col in range(3):
                filters.columnconfigure(col, weight=1, uniform="filter")
            self.view = tk.StringVar(value="Todos")
            self.scope_id = tk.StringVar()
            self._scope_kind: str | None = None
            self.period = tk.StringVar(value="Todos")
            self.start_year = tk.StringVar()
            self.end_year = tk.StringVar()
            self.validation = tk.StringVar(value="Todos")

            def field_box(col: int, row: int, label: str) -> ttk.Frame:
                frame = ttk.Frame(filters, style="CardBody.TFrame")
                frame.grid(row=row, column=col, sticky="ew", padx=6, pady=4)
                ttk.Label(frame, text=label, style="Muted.Card.TLabel").pack(anchor="w", pady=(0, 3))
                return frame

            view_box = ttk.Combobox(field_box(0, 0, "Vista"), textvariable=self.view, state="readonly",
                                    width=10, values=("Todos", "Grupo", "Investigador", "Producto"))
            view_box.pack(fill="x")
            view_box.bind("<<ComboboxSelected>>", lambda _e: self._scope_changed())
            self.scope_box = ReferenceInput(field_box(1, 0, "Nombre / título"), self.repo, "grupos",
                                            variable=self.scope_id, command=self.refresh_dashboard,
                                            style="CardBody.TFrame")
            self.scope_box.entry.configure(width=12)
            self.scope_box.pack(fill="x")
            period_box = ttk.Combobox(field_box(2, 0, "Ventana de observación"), textvariable=self.period,
                                      state="readonly", width=12,
                                      values=("Todos", "Últimos 2 años", "Últimos 5 años", "Personalizado"))
            period_box.pack(fill="x")
            period_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh_dashboard())
            status_box = ttk.Combobox(field_box(0, 1, "Validación automática"), textvariable=self.validation,
                                      state="readonly", width=12, values=("Todos", "Validado", "Rechazado"))
            status_box.pack(fill="x")
            status_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh_dashboard())
            years = field_box(1, 1, "Años: desde / hasta")
            self.start_entry = ttk.Entry(years, textvariable=self.start_year, width=7)
            self.start_entry.pack(side="left", fill="x", expand=True)
            ttk.Label(years, text="a", style="Muted.Card.TLabel").pack(side="left", padx=6)
            self.end_entry = ttk.Entry(years, textvariable=self.end_year, width=7)
            self.end_entry.pack(side="left", fill="x", expand=True)
            for variable in (self.start_year, self.end_year):
                variable.trace_add("write", self._year_changed)
            for entry in (self.start_entry, self.end_entry):
                entry.bind("<Return>", lambda _e: self.refresh_dashboard())
            self.filter_error = tk.StringVar()
            self.filter_error_label = ttk.Label(filters, textvariable=self.filter_error, style="Error.Card.TLabel", wraplength=650)

            cards = ttk.Frame(body)
            cards.pack(fill="x", pady=(0, 8))
            self.card_values = {}
            # La franja superior usa el color de estado que repiten los gráficos.
            for index, (key, title, tone) in enumerate((("total", "Productos", "sidebar"),
                                                       ("validated", "Validados", "primary"),
                                                       ("rejected", "Rechazados", "rejected"),
                                                       ("undated", "Sin año", "unknown"))):
                cards.columnconfigure(index, weight=1, uniform="cards")
                frame = ttk.Frame(cards, style="Card.TFrame")
                frame.grid(row=0, column=index, sticky="nsew", padx=(0, 10) if index < 3 else 0)
                ttk.Frame(frame, style=f"{tone}.Stripe.TFrame", height=3).pack(fill="x")
                inner = ttk.Frame(frame, style="CardBody.TFrame", padding=(14, 8, 14, 12))
                inner.pack(fill="both", expand=True)
                value = tk.StringVar(value="0")
                self.card_values[key] = value
                ttk.Label(inner, textvariable=value, style="CardValue.TLabel").pack(anchor="w")
                ttk.Label(inner, text=title, style="CardCaption.TLabel").pack(anchor="w")
            self.metric = tk.StringVar()
            self.note = tk.StringVar()
            ttk.Label(body, textvariable=self.metric, style="Muted.TLabel", wraplength=700).pack(fill="x")
            self.note_label = ttk.Label(body, textvariable=self.note, style="Muted.TLabel", wraplength=700)
            self.note_label.pack(fill="x", pady=(2, 14))
            charts = ttk.Frame(body)
            charts.pack(fill="x", pady=(0, 18))
            charts.columnconfigure(0, weight=1, uniform="preview")
            charts.columnconfigure(1, weight=1, uniform="preview")
            year_panel, self.dashboard_year_canvas = self._chart_panel(charts, 210)
            type_panel, self.dashboard_type_canvas = self._chart_panel(charts, 210)
            year_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
            type_panel.grid(row=0, column=1, sticky="nsew")
            table_heading = ttk.Frame(body)
            table_heading.pack(fill="x", pady=(0, 6))
            ttk.Label(table_heading, text="Productos de la vista", style="Section.TLabel").pack(side="left")
            ttk.Button(table_heading, text="Ver todas las distribuciones", command=lambda: self._show_page("graphs")).pack(side="right")
            columns = ("titulo", "anio", "tipologia", "validacion")
            table_frame = ttk.Frame(body)
            table_frame.pack(fill="x")
            self.stats_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=5, selectmode="browse")
            self.stats_table.tag_configure("stripe", background=self.colors["stripe"])
            column_widths = {"titulo": 360, "anio": 65, "tipologia": 200, "validacion": 100}
            for field in columns:
                self.stats_table.heading(field, anchor="w", text=LABELS[field])
                self.stats_table.column(field, width=column_widths[field], minwidth=55)
            x_scroll = AutoScrollbar(table_frame, orient="horizontal", command=self.stats_table.xview)
            y_scroll = AutoScrollbar(table_frame, orient="vertical", command=self.stats_table.yview)
            self.stats_table.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
            self.stats_table.grid(row=0, column=0, sticky="nsew")
            y_scroll.grid(row=0, column=1, sticky="ns")
            x_scroll.grid(row=1, column=0, sticky="ew")
            table_frame.columnconfigure(0, weight=1)
            self.stats_table.bind("<ButtonRelease-1>", self._open_product)
            self.stats_table.bind("<Return>", self._open_product)
            stats_pager = ttk.Frame(body)
            stats_pager.pack(fill="x", pady=(8, 0))
            self.stats_previous = ttk.Button(stats_pager, text="Anterior", command=lambda: self._stats_move(-1))
            self.stats_previous.pack(side="left")
            self.stats_page_label = tk.StringVar()
            ttk.Label(stats_pager, textvariable=self.stats_page_label).pack(side="left", padx=10)
            self.stats_next = ttk.Button(stats_pager, text="Siguiente", command=lambda: self._stats_move(1))
            self.stats_next.pack(side="left")
            self.stats_offset = 0
            self._stats_filter: tuple[Any, ...] | None = None
            self.current_stats: dict[str, Any] = {"por_anio": {}, "por_tipologia": {},
                                                  "por_validacion": {}, "por_regla": {}}
            body.bind("<Configure>", lambda event: self._dashboard_width(event.width), add="+")

        def _dashboard_width(self, width: int) -> None:
            for label in (self.context_label, self.note_label):
                label.configure(wraplength=max(260, width - 28))

        def _chart_panel(self, parent: tk.Misc, height: int = 240) -> tuple[ttk.Frame, tk.Canvas]:
            panel = ttk.Frame(parent, style="Card.TFrame", padding=(6, 8, 4, 4))
            panel.columnconfigure(0, weight=1)
            panel.rowconfigure(0, weight=1)
            canvas = tk.Canvas(panel, width=280, height=height, bg=self.colors["surface"],
                               highlightthickness=0, borderwidth=0)
            xscroll = AutoScrollbar(panel, orient="horizontal", command=canvas.xview)
            yscroll = AutoScrollbar(panel, orient="vertical", command=canvas.yview)
            canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
            canvas.grid(row=0, column=0, sticky="nsew")
            yscroll.grid(row=0, column=1, sticky="ns")
            xscroll.grid(row=1, column=0, sticky="ew")
            canvas.bind("<Configure>", lambda _e: self._redraw_charts())
            return panel, canvas

        def _build_graphs(self) -> None:
            heading = ttk.Frame(self.graphs)
            heading.pack(fill="x")
            ttk.Label(heading, text="Distribuciones de productos", style="Heading.TLabel").pack(side="left")
            ttk.Button(heading, text="Cambiar filtros en Dashboard", command=lambda: self._show_page("dashboard")).pack(side="right")
            ttk.Label(self.graphs, textvariable=self.context, style="Muted.TLabel", wraplength=700).pack(
                fill="x", pady=(2, 14))
            charts = ttk.Notebook(self.graphs)
            charts.pack(fill="both", expand=True)
            for name, title in (("year_canvas", "Por año · histograma"), ("type_canvas", "Por tipología"),
                                ("validation_canvas", "Por validación"), ("rules_canvas", "Reglas incumplidas")):
                panel, canvas = self._chart_panel(charts)
                setattr(self, name, canvas)
                charts.add(panel, text=title)

        def _build_queue(self) -> None:
            heading = ttk.Frame(self.queue_tab)
            heading.pack(fill="x")
            ttk.Label(heading, text="Revisión de productos", style="Heading.TLabel").pack(side="left")
            ttk.Button(heading, text="Añadir producto…", style="Accent.TButton", command=self.enqueue).pack(side="right")
            ttk.Button(heading, text="Enviar rechazados", command=self.enqueue_rejected).pack(side="right", padx=6)
            ttk.Label(self.queue_tab, text="La validación es automática. Los productos rechazados se revisan aquí en orden de llegada: "
                      "corrija el producto o deje una nota que explique por qué no es posible.",
                      style="Muted.TLabel", wraplength=680).pack(fill="x", pady=(2, 14))
            # La siguiente revisión, destacada en una tarjeta con la franja de «pendiente».
            front = ttk.Frame(self.queue_tab, style="Card.TFrame")
            front.pack(fill="x")
            ttk.Frame(front, style="pending.Stripe.TFrame", height=3).pack(fill="x")
            front_body = ttk.Frame(front, style="CardBody.TFrame", padding=(14, 10, 14, 12))
            front_body.pack(fill="x")
            front_body.columnconfigure(0, weight=1)
            self.queue_count = tk.StringVar()
            ttk.Label(front_body, textvariable=self.queue_count, style="Muted.Card.TLabel").grid(row=0, column=0, sticky="w")
            self.queue_front_label = tk.StringVar()
            self.queue_front_widget = ttk.Label(front_body, textvariable=self.queue_front_label, style="Card.TLabel",
                                                font=font(11, "strong"), wraplength=560)
            self.queue_front_widget.grid(row=1, column=0, sticky="ew", pady=(2, 10))
            controls = ttk.Frame(front_body, style="CardBody.TFrame")
            controls.grid(row=2, column=0, sticky="w")
            self.review_button = ttk.Button(controls, text="Revisar siguiente", command=self.process_queue)
            self.review_button.pack(side="left")
            self.discard_button = ttk.Button(controls, text="Descartar siguiente", style="Danger.TButton",
                                             command=self.discard_queue)
            self.discard_button.pack(side="left", padx=6)
            front_body.bind("<Configure>", lambda event: self.queue_front_widget.configure(wraplength=max(240, event.width - 30)))
            ttk.Label(self.queue_tab, text="En cola", style="Section.TLabel").pack(anchor="w", pady=(18, 0))
            columns = ("id", "producto_id", "motivo", "creado")
            table_frame = ttk.Frame(self.queue_tab)
            table_frame.pack(fill="both", expand=True, pady=(6, 0))
            table_frame.columnconfigure(0, weight=1)
            table_frame.rowconfigure(0, weight=1)
            # El ID del trabajo es interno (identifica la fila); no se muestra.
            self.queue_table = ttk.Treeview(table_frame, columns=columns, show="headings",
                                            displaycolumns=("producto_id", "motivo", "creado"))
            self.queue_table.tag_configure("stripe", background=self.colors["stripe"])
            for field in columns:
                self.queue_table.heading(field, anchor="w", text={"producto_id": "Producto", "creado": "Recibido", "motivo": "Motivo"}.get(field, LABELS.get(field, field)))
                self.queue_table.column(field, width=340 if field == "producto_id" else 260 if field == "motivo" else 150)
            table_y = AutoScrollbar(table_frame, orient="vertical", command=self.queue_table.yview)
            table_x = AutoScrollbar(table_frame, orient="horizontal", command=self.queue_table.xview)
            self.queue_table.configure(yscrollcommand=table_y.set, xscrollcommand=table_x.set)
            self.queue_table.grid(row=0, column=0, sticky="nsew")
            table_y.grid(row=0, column=1, sticky="ns")
            table_x.grid(row=1, column=0, sticky="ew")
            self.queue_empty = ttk.Label(table_frame, text="No hay productos pendientes de revisión.", style="Muted.TLabel")
            self.queue_table.bind("<Double-1>", lambda _e: self._open_queued_product())
            self.queue_table.bind("<Return>", lambda _e: self._open_queued_product())
            queue_pager = ttk.Frame(self.queue_tab, padding=(0, 10, 0, 0))
            queue_pager.pack(side="bottom", fill="x", before=table_frame)
            self.queue_previous = ttk.Button(queue_pager, text="Anterior", command=lambda: self._queue_move(-1))
            self.queue_previous.pack(side="left")
            self.queue_page_label = tk.StringVar()
            ttk.Label(queue_pager, textvariable=self.queue_page_label).pack(side="left", padx=10)
            self.queue_next = ttk.Button(queue_pager, text="Siguiente", command=lambda: self._queue_move(1))
            self.queue_next.pack(side="left")
            self.queue_offset = 0

        def _open_queued_product(self) -> None:
            selection = self.queue_table.selection()
            if selection:
                job = next((job for job in self.repo.queue_page(self.queue_offset, PAGE_SIZE)["rows"] if job["id"] == selection[0]), None)
                if job:
                    self.open_detail("productos", job["producto_id"])

        def _queue_move(self, direction: int) -> None:
            self.queue_offset = max(0, self.queue_offset + direction * PAGE_SIZE)
            self.refresh_queue()

        def refresh_queue(self) -> None:
            page = self.repo.queue_page(self.queue_offset, PAGE_SIZE)
            if self.queue_offset and self.queue_offset >= page["total"]:
                self.queue_offset = max(0, (page["total"] - 1) // PAGE_SIZE * PAGE_SIZE)
                page = self.repo.queue_page(self.queue_offset, PAGE_SIZE)
            self.queue_table.delete(*self.queue_table.get_children())
            for index, job in enumerate(page["rows"]):
                self.queue_table.insert("", "end", iid=job["id"],
                                        values=(job["id"], self.reference_label("productos", job["producto_id"]), reason_text(job["motivo"], short=True), job["creado"].replace("T", " ")),
                                        tags=("stripe",) if index % 2 else ())
            self.queue_count.set(f"Pendientes: {page['total']}")
            self.queue_page_label.set(f"{self.queue_offset + 1 if page['total'] else 0}–{self.queue_offset + len(page['rows'])} de {page['total']}")
            front = self.repo.queue_front()
            self.queue_front_label.set("Siguiente: " + self.reference_label("productos", front["producto_id"]) if front
                                       else "Cola vacía. Añada un producto para revisarlo.")
            state = "normal" if front else "disabled"
            self.review_button.configure(state=state)
            self.discard_button.configure(state=state)
            self.queue_previous.configure(state="normal" if self.queue_offset else "disabled")
            self.queue_next.configure(state="normal" if self.queue_offset + PAGE_SIZE < page["total"] else "disabled")
            if front:
                self.queue_empty.place_forget()
            else:
                self.queue_empty.place(relx=0.5, rely=0.45, anchor="center")

        def enqueue(self, product_id: str | None = None, *, parent: tk.Misc | None = None) -> None:
            parent = parent or self.root
            if not self.repo.page("productos", limit=0)["total"]:
                messagebox.showinfo("Sin productos", "Cree un producto primero", parent=self.root)
                return
            product_id = product_id or self.pick_record("productos", parent=parent)
            if not product_id:
                return
            reason = simpledialog.askstring("Motivo", "Motivo de la revisión:", parent=parent)
            if reason is None:
                return
            self.mutate(lambda: self.repo.enqueue_review(product_id.strip(), reason))

        def enqueue_rejected(self) -> None:
            count = self.mutate(self.repo.enqueue_rejected)
            if count == 0:
                self.status.set("No hay productos rechazados fuera de la cola")
            elif count:
                self.status.set(f"{count} productos rechazados enviados a revisión. Guarde para conservarlos.")

        def process_queue(self) -> None:
            job = self.repo.queue_front()
            if not job:
                messagebox.showinfo("Cola", "No hay revisiones pendientes", parent=self.root)
                return
            dialog = ReviewDialog(self.root, self, job)
            self.refresh()
            if dialog.result:
                self.status.set(f"Revisión cerrada; el producto quedó {dialog.result['validacion']}. Guarde para conservarlo.")

        def discard_queue(self) -> None:
            job = self.repo.queue_front()
            if job and messagebox.askyesno("Descartar siguiente", f"¿Descartar revisión de {self.reference_label('productos', job['producto_id'])}?", parent=self.root):
                self.mutate(self.repo.discard_review)

        def _stats_move(self, direction: int) -> None:
            self.stats_offset = max(0, self.stats_offset + direction * PAGE_SIZE)
            self.refresh_dashboard()

        def _redraw_charts(self) -> None:
            stats = getattr(self, "current_stats", {})
            filters = getattr(self, "_stats_filter", None)
            bounds = (filters[2], filters[3]) if filters else (None, None)
            for name in ("year_canvas", "dashboard_year_canvas"):
                canvas = getattr(self, name, None)
                if canvas is not None:
                    self._draw_histogram(canvas, stats.get("por_anio", {}), bounds)
            for name, field, title, limit in (
                    ("type_canvas", "por_tipologia", "Productos por tipología", None),
                    ("dashboard_type_canvas", "por_tipologia", "Tipologías más frecuentes", 5),
                    ("validation_canvas", "por_validacion", "Validación automática", None)):
                canvas = getattr(self, name, None)
                if canvas is not None:
                    self._draw_distribution(canvas, stats.get(field, {}), title, limit)
            canvas = getattr(self, "rules_canvas", None)
            if canvas is not None:
                rules = {VALIDATION_RULES[code]: count for code, count in stats.get("por_regla", {}).items()}
                self._draw_distribution(canvas, rules, "Reglas incumplidas",
                                        base=stats.get("por_validacion", {}).get("rechazado", 0),
                                        tone="rejected", empty="Todos los productos de la consulta cumplen las reglas")

        def _draw_histogram(self, canvas: tk.Canvas, values: dict[str, int],
                            bounds: tuple[int | None, int | None] = (None, None)) -> None:
            c = self.colors
            canvas.delete("all")
            numeric = {int(key): value for key, value in values.items() if key.isdigit()}
            missing = values.get("Sin dato", 0)
            total = sum(values.values())
            canvas.create_text(12, 14, anchor="w", text="Productos por año · histograma",
                               font=font(10, "strong"), fill=c["ink"])
            canvas.create_text(12, 34, anchor="w", text=f"{total} productos · {missing} sin año",
                               font=font(9), fill=c["muted"])
            height = max(170, canvas.winfo_height())
            if not numeric:
                canvas.create_text(12, 80, anchor="w", text="Sin años registrados" if total else "Sin productos para estos filtros",
                                   font=font(10), fill=c["muted"])
                canvas.configure(scrollregion=(0, 0, max(canvas.winfo_width(), 280), height))
                return
            first = bounds[0] if bounds[0] is not None else min(numeric)
            last = bounds[1] if bounds[1] is not None else max(numeric)
            cutoff = date.today().year - 20
            bins = []
            if first <= cutoff:
                count = sum(value for year, value in numeric.items() if first <= year <= min(cutoff, last))
                bins.append(("20 años\no más", count, f"older:{cutoff}"))
            bins.extend((str(year), numeric.get(year, 0), f"year:{year}") for year in range(max(first, cutoff + 1), last + 1))
            width = max(canvas.winfo_width(), 320)
            left, right, top, bottom = 46, width - 14, 74, height - 40
            canvas.create_text(12, 52, anchor="w", text=f"Columna clara: 20 años o más ({cutoff} y anteriores)"
                               if bins[0][2].startswith("older:") else "Un año por columna",
                               font=font(8), fill=c["muted"])
            maximum = max(1, max(count for _, count, _ in bins))
            for value in sorted({round(maximum * tick / 4) for tick in range(5)}):
                y = bottom - (bottom - top) * value / maximum
                if value:
                    canvas.create_line(left, y, right, y, fill=c["chart_grid"])
                canvas.create_text(left - 8, y, anchor="e", text=str(value),
                                   font=font(8), fill=c["muted"])
            step = (right - left) / len(bins)
            # Con pocas columnas la barra no ocupa todo el ancho.
            gap = max(min(3.0, step * 0.12), (step - 64) / 2)
            label_every = max(1, math.ceil(34 / step))
            for index, (label, count, tag) in enumerate(bins):
                x0, x1 = left + index * step, left + (index + 1) * step
                y = bottom - (bottom - top) * count / maximum
                fill = c["chart_older"] if tag.startswith("older:") else c["primary"]
                canvas.create_rectangle(x0 + gap, y, x1 - gap, bottom, fill=fill, outline="",
                                        tags=("bin", tag, f"count:{count}"))
                if count and (step >= 28 or tag.startswith("older:")):
                    canvas.create_text((x0 + x1) / 2, y - 8, text=str(count),
                                       font=font(8), fill=c["ink"])
                if (index % label_every == 0 and (index == 0 or len(bins) - 1 - index >= label_every)) or index == len(bins) - 1:
                    canvas.create_text((x0 + x1) / 2, bottom + 16, text=label,
                                       font=font(8), fill=c["muted"])
            canvas.create_line(left, bottom, right, bottom, fill=c["line_strong"])
            canvas.configure(scrollregion=(0, 0, width, height))
            signature = (tuple(sorted(numeric.items())), first, last)
            if signature != getattr(canvas, "_hist_signature", None):
                canvas.xview_moveto(0.0)
                canvas._hist_signature = signature

        def _draw_distribution(self, canvas: tk.Canvas, values: dict[str, int], title: str,
                               limit: int | None = None, base: int | None = None, tone: str | None = None,
                               empty: str = "Sin productos para estos filtros") -> None:
            """Barras horizontales; base fija el denominador cuando las categorías se solapan."""
            c = self.colors
            canvas.delete("all")
            width = max(canvas.winfo_width(), 320)
            total = sum(values.values()) if base is None else base
            canvas.create_text(12, 14, anchor="w", text=title, font=font(10, "strong"), fill=c["ink"])
            canvas.create_text(12, 34, anchor="w", text=f"Base: {total} productos (incluye «Sin dato»)" if base is None
                               else f"Base: {total} productos rechazados; un producto puede incumplir varias reglas",
                               font=font(9), fill=c["muted"])
            if not total or not any(values.values()):
                canvas.create_text(12, 80, anchor="w", text=empty if base is not None or total else "Sin productos para estos filtros",
                                   font=font(10), fill=c["muted"])
                canvas.configure(scrollregion=(0, 0, width, max(160, canvas.winfo_height())))
                return
            items = sorted(((name, count) for name, count in values.items() if count),
                           key=lambda item: (-item[1], item[0]))
            if limit is not None and len(items) > limit:
                known = [item for item in items if item[0] != "Sin dato"]
                shown = known[:limit]
                if len(known) > limit:
                    shown.append(("Otras tipologías (agrupadas)", sum(count for _, count in known[limit:])))
                if values.get("Sin dato"):
                    shown.append(("Sin dato", values["Sin dato"]))
                items = shown
            max_count = max(count for _, count in items)
            label_width = min(230, max(120, width * 0.38))
            left, right = label_width + 26, width - 100
            y = 58
            for name, count in items:
                label = canvas.create_text(12, y, anchor="nw", text=name[:1].upper() + name[1:], width=label_width,
                                           font=font(9), fill=c["ink"])
                bbox = canvas.bbox(label)
                row_height = max(30, (bbox[3] - bbox[1]) + 12) if bbox else 30
                bar_y = y + row_height / 2 - 8
                # Los estados de validación conservan su color en todo el programa.
                color = c[tone or STATUS_COLORS.get(name, "primary")]
                canvas.create_rectangle(left, bar_y, right, bar_y + 10, fill=c["chart_track"], outline="")
                canvas.create_rectangle(left, bar_y, left + max(2, (right - left) * count / max_count), bar_y + 10,
                                        fill=color, outline="", tags=("bar", f"count:{count}"))
                canvas.create_text(right + 10, bar_y + 5, anchor="w", text=f"{count} · {count / total:.1%}",
                                   font=font(8), fill=c["muted"])
                y += row_height
            canvas.configure(scrollregion=(0, 0, width, max(y + 10, canvas.winfo_height())))

        def _scope_changed(self, selected: str | None = None) -> None:
            kind = {"Grupo": "grupos", "Investigador": "investigadores", "Producto": "productos"}.get(self.view.get())
            self.scope_box.repo = self.repo
            self.scope_box.kind = kind or "grupos"
            self.scope_box.set_enabled(bool(kind))
            if selected is not None and kind and self.repo.get(kind, selected):
                self.scope_id.set(selected)
            elif kind != self._scope_kind or (kind and not self.repo.get(kind, self.scope_id.get())):
                rows = self.repo.page(kind, limit=1)["rows"] if kind else []
                self.scope_id.set(rows[0]["id"] if rows else "")
            else:
                self.scope_box._update_label()
            self._scope_kind = kind
            self.refresh_dashboard()

        def _year_changed(self, *_: Any) -> None:
            if self._year_timer:
                self.root.after_cancel(self._year_timer)
            if self.period.get() == "Personalizado":
                self._year_timer = self.root.after(350, self.refresh_dashboard)

        def clear_filters(self) -> None:
            self.period.set("Todos")
            self.start_year.set("")
            self.end_year.set("")
            self.validation.set("Todos")
            self.view.set("Todos")
            self._scope_changed()

        def refresh_dashboard(self) -> None:
            if self._year_timer:
                self.root.after_cancel(self._year_timer)
                self._year_timer = None
            custom = self.period.get() == "Personalizado"
            for entry in (self.start_entry, self.end_entry):
                entry.configure(state="normal" if custom else "disabled")
            try:
                start = end = None
                period = self.period.get()
                if period in ("Últimos 2 años", "Últimos 5 años"):
                    years = 2 if period == "Últimos 2 años" else 5
                    start, end = date.today().year - years + 1, date.today().year
                elif period == "Personalizado":
                    start = int(self.start_year.get()) if self.start_year.get().strip() else None
                    end = int(self.end_year.get()) if self.end_year.get().strip() else None
                    if start is not None and end is not None and start > end:
                        raise DataError("El año inicial supera al final")
                    if any(value is not None and not 1900 <= value <= date.today().year + 1 for value in (start, end)):
                        raise DataError("Año fuera de rango")
                status = "" if self.validation.get() == "Todos" else self.validation.get().lower()
                filters = (self.view.get(), self.scope_id.get(), start, end, status)
                if filters != self._stats_filter:
                    self.stats_offset = 0
                    self._stats_filter = filters
                result = self.repo.statistics(*filters, offset=self.stats_offset, limit=PAGE_SIZE)
                if self.stats_offset and self.stats_offset >= result["total"]:
                    self.stats_offset = max(0, (result["total"] - 1) // PAGE_SIZE * PAGE_SIZE)
                    result = self.repo.statistics(*filters, offset=self.stats_offset, limit=PAGE_SIZE)
            except (ValueError, DataError) as exc:
                self.filter_error.set(f"Filtro inválido: {exc}. Se conservan los últimos resultados válidos.")
                self.filter_error_label.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5)
                self.status.set(f"Filtro inválido: {exc}")
                return
            self.filter_error.set("")
            self.filter_error_label.grid_remove()
            self.current_stats = result
            active_groups = self.overview["active_groups"]
            active_people = self.overview["active_people"]
            scope = self.scope_box.label.get() if self.view.get() != "Todos" else "Toda la institución"
            window = f"{start or 'sin inicio'}–{end or 'sin fin'}" if start is not None or end is not None else "Todos los años"
            self.context.set(f"{self.view.get()}: {scope} · {window} · Validación: {status or 'todas'}")
            self.card_values["total"].set(f"{result['total']:,}".replace(",", "."))
            for key, field, value in (("validated", "por_validacion", "validado"),
                                       ("rejected", "por_validacion", "rechazado"),
                                       ("undated", "por_anio", "Sin dato")):
                self.card_values[key].set(f"{result[field].get(value, 0):,}".replace(",", "."))
            self.metric.set(f"Institución: {active_groups} grupos activos · {active_people} investigadores activos. Cada producto se cuenta una vez.")
            if result["total"]:
                missing = [f"{label}: {result[field].get('Sin dato', 0)} sin dato"
                           for label, field in (("Año", "por_anio"), ("Tipología", "por_tipologia"))
                           if result[field].get("Sin dato", 0)]
                rules = sorted(result["por_regla"].items(), key=lambda item: -item[1])
                causes = ", ".join(f"{VALIDATION_RULES[code].lower()} ({count})" for code, count in rules)
                self.note.set("Rechazos por: " + causes + (" · " + " · ".join(missing) if missing else "")
                              if causes else "Todos los productos cumplen las reglas de validación"
                              + (" · " + " · ".join(missing) if missing else ""))
            else:
                self.note.set("Sin productos para estos filtros")
            self.stats_table.delete(*self.stats_table.get_children())
            for index, row in enumerate(result["productos"]):
                self.stats_table.insert("", "end", iid=row["id"],
                                        values=tuple(display_value(field, row[field]) for field in self.stats_table["columns"]),
                                        tags=("stripe",) if index % 2 else ())
            self.stats_page_label.set(f"{self.stats_offset + 1 if result['total'] else 0}–{self.stats_offset + len(result['productos'])} de {result['total']}")
            self.stats_previous.configure(state="normal" if self.stats_offset else "disabled")
            self.stats_next.configure(state="normal" if self.stats_offset + PAGE_SIZE < result["total"] else "disabled")
            self._redraw_charts()

        def _open_product(self, _event: tk.Event) -> None:
            if getattr(_event, "num", None) == 1 and not self.stats_table.identify_row(_event.y):
                return
            selection = self.stats_table.selection()
            if selection:
                self.open_detail("productos", selection[0])

        def usage(self, kind: str) -> dict[str, int]:
            if kind not in self._usage_cache:
                self._usage_cache[kind] = self.repo.field_usage(kind)
            return self._usage_cache[kind]

        def refresh(self) -> None:
            self._record_cache.clear()
            self._usage_cache.clear()
            for tab in self.entity_tabs.values():
                tab.refresh()
            for tab in self.relation_tabs.values():
                tab.refresh()
            self.refresh_queue()
            self.overview = self.repo.summary()
            self._scope_changed()
            self.root.title("PEA-i UPC — Investigación" + (" *" if self.repo.dirty else ""))
            self.workspace.set(f"{self.workspace_caption} · "
                               + ("Cambios sin guardar" if self.repo.dirty else "Sin cambios pendientes"))
            self.workspace_label.configure(style="Dirty.Header.TLabel" if self.repo.dirty else "Header.TLabel")
            self.save_button.configure(text="Guardar como…" if self.data_file is None else "Guardar")
            for detail in tuple(self.details):
                if detail.winfo_exists():
                    detail.refresh()

        def mutate(self, action: Callable[[], Any]) -> Any:
            try:
                result = action()
            except (DataError, OSError, ValueError) as exc:
                messagebox.showerror("No se pudo completar", str(exc), parent=self.root)
                return None
            self.refresh()
            self.status.set("Cambio en memoria. Guarde para conservarlo al cerrar.")
            return result

        def pick_record(self, kind: str, current: str = "", parent: tk.Misc | None = None) -> str | None:
            return RecordPicker(parent or self.root, self.repo, kind, current).result

        def record(self, kind: str, key: str) -> dict[str, str]:
            cache_key = (kind, key)
            if cache_key not in self._record_cache:
                self._record_cache[cache_key] = self.repo.get(kind, key) or {"id": key, "activo": "0"}
            return self._record_cache[cache_key]

        def open_detail(self, kind: str, key: str, parent: tk.Misc | None = None) -> DetailDialog | None:
            if self.repo.get(kind, key) is None:
                self.status.set("Este registro ya no existe")
                return None
            return DetailDialog(parent or self.root, self, kind, key)

        def reference_label(self, kind: str, key: str) -> str:
            row = self.record(kind, key)
            return f"{record_name(row)} · {key}"

        def entity_page(self, kind: str, offset: int, query: str, state: str) -> dict[str, Any]:
            if state == "Todos":
                return self.repo.page(kind, offset, PAGE_SIZE, query)
            active = "1" if state == "Activos" else "0"
            total = position = 0
            rows = []
            while True:
                page = self.repo.page(kind, position, PAGE_SIZE, query)
                for row in page["rows"]:
                    if row["activo"] != active:
                        continue
                    if offset <= total < offset + PAGE_SIZE:
                        rows.append(row)
                    total += 1
                position += len(page["rows"])
                if not page["rows"] or position >= page["total"]:
                    break
            return {"total": total, "rows": rows}

        def relationship_page(self, kind: str, offset: int, query: str) -> dict[str, Any]:
            needle = query.strip().casefold()
            if not needle:
                return self.repo.page(kind, offset, PAGE_SIZE)
            ends = RELATION_ENDS[kind]
            matching_ids = []
            for entity_kind in ends[2:]:
                ids = set()
                position = 0
                while True:
                    page = self.repo.page(entity_kind, position, PAGE_SIZE, query)
                    for row in page["rows"]:
                        ids.add(row["id"])
                        self._record_cache[(entity_kind, row["id"])] = row
                    position += len(page["rows"])
                    if not page["rows"] or position >= page["total"]:
                        break
                matching_ids.append(ids)
            total = 0
            rows = []
            position = 0
            while True:
                page = self.repo.page(kind, position, PAGE_SIZE)
                for row in page["rows"]:
                    if (row[ends[0]] not in matching_ids[0] and row[ends[1]] not in matching_ids[1]
                            and needle not in " ".join(row.values()).casefold()):
                        continue
                    if offset <= total < offset + PAGE_SIZE:
                        rows.append(row)
                    total += 1
                position += len(page["rows"])
                if not page["rows"] or position >= page["total"]:
                    break
            return {"total": total, "rows": rows}

        def edit_record(self, kind: str, key: str | tuple[str, str] | None = None,
                        defaults: dict[str, str] | None = None, parent: tk.Misc | None = None,
                        external: bool = False, locked_fields: tuple[str, ...] = ()) -> bool:
            initial = self.repo.get(kind, key) if key is not None else defaults
            if key is not None and defaults:
                initial = {**(initial or {}), **defaults}
            on_save = (lambda row: self.repo.update(kind, key, row)) if key is not None else (
                lambda row: self.repo.create(kind, row))
            dialog = RecordDialog(parent or self.root, kind, initial, repo=self.repo, on_save=on_save,
                                  suggested_id=self.repo.suggest_id(kind) if kind in ENTITY_FIELDS else "",
                                  external=external, is_new=key is None, locked_fields=locked_fields)
            if dialog.result is None:
                return False
            self.refresh()
            self.status.set("Cambio en memoria. Guarde para conservarlo al cerrar.")
            return True

        def _may_discard(self) -> bool:
            if not self.repo.dirty:
                return True
            choice = messagebox.askyesnocancel("Cambios sin guardar", "¿Guardar cambios antes de continuar?", parent=self.root)
            if choice is None:
                return False
            if choice:
                return self.save()
            return True

        def start_choice(self) -> None:
            if self.initial_file is not None:
                self._load(self.initial_file)
            elif DEFAULT_DATA_FILE.exists():
                self._load(DEFAULT_DATA_FILE)
            else:
                self.status.set(f"No se encontró {DEFAULT_DATA_FILE.name}; espacio vacío.")

        def new_workspace(self) -> None:
            if self._may_discard():
                if isinstance(self.repo, CppRepository):
                    self.repo.reset()
                else:
                    self.repo = Repository()
                self.data_file = None
                self.workspace_caption = "Espacio vacío"
                self.refresh()
                self.status.set("Espacio vacío. Guarde en un archivo antes de salir.")

        def _load(self, path: Path) -> None:
            path = Path(path)
            recovered = False
            try:
                if isinstance(self.repo, CppRepository):
                    self.repo.load(path)
                else:
                    new_repo = load_repository(path)
            except (DataError, OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
                backup = backup_of(path)
                if backup.exists() and messagebox.askyesno("Datos dañados", f"{exc}\n\n¿Abrir la copia anterior de .backup?", parent=self.root):
                    try:
                        if isinstance(self.repo, CppRepository):
                            self.repo.load(backup)
                        else:
                            new_repo = load_repository(backup)
                    except (DataError, OSError, ValueError, UnicodeError, json.JSONDecodeError) as backup_exc:
                        messagebox.showerror("Copia inválida", str(backup_exc), parent=self.root)
                        return
                    path = backup
                    recovered = True
                else:
                    messagebox.showerror("No se pudo cargar", str(exc), parent=self.root)
                    return
            if not isinstance(self.repo, CppRepository):
                self.repo = new_repo
            # Una carpeta anterior o una copia recuperada se guardan en un archivo nuevo.
            folder = is_folder_data(path)
            self.data_file = None if folder or recovered else path
            self.workspace_caption = ("Copia recuperada" if recovered else
                                      "Carpeta anterior" if folder else path.name)
            self.refresh()
            self.status.set(f"Datos cargados de {path}" + (" (Guardar como crea el archivo único)"
                                                          if self.data_file is None else ""))

        def open_file(self) -> None:
            if not self._may_discard():
                return
            chosen = filedialog.askopenfilename(
                parent=self.root, title="Archivo de datos PEA-i (o manifest.csv de una carpeta anterior)",
                filetypes=[("Datos PEA-i", "*.csv"), ("Todos los archivos", "*")])
            if chosen:
                self._load(Path(chosen))

        def open_default(self) -> None:
            if self._may_discard():
                self._load(DEFAULT_DATA_FILE)

        def save(self) -> bool:
            if self.data_file is None:
                return self.save_as()
            try:
                if isinstance(self.repo, CppRepository):
                    self.repo.save(self.data_file)
                else:
                    save_repository(self.repo, self.data_file)
            except (OSError, DataError) as exc:
                messagebox.showerror("No se pudo guardar", str(exc), parent=self.root)
                return False
            self.refresh()
            self.status.set(f"Guardado en {self.data_file}")
            return True

        def save_as(self) -> bool:
            chosen = filedialog.asksaveasfilename(
                parent=self.root, title="Guardar datos en un archivo", defaultextension=".csv",
                initialfile=DEFAULT_DATA_FILE.name, filetypes=[("Datos PEA-i", "*.csv")])
            if not chosen:
                return False
            previous = self.data_file
            previous_caption = self.workspace_caption
            self.data_file = Path(chosen)
            self.workspace_caption = self.data_file.name
            if not self.save():
                self.data_file = previous
                self.workspace_caption = previous_caption
                return False
            return True

        def _keep_import(self, summary: str) -> None:
            """Lo importado se guarda de inmediato en el archivo abierto: los datos crecen con cada fuente."""
            if self.data_file is not None and self.repo.dirty:
                saved = self.save()
                self.status.set(f"{summary} " + (f"Guardado en {self.data_file.name}." if saved
                                                 else "No se pudo guardar; use Guardar como."))
                return
            self.status.set(f"{summary} Guarde para conservarlo." if self.repo.dirty else summary)

        def export_spreadsheet(self) -> None:
            folder = filedialog.askdirectory(parent=self.root, title="Carpeta para exportar a hoja de cálculo")
            if not folder:
                return
            try:
                export_repository_spreadsheet(self.repo, Path(folder))
            except (OSError, DataError) as exc:
                messagebox.showerror("No se pudo exportar", str(exc), parent=self.root)
                return
            self.status.set(f"Exportado para hoja de cálculo en {folder}")

        def close(self) -> None:
            if self._may_discard():
                self.root.destroy()

        def undo(self) -> None:
            try:
                undone = self.repo.undo()
            except DataError as exc:
                messagebox.showerror("No se pudo deshacer", str(exc), parent=self.root)
                return
            if undone:
                self.refresh()
                self.status.set("Última acción deshecha")
            else:
                self.status.set("No hay acciones para deshacer")

        def clear_history(self) -> None:
            if self.repo.history_size() and messagebox.askyesno("Vaciar historial", "¿Eliminar las acciones para deshacer?", parent=self.root):
                self.mutate(self.repo.clear_history)

        def import_csv(self) -> None:
            path = filedialog.askopenfilename(parent=self.root, title="Importar hoja de cálculo",
                                              filetypes=[("Hojas de cálculo", "*.csv *.xlsx"),
                                                         ("CSV", "*.csv"), ("Excel", "*.xlsx")])
            if not path:
                return
            path = Path(path)
            if path.suffix.lower() == ".xlsx":
                try:
                    with tempfile.TemporaryDirectory() as temporary:
                        self.import_csv_path(_xlsx_to_csv(path, Path(temporary) / "hoja.csv"))
                except (DataError, OSError) as exc:
                    messagebox.showerror("Excel inválido", str(exc), parent=self.root)
                return
            self.import_csv_path(path)

        def import_csv_path(self, path: Path) -> None:
            try:
                with path.open(encoding="utf-8-sig", newline="") as stream:
                    header = next(csv.reader(stream), [])
            except (OSError, UnicodeError, csv.Error) as exc:
                messagebox.showerror("CSV inválido", str(exc), parent=self.root)
                return
            default = next((kind for kind, fields in ALL_FIELDS.items() if tuple(header) == fields), path.stem)
            options = {TITLES[kind]: kind for kind in ALL_FIELDS}
            dialog = ChoiceDialog(self.root, "Importar datos", f"Archivo: {path.name}\nSeleccione el contenido. Los encabezados deben coincidir con el esquema PEA-i.", options, default)
            kind = dialog.result
            if not kind:
                return
            try:
                if isinstance(self.repo, CppRepository):
                    total, expected, errors = self.repo.preview_csv(path, kind)
                else:
                    total, expected, errors = preview_csv_merge(self.repo, path, kind)
            except (DataError, OSError, UnicodeError) as exc:
                messagebox.showerror("CSV inválido", str(exc), parent=self.root)
                return
            summary = f"{total} filas de {kind}\nAceptables: {expected}\nRechazadas: {total - expected}"
            if errors:
                summary += "\n\n" + "\n".join(errors[:8])
            if not messagebox.askyesno("Vista previa", summary + "\n\n¿Importar las aceptables?", parent=self.root):
                return
            try:
                if isinstance(self.repo, CppRepository):
                    accepted, errors = self.repo.import_csv(path, kind)
                else:
                    accepted, errors = merge_csv(self.repo, path, kind)
            except (DataError, OSError, UnicodeError) as exc:
                messagebox.showerror("No se pudo importar", str(exc), parent=self.root)
                return
            self.refresh()
            self._keep_import(f"Importación: {accepted} filas aceptadas; {total - accepted} rechazadas.")
            messagebox.showinfo("Resultado de importación", f"Aceptadas: {accepted}\nRechazadas: {total - accepted}\n\n" + "\n".join(errors[:20]), parent=self.root)

        def _accept_external(self, kind: str, row: dict[str, str]) -> None:
            existing = self.repo.get(kind, row["id"]) if row.get("id") else None
            initial = {**existing, **{key: value for key, value in row.items() if value}} if existing else row
            if existing and existing.get("fuente") and row.get("fuente") and row["fuente"] not in existing["fuente"]:
                initial["fuente"] = existing["fuente"] + "; " + row["fuente"]
            if self.edit_record(kind, key=existing["id"] if existing else None, defaults=initial,
                                external=existing is None):
                self._keep_import("Registro importado.")

        def import_url(self, initial_url: str | None = None) -> None:
            if self._url_busy:
                self.status.set("Ya hay una consulta URL en curso")
                return
            url = initial_url or simpledialog.askstring("Consultar URL", "Pegue una URL pública HTTP o HTTPS:", parent=self.root)
            if not url:
                return
            self.status.set("Descargando página pública...")
            self._url_busy = True
            result_queue: queue.Queue[WebPreview | Exception] = queue.Queue(maxsize=1)

            def fetch() -> None:
                try:
                    result_queue.put(fetch_web_page(url.strip()))
                except Exception as exc:
                    result_queue.put(exc)

            def check_result() -> None:
                try:
                    alive = self.root.winfo_exists()
                except tk.TclError:
                    return
                if not alive:
                    return
                try:
                    result = result_queue.get_nowait()
                except queue.Empty:
                    self.root.after(100, check_result)
                    return
                self._url_busy = False
                if isinstance(result, Exception):
                    messagebox.showerror("Consulta URL", str(result), parent=self.root)
                    self.status.set("La consulta no modificó los datos")
                    return
                self.status.set(f"Página consultada: {result.title}")
                self._show_web_preview(result)

            threading.Thread(target=fetch, daemon=True).start()
            self.root.after(100, check_result)

        def _show_web_preview(self, preview: WebPreview, source: str | None = None) -> None:
            dialog = tk.Toplevel(self.root)
            dialog.title("Vista previa de URL pública")
            dialog.transient(self.root)
            dialog.geometry("850x650")
            dialog.minsize(650, 450)
            dialog.columnconfigure(0, weight=1)
            dialog.rowconfigure(4, weight=1)
            ttk.Label(dialog, text=preview.title, style="Heading.TLabel", wraplength=780,
                      padding=(12, 10)).grid(row=0, column=0, sticky="w")
            ttk.Label(dialog, text=f"Formato: {preview.format}  •  Fuente: {source or _web_source(preview.url)}",
                      padding=(12, 0)).grid(row=1, column=0, sticky="w")
            url_box = ttk.Entry(dialog)
            url_box.insert(0, preview.url)
            url_box.configure(state="readonly")
            url_box.grid(row=2, column=0, sticky="ew", padx=12, pady=6)
            note = "Datos detectados para revisar: " + (preview.suggested_kind or "ningún registro de investigación")
            if preview.related_members or preview.related_products:
                note += (f"; {len(preview.related_members)} integrantes, {len(preview.related_products)} productos"
                         f" y {len(preview.related_authorships)} autorías coincidentes con el censo")
                if preview.related_plan:
                    note += "; plan estratégico"
            note += ". Los gráficos usan productos guardados e incluyen los campos desconocidos como «Sin dato»."
            ttk.Label(dialog, text=note, wraplength=780, padding=(12, 4)).grid(row=3, column=0, sticky="w")
            body = ttk.Frame(dialog, padding=(12, 4))
            body.grid(row=4, column=0, sticky="nsew")
            body.columnconfigure(0, weight=1)
            body.rowconfigure(0, weight=1)
            shown = tk.Text(body, wrap="word", state="normal")
            scroll = AutoScrollbar(body, orient="vertical", command=shown.yview)
            shown.configure(yscrollcommand=scroll.set)
            shown.grid(row=0, column=0, sticky="nsew")
            scroll.grid(row=0, column=1, sticky="ns")
            details = ["METADATOS DECLARADOS POR LA PÁGINA"]
            details.extend(f"{key}: {value}" for key, value in preview.metadata.items())
            if not preview.metadata:
                details.append("Ninguno")
            details.extend(("", "TEXTO VISIBLE (primeras 300 líneas)", *preview.lines))
            if preview.tables:
                details.append("\nTABLAS DETECTADAS (hasta 5 tablas y 100 filas por tabla)")
                for index, table in enumerate(preview.tables, start=1):
                    details.append(f"Tabla {index}")
                    details.extend(" | ".join(row) for row in table)
                    details.append("")
            shown.insert("1.0", "\n".join(details))
            shown.configure(state="disabled")
            actions = ttk.Frame(dialog, padding=10)
            actions.grid(row=5, column=0, sticky="ew")

            def create(kind: str) -> None:
                row = (preview.suggested_row or {}).copy() if preview.suggested_kind == kind else {}
                row.setdefault("id", new_id({"grupos": "G", "investigadores": "I", "productos": "P"}[kind]))
                if source is None:
                    row["url"] = _redact_url(preview.url)
                    row.setdefault("fuente", _web_source(preview.url))
                else:
                    row.setdefault("fuente", source)
                dialog.destroy()
                self._accept_external(kind, row)

            def import_group_profile() -> None:
                dialog.destroy()
                proposed = (preview.suggested_row or {}).copy()
                if not proposed:
                    return
                reviewed = None
                if self.repo.get("grupos", proposed["id"]) is None:
                    review = RecordDialog(self.root, "grupos", proposed, external=True, repo=self.repo)
                    if not review.result:
                        return
                    reviewed = review.result
                self.status.set("Incorporando ficha GrupLAC...")
                self.root.update_idletasks()
                try:
                    counts = import_gruplac_preview(self.repo, preview, reviewed)
                except (DataError, OSError, ValueError) as exc:
                    messagebox.showerror("Ficha GrupLAC", str(exc), parent=self.root)
                    return
                self.refresh()
                self._keep_import(f"Ficha incorporada: {counts['actualizados']} registros actualizados.")
                summary = "\n".join(f"{label}: {counts[key]}" for key, label in (
                    ("grupos", "Grupos"), ("investigadores", "Investigadores"),
                    ("membresias", "Membresías"), ("planes", "Planes"),
                    ("productos", "Productos"), ("grupos_productos", "Vínculos grupo-producto"),
                    ("autorias", "Autorías"), ("actualizados", "Actualizados con la fuente"),
                    ("existentes", "Sin cambios")))
                if counts["errors"]:
                    summary += f"\nErrores: {len(counts['errors'])}\n" + "\n".join(counts["errors"][:5])
                messagebox.showinfo("Ficha GrupLAC", summary, parent=self.root)

            for kind, label in (("grupos", "Crear grupo"), ("investigadores", "Crear investigador"),
                                ("productos", "Crear producto")):
                ttk.Button(actions, text=label, command=lambda name=kind: create(name)).pack(side="left", padx=3)
            if preview.related_members or preview.related_products or preview.related_plan:
                ttk.Button(actions, text="Importar datos detectados", style="Accent.TButton",
                           command=import_group_profile).pack(side="left", padx=3)
            if preview.csv_bytes is not None:
                def import_downloaded_csv() -> None:
                    dialog.destroy()
                    with tempfile.TemporaryDirectory() as temporary:
                        path = Path(temporary) / "descarga.csv"
                        path.write_bytes(preview.csv_bytes or b"")
                        self.import_csv_path(path)
                ttk.Button(actions, text="Importar CSV PEA-i", command=import_downloaded_csv).pack(side="left", padx=3)
            ttk.Button(actions, text="Cerrar", command=dialog.destroy).pack(side="right", padx=3)
            dialog.bind("<Escape>", lambda _event: dialog.destroy())
            dialog.grab_set()

        def import_pdf(self) -> None:
            path = filedialog.askopenfilename(parent=self.root, title="PDF de GrupLAC o CvLAC", filetypes=[("PDF", "*.pdf")])
            if not path:
                return
            url = simpledialog.askstring("Origen del PDF", "URL original pública de la ficha GrupLAC/CvLAC:", parent=self.root)
            if not url:
                return
            try:
                kind, row = parse_scienti_pdf(Path(path), url.strip())
                row["fuente"] = f"PDF {Path(path).name}, consultado {date.today().isoformat()}"
            except (DataError, OSError, ValueError) as exc:
                messagebox.showerror("Importación PDF", str(exc), parent=self.root)
                return
            self._accept_external(kind, row)

        def import_docx(self) -> None:
            path = filedialog.askopenfilename(parent=self.root, title="Documento Word",
                                              filetypes=[("Word", "*.docx")])
            if not path:
                return
            path = Path(path)
            try:
                html = extract_docx_html(path)
            except DataError as exc:
                messagebox.showerror("Documento Word", str(exc), parent=self.root)
                return
            preview = parse_web_page(html, path.resolve().as_uri(), "HTML")
            self._show_web_preview(preview, source=f"DOCX {path.name}, consultado {date.today().isoformat()}")

    return App(root, data_file, repository)


def run_gui(data_file: Path | None = None, *, python_backend: bool = False,
            cpp_binary: Path | None = None) -> None:
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    repository: Repository | CppRepository | None = None
    try:
        repository, fallback_reason = open_gui_repository(
            python_backend=python_backend, cpp_binary=cpp_binary)
        app = build_gui(root, repository, data_file)
        if fallback_reason:
            app.status.set(f"Motor Python activo: {fallback_reason}")
        root.mainloop()
    except DataError as exc:
        messagebox.showerror("Backend C++", str(exc), parent=root)
        raise
    finally:
        if isinstance(repository, CppRepository):
            repository.close()
        try:
            root.destroy()
        except tk.TclError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="PEA-i UPC con interfaz Tkinter")
    parser.add_argument("--data", type=Path,
                        help="Archivo de datos PEA-i (.csv) que se abre al iniciar; por defecto data/pea_upc.csv. "
                             "También acepta una carpeta anterior para convertirla")
    parser.add_argument("--cpp-binary", type=Path, help="Ejecutable C++ compilado (opcional)")
    parser.add_argument("--python-backend", action="store_true",
                        help="Usar la implementación Python independiente en vez del backend C++")
    args = parser.parse_args()
    try:
        run_gui(args.data, python_backend=args.python_backend, cpp_binary=args.cpp_binary)
    except DataError as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()

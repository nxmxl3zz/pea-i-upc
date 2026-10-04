# Plan de rediseño visual — PEA-i UPC

Fecha: 2026-10-02. Sustituye la parte visual de `PLAN_UI_UX.md`; los flujos
funcionales de ese plan (filtros automáticos, fichas en contexto, selector
paginado, cola FIFO) se conservan sin cambios.

## Revisión del plan anterior

El plan de Codex resolvió problemas de flujo reales, pero su etapa 4
(«Diseño») se limitó a retocar estilos `clam` sobre la misma base:

| Problema observado | Causa |
|---|---|
| Aspecto genérico de panel corporativo (azul marino + verde azulado). | Paleta sin relación con la institución ni con los datos. |
| Barras de desplazamiento grises con flechas, también en modo oscuro. | No se estilizó `TScrollbar`; quedan los colores por defecto de `clam`. |
| Los gráficos muestran barras de desplazamiento aunque no hagan falta. | `_chart_panel` crea y muestra siempre ambas barras. |
| En modo oscuro los botones secundarios casi no se ven. | Botón con fondo igual a la superficie y sin borde visible. |
| La barra de trabajo blanca corta la ventana por encima del menú lateral. | Barra empaquetada en la raíz antes que el lateral. |
| Filtros en un `LabelFrame` con borde fino y título duplicado. | Contenedor por defecto en lugar de una tarjeta. |
| Encabezados de tabla centrados sobre contenido alineado a la izquierda. | `Treeview.Heading` sin `anchor`. |
| Selección de fila en bloque azul marino saturado. | `select_bg` igual al color del lateral. |
| La ficha «Resumen» es un bloque de texto plano: etiqueta y valor iguales. | `tk.Text` sin etiquetas de estilo. |
| La fuente «Segoe UI» está fijada 24 veces; en Linux cae en una genérica. | Sin resolución de familias disponibles. |
| Los colores de validación no significan nada: todo es verde azulado. | Las barras usan un único color. |

## Dirección

**Concepto: «Sierra y sabana».** La UPC es una universidad de Valledupar; su
color institucional es el verde. Se reemplaza el azul marino por un verde
perenne profundo (Sierra Nevada) y el fondo azul grisáceo por un blanco salvia
suave. Se mantiene la misma estructura que el usuario ya conoce: menú lateral
oscuro, contenido claro, un único color de acción. El cambio busca calma y
legibilidad, no decoración.

Un solo elemento audaz: **el color tiene significado**. El amarillo
caña‑flecha aparece solo para lo pendiente, el verde para lo validado, el
arcilla para lo rechazado y el gris para «Sin dato», tanto en las tarjetas como
en el gráfico de validación. Todo lo demás es sobrio.

### Paleta (claro / oscuro)

| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `page` | `#F3F6F3` | `#111714` | Fondo del contenido |
| `surface` | `#FFFFFF` | `#18201C` | Tarjetas, tablas, campos |
| `sidebar` | `#163A2E` | `#0B100E` | Menú lateral |
| `ink` | `#1C2A24` | `#E3ECE7` | Texto principal |
| `muted` | `#5B6C64` | `#94A69D` | Texto secundario |
| `line` | `#DCE4DF` | `#28332E` | Bordes y divisores |
| `primary` | `#1E6B50` | `#4DB38C` | Acciones, barras, foco |
| `pending` | `#BB7E0E` | `#E6B04A` | Pendiente (único acento cálido) |
| `rejected` | `#B5472F` | `#E07A62` | Rechazado, acciones destructivas |

Contraste comprobado (WCAG): texto principal ≥ 13:1; texto secundario ≥ 5:1;
texto blanco sobre el botón primario 6,4:1 (claro) y 5,2:1 (oscuro, fondo
`#2A7A5C`); los colores de estado superan 3:1 como gráficos. El primer
amarillo propuesto (`#D99A1E`, 2,4:1) se oscureció a `#BB7E0E` (3,4:1).

### Tipografía

Resolución por disponibilidad, sin dependencias nuevas:

- Texto: Segoe UI Variable Text → Segoe UI → Inter → Noto Sans → DejaVu Sans.
- Títulos: Segoe UI Semibold → Inter SemiBold → (texto en negrita).
- Cifras: Bahnschrift SemiBold (Windows) → Inter Display SemiBold → títulos.
  Bahnschrift, de rasgos DIN, da a las métricas un carácter técnico.

Escala: 9 (notas) · 10 (texto) · 12 (sección) · 20 (título de página) · 26 (cifras).

### Estructura

```
┌──────────┬──────────────────────────────────────────────┐
│ PEA-i    │ Muestra pública UPC · Sin cambios  [Guardar] │ ← cabecera del contenido
│ Univ. P. ├──────────────────────────────────────────────┤
│          │ Panorama de investigación                    │
│ Análisis │ Todos · Toda la institución · Todos los años │
│ ▌Dashb.  │ ┌ filtros (tarjeta) ───────────────────────┐ │
│  Gráficos│ └──────────────────────────────────────────┘ │
│ Registros│ ▬▬▬▬ ▬▬▬▬ ▬▬▬▬ ▬▬▬▬  cifras con franja de estado│
│  Grupos  │ ┌ histograma ──────┐ ┌ tipologías ──────────┐ │
│  …       │ └──────────────────┘ └──────────────────────┘ │
│ Seguim.  │ Productos de la vista (tabla)                │
│  Cola    │                                              │
│ [Tema]   ├──────────────────────────────────────────────┤
│          │ estado                                       │
└──────────┴──────────────────────────────────────────────┘
```

- El lateral ocupa toda la altura; la barra de trabajo y el estado pasan a la
  columna de contenido.
- El menú se agrupa en «Análisis», «Registros» y «Seguimiento» (texto normal,
  sin mayúsculas sostenidas). El elemento activo toma el color de la página, como
  una pestaña unida al contenido.
- Contenido alineado a la izquierda; encabezados de tabla también.

## Etapas

| Etapa | Cambios | Criterio de aceptación |
|---|---|---|
| 1. Tokens y tipografía | Paletas nuevas con colores de estado; resolución de fuentes; helper de fuentes; `option_add` para `Toplevel`, `Text` y listas desplegables. | Ninguna fuente fija en el código; diálogos y listas desplegables siguen el tema. |
| 2. Controles | Barras de desplazamiento finas sin flechas; barras que se ocultan cuando sobran (gráficos y horizontales de tablas); botones secundarios con borde; `Danger.TButton`; campos con anillo de foco; pestañas planas; encabezados de tabla a la izquierda; selección tenue. | Botones visibles en ambos temas; sin barras inútiles en el Dashboard a 1280×850. |
| 3. Estructura | Lateral a toda altura con marca y grupos; cabecera de trabajo y estado en la columna de contenido; filtros en tarjeta; tarjetas de cifras con franja de estado. | Mismos atributos públicos (`status_label`, `card_values`, `nav_buttons`…); pruebas de interfaz sin cambios. |
| 4. Gráficos y fichas | Barras con pista de fondo; colores de validación con significado; tramo «20 años o más» en tono claro; rejilla tenue; resumen de ficha con etiquetas y valores diferenciados. | Etiquetas de prueba (`bin`, `year:`, `older:`, `count:`) y textos «n · p%» intactos. |
| 5. Verificación | 57 pruebas Python; capturas claro/oscuro a 1280×850 y 900×620; ficha de grupo. | Pruebas correctas; revisión visual de capturas. |

Estado: las cinco etapas están completas.

## Límites

Sin dependencias nuevas, sin cambios en el motor, el protocolo C++, la
persistencia ni los textos funcionales. Solo cambia la capa de presentación de
`build_gui`.

## Resultado

- 57 pruebas Python correctas (1 omitida: requiere `PEA_TEST_CPP`), sin cambios
  en las pruebas.
- Revisión visual con la muestra real (6.363 productos): Dashboard, Gráficos,
  Grupos, Productos, Relaciones, Cola, ficha de grupo y de producto, y formulario
  de producto, en claro y oscuro, a 1280×850 y 900×620.
- Correcciones encontradas durante la revisión: pestaña seleccionada más baja que
  las demás (relleno de `clam`), botones con ancho mínimo excesivo, marcas
  repetidas en el eje Y con pocos productos («1, 1, 0, 0, 0») y una barra única
  que ocupaba todo el ancho del histograma.
- Lateral de 196 px: a 900 px de ancho los filtros siguen siendo legibles.
- Pendiente: revisar en Windows real, donde se usarán Segoe UI Semibold y
  Bahnschrift; en Linux se usan Inter e Inter Display.

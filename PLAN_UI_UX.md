# Plan de mejora UI/UX y cumplimiento — PEA-i UPC

Fecha: 2026-10-02. Base: `ENUNCIADO_TALLER_2.md` y auditoría de código,
pruebas y ventana realizada en esta sesión. Implementación secuencial por prioridad.

Se conservan las dos soluciones, las estructuras enlazadas, el protocolo C++,
la persistencia CSV v2 y los datos públicos incluidos. La interfaz sigue siendo
Tkinter, sin dependencias nuevas para el uso básico. Los textos del producto
siguen en español.

| Etapa | Prioridad | Cambios | Criterio de aceptación | Estado |
|---|---|---|---|---|
| 1. Corregir los flujos | P0 | Rango de años automático; errores visibles; formularios que conservan valores ante errores de dominio; selector por nombre/ID con búsqueda y páginas sobre todo el repositorio; feedback de guardado. | Filtrar 2010–2010 actualiza los resultados; un error no cierra el formulario; se puede seleccionar un investigador/producto posterior a la fila 100; los mensajes son visibles. | Completa |
| 2. Dashboard y gráficos | P1 | Resumen con métricas, contexto de filtros, histograma por año y barras de tipología/categoría/validación; gráficos junto a filtros y resultados; desglose completo en Gráficos; denominadores y datos desconocidos explícitos. | Totales, tabla y gráficos usan exactamente la misma consulta; los años ausentes se muestran con cero; ninguna categoría desaparece sin explicación; vistas Todos/Grupo/Investigador/Producto verificadas. | Completa |
| 3. Gestión en contexto | P1 | Fichas de grupos con integrantes, planes, productos y estadísticas; investigadores con grupos/productos; productos con autores/grupos/validación; crear, editar y vincular desde la ficha con nombres; relaciones buscables. | Se gestiona un grupo completo sin copiar IDs; ambos extremos de los vínculos se consultan y editan; dependencias y estados desactivados son visibles; detalle paginado. | Completa |
| 4. Diseño y flujos auxiliares | P2 | Identidad UPC, navegación seleccionada, barra de trabajo/guardado, estados legibles, tablas y formularios adaptables, teclado, estados vacíos; CSV y revisión mediante opciones visuales en lugar de nombres técnicos escritos. | Pantallas utilizables a 900×620 y 1280×850; tema claro/oscuro consistente; importación y cola mantienen validación, previsualización y orden FIFO. | Completa |
| 5. Verificación y documentación | P1 | Regresiones de interfaz con repositorios temporales, pruebas con ambos motores, CRUD/relaciones/revisión/deshacer/persistencia, capturas de escritorio y actualización de README/esquema/progreso. | Pruebas existentes y nuevas correctas; muestra real intacta; plan con evidencia por etapa y guía manual para Windows. | Completa |

## Orden y límites

Cada etapa se implementa y se comprueba antes de continuar. Los errores
reproducibles detectados durante las siguientes etapas se corrigen en esta misma
serie. No se agregan puntuaciones de Minciencias ni se infieren categorías de
productos a partir de categorías de grupos. El histograma describe años de
productos y agrupa los de hace 20 años o más; las barras categóricas incluyen
«Sin dato» y explican su población.

Las pruebas nuevas se concentran en las regresiones y los recorridos reales,
sin duplicar pruebas de colores o detalles de implementación. Las pruebas Tkinter
requieren una sesión gráfica y se omiten expresamente si no existe. La comprobación
manual en Windows real se documenta como pendiente hasta tener evidencia allí.

## Ajustes solicitados durante la implementación

Integrados en las etapas 2–4 y en la verificación final:

- Quitar los botones «Aplicar» y «Limpiar» de los filtros. Todos los filtros
  responden automáticamente al seleccionar o escribir; los años esperan
  brevemente mientras se escribe para evitar consultas por cada tecla.
- Reducir las columnas del histograma: agrupar los años de hace 20 años o más
  en «20 años o más». En 2026 incluye 2006 y anteriores; el corte avanza con
  el año actual. El rótulo explica el corte y respeta la ventana seleccionada.
- Abrir la ficha completa al pulsar un producto: información, autores,
  investigadores, grupos y estadísticas disponibles. Abrir una ficha no debe
  cambiar la búsqueda ni dejar la lista Productos filtrada a un único registro.
  Se aplica al dashboard y a las tablas de productos de las fichas.

## Trazabilidad

- Requisitos 1–4, 9 y 11: entidades, fichas, relaciones, formularios y revisión.
- Requisitos 6–8: contrato y fuentes de datos existentes, sin alterar estructuras.
- Requisito 10: ventanas de años comunes a métricas, gráficos y tabla.
- Requisito 12: tres vistas, estadísticas descriptivas, histogramas y barras.
- Notas 2, 9 y 10: documentación, persistencia e inicio vacío/carga de carpeta.
- Complementos: GUI, Git y conexión Python/C++ ya existentes.

## Evidencia inicial

- 40 pruebas Python y 4 pruebas C++/integración correctas.
- Rango 2010–2010: el total permanecía en 6.363 al escribir; refrescar daba 71.
- Selector: 100 opciones de 2.736 investigadores.
- Formulario inválido: cerraba y perdía valores antes de mostrar «Falta Título».
- Estado: variable actualizada, sin widget visible (consulta solo desde Ayuda).

## Registro de implementación

1. Flujos corregidos: cinco regresiones Tkinter correctas (años automáticos,
   estado visible, conservación de campos ante errores de formato e ID duplicado,
   selección por búsqueda y segunda página, creación/deshacer). La ventana se
   construye con `build_gui` para probarla con datos aislados. Los cambios de
   formularios se validan y aplican en el motor activo antes de cerrar el diálogo.
2. Dashboard integrado con cuatro tarjetas, contexto, histograma con una columna
   para «20 años o más», barras y tabla. Gráficos completos desplazables; la vista previa
   agrupa solo tipologías menores y lo rotula. «Sin dato» forma parte del
   denominador. Siete regresiones de interfaz correctas; captura revisada con
   los 6.363 productos del motor C++ a 1280×850.
3. Fichas en contexto: integrantes/planes/productos por grupo, grupos/productos
   por investigador y autores/grupos por producto; páginas y búsqueda, edición de
   registros y vínculos, creación de planes y estadísticas de la ficha. Las
   relaciones institucionales buscan también por nombre. Diez regresiones
   correctas, incluidos G1/G10 (planes exactos), ambos extremos de relaciones,
   creación en contexto y desactivación/deshacer sin ocultar el vínculo.
4. Diseño y flujos auxiliares: navegación seleccionada, barra de guardado y estado,
   formularios agrupados/desplazables, opciones visuales para CSV y revisión,
   tablas con nombres y controles de página visibles en ventanas pequeñas.
   Filtros automáticos sin botones, histograma compacto y apertura de la ficha
   completa por un clic, sin alterar la lista de productos. Inspección en claro y
   oscuro a 1280×850 y 900×620 con la muestra real; 17 recorridos de interfaz
   comprobados con cada motor (34 regresiones).
5. Verificación final: 74 pruebas Python correctas (40 existentes y 34 de interfaz)
   y 4/4 CTest; compilación CMake, `py_compile` y `git diff --check` correctos.
   La muestra `data/real` conserva sus archivos. README, esquema y progreso
   actualizados; [guía de verificación](docs/UI_UX_VERIFICACION.md) con trazabilidad
   al enunciado y recorrido reproducible para Windows. Las capturas finales
   confirman dashboard, fichas, estados vacíos y paginación en ambas apariencias.
   La revisión manual de la interfaz nueva en Windows real queda expresamente
   fuera de la evidencia disponible en Linux.

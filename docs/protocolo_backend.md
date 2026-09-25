# Conexión Tkinter ↔ C++

La interfaz `src/python/Taller2_XX.py` intenta usar `CppRepository` al abrirse. Localiza `pea_cpp` en `build/`; en Windows de 64 bits también puede usar el ejecutable incluido en `bin/windows/` si corresponde al código fuente. Si no existe un ejecutable vigente, intenta compilarlo con CMake. Cuando C++ no está disponible, abre el motor Python independiente. Cuando C++ sí arranca, inicia `pea_cpp --api` como proceso hijo y lo cierra al salir. El usuario abre **una sola ventana**. No hay servidor, puerto ni conexión a Internet.

```text
Acción en Tkinter → solicitud JSON por stdin → C++ Repository
Pantalla actualizada ← respuesta JSON por stdout ← validación, estructuras y estadísticas
                                              └── CSV al elegir Guardar
```

## Responsabilidades

- **C++:** listas dobles, multilistas, pila, cola, CRUD, integridad, estadísticas, importación CSV, deshacer, carga y guardado.
- **Python Tkinter:** ventanas, formularios, filtros, gráficos, mensajes y extracción básica de perfiles HTML/PDF. En ese caso Python envía el registro revisado a C++ para validarlo e incorporarlo.
- **Datos:** ambos modos comparten el [esquema CSV](esquema_datos.md). La consola `pea_cpp` sigue funcionando sola. `python3 src/python/Taller2_XX.py --python-backend` permite ejecutar el núcleo Python independiente si se necesita demostrar la segunda implementación.

## Protocolo local

Cada solicitud ocupa una línea JSON en UTF-8. Sus propiedades son cadenas; para `create` y `update`, `values` contiene un objeto JSON codificado como cadena. C++ responde con una línea JSON y vacía el búfer después de cada respuesta. `stdout` queda reservado para el protocolo; los menús solo aparecen sin `--api`.

Ejemplo de comprobación manual desde la raíz del proyecto:

```bash
printf '%s\n' '{"action":"ping"}' '{"action":"statistics","view":"Todos"}' | ./build/pea_cpp --api --demo
```

La primera respuesta es:

```json
{"ok":true,"result":{"backend":"cpp","protocol":"1"},"state":{"dirty":false,"history_size":0,"queue_size":2}}
```

El estado se adjunta a todas las respuestas: cambios sin guardar, longitud de pila de deshacer y trabajos en cola. Si una operación falla, C++ devuelve `{"ok":false,"error":"...","state":{...}}` y la ventana muestra el error sin cerrar el proceso.

| Acción | Uso |
|---|---|
| `ping`, `state`, `shutdown` | Comprobar versión y estado; cerrar el proceso hijo. |
| `new_id` | Sugerir un ID de entidad desde C++ para un formulario nuevo. |
| `reset`, `load`, `save` | Iniciar vacío, abrir una carpeta PEA-i, guardar CSV. |
| `page`, `get`, `related_page` | Leer hasta 200 registros por solicitud y obtener el total de coincidencias. `page` admite `offset`, `limit` y `query`; `related_page` añade `side` (`left`/`right`) y `active` (`1`/`0`). |
| `rows`, `related` | Lecturas completas conservadas para compatibilidad; la interfaz no las usa en sus tablas. |
| `summary` | Contar grupos e investigadores activos y categorías de productos sin enviar todas las filas. |
| `create`, `update`, `delete`, `toggle` | Gestionar entidades y relaciones con validación C++. |
| `statistics` | Recibir totales y conteos completos con una página de productos (`offset`, `limit`; 100 por defecto). |
| `queue_page`, `queue_front`, `enqueue_review`, `process_review`, `discard_review` | Gestionar la cola FIFO con páginas. `queue_rows` queda disponible para compatibilidad. |
| `undo`, `clear_history` | Usar la pila de cambios reversibles C++; acepta también instantáneas anteriores. |
| `preview_csv`, `import_csv` | Revisar y aplicar una importación CSV. |

El adaptador Python conserva el proceso abierto durante toda la sesión para que cola, pila y cambios no guardados sigan en memoria. Si la ventana se cierra normalmente, envía `shutdown`. El ejecutable se compila en cada computadora; `build/` está excluido de Git.

La carga y la importación CSV del backend leen registros uno a uno. La importación hace una pasada de validación antes de aplicar cambios, de modo que un CSV malformado no deja importada una primera parte. Las listas y multilistas siguen guardando los datos; los índices auxiliares aceleran la búsqueda por ID y por códigos externos.

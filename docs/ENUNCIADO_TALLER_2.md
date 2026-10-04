# Universidad Popular del Cesar

**Facultad de Ingeniería y Tecnológicas**<br>
**Ingeniería de Sistemas**<br>
**Estructura de Datos**<br>
**Taller 2**

En el TALLER los estudiantes podrán hacer uso de libros, cuadernos, apuntes, calculadoras, celulares, smartphones, tablets, portátiles, ChatGPT, LLMs, las esferas del dragón, las gemas del infinito, la lámpara de Aladino, invocar a Satanás, el anillo único….etc.

En grupos de 3 estudiantes, se deben resolver los siguientes ejercicios:

**Nombre:**

Usted ha sido contratado por la UPC para que realice un Programa Estadístico de Análisis de Investigación (PEA-i) para gestionar el funcionamiento de la investigación en la Universidad. El programa debe gestionar la información de investigación de la institución descargada desde el [SCIENTI](https://minciencias.gov.co/scienti), el cual pueden acceder desde la página de consulta. Recuerde, para cada estructura de datos, el sistema debe suministrar funciones de creación, inclusión, eliminación, desactivación, consulta, modificación y persistencia de los datos (operaciones CRUD). La información debe ser representada en LISTAS, MULTILISTAS, PILAS Y COLAS.

**NOTA:** Se recomienda un modelo basado en un *hipercubo de información*.

Ustedes deben desarrollar dos soluciones; una en C(C++) **Y** otra en Python que permita gestionar la información de investigación de la Universidad Popular del Cesar.

1. Las soluciones (aplicaciones) debe gestionar la información de los grupos y los investigadores de la institución.

2. Para cada grupo de investigación el sistema debe gestionar los datos de cada producto de investigación, al igual que para cada investigador.

3. Para cada grupo de investigación el sistema debe gestionar los datos correspondientes a sus integrantes, plan y los productos de investigación.

4. Para cada investigador se debe gestionar su información personal, y de productos

5. Los detalles los pueden consultar en el siguiente documento: [Modelo](https://minciencias.gov.co/sistemas-informacion/modelo-medicion-grupos).

6. Identifique claramente las variables de entrada y salida del modelo de datos. Tanto de la estructura de grupos, como de investigadores, como de productos.

7. Los programas deben están en capacidad de descargar los datos desde una URL (Web Scrapping) ([GrupLAC](https://scienti.minciencias.gov.co/gruplac/jsp/visualiza/visualizagr.jsp?nro=00000000002099)) o ([CvLAC](https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000494917)) o procesar un archivo PDF o un archivo CSV.

8. Diseñe una estructura de datos de LISTAS (la que usted prefiera) que modele el problema.

9. La estructura de datos debe permitir ingresar, eliminar, desactivar, y modificar los datos de un producto incluyendo su categoría y su validación; y los datos correspondientes a los grupos, investigadores y productos.

10. El programa debe permitirle al usuario filtrar los datos por año (ventana de observación, v.g.: los últimos dos años, los últimos 5 años, etc)

11. El programa debe permitir editar y modificar cualquier dato.

12. Para las estadísticas se utilizará un esquema descriptivo:

    a. En C la información se presentará en tipo resumen de datos. Tablas y números. (no es necesaria GUI)

    b. En Python el programa mostrara un DASHBOARD con la información estadística, histogramas y diagramas de barras. Ejemplo: <https://sistemainvestigacion.uniminuto.edu/PGrupos/Ver/141>

    c. El usuario final, puede utilizar diferentes vistas o aproximaciones:

       i. Por grupo.

       ii. Por investigador.

       iii. Por productos.

13. Sí el grupo realiza estos requerimientos tendrá una evaluación de 4.0

14. Complementos:

    a. Usar Git y GitHub.

    b. Uso de Base de Datos.

    c. Uso de GUI creativa.

    d. Integración entre lenguajes. (interoperabilidad)

    e. Documentación

    f. ¿Rust?

## NOTAS

1. Los estudiantes deben entregar los 2 archivos formato de texto donde se consignen las respuestas a los ejercicios. (v.g. Taller2_AB_PO_XX.cpp, Taller2_AB_PO_XX.py)

2. Los estudiantes deben entregar un archivo Word (texto) de especificación técnica donde se describa el diseño de la estructura de datos, la estrategia de solución y la documentación referida al proyecto. Se recomienda el uso de imágenes y diagramas. Se recomienda:

    a. Usar diagramas de casos de uso.

    b. Especificación formal de requerimientos (SPEC)

    c. HU – Historias de Usuario

3. Los estudiantes deben realizar un video donde se explique la solución a todos y cada uno de los ejercicios propuestos, el video debe cargarse en YouTube y permitir que el profesor pueda revisarlo. (o en una carpeta compartida)

    i. El video debe durar alrededor de 10 minutos.

    ii. Debe respetarse la identidad institucional de la Universidad Popular del Cesar.

    iii. Los estudiantes deben ser visibles en video todo el tiempo.

4. Un archivo texto con la información de identificación de los estudiantes.

5. Los archivos deben entregarse al correo electrónico adithperez@unicesar.edu.co

6. La entrega debe realizarse antes del lunes 19 de octubre a las 11:59 am.

7. El tema del correo (subject) debe ser: Estructura de datos Taller 2 Grupo XX 2026

8. Los archivos fuente deben llevar por nombre las iniciales de los estudiantes. (AB-PO.py)

9. Los estudiantes deben suministrar un archivo de su preferencia donde se consigne la persistencia de los datos utilizados.

10. El usuario puede decidir si cargar los datos del archivo o ejecutar sin datos.

11. Suerte!!!

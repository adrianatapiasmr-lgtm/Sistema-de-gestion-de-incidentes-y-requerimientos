# app.py

# Importamos las herramientas necesarias para gestionar las rutas y páginas.
from flask import (
    Flask,
    request,
    send_from_directory,
    render_template_string,
    redirect,
    url_for,
    jsonify,
    session
)

# Importamos la función encargada de leer y validar los archivos CSV.
from leer_csv import leer_csv

# Importamos las funciones para almacenar casos y calcular sus fechas.
from almacenar_casos import (
    almacenar_casos,
    obtener_festivos,
    calcular_fecha_inicio_gestion,
    calcular_fecha_vencimiento
)

# Importamos datetime para interpretar la fecha del formulario.
from datetime import datetime, time, timedelta

# Importamos la función encargada de transferir los casos a la BD principal.
from transferir_casos import transferir_casos

# Importamos las conexiones a las bases de datos.
from conexion import conectar_temporal, conectar_principal

from gestionar_invalidos import (
    consultar_registros_invalidos,
    actualizar_registro_invalido,
    validar_registro_invalido,
    transferir_registro_corregido,
    actualizar_caso,
    corregir_registro_invalido
)

# Importamos la función que genera el ranking de técnicos disponibles.
from algoritmo_asignacion import recomendar_tecnicos

# Importamos json para interpretar los campos adicionales enviados desde el panel.
import json

# ==================================================
# CONFIGURACIÓN
# ==================================================

# Creamos la aplicación web.
app = Flask(__name__)

# Configuramos una clave para proteger los datos de sesión.
app.secret_key = "clave_temporal_proyecto_aris"

# Importamos wraps para conservar la información de las funciones protegidas.
from functools import wraps

# ==================================================
# FUNCIÓN: INICIAR SESIÓN
# ==================================================


# ==================================================
# FUNCIÓN: INICIAR SESIÓN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    # Leemos la plantilla para mostrar el formulario.
    with open(f"{app.root_path}/login.html", encoding="utf-8") as archivo:
        plantilla = archivo.read()

    # Si ingresamos mediante GET, mostramos el formulario.
    if request.method == "GET":
        return render_template_string(
            plantilla,
            mensaje_error=request.args.get("error", "")
        )

    # Recuperamos las credenciales escritas en el formulario.
    usuario = request.form.get("usuario", "").strip()
    contrasena = request.form.get("contrasena", "")

    # Comprobamos que los campos no estén vacíos.
    if not usuario or not contrasena:
        return redirect(url_for(
            "login",
            error="Debes ingresar el usuario y la contraseña."
        ))

    conexion = None
    cursor = None

    try:
        # Conectamos con la base de datos principal.
        conexion = conectar_principal()

        # Creamos el cursor para consultar las credenciales.
        cursor = conexion.cursor(dictionary=True)

        # Buscamos el usuario registrado en SQL.
        cursor.execute("""
            SELECT usuario, contrasena, rol
            FROM usuarios
            WHERE usuario = %s
        """, (usuario,))

        resultado = cursor.fetchone()

        # Mostramos los datos recuperados para comprobar la consulta.
        print("USUARIO RECIBIDO:", repr(usuario))
        print("CONTRASEÑA RECIBIDA:", repr(contrasena))
        print("RESULTADO SQL:", resultado)

        if resultado:
            print("CONTRASEÑA SQL:", repr(resultado["contrasena"]))
            print("COINCIDENCIA:", resultado["contrasena"] == contrasena)

        # Comparamos directamente la contraseña almacenada en SQL.
        if resultado and resultado["contrasena"] == contrasena:

            # Guardamos los datos del usuario en la sesión.
            session["usuario"] = resultado["usuario"]
            session["rol"] = resultado["rol"]

            # Permitimos el ingreso a la página de asignación.
            return redirect(url_for("mostrar_dashboard"))

        # Si las credenciales son incorrectas, mostramos el mensaje.
        return redirect(url_for(
            "login",
            error="Usuario o contraseña incorrectos."
        ))

    except Exception as error:

        # Mostramos el error en la consola para facilitar su revisión.
        print(f"Error durante el inicio de sesión: {error}")

        return redirect(url_for(
            "login",
            error="No fue posible verificar las credenciales."
        ))

    finally:

        # Cerramos el cursor si fue creado.
        if cursor:
            cursor.close()

        # Cerramos la conexión si fue establecida.
        if conexion:
            conexion.close()


# ==================================================
# FUNCIÓN: CERRAR SESIÓN
# ==================================================

@app.route("/cerrar-sesion")
def cerrar_sesion():

    # Eliminamos los datos de autenticación de la sesión.
    session.clear()

    # Regresamos al inicio de sesión.
    return redirect(url_for("login"))


# ==================================================
# FUNCIÓN: COMPARTIR USUARIO CON LAS PLANTILLAS
# ==================================================

@app.context_processor
def compartir_usuario():

    # Enviamos el usuario conectado a todas las plantillas HTML.
    return {
        "usuario_actual": session.get("usuario")
    }


# ==================================================
# FUNCIÓN: VERIFICAR INICIO DE SESIÓN
# ==================================================

def requiere_login(funcion):

    # Conservamos los datos originales de la función protegida.
    @wraps(funcion)
    def funcion_protegida(*args, **kwargs):

        # Comprobamos si existe un usuario autenticado.
        if "usuario" not in session:

            # Si no hay una sesión activa, enviamos al inicio de sesión.
            return redirect(url_for("login"))

        # Si existe una sesión, permitimos continuar.
        return funcion(*args, **kwargs)

    return funcion_protegida


# ==================================================
# PLANTILLA DE RESPUESTA
# ==================================================

# Definimos una página para mostrar los resultados de las operaciones.
PLANTILLA_RESULTADO = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Proyecto Maullidos</title>
</head>
<body>

    <!-- Mostramos el mensaje correspondiente al resultado. -->
    <h3>{{ mensaje }}</h3>

    <!-- Mostramos información adicional cuando exista. -->
    {% if detalle %}
        <p style="white-space: pre-line;">{{ detalle }}</p>
    {% endif %}

    <!-- El botón solo aparece cuando el almacenamiento temporal fue exitoso. -->
    {% if mostrar_boton %}
        <form action="/confirmar-transferencia" method="GET">
            <button type="submit">Subir a la BD principal</button>
        </form>
    {% endif %}

    <!-- Permitimos regresar a la página principal. -->
    <a href="/">Volver</a>

</body>
</html>
"""


# Plantilla para mostrar el resultado de una transferencia exitosa.
PLANTILLA_TRANSFERENCIA = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Transferencia completada - Proyecto Aris</title>
</head>
<body>

    <h1>¡Transferencia completada!</h1>

    <p>Los resultados de la operación son los siguientes:</p>

    <ul>
        <li>Casos insertados en la BD principal: {{ insertados }}</li>
        <li>Casos eliminados de la BD temporal: {{ eliminados }}</li>
        <li>Casos duplicados: {{ duplicados }}</li>
    </ul>

    {% if not limpieza_exitosa %}
        <h3>Advertencia: la limpieza temporal no se completó.</h3>
        <p>{{ error_limpieza }}</p>
    {% endif %}

    <a href="/">
        <button type="button">Volver al inicio</button>
    </a>

</body>
</html>
"""


# Plantilla para confirmar la transferencia de casos.
PLANTILLA_CONFIRMACION = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Confirmar transferencia</title>
</head>
<body>

    <h1>Confirmar transferencia</h1>

    <p>Casos disponibles para transferir: {{ cantidad }}</p>

    {% if cantidad_invalidos > 0 %}

        <h3>No es posible realizar la transferencia.</h3>

        <p>
            Hay {{ cantidad_invalidos }} registros inválidos
            pendientes de corrección.
        </p>

        <p>Corrige todos los registros antes de continuar.</p>

        <a href="/panel">Volver al panel</a>

    {% elif casos_sin_sede %}

        <h3>No es posible realizar la transferencia.</h3>

        <p>
            Hay {{ casos_sin_sede | length }}
            casos sin una sede seleccionada.
        </p>

        <p>Debes seleccionar una sede para los siguientes casos:</p>

        <p>{{ casos_sin_sede | join(', ') }}</p>

        <a href="/panel">Volver al panel para corregirlos</a>

    {% elif cantidad > 0 %}

        <p>Todos los registros han superado la validación.</p>

        <form action="/transferir-casos" method="POST">
            <button type="submit">Confirmar transferencia</button>
        </form>

        <a href="/panel">Volver al panel</a>

    {% else %}

        <p>No hay casos disponibles para transferir.</p>

        <a href="/panel">Volver al panel</a>

    {% endif %}

</body>
</html>
"""

PLANTILLA_PANEL = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Panel - Proyecto Aris</title>

    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 30px;
        }

        h1, h2 {
            text-align: center;
        }

        .contenedor-tabla {
            overflow-x: auto;
            margin-bottom: 35px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }

        th, td {
            border: 1px solid #ccc;
            padding: 8px;
            text-align: left;
        }
        /* Eliminamos el espacio visual izquierdo de las celdas de errores. */
        td.errores {
            padding-left: 0 !important;
        }

        th {
            background-color: #eee;
        }

        td[contenteditable="true"] {
            background-color: #fffde7;
            cursor: text;
            min-width: 100px;
        }

        td[contenteditable="true"]:focus {
            outline: 2px solid #4285f4;
        }

        .boton {
            padding: 10px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin: 5px;
        }

        /* Identificamos visualmente las acciones de eliminación. */
        .boton-eliminar {
            background-color: #c62828;
            color: white;
        }

        .boton-transferir {
            background-color: #218838;
            color: white;
            font-size: 16px;
        }

        .errores {
            color: #b00020;
            white-space: pre-wrap;
            padding-left: 0;
        }

        .acciones {
            text-align: center;
            margin: 25px 0;
        }

        .nota {
            text-align: center;
            color: #555;
        }
                /* Presentamos los mensajes de las operaciones realizadas. */
        .mensaje {
            padding: 12px;
            margin: 20px 0;
            border: 1px solid #ccc;
            border-radius: 5px;
            text-align: center;
        }
    </style>
</head>

<body>

    <h1>Panel de gestión de casos</h1>
    <!-- Mostramos el resultado de la última operación, si existe. -->
    {% if mensaje %}
        <div class="mensaje">
            <h3>{{ mensaje }}</h3>

            {% if detalle %}
                <p>{{ detalle }}</p>
            {% endif %}
        </div>
    {% endif %}
    <p class="nota">
        Haz clic en las celdas editables para modificar los datos.
        Después, guarda los cambios de cada registro.
    </p>

    <h2>Casos correctos</h2>

    <div class="contenedor-tabla">
        <table id="tabla-casos">
            <thead>
                <tr>
                    {% for columna in columnas_casos %}
                        <th>{{ columna }}</th>
                    {% endfor %}
                    <th>Acciones</th>
                </tr>
            </thead>
            <tbody>
                {% for caso in casos %}
                    <tr data-codigo-original="{{ caso.codigo_caso }}">

                   
                {% for columna in columnas_casos %}
                    <td
                        data-columna="{{ columna }}"
                        {% if columna in [
                            'codigo_caso', 'estado', 'descripcion',
                            'prioridad', 'fecha_apertura', 'observaciones'
                        ] %}
                            contenteditable="true"
                        {% endif %}
                    >

                        {% if columna == 'es_vip' %}

                            <select>
                                <option value="No" {% if not caso[columna] %}selected{% endif %}>
                                    No
                                </option>
                                <option value="Si" {% if caso[columna] %}selected{% endif %}>
                                    Si
                                </option>
                            </select>

                        {% elif columna == 'nombre_sede' %}

                            <select>
                                <option value="" disabled
                                    {% if not caso[columna] %}selected{% endif %}>
                                    Seleccione una sede
                                </option>

                                {% for sede in sedes %}
                                    <option value="{{ sede.nombre_sede }}"
                                        {% if caso[columna] == sede.nombre_sede %}selected{% endif %}>
                                        {{ sede.nombre_sede }}
                                    </option>
                                {% endfor %}
                            </select>

                            {% elif columna == 'fecha_apertura' and caso[columna] %}

                                {% if caso[columna].strftime is defined %}
                                    {{ caso[columna].strftime('%Y-%m-%dT%H:%M') }}
                                {% else %}
                                    {{ caso[columna] }}
                                {% endif %}

                        {% else %}

                            {{ caso[columna] if caso[columna] is not none else '' }}

                        {% endif %}

                    </td>
                {% endfor %}

                        <td>

                            <!-- Permitimos eliminar individualmente el caso seleccionado. -->
                            <form
                                action="/eliminar-caso"
                                method="POST"
                                onsubmit="return confirm('¿Estás seguro de eliminar este caso?');"
                                style="display: inline;"
                            >
                                <input
                                    type="hidden"
                                    name="codigo_caso"
                                    value="{{ caso.codigo_caso }}"
                                >

                                <button class="boton boton-eliminar" type="submit">
                                    Eliminar
                                </button>
                            </form>
                        </td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
     <!-- Permitimos guardar todos los casos modificados desde un solo botón. -->
    <div class="acciones">
        <button
            class="boton boton-transferir"
            type="button"
            onclick="guardarTodosLosCasos()"
        >
            Guardar cambios de los casos
        </button>
    </div>

    <h2>Registros incorrectos</h2>

    <div class="contenedor-tabla">
        <table id="tabla-invalidos">
            <thead>
                <tr>
                    {% for columna in columnas_invalidos %}
                        <th>{{ columna }}</th>
                    {% endfor %}
                    <th>Acciones</th>
                </tr>
            </thead>

                <tbody>
        {% for registro in invalidos %}
            <tr data-id-registro="{{ registro.id_registro }}">
                {% for columna in columnas_invalidos %}
                    <td
                        {% if columna in [
                            'codigo_caso',
                            'estado',
                            'descripcion',
                            'fecha_prevista',
                            'prioridad',
                            'fecha_apertura',
                            'campos_adicionales'
                        ] %}
                            contenteditable="true"
                        {% endif %}
                        data-columna="{{ columna }}"
                        {% if columna in ['errores', 'campos_adicionales'] %}
                            class="errores"
                        {% endif %}
                    >
                        {% if columna == 'es_vip' %}
                            <!-- Seleccionamos si el caso es VIP o no. -->
                            <select>
                                <option value="No"
                                    {% if not registro[columna] %}selected{% endif %}>
                                    No
                                </option>
                                <option value="Si"
                                    {% if registro[columna] %}selected{% endif %}>
                                    Si
                                </option>
                            </select>

                        {% elif columna == 'nombre_sede' %}
                            <!-- Permitimos seleccionar una sede obligatoriamente. -->
                            <select>
                                <option value="" disabled
                                    {% if not registro[columna] %}selected{% endif %}>
                                    Seleccione una sede
                                </option>

                                {% for sede in sedes %}
                                    <option value="{{ sede.nombre_sede }}"
                                        {% if registro[columna] == sede.nombre_sede %}selected{% endif %}>
                                        {{ sede.nombre_sede }}
                                    </option>
                                {% endfor %}
                            </select>

                        {% elif columna == 'errores' %}
                            <!-- Mostramos los errores sin espacios sobrantes. -->
                            {{- registro[columna] | map('trim') | join('|') | trim -}}

                        {% elif columna == 'campos_adicionales' %}
                            <!-- Mostramos los campos adicionales sin espacios sobrantes. -->
                            {{- registro[columna] | map('trim') | join('|') | trim -}}

                        {% else %}
                            {{- registro[columna] if registro[columna] is not none else '' -}}
                        {% endif %}
                    </td>
                {% endfor %}

                <td>
                    <button
                        class="boton boton-guardar"
                        onclick="guardarInvalido(this)"
                    >
                        Guardar y validar
                    </button>

                    <!-- Permitimos eliminar individualmente el registro incorrecto. -->
                    <form
                        action="/eliminar-registro-invalido"
                        method="POST"
                        onsubmit="return confirm('¿Estás seguro de eliminar este registro?');"
                        style="display: inline;"
                    >
                        <input
                            type="hidden"
                            name="id_registro"
                            value="{{ registro.id_registro }}"
                        >

                        <button class="boton boton-eliminar" type="submit">
                            Eliminar
                        </button>
                    </form>
                </td>
            </tr>
        {% endfor %}
    </tbody>
        </table>
    </div>

    <div class="acciones">

        <!-- Permitimos transferir los casos correctos. -->
        <form action="/confirmar-transferencia" method="GET">
            <button class="boton boton-transferir" type="submit">
                Subir casos correctos a la BD
            </button>
        </form>

        <!-- Permitimos cancelar y eliminar toda la importación temporal. -->
        <form
            action="/cancelar-importacion"
            method="POST"
            onsubmit="return confirm('¿Estás seguro? Se eliminarán TODOS los casos correctos e incorrectos de la importación temporal. Esta acción no se puede deshacer.');"
        >
            <button class="boton boton-eliminar" type="submit">
                Cancelar importación
            </button>
        </form>

    </div>  

    <script>
        // Recuperamos el contenido de una fila según el nombre de cada columna.
        function obtenerDatosFila(fila) {
            const datos = {};

            fila.querySelectorAll("td[data-columna]").forEach(celda => {

                // Si la celda tiene una lista desplegable, recuperamos su opción seleccionada.
                const selector = celda.querySelector("select");

                if (selector) {
                    datos[celda.dataset.columna] = selector.value;
                } else {
                    // Si no tiene selector, recuperamos el texto de la celda.
                    datos[celda.dataset.columna] = celda.innerText.trim();
                }
            });

            return datos;
        }

        // Enviamos todos los casos de la tabla para actualizarlos individualmente.
        function guardarTodosLosCasos() {

            const filas = document.querySelectorAll(
                "#tabla-casos tbody tr"
            );

            const casos = [];

            // Recuperamos los datos de cada fila.
            filas.forEach(fila => {

                const datos = obtenerDatosFila(fila);

                datos.codigo_original = fila.dataset.codigoOriginal;

                casos.push(datos);
            });

            // Creamos un formulario para enviar todos los casos a Flask.
            const formulario = document.createElement("form");
            formulario.method = "POST";
            formulario.action = "/actualizar-todos-los-casos";

            const campo = document.createElement("input");
            campo.type = "hidden";
            campo.name = "casos";
            campo.value = JSON.stringify(casos);

            formulario.appendChild(campo);
            document.body.appendChild(formulario);

            formulario.submit();
        }

        // Enviamos los cambios de un caso válido a Flask.
        function guardarCaso(boton) {
            const fila = boton.closest("tr");
            const datos = obtenerDatosFila(fila);

            const formulario = document.createElement("form");
            formulario.method = "POST";
            formulario.action = "/actualizar-caso";

            const valores = {
                ...datos,
                codigo_original: fila.dataset.codigoOriginal
            };

            Object.entries(valores).forEach(([nombre, valor]) => {
                const campo = document.createElement("input");
                campo.type = "hidden";
                campo.name = nombre;
                campo.value = valor;
                formulario.appendChild(campo);
            });

            document.body.appendChild(formulario);
            formulario.submit();
        }

        // Enviamos los cambios de un registro incorrecto para validarlo.
        function guardarInvalido(boton) {
            const fila = boton.closest("tr");
            const datos = obtenerDatosFila(fila);
            // Convertimos los campos adicionales escritos en la celda en una lista.
            // Cada línea representa un campo adicional.
            // Si la celda está vacía, enviamos una lista vacía.
            // Separamos los campos adicionales utilizando los saltos de línea.
            const camposAdicionales = (datos.campos_adicionales || "")
                .split("\\n")
                .map(campo => campo.trim())
                .filter(campo => campo !== "");

            // Convertimos la lista a JSON para enviarla correctamente a Python.
            datos.campos_adicionales = JSON.stringify(camposAdicionales);

            const formulario = document.createElement("form");
            formulario.method = "POST";
            formulario.action = "/corregir-registro-invalido";

            const valores = {
                ...datos,
                id_registro: fila.dataset.idRegistro
            };

            Object.entries(valores).forEach(([nombre, valor]) => {
                const campo = document.createElement("input");
                campo.type = "hidden";
                campo.name = nombre;
                campo.value = valor;
                formulario.appendChild(campo);
            });

            document.body.appendChild(formulario);
            formulario.submit();
        }
    </script>

</body>
</html>
"""

# ==================================================
# FUNCIÓN: CONSULTAR Y MOSTRAR EL PANEL DE REGISTROS
# ==================================================

@app.route("/panel", methods=["GET"])
def mostrar_panel(
    datos_pendientes=None,
    mensaje_personalizado="",
    detalle_personalizado=""
):

    # Inicializamos las conexiones y los cursores.
    conexion = None
    cursor = None
    conexion_principal = None
    cursor_principal = None

    try:

        # Nos conectamos a la base de datos temporal.
        conexion = conectar_temporal()

        # Creamos un cursor que devuelve los resultados como diccionarios.
        cursor = conexion.cursor(dictionary=True)

        # Consultamos los casos directamente desde la tabla temporal.
        cursor.execute("""
            SELECT
                codigo_caso,
                estado,
                descripcion,
                prioridad,
                fecha_apertura,
                fecha_inicio_gestion,
                fecha_vencimiento,
                es_vip,
                nombre_sede,
                observaciones,
                fecha_registro
            FROM casos
            ORDER BY fecha_registro DESC
        """)

        # Recuperamos todos los casos encontrados.
        casos = cursor.fetchall()

        

        # Conservamos en pantalla los datos de los casos que no pudieron actualizarse.
        if datos_pendientes:
            for caso in casos:
                codigo_original = caso["codigo_caso"]

                if codigo_original in datos_pendientes:
                    caso.update(datos_pendientes[codigo_original])

        # Obtenemos los nombres de todas las columnas de la tabla casos.
        columnas_casos = [columna[0] for columna in cursor.description]

        # Consultamos todos los registros incorrectos.
        invalidos = consultar_registros_invalidos()
        # Nos conectamos a la base de datos principal.
        conexion_principal = conectar_principal()

        # Creamos un cursor que devuelve los resultados como diccionarios.
        cursor_principal = conexion_principal.cursor(dictionary=True)

        # Consultamos las sedes disponibles para los selectores del panel.
        cursor_principal.execute("""
            SELECT id_sede, nombre_sede
            FROM sedes
            ORDER BY nombre_sede ASC
        """)

        # Recuperamos todas las sedes registradas.
        sedes = cursor_principal.fetchall()

        # Obtenemos los nombres de las columnas de los registros incorrectos.
        # Definimos todas las columnas de los registros inválidos.
        # Así los encabezados se mantienen visibles aunque no haya registros.
        columnas_invalidos = [
            "id_registro",
            "numero_registro",
            "codigo_caso",
            "estado",
            "descripcion",
            "fecha_prevista",
            "prioridad",
            "fecha_apertura",
            "es_vip",
            "nombre_sede",
            "errores",
            "campos_adicionales",
            "fecha_registro"
        ]

        # Priorizamos los mensajes de una operación recién ejecutada.
        mensaje = mensaje_personalizado or request.args.get("mensaje", "")
        detalle = detalle_personalizado or request.args.get("detalle", "")

        # Mostramos el panel con ambas tablas y los mensajes correspondientes.
        return render_template_string(
            PLANTILLA_PANEL,
            casos=casos,
            columnas_casos=columnas_casos,
            invalidos=invalidos,
            columnas_invalidos=columnas_invalidos,
            mensaje=mensaje,
            sedes=sedes,
            detalle=detalle
        )

    except Exception as error:

        # Conservamos el error técnico en la terminal.
        print(f"ERROR AL CONSULTAR LOS REGISTROS: {error}")

        # Informamos que no fue posible cargar el panel.
        return mostrar_resultado(
            "No fue posible consultar los registros de la base temporal.",
            codigo_http=500
        )

    finally:

        # Cerramos el cursor si fue creado.
        if cursor is not None:
            cursor.close()

        # Cerramos la conexión si fue establecida.
        if conexion is not None and conexion.is_connected():
            conexion.close()

        # Cerramos el cursor de la base principal.
        if cursor_principal is not None:
            cursor_principal.close()

        # Cerramos la conexión con la base principal.
        if conexion_principal is not None and conexion_principal.is_connected():
            conexion_principal.close()

# ==================================================
# FUNCIÓN: MOSTRAR RESULTADOS
# ==================================================

def mostrar_resultado(mensaje, mostrar_boton=False, detalle=None, codigo_http=200):

    # Renderizamos la plantilla con el mensaje y las opciones correspondientes.
    return render_template_string(
        PLANTILLA_RESULTADO,
        mensaje=mensaje,
        mostrar_boton=mostrar_boton,
        detalle=detalle
    ), codigo_http



# ==================================================
# FUNCIÓN: MOSTRAR PÁGINA PRINCIPAL
# ==================================================

@app.route("/", methods=["GET"])
def inicio():

    # Mostramos la nueva página de inicio de sesión.
    return redirect(url_for("login"))



@app.route("/asignacion", methods=["GET"])
@requiere_login
def mostrar_asignacion():

    # Inicializamos las listas de registros de la carga temporal.
    casos_temporales = []
    registros_invalidos = []

    # Inicializamos las columnas que utilizarán las tablas.
    columnas_casos_temporales = []
    columnas_invalidos = []

    # Recuperamos los mensajes generados durante la carga del CSV.
    mensaje_carga = session.pop("mensaje_carga", "")
    detalle_carga = session.pop("detalle_carga", "")
    mostrar_resultados_carga = session.pop("mostrar_resultados_carga", False)

    # Recuperamos el resumen de la última transferencia realizada.
    resultado_transferencia = session.pop("resultado_transferencia", None)

    # Recuperamos si ocurrió algún error durante la transferencia.
    error_transferencia = session.pop("error_transferencia", "")

    # Recuperamos si debemos abrir automáticamente el modal de carga.
    abrir_modal_carga = session.pop("abrir_modal_carga", False)

    # Comprobamos si existen registros pertenecientes a la última carga.
    hay_carga_para_limpiar = bool(
    session.get("codigos_carga") or
    session.get("ids_invalidos_carga")
)

    # Comprobamos si los identificadores siguen disponibles en la sesión.
    print("CARGA DISPONIBLE PARA LIMPIAR:", hay_carga_para_limpiar)
    print("CÓDIGOS GUARDADOS:", session.get("codigos_carga", []))
    print("IDS INVÁLIDOS GUARDADOS:", session.get("ids_invalidos_carga", []))

    # Recuperamos el código escrito o seleccionado por el usuario.
    codigo_busqueda = request.args.get("codigo", "").strip()

    # Recuperamos el mensaje que se mostrará después de una operación.
    mensaje_exito = request.args.get("mensaje", "")

    # Recuperamos el mensaje de error que se mostrará en la página.
    mensaje_error = request.args.get("error", "")

    # Recuperamos las recomendaciones guardadas para el caso seleccionado.
    recomendaciones = []

    if codigo_busqueda == session.get("codigo_recomendaciones"):
        recomendaciones = session.get("recomendaciones", [])

    # Leemos la plantilla HTML de asignación.
    with open(f"{app.root_path}/asignacion.html", encoding="utf-8") as archivo:
        plantilla = archivo.read()

    conexion = None
    cursor = None

    # Inicializamos las listas y variables de la página.
    casos_pendientes = []
    tecnicos = []
    sedes = []
    caso_seleccionado = None
    mensaje_busqueda = None

    try:
        # Conectamos con la base de datos principal.
        conexion = conectar_principal()

        # Creamos un cursor con resultados almacenados en búfer.
        cursor = conexion.cursor(dictionary=True, buffered=True)

        # Consultamos todos los casos activos que todavía no tienen asignación.
        cursor.execute("""
            SELECT
                c.codigo_caso,
                c.descripcion,
                c.prioridad,
                c.nombre_sede,
                c.es_vip,
                c.fecha_apertura
            FROM casos c
            LEFT JOIN asignaciones a
                ON c.codigo_caso = a.codigo_caso
            WHERE c.estado = 'Activo'
              AND a.codigo_caso IS NULL
            ORDER BY c.fecha_apertura ASC
        """)

        casos_pendientes = cursor.fetchall()

        # Consultamos todos los técnicos y sus respectivas sedes.
        cursor.execute("""
            SELECT
                t.id_tecnico,
                t.nombre,
                t.es_vip,
                t.activo,
                t.id_sede,
                s.nombre_sede
            FROM tecnicos t
            INNER JOIN sedes s
                ON t.id_sede = s.id_sede
            ORDER BY t.nombre ASC
        """)

        # Recuperamos inmediatamente los técnicos consultados.
        tecnicos = cursor.fetchall()

        # Comprobamos cuántos técnicos recuperamos.
        print("TÉCNICOS RECUPERADOS:", tecnicos)
        print("TOTAL TÉCNICOS:", len(tecnicos))

        # Consultamos todas las sedes registradas.
        cursor.execute("""
            SELECT
                id_sede,
                nombre_sede
            FROM sedes
            ORDER BY nombre_sede ASC
        """)

        # Recuperamos las sedes consultadas.
        sedes = cursor.fetchall()

        # Si se recibió un código, buscamos el caso correspondiente.
        if codigo_busqueda:

            cursor.execute("""
                SELECT
                    c.codigo_caso,
                    c.descripcion,
                    c.prioridad,
                    c.nombre_sede,
                    c.es_vip,
                    c.fecha_apertura
                FROM casos c
                LEFT JOIN asignaciones a
                    ON c.codigo_caso = a.codigo_caso
                WHERE c.codigo_caso = %s
                  AND c.estado = 'Activo'
                  AND a.codigo_caso IS NULL
            """, (codigo_busqueda,))

            caso_seleccionado = cursor.fetchone()

            # Informamos si el código no corresponde a un caso pendiente.
            if not caso_seleccionado:
                mensaje_busqueda = "No se encontró un caso pendiente con ese código."

        # Comprobamos qué técnicos pueden asignarse al caso seleccionado.
        for tecnico in tecnicos:

            tecnico["seleccionable"] = (
                caso_seleccionado is not None
                and bool(tecnico["activo"])
                and tecnico["nombre_sede"] == caso_seleccionado["nombre_sede"]
            )

                # Conectamos con la base de datos temporal.
        conexion_temporal = conectar_temporal()
        cursor_temporal = conexion_temporal.cursor(dictionary=True)

        # Consultamos los casos válidos almacenados temporalmente.
        cursor_temporal.execute("""
            SELECT
                codigo_caso,
                estado,
                descripcion,
                prioridad,
                fecha_apertura,
                fecha_inicio_gestion,
                fecha_vencimiento,
                es_vip,
                nombre_sede,
                observaciones,
                fecha_registro
            FROM casos
            ORDER BY fecha_registro DESC
        """)

        # Recuperamos los casos válidos.
        casos_temporales = cursor_temporal.fetchall()

        # Consultamos los nombres de las columnas.
        columnas_casos_temporales = [
            columna[0] for columna in cursor_temporal.description
        ]

        # Cerramos el cursor y la conexión temporal.
        cursor_temporal.close()
        conexion_temporal.close()

        # Consultamos los registros que todavía tienen errores.
        registros_invalidos = consultar_registros_invalidos()

        # Definimos las columnas de los registros inválidos.
        columnas_invalidos = [
            "id_registro",
            "numero_registro",
            "codigo_caso",
            "estado",
            "descripcion",
            "fecha_prevista",
            "prioridad",
            "fecha_apertura",
            "es_vip",
            "nombre_sede",
            "errores",
            "campos_adicionales",
            "fecha_registro"
        ]

        # Mostramos la página con los casos, técnicos y selección realizada.
        return render_template_string(
            plantilla,
            casos_pendientes=casos_pendientes,
            tecnicos=tecnicos,
            sedes=sedes,
            caso_seleccionado=caso_seleccionado,
            recomendaciones=recomendaciones,
            codigo_busqueda=codigo_busqueda,
            mensaje_busqueda=mensaje_busqueda,
            mensaje_exito=mensaje_exito,
            mensaje_error=mensaje_error,
            # Información de la transferencia de casos.
            resultado_transferencia=resultado_transferencia,
            error_transferencia=error_transferencia,

            # Datos de los registros almacenados temporalmente.
            casos_temporales=casos_temporales,
            registros_invalidos=registros_invalidos,
            columnas_casos_temporales=columnas_casos_temporales,
            columnas_invalidos=columnas_invalidos,

            # Información del procesamiento del archivo CSV.
            mensaje_carga=mensaje_carga,
            detalle_carga=detalle_carga,
            mostrar_resultados_carga=mostrar_resultados_carga,
            hay_carga_para_limpiar=hay_carga_para_limpiar,
            abrir_modal_carga=abrir_modal_carga,

            error_consulta=None
        )

    except Exception as error:
        # Informamos el error en la consola para facilitar su revisión.
        print(f"Error al consultar la información de asignación: {error}")

        # Mostramos la página con un mensaje de error.
        return render_template_string(
            plantilla,
            casos_pendientes=[],
            tecnicos=[],
            sedes=[],
            recomendaciones=[],
            caso_seleccionado=None,
            codigo_busqueda=codigo_busqueda,
            mensaje_busqueda=None,
            mensaje_exito="",
            mensaje_error="",
            resultado_transferencia=resultado_transferencia,
            error_transferencia=error_transferencia,
            # Enviamos listas vacías si ocurre un error en las consultas.
            casos_temporales=[],
            registros_invalidos=[],
            columnas_casos_temporales=[],
            columnas_invalidos=[],
            mensaje_carga="",
            detalle_carga="",
            mostrar_resultados_carga=False,
            hay_carga_para_limpiar=False,
            error_consulta="No fue posible cargar la información de asignación."
        )

# ==================================================
# BASE DE CONOCIMIENTOS
# ==================================================

@app.route("/base-conocimientos", methods=["GET"])
@requiere_login
def mostrar_base_conocimientos():

    try:
        # Leemos la plantilla HTML de la base de conocimientos.
        with open(f"{app.root_path}/base_conocimiento.html", encoding="utf-8") as archivo:
            plantilla = archivo.read()

        # Mostramos la página con el usuario conectado.
        return render_template_string(
            plantilla
        )

    except Exception as error:
        # Informamos el error en la consola para facilitar su revisión.
        print(f"Error al cargar la base de conocimientos: {error}")

        return "No fue posible cargar la base de conocimientos.", 500

@app.route("/dashboard", methods=["GET"])
@requiere_login
def mostrar_dashboard():

    conexion = None
    cursor = None

    # Inicializamos los datos que utilizará el Dashboard.
    resumen = {
        "tickets_activos": 0,
        "sla_criticos": 0,
        "tecnicos_activos": 0,
        "vip_activos": 0
    }

    tickets = []
    casos_asignados = []
    tecnicos = []

    try:
        # Conectamos con la base de datos principal.
        conexion = conectar_principal()
        cursor = conexion.cursor(dictionary=True, buffered=True)

        # Consultamos los días festivos registrados.
        festivos = obtener_festivos(cursor)

        # Obtenemos la fecha y hora actual.
        ahora = datetime.now()

        # Consultamos todos los casos que no estén completados.
        cursor.execute("""
            SELECT
                codigo_caso,
                prioridad,
                estado,
                fecha_vencimiento
            FROM casos
            WHERE estado <> 'Completado'
            ORDER BY
                fecha_vencimiento IS NULL ASC,
                fecha_vencimiento ASC
        """)

        casos = cursor.fetchall()

        # Contamos los tickets activos.
        resumen["tickets_activos"] = len(casos)

        # Calculamos el SLA restante de cada caso.
        for caso in casos:

            fecha_vencimiento = caso["fecha_vencimiento"]

            if caso["estado"] == "Vencido":
                caso["sla_restante"] = "Vencido"
                resumen["sla_criticos"] += 1

            elif fecha_vencimiento is None:
                caso["sla_restante"] = "Sin fecha"

            else:
                minutos = calcular_minutos_habiles(
                    ahora,
                    fecha_vencimiento,
                    festivos
                )

                # Los casos con una hora o menos son críticos.
                if minutos <= 60:
                    resumen["sla_criticos"] += 1

                if fecha_vencimiento <= ahora:
                    caso["sla_restante"] = "Vencido"

                elif minutos < 60:
                    caso["sla_restante"] = f"{minutos} min"

                else:
                    horas = minutos // 60
                    minutos_restantes = minutos % 60

                    if minutos_restantes:
                        caso["sla_restante"] = (
                            f"{horas} h {minutos_restantes} min"
                        )
                    else:
                        caso["sla_restante"] = f"{horas} horas"

        # Mostramos los tres tickets más próximos a vencer.
        tickets = casos[:3]

        # Consultamos los casos asignados y el técnico responsable.
        cursor.execute("""
            SELECT
                c.codigo_caso,
                c.estado,
                c.fecha_vencimiento,
                t.nombre AS tecnico
            FROM casos c
            INNER JOIN asignaciones a
                ON c.codigo_caso = a.codigo_caso
            INNER JOIN tecnicos t
                ON a.id_tecnico = t.id_tecnico
            WHERE c.estado <> 'Completado'
            ORDER BY
                c.fecha_vencimiento IS NULL ASC,
                c.fecha_vencimiento ASC
        """)

        casos_asignados = cursor.fetchall()

        # Calculamos el tiempo restante de cada caso asignado.
        for caso in casos_asignados:

            fecha_vencimiento = caso["fecha_vencimiento"]

            if caso["estado"] == "Vencido":
                caso["tiempo_restante"] = "Vencido"

            elif fecha_vencimiento is None:
                caso["tiempo_restante"] = "Sin fecha"

            elif fecha_vencimiento <= ahora:
                caso["tiempo_restante"] = "Vencido"

            else:
                minutos = calcular_minutos_habiles(
                    ahora,
                    fecha_vencimiento,
                    festivos
                )

                # Convertimos los minutos a horas y minutos.
                if minutos < 60:
                    caso["tiempo_restante"] = f"{minutos} min"

                else:
                    horas = minutos // 60
                    minutos_restantes = minutos % 60

                    if minutos_restantes:
                        caso["tiempo_restante"] = (
                            f"{horas} h {minutos_restantes} min"
                        )
                    else:
                        caso["tiempo_restante"] = f"{horas} horas"

        # Consultamos los técnicos activos y los VIP activos.
        cursor.execute("""
            SELECT
                COUNT(*) AS tecnicos_activos,
                COALESCE(SUM(es_vip = TRUE), 0) AS vip_activos
            FROM tecnicos
            WHERE activo = TRUE
        """)

        resultado_tecnicos = cursor.fetchone()

        resumen["tecnicos_activos"] = resultado_tecnicos["tecnicos_activos"]
        resumen["vip_activos"] = resultado_tecnicos["vip_activos"]

        # Consultamos la carga laboral de cada técnico activo.
        cursor.execute("""
            SELECT
                t.id_tecnico,
                t.nombre,
                COUNT(c.codigo_caso) AS carga_laboral
            FROM tecnicos t
            LEFT JOIN asignaciones a
                ON t.id_tecnico = a.id_tecnico
            LEFT JOIN casos c
                ON a.codigo_caso = c.codigo_caso
                AND c.estado <> 'Completado'
            WHERE t.activo = TRUE
            GROUP BY
                t.id_tecnico,
                t.nombre
            ORDER BY t.nombre ASC
        """)

        tecnicos = cursor.fetchall()

        # Cargamos la plantilla del Dashboard.
        with open(
            f"{app.root_path}/dashboard.html",
            encoding="utf-8"
        ) as archivo:
            plantilla = archivo.read()

        return render_template_string(
            plantilla,
            resumen=resumen,
            tickets=tickets,
            tecnicos=tecnicos,
            casos_asignados=casos_asignados,
            error_consulta=None
        )

    except Exception as error:
        # Mostramos el error completo en la consola para identificar el problema.
        import traceback

        print("Error al cargar el Dashboard:")
        traceback.print_exc()

        try:
            with open(
                f"{app.root_path}/dashboard.html",
                encoding="utf-8"
            ) as archivo:
                plantilla = archivo.read()

            return render_template_string(
                plantilla,
                resumen=resumen,
                tickets=[],
                tecnicos=[],
                casos_asignados=[],
                error_consulta="No fue posible cargar la información del Dashboard."
            )

        except Exception as error_plantilla:
            print(f"Error al cargar la plantilla: {error_plantilla}")
            return "No fue posible cargar el Dashboard.", 500

    finally:
        # Cerramos los recursos de la base de datos.
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()

            
@app.route("/tecnicos", methods=["GET"])
@requiere_login
def mostrar_tecnicos():

    conexion = None
    cursor = None

    # Inicializamos las variables que utilizará la página.
    tecnicos = []
    resumen = {
        "total": 0,
        "activos": 0,
        "inactivos": 0,
        "vip": 0,
        "estandar": 0
    }

    try:
        # Conectamos con la base de datos principal.
        conexion = conectar_principal()

        # Creamos un cursor que devuelve los resultados como diccionarios.
        cursor = conexion.cursor(dictionary=True, buffered=True)

        # Consultamos los técnicos y su carga laboral actual.
        cursor.execute("""
            SELECT
                t.id_tecnico,
                t.nombre,
                t.es_vip,
                t.activo,
                t.id_sede,
                s.nombre_sede,
                COUNT(c.codigo_caso) AS carga_laboral
            FROM tecnicos t
            INNER JOIN sedes s
                ON t.id_sede = s.id_sede
            LEFT JOIN asignaciones a
                ON t.id_tecnico = a.id_tecnico
            LEFT JOIN casos c
                ON a.codigo_caso = c.codigo_caso
                AND c.estado <> 'Completado'
            GROUP BY
                t.id_tecnico,
                t.nombre,
                t.es_vip,
                t.activo,
                t.id_sede,
                s.nombre_sede
            ORDER BY t.nombre ASC
        """)

        # Recuperamos todos los técnicos.
        tecnicos = cursor.fetchall()

        # Consultamos todas las sedes registradas en la base de datos.
        cursor.execute("""
            SELECT id_sede, nombre_sede
            FROM sedes
            ORDER BY nombre_sede ASC
        """)

        sedes = cursor.fetchall()

        # Calculamos los indicadores generales.
        resumen["total"] = len(tecnicos)
        resumen["activos"] = sum(bool(t["activo"]) for t in tecnicos)
        resumen["inactivos"] = sum(not bool(t["activo"]) for t in tecnicos)
        resumen["vip"] = sum(bool(t["es_vip"]) for t in tecnicos)
        resumen["estandar"] = sum(not bool(t["es_vip"]) for t in tecnicos)

        # Cargamos la plantilla de técnicos.
        with open(f"{app.root_path}/tecnicos.html", encoding="utf-8") as archivo:
            plantilla = archivo.read()

        # Mostramos la página con la información consultada.
        return render_template_string(
            plantilla,
            tecnicos=tecnicos,
            sedes=sedes,
            resumen=resumen,
            error_consulta=None
        )

    except Exception as error:
        # Mostramos el error en la consola para facilitar su revisión.
        print(f"Error al consultar la información de técnicos: {error}")

        # Informamos el problema en la página.
        try:
            with open(f"{app.root_path}/tecnicos.html", encoding="utf-8") as archivo:
                plantilla = archivo.read()

            return render_template_string(
                plantilla,
                tecnicos=[],
                sedes=[],
                resumen=resumen,
                error_consulta="No fue posible cargar la información de los técnicos."
            )

        except Exception as error_plantilla:
            print(f"Error al cargar la plantilla de técnicos: {error_plantilla}")
            return "No fue posible cargar la página de técnicos.", 500

    finally:
        # Cerramos los recursos de la base de datos.
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


@app.route("/eliminar-caso-asignacion", methods=["POST"])
def eliminar_caso_asignacion():

    # Recuperamos el código del caso enviado desde el formulario.
    codigo_caso = request.form.get("codigo_caso", "").strip()

    conexion = None
    cursor = None

    try:

        # Comprobamos que se haya recibido un código.
        if not codigo_caso:
            raise ValueError("No se recibió el código del caso que se desea eliminar.")

        # Conectamos con la base de datos principal.
        conexion = conectar_principal()

        # Creamos un cursor para ejecutar las consultas.
        cursor = conexion.cursor()

        # Eliminamos únicamente casos activos que no tengan asignación.
        cursor.execute("""
            DELETE FROM casos
            WHERE codigo_caso = %s
              AND estado = 'Activo'
              AND NOT EXISTS (
                  SELECT 1
                  FROM asignaciones
                  WHERE asignaciones.codigo_caso = casos.codigo_caso
              )
        """, (codigo_caso,))

        # Comprobamos si se eliminó exactamente un registro.
        if cursor.rowcount == 0:

            # Consultamos si el caso todavía existe.
            cursor.execute("""
                SELECT codigo_caso
                FROM casos
                WHERE codigo_caso = %s
            """, (codigo_caso,))

            caso_existente = cursor.fetchone()

            if caso_existente:
                raise ValueError(
                    "El caso no se puede eliminar porque ya no está disponible para eliminación."
                )

            raise ValueError("El caso que intentas eliminar no existe.")

        # Confirmamos la eliminación en la base de datos.
        conexion.commit()

        # Regresamos a la página con el mensaje de éxito.
        return redirect(url_for(
            "mostrar_asignacion",
            mensaje=f"El caso {codigo_caso} fue eliminado correctamente."
        ))

    except ValueError as error:

        # Informamos los errores relacionados con la eliminación.
        return redirect(url_for(
            "mostrar_asignacion",
            error=str(error)
        ))

    except Exception as error:

        # Revertimos los cambios si ocurre un error.
        if conexion is not None and conexion.is_connected():
            conexion.rollback()

        # Registramos el error para facilitar su revisión.
        print(f"Error al eliminar el caso {codigo_caso}: {error}")

        return redirect(url_for(
            "mostrar_asignacion",
            error="No fue posible eliminar el caso. Revisa la información e intenta nuevamente."
        ))

    finally:

        # Cerramos el cursor y la conexión.
        if cursor is not None:
            cursor.close()

        if conexion is not None and conexion.is_connected():
            conexion.close()


@app.route("/asignar-recomendado", methods=["POST"])
def asignar_recomendado():

    # Recuperamos el código del caso y el técnico enviado desde el formulario.
    codigo_caso = request.form.get("codigo_caso", "").strip()
    id_tecnico = request.form.get("id_tecnico", "").strip()

    # Recuperamos las recomendaciones guardadas durante la búsqueda.
    codigo_recomendaciones = session.get("codigo_recomendaciones")
    recomendaciones = session.get("recomendaciones", [])

    # Comprobamos que exista una recomendación para el caso seleccionado.
    if (
        not codigo_caso
        or codigo_caso != codigo_recomendaciones
        or not recomendaciones
    ):
        return redirect(url_for(
            "mostrar_asignacion",
            codigo=codigo_caso,
            error="No hay una recomendación válida para este caso."
        ))

    # Recuperamos el primer técnico del ranking.
    tecnico_recomendado = recomendaciones[0]

    # Comprobamos que el técnico enviado sea realmente el recomendado.
    if str(tecnico_recomendado["id_tecnico"]) != id_tecnico:
        return redirect(url_for(
            "mostrar_asignacion",
            codigo=codigo_caso,
            error="El técnico seleccionado no coincide con la recomendación."
        ))

    # Registramos la asignación utilizando la función existente.
    exito, mensaje = registrar_asignacion(
        codigo_caso,
        tecnico_recomendado["id_sede"],
        tecnico_recomendado["id_tecnico"]
    )

    # Si la asignación fue exitosa, eliminamos el ranking anterior.
    if exito:
        session.pop("recomendaciones", None)
        session.pop("codigo_recomendaciones", None)

    # Regresamos a la página mostrando el resultado de la operación.
    if exito:
        return redirect(url_for(
            "mostrar_asignacion",
            mensaje=mensaje
        ))

    return redirect(url_for(
        "mostrar_asignacion",
        codigo=codigo_caso,
        error=mensaje
    ))


@app.route("/buscar-tecnico", methods=["POST"])
def buscar_tecnico():

    # Recuperamos el código del caso enviado desde el formulario.
    codigo_caso = request.form.get("codigo_caso", "").strip()

    # Comprobamos que se haya seleccionado un caso.
    if not codigo_caso:
        return redirect(url_for(
            "mostrar_asignacion",
            error="Primero debes seleccionar un caso."
        ))

    # Ejecutamos el algoritmo para obtener las recomendaciones.
    resultado = recomendar_tecnicos(codigo_caso)

    # Si el algoritmo no pudo generar recomendaciones, mostramos el error.
    if not resultado["exito"]:

        # Eliminamos cualquier ranking anterior.
        session.pop("recomendaciones", None)
        session.pop("codigo_recomendaciones", None)

        return redirect(url_for(
            "mostrar_asignacion",
            codigo=codigo_caso,
            error=resultado["mensaje"]
        ))

    # Guardamos las recomendaciones y el código del caso en la sesión.
    session["recomendaciones"] = resultado["recomendaciones"]
    session["codigo_recomendaciones"] = codigo_caso

    # Mostramos el resultado en la consola para facilitar las pruebas.
    print("RESULTADO DEL ALGORITMO:", resultado)

    # Regresamos a la página conservando el caso seleccionado.
    return redirect(url_for(
        "mostrar_asignacion",
        codigo=codigo_caso,
        mensaje=resultado["mensaje"]
    ))

def registrar_asignacion(codigo_caso, id_sede, id_tecnico):

    conexion = None
    cursor = None

    try:
        # Conectamos con la base de datos principal.
        conexion = conectar_principal()

        # Iniciamos una transacción para proteger la asignación.
        conexion.start_transaction()

        # Creamos un cursor con resultados almacenados en búfer.
        cursor = conexion.cursor(dictionary=True, buffered=True)

        # Comprobamos que el caso exista y continúe activo.
        cursor.execute("""
            SELECT estado
            FROM casos
            WHERE codigo_caso = %s
            FOR UPDATE
        """, (codigo_caso,))

        caso = cursor.fetchone()

        if not caso or caso["estado"] != "Activo":
            conexion.rollback()
            return False, "El caso no existe o ya no está pendiente de asignación."

        # Comprobamos que el técnico exista, esté activo y pertenezca a la sede indicada.
        cursor.execute("""
            SELECT id_sede, activo
            FROM tecnicos
            WHERE id_tecnico = %s
            FOR UPDATE
        """, (id_tecnico,))

        tecnico = cursor.fetchone()

        if (
            not tecnico
            or not bool(tecnico["activo"])
            or tecnico["id_sede"] != id_sede
        ):
            conexion.rollback()
            return False, "El técnico seleccionado no está disponible para esa sede."

        # Registramos la asignación del caso al técnico.
        cursor.execute("""
            INSERT INTO asignaciones (
                codigo_caso,
                id_tecnico
            )
            VALUES (%s, %s)
        """, (codigo_caso, id_tecnico))

        # Actualizamos el estado del caso.
        cursor.execute("""
            UPDATE casos
            SET estado = 'Asignado'
            WHERE codigo_caso = %s
              AND estado = 'Activo'
        """, (codigo_caso,))

        # Comprobamos que el estado se haya actualizado correctamente.
        if cursor.rowcount != 1:
            raise Exception("No fue posible actualizar el estado del caso.")

        # Confirmamos los cambios en la base de datos.
        conexion.commit()

        return True, "¡El técnico fue asignado correctamente al caso!"

    except Exception as error:
        # Deshacemos los cambios si ocurre algún problema.
        if conexion:
            conexion.rollback()

        print(f"Error al registrar la asignación: {error}")

        return False, "No fue posible completar la asignación. Inténtalo nuevamente."

    finally:
        # Cerramos el cursor y la conexión.
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()
        
@app.route("/agregar-caso-manual", methods=["POST"])  
def agregar_caso_manual():

    # Recuperamos los datos enviados desde el formulario.
    codigo_caso = request.form.get("codigo_caso", "").strip()
    descripcion = request.form.get("descripcion", "").strip()
    prioridad = request.form.get("prioridad", "").strip()
    nombre_sede = request.form.get("nombre_sede", "").strip()
    es_vip_texto = request.form.get("es_vip", "").strip()
    fecha_apertura_texto = request.form.get("fecha_apertura", "").strip()

    conexion = None
    cursor = None

    try:

        # Comprobamos que todos los campos obligatorios tengan información.
        if not all([
            codigo_caso,
            descripcion,
            prioridad,
            nombre_sede,
            es_vip_texto,
            fecha_apertura_texto
        ]):
            raise ValueError("Todos los campos son obligatorios.")

        # Validamos que la prioridad corresponda a una opción permitida.
        if prioridad not in ("Alta", "Media", "Baja"):
            raise ValueError("La prioridad seleccionada no es válida.")

        # Validamos que el valor VIP sea 0 o 1.
        if es_vip_texto not in ("0", "1"):
            raise ValueError("La selección VIP no es válida.")

        es_vip = bool(int(es_vip_texto))

        # Convertimos la fecha recibida desde el formulario.
        fecha_apertura = datetime.strptime(
            fecha_apertura_texto,
            "%Y-%m-%dT%H:%M"
        )

        # Conectamos con la base de datos principal.
        conexion = conectar_principal()
        cursor = conexion.cursor()

        # Comprobamos que el código no esté registrado previamente.
        cursor.execute("""
            SELECT codigo_caso
            FROM casos
            WHERE codigo_caso = %s
        """, (codigo_caso,))

        if cursor.fetchone():
            raise ValueError("Ya existe un caso registrado con ese código.")

        # Comprobamos que la sede seleccionada exista.
        cursor.execute("""
            SELECT id_sede
            FROM sedes
            WHERE nombre_sede = %s
        """, (nombre_sede,))

        if not cursor.fetchone():
            raise ValueError("La sede seleccionada no existe.")

        # Recuperamos los festivos de la base de datos principal.
        festivos = obtener_festivos(cursor)

        # Adaptamos la fecha al formato utilizado por las funciones existentes.
        fecha_para_calculo = fecha_apertura.strftime("%d/%m/%y %H:%M:%S")

        # Calculamos el inicio de gestión del caso.
        fecha_inicio, observacion = calcular_fecha_inicio_gestion(
            fecha_para_calculo,
            festivos
        )

        # Calculamos el vencimiento acumulando 8 horas hábiles.
        fecha_vencimiento = calcular_fecha_vencimiento(
            fecha_inicio,
            festivos
        )

        # Insertamos el nuevo caso en la base de datos principal.
        cursor.execute("""
            INSERT INTO casos (
                codigo_caso,
                estado,
                descripcion,
                prioridad,
                fecha_apertura,
                fecha_inicio_gestion,
                fecha_vencimiento,
                es_vip,
                nombre_sede,
                observaciones
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            codigo_caso,
            "Activo",
            descripcion,
            prioridad,
            fecha_apertura,
            fecha_inicio,
            fecha_vencimiento,
            es_vip,
            nombre_sede,
            observacion
        ))

        # Confirmamos el registro en la base de datos.
        conexion.commit()

        # Regresamos a la página con el mensaje de éxito.
        return redirect(url_for(
            "mostrar_asignacion",
            mensaje="El caso fue registrado correctamente."
        ))

    except ValueError as error:

        # Informamos los errores de validación al usuario.
        return redirect(url_for(
            "mostrar_asignacion",
            error=str(error)
        ))

    except Exception as error:

        # Revertimos los cambios si ocurre un error durante el registro.
        if conexion is not None and conexion.is_connected():
            conexion.rollback()

        print(f"Error al registrar el caso manualmente: {error}")

        return redirect(url_for(
            "mostrar_asignacion",
            error="No fue posible registrar el caso. Revisa los datos e intenta nuevamente."
        ))

    finally:

        # Cerramos el cursor y la conexión.
        if cursor is not None:
            cursor.close()

        if conexion is not None and conexion.is_connected():
            conexion.close()


@app.route("/actualizar-caso-manual", methods=["POST"])
def actualizar_caso_manual():

    # Recuperamos el código original y los nuevos datos del formulario.
    codigo_original = request.form.get("codigo_original", "").strip()
    codigo_caso = request.form.get("codigo_caso", "").strip()
    descripcion = request.form.get("descripcion", "").strip()
    prioridad = request.form.get("prioridad", "").strip()
    nombre_sede = request.form.get("nombre_sede", "").strip()
    es_vip_texto = request.form.get("es_vip", "").strip()
    fecha_apertura_texto = request.form.get("fecha_apertura", "").strip()

    conexion = None
    cursor = None

    try:

        # Comprobamos que todos los campos obligatorios tengan información.
        if not all([
            codigo_original,
            codigo_caso,
            descripcion,
            prioridad,
            nombre_sede,
            es_vip_texto,
            fecha_apertura_texto
        ]):
            raise ValueError("Todos los campos son obligatorios.")

        # Validamos que la prioridad corresponda a una opción permitida.
        if prioridad not in ("Alta", "Media", "Baja"):
            raise ValueError("La prioridad seleccionada no es válida.")

        # Validamos que el valor VIP sea 0 o 1.
        if es_vip_texto not in ("0", "1"):
            raise ValueError("La selección VIP no es válida.")

        es_vip = bool(int(es_vip_texto))

        # Convertimos la fecha recibida desde el formulario.
        fecha_apertura = datetime.strptime(
            fecha_apertura_texto,
            "%Y-%m-%dT%H:%M"
        )

        # Conectamos con la base de datos principal.
        conexion = conectar_principal()
        cursor = conexion.cursor()

        # Comprobamos que el caso original todavía exista.
        cursor.execute("""
            SELECT codigo_caso
            FROM casos
            WHERE codigo_caso = %s
              AND estado = 'Activo'
        """, (codigo_original,))

        if not cursor.fetchone():
            raise ValueError("El caso que intentas editar ya no existe o no está activo.")

        # Comprobamos que el nuevo código no pertenezca a otro caso.
        cursor.execute("""
            SELECT codigo_caso
            FROM casos
            WHERE codigo_caso = %s
              AND codigo_caso <> %s
        """, (codigo_caso, codigo_original))

        if cursor.fetchone():
            raise ValueError("Ya existe otro caso registrado con ese código.")

        # Comprobamos que la sede seleccionada exista.
        cursor.execute("""
            SELECT id_sede
            FROM sedes
            WHERE nombre_sede = %s
        """, (nombre_sede,))

        if not cursor.fetchone():
            raise ValueError("La sede seleccionada no existe.")

        # Recuperamos los festivos de la base de datos principal.
        festivos = obtener_festivos(cursor)

        # Adaptamos la fecha al formato utilizado por las funciones existentes.
        fecha_para_calculo = fecha_apertura.strftime("%d/%m/%y %H:%M:%S")

        # Recalculamos el inicio de gestión.
        fecha_inicio, observacion = calcular_fecha_inicio_gestion(
            fecha_para_calculo,
            festivos
        )

        # Recalculamos el vencimiento acumulando 8 horas hábiles.
        fecha_vencimiento = calcular_fecha_vencimiento(
            fecha_inicio,
            festivos
        )

        # Actualizamos los datos del caso identificado por su código original.
        cursor.execute("""
            UPDATE casos
            SET
                codigo_caso = %s,
                descripcion = %s,
                prioridad = %s,
                nombre_sede = %s,
                es_vip = %s,
                fecha_apertura = %s,
                fecha_inicio_gestion = %s,
                fecha_vencimiento = %s,
                observaciones = %s
            WHERE codigo_caso = %s
              AND estado = 'Activo'
        """, (
            codigo_caso,
            descripcion,
            prioridad,
            nombre_sede,
            es_vip,
            fecha_apertura,
            fecha_inicio,
            fecha_vencimiento,
            observacion,
            codigo_original
        ))

        # Confirmamos los cambios en la base de datos.
        conexion.commit()

        return redirect(url_for(
            "mostrar_asignacion",
            mensaje="El caso fue actualizado correctamente."
        ))

    except ValueError as error:

        # Informamos los errores de validación al usuario.
        return redirect(url_for(
            "mostrar_asignacion",
            error=str(error)
        ))

    except Exception as error:

        # Revertimos los cambios si ocurre un error durante la actualización.
        if conexion is not None and conexion.is_connected():
            conexion.rollback()

        print(f"Error al actualizar el caso: {error}")

        return redirect(url_for(
            "mostrar_asignacion",
            error="No fue posible actualizar el caso. Revisa los datos e intenta nuevamente."
        ))

    finally:

        # Cerramos el cursor y la conexión.
        if cursor is not None:
            cursor.close()

        if conexion is not None and conexion.is_connected():
            conexion.close()

@app.route("/asignar-manual", methods=["POST"])
def asignar_manual():

    # Recuperamos los datos enviados desde el formulario.
    codigo_caso = request.form.get("codigo_caso", "").strip()
    id_sede = request.form.get("id_sede", "").strip()
    id_tecnico = request.form.get("id_tecnico", "").strip()

    # Validamos que todos los campos tengan información.
    if not codigo_caso or not id_sede or not id_tecnico:
        return redirect(url_for(
            "mostrar_asignacion",
            codigo=codigo_caso,
            error="Faltan datos para realizar la asignación."
        ))

    # Validamos que los identificadores sean números enteros.
    try:
        id_sede = int(id_sede)
        id_tecnico = int(id_tecnico)

    except ValueError:
        return redirect(url_for(
            "mostrar_asignacion",
            codigo=codigo_caso,
            error="La sede o el técnico seleccionado no son válidos."
        ))

    # Ejecutamos la función auxiliar para registrar la asignación.
    exito, mensaje = registrar_asignacion(
        codigo_caso,
        id_sede,
        id_tecnico
    )

    # Regresamos a la página con el resultado de la operación.
    if exito:
        return redirect(url_for(
            "mostrar_asignacion",
            mensaje=mensaje
        ))

    return redirect(url_for(
        "mostrar_asignacion",
        codigo=codigo_caso,
        error=mensaje
    ))


# ==================================================
# FUNCIÓN: RECIBIR Y ALMACENAR ARCHIVO CSV
# ==================================================


@app.route("/cargar-csv", methods=["POST"])
def cargar_csv():

    # Comprobamos que la solicitud contenga un archivo.
    if "archivo" not in request.files:
        session["mensaje_carga"] = "No se recibió ningún archivo."
        session["detalle_carga"] = ""
        session["mostrar_resultados_carga"] = True
        return redirect(url_for("mostrar_asignacion"))

    # Obtenemos el archivo enviado desde HTML.
    archivo = request.files["archivo"]

    # Comprobamos que se haya seleccionado un archivo.
    if archivo.filename == "":
        session["mensaje_carga"] = "No se seleccionó ningún archivo."
        session["detalle_carga"] = ""
        session["mostrar_resultados_carga"] = True
        return redirect(url_for("mostrar_asignacion"))

    # Comprobamos que el archivo tenga extensión CSV.
    if not archivo.filename.lower().endswith(".csv"):
        session["mensaje_carga"] = "El archivo debe tener formato CSV."
        session["detalle_carga"] = ""
        session["mostrar_resultados_carga"] = True
        return redirect(url_for("mostrar_asignacion"))

    try:

        # Leemos y validamos los registros del archivo CSV.
        registros = leer_csv(archivo)

        # Almacenamos los registros validados en la base de datos temporal.
        cantidad_almacenada = almacenar_casos(registros)

        # Guardamos los identificadores de los registros de esta carga.
        session["codigos_carga"] = cantidad_almacenada["codigos_validos"]
        session["ids_invalidos_carga"] = cantidad_almacenada["ids_invalidos"]

        # Comprobamos qué identificadores quedaron asociados a la carga.
        print("CÓDIGOS DE LA ÚLTIMA CARGA:", session["codigos_carga"])
        print("IDS DE REGISTROS INVÁLIDOS:", session["ids_invalidos_carga"])

        # Informamos que el almacenamiento temporal fue exitoso.
        mensaje = (
            "Archivo procesado y almacenado correctamente en la base temporal."
        )

        # Calculamos el total de registros leídos del archivo CSV.
        total_leidos = len(registros["validos"]) + len(registros["invalidos"])

        # Obtenemos las cantidades de registros almacenados en cada categoría.
        total_validos = cantidad_almacenada["validos"]
        total_invalidos = cantidad_almacenada["invalidos"]

        # Construimos el resumen de los resultados del almacenamiento.
        detalle = (
            f"Registros leídos: {total_leidos}. "
            f"Registros válidos almacenados: {total_validos}. "
            f"Registros inválidos almacenados: {total_invalidos}."
        )

        # Guardamos el resumen para mostrarlo dentro del modal.
        session["mensaje_carga"] = mensaje
        session["detalle_carga"] = detalle
        session["mostrar_resultados_carga"] = True

        # Regresamos a la pantalla de asignación con el modal abierto.
        return redirect(url_for("mostrar_asignacion"))

    except Exception as error:

        # Conservamos el error técnico en la terminal para diagnóstico.
        print(f"ERROR AL PROCESAR EL ARCHIVO: {error}")

        # Identificamos si el problema corresponde a códigos duplicados.
        if "1062" in str(error) or "Duplicate entry" in str(error):

            # Informamos que existen casos repetidos en la base temporal.
            mensaje = (
                "No se pudo completar la carga. "
                "Uno o más casos ya existen en la base de datos temporal. "
                "Puedes revisar los registros o limpiar el cargue "
                "antes de volver a intentarlo."
            )

        else:

            # Informamos que ocurrió otro problema durante el procesamiento.
            mensaje = (
                "No fue posible procesar el archivo. "
                "Verifica la información e intenta nuevamente."
            )

        # Guardamos el error para mostrarlo dentro del modal.
        session["mensaje_carga"] = mensaje
        session["detalle_carga"] = ""
        session["mostrar_resultados_carga"] = True

        # Regresamos a asignación sin abandonar el modal.
        return redirect(url_for("mostrar_asignacion"))

# ==================================================
# FUNCIÓN: CONSULTAR CASOS PENDIENTES DE TRANSFERENCIA
# ==================================================

@app.route("/confirmar-transferencia")
def confirmar_transferencia():

    conexion = conectar_temporal()
    cursor = None

    try:
        cursor = conexion.cursor()

        # Consultamos la cantidad de casos válidos disponibles.
        cursor.execute("SELECT COUNT(*) FROM casos")
        cantidad = cursor.fetchone()[0]

        # Consultamos la cantidad de registros inválidos pendientes.
        cursor.execute("SELECT COUNT(*) FROM registros_invalidos")
        cantidad_invalidos = cursor.fetchone()[0]

        # Consultamos los casos que todavía no tienen una sede seleccionada.
        cursor.execute("""
            SELECT codigo_caso
            FROM casos
            WHERE nombre_sede IS NULL
               OR TRIM(nombre_sede) = ''
        """)

        # Recuperamos los códigos de los casos sin sede.
        casos_sin_sede = [
            registro[0]
            for registro in cursor.fetchall()
        ]

        # Mostramos la confirmación con los resultados de ambas consultas.
        return render_template_string(
            PLANTILLA_CONFIRMACION,
            cantidad=cantidad,
            cantidad_invalidos=cantidad_invalidos,
            casos_sin_sede=casos_sin_sede
        )

    except Exception as error:
        return mostrar_resultado(
            "No fue posible consultar los registros.",
            detalle=str(error)
        )

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()

# ==================================================
# FUNCIÓN: TRANSFERIR CASOS A LA BD PRINCIPAL
# ==================================================


@app.route("/transferir-casos", methods=["POST"])
def transferir():

    try:

        # Ejecutamos la función encargada de transferir los casos.
        resultado = transferir_casos()

        # Guardamos el resumen de la transferencia en la sesión.
        session["resultado_transferencia"] = {
            "insertados": resultado["insertados"],
            "eliminados": resultado["eliminados_temporal"],
            "duplicados": len(resultado["duplicados"]),
            "limpieza_exitosa": resultado["limpieza_temporal_exitosa"],
            "error_limpieza": resultado["error_limpieza"]
        }

        # Volvemos a abrir el modal para mostrar los casos que permanecen temporalmente.
        session["mostrar_resultados_carga"] = True
        session["abrir_modal_carga"] = True

        # Preparamos un mensaje para informar el resultado de la transferencia.
        session["mensaje_carga"] = "Transferencia finalizada."

        session["detalle_carga"] = (
            f"Casos enviados: {resultado['insertados']} | "
            f"Duplicados que permanecen para revisión: {len(resultado['duplicados'])}."
        )

        # Regresamos a la página de asignación para mostrar el resultado.
        return redirect(url_for("mostrar_asignacion"))

    except Exception as e:

        # Conservamos el mensaje de error de la transferencia.
        session["error_transferencia"] = (
            "No fue posible completar la transferencia. "
            "Verifica que todos los casos tengan una sede seleccionada "
            "y vuelve a intentarlo."
        )

        # Mantenemos visible el modal con los resultados de la carga.
        session["mostrar_resultados_carga"] = True
        session["abrir_modal_carga"] = True

        return redirect(url_for("mostrar_asignacion"))

@app.route("/actualizar-caso", methods=["POST"])
def guardar_caso():
    """
    Recibe los cambios de un caso válido y solicita su actualización.
    Regresa a asignación mostrando nuevamente el modal de carga.
    """

    try:
        # Recuperamos el código original para identificar el caso.
        codigo_original = request.form.get("codigo_original", "").strip()

        # Recuperamos todos los datos modificados desde el formulario.
        datos = {
            "codigo_caso": request.form.get("codigo_caso", "").strip(),
            "estado": request.form.get("estado", "").strip(),
            "descripcion": request.form.get("descripcion", "").strip(),
            "prioridad": request.form.get("prioridad", "").strip(),
            "fecha_apertura": request.form.get("fecha_apertura", "").strip(),
            "es_vip": request.form.get("es_vip", "No").strip(),
            "nombre_sede": request.form.get("nombre_sede", "").strip(),
            "observaciones": request.form.get("observaciones", "").strip()
        }

        # Validamos y guardamos los cambios en la base temporal.
        resultado = actualizar_caso(codigo_original, datos)

        # Recuperamos los errores encontrados, si existen.
        detalle = " ".join(resultado.get("errores", []))

        # Actualizamos el código registrado en la última carga si fue modificado.
        if resultado.get("valido"):
            codigos_carga = session.get("codigos_carga", [])

            if codigo_original in codigos_carga:
                indice = codigos_carga.index(codigo_original)
                codigos_carga[indice] = resultado["codigo_caso"]

            session["codigos_carga"] = codigos_carga

        # Guardamos el resultado para mostrarlo en el modal.
        session["mensaje_carga"] = resultado["mensaje"]
        session["detalle_carga"] = detalle
        session["mostrar_resultados_carga"] = True
        session["abrir_modal_carga"] = True

        # Regresamos a la pantalla de asignación.
        return redirect(url_for("mostrar_asignacion"))

    except Exception as error:

        # Conservamos el error técnico en la terminal.
        print(f"ERROR AL ACTUALIZAR EL CASO: {error}")

        # Informamos el problema dentro del modal.
        session["mensaje_carga"] = "No fue posible actualizar el caso."
        session["detalle_carga"] = ""
        session["mostrar_resultados_carga"] = True
        session["abrir_modal_carga"] = True

        return redirect(url_for("mostrar_asignacion"))


@app.route("/actualizar-casos", methods=["POST"])
def actualizar_casos_multiples():

    # Inicializamos las listas del resultado.
    actualizados = []
    pendientes = []

    try:
        # Recuperamos todos los registros enviados desde la tabla.
        registros = json.loads(request.form.get("registros", "[]"))
        # Mostramos cuántos registros llegaron desde el formulario.
        print("TOTAL DE REGISTROS RECIBIDOS:", len(registros))
        print("DATOS RECIBIDOS:", registros)
        # Procesamos cada registro individualmente.
        for registro in registros:

            codigo_original = registro.get("codigo_original", "").strip()

            datos = {
                "codigo_caso": registro.get("codigo_caso", "").strip(),
                "estado": registro.get("estado", "").strip(),
                "descripcion": registro.get("descripcion", "").strip(),
                "prioridad": registro.get("prioridad", "").strip(),
                "fecha_apertura": registro.get("fecha_apertura", "").strip(),
                "es_vip": registro.get("es_vip", "No").strip(),
                "nombre_sede": registro.get("nombre_sede", "").strip(),
                "observaciones": registro.get("observaciones", "").strip()
            }

            # Reutilizamos la validación y actualización individual.
            resultado = actualizar_caso(codigo_original, datos)
            # Mostramos el resultado de la validación de cada registro.
            print("RESULTADO DE ACTUALIZACIÓN:", codigo_original, resultado)

            if resultado.get("valido"):

                codigo_nuevo = resultado["codigo_caso"]

                # Actualizamos el identificador de la última carga.
                codigos_carga = session.get("codigos_carga", [])

                if codigo_original in codigos_carga:
                    indice = codigos_carga.index(codigo_original)
                    codigos_carga[indice] = codigo_nuevo
                    session["codigos_carga"] = codigos_carga

                actualizados.append(codigo_nuevo)

            else:
                # Conservamos los errores para mostrarlos al usuario.
                pendientes.append({
                    "codigo": codigo_original,
                    "errores": resultado.get("errores", [])
                })

        # Construimos el resumen de la operación.
        partes = [
            f"Registros actualizados: {len(actualizados)}.",
            f"Registros pendientes de corrección: {len(pendientes)}."
        ]

        if actualizados:
            partes.append(
                "Actualizados: " + ", ".join(actualizados)
            )

        if pendientes:
            partes.append(
                "Pendientes: " + "; ".join(
                    f"{registro['codigo']}: {', '.join(registro['errores'])}"
                    for registro in pendientes
                )
            )

        # Guardamos el resumen para mostrarlo en el modal.
        session["mensaje_carga"] = "Procesamiento de cambios finalizado."
        session["detalle_carga"] = " ".join(partes)
        session["mostrar_resultados_carga"] = True
        session["abrir_modal_carga"] = True

        return redirect(url_for("mostrar_asignacion"))

    except Exception as error:

        # Conservamos el error técnico para facilitar su revisión.
        print(f"ERROR AL ACTUALIZAR LOS CASOS: {error}")

        session["mensaje_carga"] = "No fue posible actualizar todos los registros."
        session["detalle_carga"] = ""
        session["mostrar_resultados_carga"] = True
        session["abrir_modal_carga"] = True

        return redirect(url_for("mostrar_asignacion"))

# ==================================================
# FUNCIÓN: ACTUALIZAR TODOS LOS CASOS CORRECTOS
# ==================================================

@app.route("/actualizar-todos-los-casos", methods=["POST"])
def actualizar_todos_los_casos():

    # Preparamos las listas para resumir los resultados.
    casos_actualizados = []
    casos_con_errores = []
    datos_pendientes = {}

    try:

        # Recuperamos todos los casos enviados desde la tabla.
        casos = json.loads(request.form.get("casos", "[]"))

        # Comprobamos que la información recibida sea una lista.
        if not isinstance(casos, list):
            raise ValueError("La información recibida no tiene un formato válido.")

        # Procesamos cada caso de manera independiente.
        for caso in casos:

            # Recuperamos el código original para identificar el registro.
            codigo_original = str(
                caso.get("codigo_original", "")
            ).strip()

            # Recuperamos únicamente los campos que pueden modificarse.
            datos = {
                "codigo_caso": caso.get("codigo_caso", ""),
                "estado": caso.get("estado", ""),
                "descripcion": caso.get("descripcion", ""),
                "prioridad": caso.get("prioridad", ""),
                "fecha_apertura": caso.get("fecha_apertura", ""),
                "es_vip": caso.get("es_vip", ""),
                "nombre_sede": caso.get("nombre_sede", ""),
                "observaciones": caso.get("observaciones", "")
            }

            try:

                # Validamos y actualizamos el caso seleccionado.
                resultado = actualizar_caso(codigo_original, datos)

                if resultado.get("valido"):

                    # Registramos los casos que se guardaron correctamente.
                    casos_actualizados.append(
                        resultado.get("codigo_caso", codigo_original)
                    )

                else:

                    # Conservamos los datos para que sigan visibles en el panel.
                    datos_pendientes[codigo_original] = datos

                    # Guardamos el código y los errores encontrados.
                    casos_con_errores.append({
                        "codigo": datos["codigo_caso"] or codigo_original,
                        "errores": resultado.get(
                            "errores",
                            ["No fue posible actualizar este caso."]
                        )
                    })

            except Exception as error:

                # Un error individual no impide procesar los demás casos.
                print(
                    f"ERROR AL ACTUALIZAR EL CASO "
                    f"{codigo_original}: {error}"
                )

                datos_pendientes[codigo_original] = datos

                casos_con_errores.append({
                    "codigo": datos["codigo_caso"] or codigo_original,
                    "errores": [str(error)]
                })

        # Construimos el resumen general de la operación.
        mensaje = (
            f"Proceso terminado. Casos actualizados: "
            f"{len(casos_actualizados)}. "
            f"Casos con errores: {len(casos_con_errores)}."
        )

        # Preparamos el detalle de los registros que necesitan corrección.
        detalle = ""

        for caso in casos_con_errores:
            detalle += (
                f"Caso {caso['codigo']}:\n"
                + "\n".join(caso["errores"])
                + "\n\n"
            )

        # Mostramos nuevamente el panel con los resultados.
        return mostrar_panel(
            datos_pendientes=datos_pendientes,
            mensaje_personalizado=mensaje,
            detalle_personalizado=detalle.strip()
        )

    except Exception as error:

        # Conservamos el error técnico para facilitar su diagnóstico.
        print(f"ERROR EN LA ACTUALIZACIÓN MASIVA: {error}")

        return redirect(url_for(
            "mostrar_panel",
            mensaje="No fue posible procesar la actualización masiva.",
            detalle="Verifica la información enviada e intenta nuevamente."
        ))

@app.route("/corregir-registro-invalido", methods=["POST"])
def guardar_registro_invalido():
    """
    Recibe los cambios de un registro inválido.
    Lo valida y, si es correcto, lo traslada automáticamente a casos.
    Regresa a asignación mostrando nuevamente el modal de carga.
    """

    try:
        # Recuperamos el identificador del registro inválido.
        id_registro = request.form.get("id_registro", type=int)

        # Recuperamos los campos modificados desde el formulario.
        datos = {
            "codigo_caso": request.form.get("codigo_caso", "").strip(),
            "estado": request.form.get("estado", "").strip(),
            "descripcion": request.form.get("descripcion", "").strip(),
            "fecha_prevista": request.form.get("fecha_prevista", "").strip(),
            "prioridad": request.form.get("prioridad", "").strip(),
            "fecha_apertura": request.form.get("fecha_apertura", "").strip(),
            "es_vip": request.form.get("es_vip", "No").strip(),
            "nombre_sede": request.form.get("nombre_sede", "").strip()
        }

        # Recuperamos los campos adicionales conservados del CSV.
        campos_adicionales = json.loads(
            request.form.get("campos_adicionales", "[]")
        )

        # Guardamos, validamos y trasladamos el registro si es correcto.
        resultado = corregir_registro_invalido(
            id_registro,
            datos,
            campos_adicionales
        )

        # Recuperamos los errores encontrados, si existen.
        detalle = " ".join(resultado.get("errores", []))

        # Actualizamos los identificadores si el registro pasó a casos.
        if resultado.get("valido"):

            # Incorporamos el nuevo caso a los registros de la última carga.
            codigos_carga = session.get("codigos_carga", [])
            codigo_nuevo = resultado["codigo_caso"]

            if codigo_nuevo not in codigos_carga:
                codigos_carga.append(codigo_nuevo)

            session["codigos_carga"] = codigos_carga

            # Retiramos el identificador del registro inválido ya trasladado.
            ids_invalidos = session.get("ids_invalidos_carga", [])

            if id_registro in ids_invalidos:
                ids_invalidos.remove(id_registro)

            session["ids_invalidos_carga"] = ids_invalidos

        # Guardamos el resultado para mostrarlo en el modal.
        session["mensaje_carga"] = resultado["mensaje"]
        session["detalle_carga"] = detalle
        session["mostrar_resultados_carga"] = True
        session["abrir_modal_carga"] = True

        return redirect(url_for("mostrar_asignacion"))

    except Exception as error:

        # Conservamos el error técnico en la terminal.
        print(f"ERROR AL CORREGIR EL REGISTRO: {error}")

        # Identificamos si el problema corresponde a un código duplicado.
        if "ya existe" in str(error).lower() or "duplicado" in str(error).lower():

            mensaje = (
                "No se puede trasladar el registro porque ese código "
                "ya existe en los casos correctos."
            )

        else:

            mensaje = "No fue posible corregir el registro."

        # Informamos el problema dentro del modal.
        session["mensaje_carga"] = mensaje
        session["detalle_carga"] = ""
        session["mostrar_resultados_carga"] = True
        session["abrir_modal_carga"] = True

        return redirect(url_for("mostrar_asignacion"))


# ==================================================
# GUARDAR TODOS LOS REGISTROS INVÁLIDOS
# ==================================================

@app.route("/corregir-todos-registros-invalidos", methods=["POST"])
def guardar_todos_registros_invalidos():

    # Recuperamos la lista de registros enviados desde la interfaz.
    registros = request.get_json(silent=True)

    if not isinstance(registros, list):
        return jsonify({
            "exito": False,
            "mensaje": "No se recibió una lista válida de registros."
        }), 400

    resultados = []

    # Recuperamos las listas de seguimiento de la sesión.
    codigos_carga = session.get("codigos_carga", [])
    ids_invalidos_carga = session.get("ids_invalidos_carga", [])

    # Procesamos cada registro de manera independiente.
    for registro in registros:

        try:
            id_registro = int(registro["id_registro"])
            datos = registro["datos"]
            campos_adicionales = registro.get("campos_adicionales", [])

            # Aplicamos la misma corrección y validación del guardado individual.
            resultado = corregir_registro_invalido(
                id_registro,
                datos,
                campos_adicionales
            )

            if resultado["valido"]:

                codigo = datos["codigo_caso"]

                # Registramos el caso que pasó correctamente a válidos.
                if codigo not in codigos_carga:
                    codigos_carga.append(codigo)

                # Retiramos el registro de la lista de inválidos.
                ids_invalidos_carga = [
                    identificador
                    for identificador in ids_invalidos_carga
                    if int(identificador) != id_registro
                ]

            resultados.append({
                "id_registro": id_registro,
                "valido": resultado["valido"],
                "mensaje": resultado.get("mensaje", "")
            })

        except Exception as error:

            # Un error individual no detiene el procesamiento de los demás.
            print(
                f"ERROR AL PROCESAR EL REGISTRO {registro.get('id_registro')}: {error}"
            )

            resultados.append({
                "id_registro": registro.get("id_registro"),
                "valido": False,
                "mensaje": "No fue posible procesar este registro."
            })

    # Actualizamos el seguimiento de los registros en la sesión.
    session["codigos_carga"] = codigos_carga
    session["ids_invalidos_carga"] = ids_invalidos_carga

    # Conservamos abierto el modal de resultados.
    session["mostrar_resultados_carga"] = True
    session["abrir_modal_carga"] = True

    # Calculamos el resumen del procesamiento.
    corregidos = sum(1 for r in resultados if r["valido"])
    pendientes = len(resultados) - corregidos

    return jsonify({
        "exito": True,
        "total": len(resultados),
        "corregidos": corregidos,
        "pendientes": pendientes,
        "resultados": resultados
    })



# ==================================================
# FUNCIÓN: ELIMINAR CASO CORRECTO
# ==================================================


@app.route("/eliminar-caso", methods=["POST"])
def eliminar_caso():

    conexion = None
    cursor = None

    try:
        # Recuperamos el código del caso que se desea eliminar.
        codigo_caso = request.form.get("codigo_caso", "").strip()

        # Nos conectamos a la base de datos temporal.
        conexion = conectar_temporal()
        cursor = conexion.cursor()

        # Eliminamos únicamente el caso seleccionado.
        cursor.execute(
            "DELETE FROM casos WHERE codigo_caso = %s",
            (codigo_caso,)
        )

        # Confirmamos la eliminación.
        conexion.commit()

        # Retiramos el código de la última carga, si pertenecía a ella.
        codigos_carga = session.get("codigos_carga", [])

        if codigo_caso in codigos_carga:
            codigos_carga.remove(codigo_caso)
            session["codigos_carga"] = codigos_carga

        # Preparamos el mensaje y la reapertura del modal.
        session["mensaje_carga"] = "El caso fue eliminado correctamente."
        session["detalle_carga"] = ""
        session["mostrar_resultados_carga"] = True
        session["abrir_modal_carga"] = True

        return redirect(url_for("mostrar_asignacion"))

    except Exception as error:
        if conexion:
            conexion.rollback()

        print(f"ERROR AL ELIMINAR EL CASO: {error}")

        # Informamos el error y regresamos al modal de carga.
        session["mensaje_carga"] = "No fue posible eliminar el caso."
        session["detalle_carga"] = ""
        session["mostrar_resultados_carga"] = True
        session["abrir_modal_carga"] = True

        return redirect(url_for("mostrar_asignacion"))

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()


# ==================================================
# FUNCIÓN: ELIMINAR REGISTRO INCORRECTO
# ==================================================


@app.route("/eliminar-registro-invalido", methods=["POST"])
def eliminar_registro_invalido():

    conexion = None
    cursor = None

    try:
        # Recuperamos el identificador del registro seleccionado.
        id_registro = request.form.get("id_registro", type=int)

        if not id_registro:
            raise ValueError("No se recibió un identificador válido.")

        # Nos conectamos a la base de datos temporal.
        conexion = conectar_temporal()
        cursor = conexion.cursor()

        # Eliminamos únicamente el registro seleccionado.
        cursor.execute(
            "DELETE FROM registros_invalidos WHERE id_registro = %s",
            (id_registro,)
        )

        # Comprobamos que realmente se haya eliminado un registro.
        if cursor.rowcount == 0:
            raise ValueError("El registro seleccionado ya no existe.")

        # Confirmamos la eliminación.
        conexion.commit()

        # Retiramos el identificador de la lista de inválidos de la sesión.
        ids_invalidos = session.get("ids_invalidos_carga", [])

        if id_registro in ids_invalidos:
            ids_invalidos.remove(id_registro)

        session["ids_invalidos_carga"] = ids_invalidos

        # Preparamos el mensaje para mostrarlo en la interfaz.
        session["mensaje_carga"] = (
            "El registro fue eliminado correctamente."
        )

        session["mostrar_resultados_carga"] = True
        session["abrir_modal_carga"] = True

    except Exception as error:

        if conexion:
            conexion.rollback()

        print(f"ERROR AL ELIMINAR EL REGISTRO INVÁLIDO: {error}")

        session["mensaje_carga"] = (
            "No fue posible eliminar el registro seleccionado."
        )

        session["mostrar_resultados_carga"] = True
        session["abrir_modal_carga"] = True

    finally:

        if cursor:
            cursor.close()

        if conexion:
            conexion.close()

    # Regresamos a la interfaz donde se muestra la tabla de registros.
    return redirect(url_for("mostrar_asignacion"))

# ==================================================
# FUNCIÓN: CANCELAR TODA LA IMPORTACIÓN
# ==================================================


@app.route("/cancelar-importacion", methods=["POST"])
def cancelar_importacion():

    conexion = None
    cursor = None

    try:
        # Recuperamos los identificadores de la última carga.
        codigos_carga = session.get("codigos_carga", [])
        ids_invalidos_carga = session.get("ids_invalidos_carga", [])

        # Nos conectamos a la base de datos temporal.
        conexion = conectar_temporal()
        cursor = conexion.cursor()

        # Eliminamos únicamente los casos válidos de esta carga.
        if codigos_carga:
            marcadores = ", ".join(["%s"] * len(codigos_carga))

            cursor.execute(
                f"DELETE FROM casos WHERE codigo_caso IN ({marcadores})",
                tuple(codigos_carga)
            )

        # Eliminamos únicamente los registros inválidos de esta carga.
        if ids_invalidos_carga:
            marcadores = ", ".join(["%s"] * len(ids_invalidos_carga))

            cursor.execute(
                f"DELETE FROM registros_invalidos WHERE id_registro IN ({marcadores})",
                tuple(ids_invalidos_carga)
            )

        # Confirmamos las eliminaciones.
        conexion.commit()

        # Limpiamos los identificadores y mensajes de la sesión.
        session.pop("codigos_carga", None)
        session.pop("ids_invalidos_carga", None)
        session.pop("mensaje_carga", None)
        session.pop("detalle_carga", None)

        # Dejamos el modal preparado para una nueva carga.
        session["mostrar_resultados_carga"] = False
        # Indicamos que se debe volver a abrir el modal de carga.
        session["abrir_modal_carga"] = True

        return redirect(url_for("mostrar_asignacion"))

    except Exception as error:
        # Revertimos los cambios si ocurre algún problema.
        if conexion:
            conexion.rollback()

        print(f"ERROR AL LIMPIAR LA CARGA: {error}")

        # Mostramos el error dentro del modal.
        session["mensaje_carga"] = "No fue posible limpiar la carga temporal."
        session["detalle_carga"] = ""
        session["mostrar_resultados_carga"] = True

        return redirect(url_for("mostrar_asignacion"))

    finally:
        # Cerramos los recursos utilizados.
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()

def calcular_minutos_habiles(inicio, fin, festivos):
    # Si el vencimiento ya pasó, no quedan minutos.
    if fin <= inicio:
        return 0

    minutos_totales = 0
    fecha_actual = inicio.date()

    # Recorremos cada día del periodo.
    while fecha_actual <= fin.date():

        # Solo contamos de lunes a viernes que no sean festivos.
        if fecha_actual.weekday() < 5 and fecha_actual not in festivos:

            # Definimos la jornada laboral.
            inicio_jornada = datetime.combine(
                fecha_actual,
                time(6, 0)
            )

            fin_jornada = datetime.combine(
                fecha_actual,
                time(18, 0)
            )

            # Limitamos el cálculo al horario de atención.
            tramo_inicio = max(inicio, inicio_jornada)
            tramo_fin = min(fin, fin_jornada)

            if tramo_fin > tramo_inicio:
                diferencia = tramo_fin - tramo_inicio
                minutos_totales += int(diferencia.total_seconds() / 60)

        fecha_actual += timedelta(days=1)

    return minutos_totales

# ==================================================
# INICIAR SERVIDOR
# ==================================================

if __name__ == "__main__":

    # Iniciamos el servidor en el equipo local.
    app.run(debug=True)




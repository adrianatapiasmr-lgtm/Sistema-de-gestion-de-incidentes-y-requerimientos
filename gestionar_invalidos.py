
# gestionar_invalidos.py

# Importamos json para interpretar los datos almacenados en formato JSON.
import json

# Importamos la función de conexión a la base temporal.
from conexion import conectar_temporal, conectar_principal

# Permiten reconstruir un CSV temporal para reutilizar la validación existente.
import csv
import io

# Reutilizamos las mismas reglas de validación del archivo original.
from leer_csv import leer_csv, COLUMNAS_ESPERADAS

# Reutilizamos las funciones de cálculo de fechas del almacenamiento original.
from almacenar_casos import (
    obtener_festivos,
    calcular_fecha_inicio_gestion,
    calcular_fecha_vencimiento,
    FORMATO_FECHA
)

from datetime import datetime

# ==================================================
# FUNCIÓN: CONSULTAR REGISTROS INVÁLIDOS
# ==================================================

def consultar_registros_invalidos():

    # Inicializamos las variables de conexión.
    conexion = None
    cursor = None

    try:

        # Establecemos conexión con la base de datos temporal.
        conexion = conectar_temporal()

        # Creamos un cursor para ejecutar consultas SQL.
        cursor = conexion.cursor(dictionary=True)

        # Consultamos todos los registros pendientes de corrección.
        consulta = """
            SELECT
                id_registro,
                numero_registro,
                codigo_caso,
                estado,
                descripcion,
                fecha_prevista,
                prioridad,
                fecha_apertura,
                es_vip,
                nombre_sede,
                errores,
                campos_adicionales,
                fecha_registro
            FROM registros_invalidos
            ORDER BY id_registro ASC
        """

        # Ejecutamos la consulta.
        cursor.execute(consulta)

        # Recuperamos todos los registros encontrados.
        registros = cursor.fetchall()

        # Recorremos los registros para interpretar los campos JSON.
        for registro in registros:

            # Convertimos los errores a una lista de Python.
            if isinstance(registro["errores"], str):
                registro["errores"] = json.loads(registro["errores"])

            # Convertimos los campos adicionales a una lista de Python.
            if isinstance(registro["campos_adicionales"], str):
                registro["campos_adicionales"] = json.loads(
                    registro["campos_adicionales"]
                )

        # Devolvemos todos los registros consultados.
        return registros

    except Exception as error:

        # Informamos si ocurrió un problema durante la consulta.
        raise RuntimeError(
            f"No fue posible consultar los registros inválidos: {error}"
        ) from error

    finally:

        # Cerramos el cursor si llegó a crearse.
        if cursor is not None:
            cursor.close()

        # Cerramos la conexión si llegó a establecerse.
        if conexion is not None and conexion.is_connected():
            conexion.close()

def actualizar_registro_invalido(id_registro, datos, campos_adicionales):
    """
    Guarda los cambios realizados en un registro inválido.
    Los errores anteriores se conservan hasta ejecutar una nueva validación.
    """

    conexion = None
    cursor = None

    try:
        # Conectamos con la base de datos temporal.
        conexion = conectar_temporal()
        cursor = conexion.cursor()

        # Comprobamos que el registro exista.
        cursor.execute(
            "SELECT id_registro FROM registros_invalidos WHERE id_registro = %s",
            (id_registro,)
        )

        if cursor.fetchone() is None:
            raise ValueError("El registro inválido no existe.")

        # Actualizamos los datos modificados.
        consulta = """
            UPDATE registros_invalidos
            SET
                codigo_caso = %s,
                estado = %s,
                descripcion = %s,
                fecha_prevista = %s,
                prioridad = %s,
                fecha_apertura = %s,
                es_vip = %s,
                nombre_sede = %s,
                campos_adicionales = %s
            WHERE id_registro = %s
        """

        # Recuperamos el valor seleccionado en la lista desplegable.
        valor_vip = datos.get("es_vip", "No").strip()

        # Convertimos la selección VIP a un valor booleano para MySQL.
        es_vip = valor_vip == "Si"

        valores = (
            datos.get("codigo_caso") or None,
            datos.get("estado") or None,
            datos.get("descripcion") or None,
            datos.get("fecha_prevista") or None,
            datos.get("prioridad") or None,
            datos.get("fecha_apertura") or None,
            es_vip,
            datos.get("nombre_sede") or None,
            json.dumps(campos_adicionales, ensure_ascii=False),
            id_registro
        )

        cursor.execute(consulta, valores)

        # Confirmamos los cambios en la base de datos.
        conexion.commit()

        return True

    except Exception as error:
        # Deshacemos los cambios si ocurre algún problema.
        if conexion is not None:
            conexion.rollback()

        raise RuntimeError(
            f"No fue posible actualizar el registro inválido: {error}"
        ) from error

    finally:
        # Cerramos los recursos utilizados.
        if cursor is not None:
            cursor.close()

        if conexion is not None and conexion.is_connected():
            conexion.close()




def actualizar_caso(codigo_original, datos):
    """
    Actualiza un caso existente en la base temporal después de validar
    sus datos, conserva sus observaciones y recalcula las fechas de gestión.
    """

    # Inicializamos las conexiones y los cursores.
    conexion = conectar_temporal()
    cursor = None
    conexion_principal = None
    cursor_principal = None

    try:
        cursor = conexion.cursor()

        # Recuperamos los datos enviados desde el panel.
        codigo_nuevo = datos.get("codigo_caso", "").strip()
        estado = datos.get("estado", "").strip()
        descripcion = datos.get("descripcion", "").strip()
        prioridad = datos.get("prioridad", "").strip()
        fecha_apertura = datos.get("fecha_apertura", "").strip()

        # Recuperamos el nombre de la sede seleccionada.
        nombre_sede = datos.get("nombre_sede", "").strip()

        # Comprobamos que se haya seleccionado una sede.
        if not nombre_sede:
            return {
                "valido": False,
                "errores": ["Debe seleccionar una sede."],
                "mensaje": "No se pudo actualizar el caso."
            }

        # Recuperamos el valor seleccionado en la lista desplegable.
        valor_vip = datos.get("es_vip", "No").strip()

        # Comprobamos que el valor VIP sea válido.
        if valor_vip not in ("No", "Si"):
            return {
                "valido": False,
                "errores": ["El campo VIP debe ser No o Si."],
                "mensaje": "No se pudo actualizar el caso."
            }

        # Convertimos la selección VIP a un valor booleano para MySQL.
        es_vip = valor_vip == "Si"

        # Recuperamos las observaciones escritas desde el panel.
        observaciones_usuario = datos.get("observaciones", "").strip()

        # Convertimos la fecha al formato que utiliza leer_csv.py.
        try:
            try:
                fecha_convertida = datetime.strptime(
                    fecha_apertura,
                    "%Y-%m-%dT%H:%M"
                )
            except ValueError:
                fecha_convertida = datetime.strptime(
                    fecha_apertura,
                    FORMATO_FECHA
                )

            fecha_csv = fecha_convertida.strftime(FORMATO_FECHA)

        except ValueError:
            return {
                "valido": False,
                "errores": [
                    "La fecha de apertura no tiene un formato válido."
                ],
                "mensaje": "No se pudo actualizar el caso."
            }

        # Reconstruimos un CSV para reutilizar las reglas de validación.
        archivo = io.StringIO()
        escritor = csv.writer(archivo, delimiter=";")

        escritor.writerow(COLUMNAS_ESPERADAS)
        escritor.writerow([
            codigo_nuevo,
            estado,
            descripcion,
            "",
            prioridad,
            fecha_csv
        ])

        archivo.seek(0)

        # Validamos los datos con la función original del proyecto.
        resultado = leer_csv(archivo)

        # Si los datos tienen errores, no modificamos el caso.
        if resultado["invalidos"]:
            errores = resultado["invalidos"][0]["errores"]

            return {
                "valido": False,
                "errores": errores,
                "mensaje": "El caso contiene errores y no fue actualizado."
            }

        # Recuperamos los datos normalizados por la validación.
        registro_validado = resultado["validos"][0]

        fecha_convertida = datetime.strptime(
            registro_validado["Fecha/hora de apertura"],
            FORMATO_FECHA
        )

        # Comprobamos que el caso original todavía exista.
        cursor.execute("""
            SELECT codigo_caso
            FROM casos
            WHERE codigo_caso = %s
        """, (codigo_original,))

        if cursor.fetchone() is None:
            return {
                "valido": False,
                "errores": ["El caso original ya no existe."],
                "mensaje": "No se pudo actualizar el caso."
            }

        # Comprobamos que el nuevo código no pertenezca a otro caso.
        cursor.execute("""
            SELECT codigo_caso
            FROM casos
            WHERE codigo_caso = %s
              AND codigo_caso <> %s
        """, (registro_validado["ID"], codigo_original))

        if cursor.fetchone() is not None:
            return {
                "valido": False,
                "errores": [
                    f"El código de caso '{registro_validado['ID']}' "
                    "ya existe en la base temporal."
                ],
                "mensaje": "No se pudo actualizar el caso."
            }

        # Recuperamos los festivos para calcular las fechas laborales.
        festivos = obtener_festivos(cursor)

        # Calculamos el inicio de gestión.
        fecha_inicio, observacion_calculada = calcular_fecha_inicio_gestion(
            registro_validado["Fecha/hora de apertura"],
            festivos
        )

        # Calculamos el vencimiento sumando las 8 horas hábiles.
        fecha_vencimiento = calcular_fecha_vencimiento(
            fecha_inicio,
            festivos
        )

        # Conservamos las observaciones del usuario.
        # Si están vacías, utilizamos la observación calculada.
        observaciones = observaciones_usuario or observacion_calculada

        # Actualizamos el caso después de validar todos los datos.
        cursor.execute("""
            UPDATE casos
            SET codigo_caso = %s,
                estado = %s,
                descripcion = %s,
                prioridad = %s,
                fecha_apertura = %s,
                fecha_inicio_gestion = %s,
                fecha_vencimiento = %s,
                es_vip = %s,
                nombre_sede = %s,
                observaciones = %s
            WHERE codigo_caso = %s
        """, (
            codigo_nuevo,
            estado,
            descripcion,
            prioridad,
            fecha_convertida,
            fecha_inicio,
            fecha_vencimiento,
            es_vip,
            nombre_sede,
            observaciones,
            codigo_original
        ))

        # Confirmamos los cambios en la base temporal.
        conexion.commit()

        return {
            "valido": True,
            "errores": [],
            "codigo_caso": registro_validado["ID"],
            "mensaje": "El caso fue actualizado correctamente."
        }

    except Exception as error:
        # Cancelamos los cambios si ocurre algún problema.
        conexion.rollback()

        return {
            "valido": False,
            "errores": [str(error)],
            "mensaje": "No fue posible actualizar el caso."
        }

    finally:
        # Cerramos el cursor de la base temporal.
        if cursor is not None:
            cursor.close()

        # Cerramos la conexión temporal.
        if conexion is not None and conexion.is_connected():
            conexion.close()

        # Cerramos el cursor de la base principal.
        if cursor_principal is not None:
            cursor_principal.close()

        # Cerramos la conexión principal.
        if conexion_principal is not None and conexion_principal.is_connected():
            conexion_principal.close()



def validar_registro_invalido(id_registro):
    """
    Vuelve a validar un registro inválido utilizando las reglas de leer_csv.py.
    Actualiza sus errores y determina si ya está listo para pasar a casos.
    """

    conexion = None
    cursor = None

    try:
        # Consultamos el registro que se desea validar.
        conexion = conectar_temporal()
        cursor = conexion.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                codigo_caso,
                estado,
                descripcion,
                fecha_prevista,
                prioridad,
                fecha_apertura,
                nombre_sede,
                campos_adicionales
            FROM registros_invalidos
            WHERE id_registro = %s
            """,
            (id_registro,)
        )

        registro = cursor.fetchone()

        if registro is None:
            raise ValueError("El registro inválido no existe.")

        # Recuperamos las columnas adicionales almacenadas como JSON.
        campos_adicionales = registro["campos_adicionales"]

        if isinstance(campos_adicionales, str):
            campos_adicionales = json.loads(campos_adicionales)

        if campos_adicionales is None:
            campos_adicionales = []

        # Reconstruimos los datos con el mismo orden del CSV original.
        datos = [
            registro["codigo_caso"] or "",
            registro["estado"] or "",
            registro["descripcion"] or "",
            registro["fecha_prevista"] or "",
            registro["prioridad"] or "",
            registro["fecha_apertura"] or ""
        ]

        # Creamos un CSV temporal para reutilizar leer_csv().
        archivo_temporal = io.StringIO()
        escritor = csv.writer(archivo_temporal, delimiter=";")

        # Agregamos encabezado y registro.
        escritor.writerow(COLUMNAS_ESPERADAS)
        escritor.writerow(datos + campos_adicionales)

        # Volvemos al inicio del archivo para que pueda leerse.
        archivo_temporal.seek(0)

        # Ejecutamos la validación con las reglas existentes.
        resultado = leer_csv(archivo_temporal)

        # Recuperamos la sede seleccionada en el registro.
        nombre_sede = (registro["nombre_sede"] or "").strip()

        # Recuperamos los errores encontrados en los campos del CSV.
        if resultado["invalidos"]:
            errores = resultado["invalidos"][0]["errores"]
        else:
            errores = []

        # Comprobamos que el registro tenga una sede seleccionada.
        if not nombre_sede:
            errores.append("Debe seleccionar una sede.")

        # El registro solo será válido si no tiene ningún error.
        es_valido = len(errores) == 0

        # Actualizamos los errores encontrados en la base de datos.
        cursor.execute(
            """
            UPDATE registros_invalidos
            SET errores = %s
            WHERE id_registro = %s
            """,
            (json.dumps(errores, ensure_ascii=False), id_registro)
        )

        conexion.commit()

        return {
            "valido": es_valido,
            "errores": errores,
            "mensaje": (
                "El registro es válido y está listo para pasar a casos."
                if es_valido
                else "El registro todavía contiene errores."
            )
        }

    except Exception as error:
        # Deshacemos los cambios si ocurre algún problema.
        if conexion is not None:
            conexion.rollback()

        raise RuntimeError(
            f"No fue posible validar el registro: {error}"
        ) from error

    finally:
        # Cerramos los recursos utilizados.
        if cursor is not None:
            cursor.close()

        if conexion is not None and conexion.is_connected():
            conexion.close()


def transferir_registro_corregido(id_registro):
    """
    Traslada un registro corregido desde registros_invalidos hacia casos.
    Elimina el registro inválido solamente si la inserción fue exitosa.
    """

    conexion = None
    cursor = None

    try:
        # Conectamos con la base de datos temporal.
        conexion = conectar_temporal()
        cursor = conexion.cursor()

        # Consultamos el registro y bloqueamos su modificación durante la operación.
        cursor.execute(
            """
            SELECT
                codigo_caso,
                estado,
                descripcion,
                prioridad,
                fecha_apertura,
                es_vip,
                nombre_sede,
                errores,
                campos_adicionales
            FROM registros_invalidos
            WHERE id_registro = %s
            FOR UPDATE
            """,
            (id_registro,)
        )

        registro = cursor.fetchone()

        if registro is None:
            raise ValueError("El registro inválido no existe.")

        # Descomponemos los datos consultados.
        (
            codigo_caso,
            estado,
            descripcion,
            prioridad,
            fecha_apertura,
            es_vip,
            nombre_sede,
            errores,
            campos_adicionales
        ) = registro

        # Interpretamos los errores almacenados en formato JSON.
        if isinstance(errores, str):
            errores = json.loads(errores)

        # Interpretamos las columnas adicionales almacenadas en formato JSON.
        if isinstance(campos_adicionales, str):
            campos_adicionales = json.loads(campos_adicionales)

        # Comprobamos que el registro haya superado la validación.
        if errores:
            raise ValueError(
                "El registro todavía tiene errores pendientes de corregir."
            )

        # Comprobamos que no existan columnas adicionales pendientes.
        if campos_adicionales:
            raise ValueError(
                "El registro todavía contiene columnas adicionales."
            )

        # Comprobamos que el código del caso no exista en la tabla principal.
        cursor.execute(
            "SELECT codigo_caso FROM casos WHERE codigo_caso = %s",
            (codigo_caso,)
        )

        if cursor.fetchone() is not None:
            raise ValueError(
                f"El caso {codigo_caso} ya existe en la tabla casos."
            )

        # Consultamos los festivos para calcular las fechas hábiles.
        festivos = obtener_festivos(cursor)

        # Convertimos la fecha de apertura al formato datetime.
        fecha_apertura_datetime = datetime.strptime(
            fecha_apertura,
            FORMATO_FECHA
        )

        # Calculamos la fecha de inicio de gestión.
        # Utilizamos la fecha de apertura almacenada en el registro.
        fecha_inicio, observacion = calcular_fecha_inicio_gestion(
            fecha_apertura,
            festivos
        )

        # Calculamos el vencimiento acumulando 8 horas hábiles.
        fecha_vencimiento = calcular_fecha_vencimiento(
            fecha_inicio,
            festivos
        )

        # Insertamos el registro corregido en la tabla casos.
        cursor.execute(
            """
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
            """,
            (
                codigo_caso,
                estado,
                descripcion,
                prioridad,
                fecha_apertura_datetime,
                fecha_inicio,
                fecha_vencimiento,
                es_vip,
                nombre_sede,
                observacion
            )
        )

        # Eliminamos el registro inválido después de insertarlo correctamente.
        cursor.execute(
            "DELETE FROM registros_invalidos WHERE id_registro = %s",
            (id_registro,)
        )

        # Confirmamos la inserción y eliminación en una sola transacción.
        conexion.commit()

        return {
            "codigo_caso": codigo_caso,
            "mensaje": "El registro fue trasladado correctamente a casos."
        }

    except Exception as error:
        # Revertimos las operaciones si ocurre algún problema.
        if conexion is not None:
            conexion.rollback()

        raise RuntimeError(
            f"No fue posible transferir el registro corregido: {error}"
        ) from error

    finally:
        # Cerramos los recursos utilizados.
        if cursor is not None:
            cursor.close()

        if conexion is not None and conexion.is_connected():
            conexion.close()


def corregir_registro_invalido(id_registro, datos, campos_adicionales):
    """
    Guarda los cambios de un registro incorrecto, lo valida y,
    si es correcto, lo traslada automáticamente a la tabla casos.
    """

    # Guardamos los cambios realizados desde el panel.
    actualizar_registro_invalido(
        id_registro,
        datos,
        campos_adicionales
    )

    # Volvemos a validar el registro con las reglas del CSV original.
    resultado = validar_registro_invalido(id_registro)

    # Si todavía tiene errores, permanece en registros_invalidos.
    if not resultado["valido"]:
        return {
            "valido": False,
            "errores": resultado["errores"],
            "mensaje": "El registro todavía contiene errores. Puedes corregirlo nuevamente."
        }

    # Si es válido, lo trasladamos automáticamente a la tabla casos.
    resultado_transferencia = transferir_registro_corregido(id_registro)

    return {
        "valido": True,
        "errores": [],
        "codigo_caso": resultado_transferencia["codigo_caso"],
        "mensaje": resultado_transferencia["mensaje"]
    }

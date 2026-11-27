# transferir_casos.py

# Importamos las funciones para conectarnos a ambas bases de datos.
from conexion import conectar_temporal, conectar_principal
# Importamos las herramientas para reconstruir el CSV.
import csv
import io

# Reutilizamos las reglas de validación del archivo original.
from leer_csv import leer_csv, COLUMNAS_ESPERADAS

# Importamos el formato de fecha utilizado por el proyecto.
from almacenar_casos import FORMATO_FECHA


# ==================================================
# FUNCIÓN: TRANSFERIR CASOS A LA BASE PRINCIPAL
# ==================================================

def transferir_casos():

    # Inicializamos las conexiones y los cursores.
    conexion_temporal = None
    conexion_principal = None

    cursor_temporal = None
    cursor_principal = None

    try:

        # Establecemos conexión con ambas bases de datos.
        conexion_temporal = conectar_temporal()
        conexion_principal = conectar_principal()

        # Creamos los cursores para ejecutar consultas SQL.
        cursor_temporal = conexion_temporal.cursor()
        cursor_principal = conexion_principal.cursor()

                # Comprobamos qué base de datos está utilizando Python.
        cursor_principal.execute("SELECT DATABASE()")
        print("BASE PRINCIPAL CONECTADA:", cursor_principal.fetchone()[0])

        # Comprobamos si la tabla principal contiene la columna nombre_sede.
        cursor_principal.execute("""
            SHOW COLUMNS FROM casos LIKE 'nombre_sede'
        """)

        print("COLUMNA NOMBRE_SEDE:", cursor_principal.fetchall())


        # Consultamos los casos almacenados en la base temporal.
        cursor_temporal.execute("""
            SELECT
                codigo_caso,
                estado,
                descripcion,
                prioridad,
                fecha_apertura,
                fecha_inicio_gestion,
                fecha_vencimiento,
                observaciones,
                fecha_registro,
                es_vip,
                nombre_sede
            FROM casos
        """)

        # Recuperamos todos los registros temporales.
        registros = cursor_temporal.fetchall()

        # Si no existen casos, finalizamos la operación.
        if not registros:
            return {
                "insertados": 0,
                "duplicados": [],
                "eliminados_temporal": 0,
                "limpieza_temporal_exitosa": True,
                "error_limpieza": None
            }
        # Identificamos los casos que no tienen una sede seleccionada.
        casos_sin_sede = [
            registro[0]
            for registro in registros
            if not registro[10] or not str(registro[10]).strip()
        ]

        # Impedimos la transferencia si algún caso no tiene sede.
        if casos_sin_sede:
            raise ValueError(
                "No se puede realizar la transferencia. "
                "Los siguientes casos no tienen una sede seleccionada: "
                + ", ".join(casos_sin_sede)
            )
        
                # Reconstruimos un CSV con los casos almacenados temporalmente.
        archivo = io.StringIO()
        escritor = csv.writer(archivo, delimiter=";")

        # Escribimos los encabezados que utiliza la validación original.
        escritor.writerow(COLUMNAS_ESPERADAS)

        # Agregamos los datos de cada caso al CSV.
        for registro in registros:

            # Convertimos la fecha de apertura al formato del CSV.
            fecha_apertura = registro[4].strftime(FORMATO_FECHA)

            escritor.writerow([
                registro[0],  # ID
                registro[1],  # Estado
                registro[2],  # Descripción
                "",            # Fecha prevista
                registro[3],  # Prioridad
                fecha_apertura
            ])

        # Regresamos al inicio del archivo reconstruido.
        archivo.seek(0)

        # Validamos todos los casos con las reglas originales.
        resultado_validacion = leer_csv(archivo)

        # Recuperamos los registros que no superaron la validación.
        registros_invalidos = resultado_validacion["invalidos"]

        # Bloqueamos la transferencia si algún caso tiene errores.
        if registros_invalidos:

            # Preparamos el detalle de los errores encontrados.
            detalles = []

            for indice, registro_invalido in enumerate(
                registros_invalidos,
                start=1
            ):
                errores = registro_invalido.get("errores", [])

                # Identificamos el registro que contiene los errores.
                detalles.append(
                    f"Registro {indice}: {'; '.join(errores)}"
                )

            # Informamos los errores para que puedan corregirse.
            raise ValueError(
                "No se puede realizar la transferencia. "
                "Se encontraron casos con información incorrecta: "
                + " | ".join(detalles)
            )

        # Extraemos los códigos de todos los casos temporales.
        codigos = [registro[0] for registro in registros]

        # Creamos los marcadores necesarios para la consulta IN.
        marcadores = ", ".join(["%s"] * len(codigos))

        # Consultamos cuáles códigos ya existen en la base principal.
        consulta_duplicados = f"""
            SELECT codigo_caso
            FROM casos
            WHERE codigo_caso IN ({marcadores})
        """

        cursor_principal.execute(consulta_duplicados, tuple(codigos))

        # Guardamos los códigos que ya existen en la base principal.
        duplicados = {
            registro[0]
            for registro in cursor_principal.fetchall()
        }

        # Separamos los casos nuevos de los casos duplicados.
        registros_nuevos = [
            registro
            for registro in registros
            if registro[0] not in duplicados
        ]

        # Obtenemos los códigos de los casos que se transferirán.
        codigos_insertados = [
            registro[0]
            for registro in registros_nuevos
        ]

        # Si todos los casos son duplicados, no realizamos inserciones.
        if not registros_nuevos:
            return {
                "insertados": 0,
                "duplicados": sorted(duplicados),
                "eliminados_temporal": 0,
                "limpieza_temporal_exitosa": True,
                "error_limpieza": None
            }

        # Definimos los campos que se insertarán en la base principal.
        consulta_insertar = """
            INSERT INTO casos_temporales (
                codigo_caso,
                estado,
                descripcion,
                prioridad,
                fecha_apertura,
                fecha_inicio_gestion,
                fecha_vencimiento,
                observaciones,
                fecha_registro,
                es_vip,
                nombre_sede
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        # Insertamos los casos nuevos en la base principal.
        try:

            cursor_principal.executemany(
                consulta_insertar,
                registros_nuevos
            )

            # Confirmamos la inserción en la base principal.
            conexion_principal.commit()

        except Exception as error:

            # Revertimos todas las inserciones si ocurre un error.
            conexion_principal.rollback()

            raise RuntimeError(
                f"Error al insertar los casos en la base principal: {error}"
            ) from error

        # Inicializamos el resultado de la limpieza temporal.
        limpieza_exitosa = True
        error_limpieza = None
        cantidad_eliminada = 0

        # Eliminamos únicamente los casos insertados correctamente.
        try:

            # Preparamos la consulta de eliminación.
            consulta_eliminar = """
                DELETE FROM casos_temporales
                WHERE codigo_caso = %s
            """

            # Ejecutamos la eliminación de los casos transferidos.
            cursor_temporal.executemany(
                consulta_eliminar,
                [(codigo,) for codigo in codigos_insertados]
            )

            # Confirmamos la eliminación en la base temporal.
            conexion_temporal.commit()

            # Registramos la cantidad de casos eliminados.
            cantidad_eliminada = cursor_temporal.rowcount

        except Exception as error:

            # Revertimos la limpieza si ocurre un error.
            conexion_temporal.rollback()

            # Informamos que los casos siguen en la base temporal.
            limpieza_exitosa = False
            error_limpieza = str(error)

        # Devolvemos el resumen de la transferencia.
        return {
            "insertados": len(registros_nuevos),
            "duplicados": sorted(duplicados),
            "eliminados_temporal": cantidad_eliminada,
            "limpieza_temporal_exitosa": limpieza_exitosa,
            "error_limpieza": error_limpieza
        }

    except Exception as error:

        # Informamos los errores generales de la transferencia.
        raise RuntimeError(
            f"No fue posible completar la transferencia: {error}"
        ) from error

    finally:

        # Cerramos el cursor de la base temporal.
        if cursor_temporal is not None:
            cursor_temporal.close()

        # Cerramos el cursor de la base principal.
        if cursor_principal is not None:
            cursor_principal.close()

        # Cerramos la conexión temporal.
        if conexion_temporal is not None and conexion_temporal.is_connected():
            conexion_temporal.close()

        # Cerramos la conexión principal.
        if conexion_principal is not None and conexion_principal.is_connected():
            conexion_principal.close()
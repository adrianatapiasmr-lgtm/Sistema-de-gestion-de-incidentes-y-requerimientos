# conexion.py

# Importamos el conector para comunicarnos con MySQL.
import mysql.connector

# Importamos Error para manejar posibles errores de conexión.
from mysql.connector import Error


# ==================================================
# CONFIGURACIÓN DE LA CONEXIÓN
# ==================================================

# Datos de acceso al servidor MySQL.
import os

CONFIGURACION_DB = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

DB_NAME = os.getenv("DB_NAME")

# ==================================================
# FUNCIÓN: CONECTAR A UNA BASE DE DATOS
# ==================================================

def conectar_bd(nombre_bd):

    # Intentamos establecer la conexión con la base de datos indicada.
    try:
        conexion = mysql.connector.connect(
            **CONFIGURACION_DB,
            database=nombre_bd
        )

        # Comprobamos que la conexión se haya establecido.
        if conexion.is_connected():
            return conexion

    # Capturamos los errores que puedan ocurrir durante la conexión.
    except Error as error:
        raise ConnectionError(
            f"No fue posible conectar con la base de datos "
            f"'{nombre_bd}': {error}"
        ) from error

    # Informamos si MySQL no logró establecer la conexión.
    raise ConnectionError(
        f"No se pudo establecer conexión con '{nombre_bd}'."
    )


# ==================================================
# FUNCIÓN: CONECTAR A LA BASE TEMPORAL
# ==================================================

def conectar_temporal():
    return conectar_bd(os.getenv("DB_NAME"))

def conectar_principal():
    return conectar_bd(os.getenv("DB_NAME"))


### Pruebas a las BDS
print("======================================")
print("PRUEBA 1: BASE DE DATOS TEMPORAL")
print("======================================")

try:

    # Intentamos conectarnos a la base temporal.
    conexion = conectar_temporal()

    print("Conexión a la base temporal exitosa.")

    # Cerramos la conexión después de la prueba.
    conexion.close()

except Exception as error:
    print(f"Error en la conexión temporal: {error}")


# ==================================================
# PRUEBA 2: CONEXIÓN A LA BASE PRINCIPAL
# ==================================================

print("\n======================================")
print("PRUEBA 2: BASE DE DATOS PRINCIPAL")
print("======================================")

try:

    # Intentamos conectarnos a la base principal.
    conexion = conectar_principal()

    print("Conexión a la base principal exitosa.")

    # Cerramos la conexión después de la prueba.
    conexion.close()

except Exception as error:
    print(f"Error en la conexión principal: {error}")


# ==================================================
# FINALIZACIÓN
# ==================================================

print("\nPruebas de conexión finalizadas.")
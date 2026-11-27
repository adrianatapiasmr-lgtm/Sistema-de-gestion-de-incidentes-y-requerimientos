
# leer_csv.py

# Importamos csv para interpretar los registros del archivo.
import csv

# Importamos io para trabajar con el contenido del archivo en memoria.
import io

# Se importa datetime
from datetime import datetime


# ==================================================
# CONFIGURACIÓN
# ==================================================

# Definimos los nombres de las seis columnas esperadas.
COLUMNAS_ESPERADAS = [
    "ID",
    "Estado",
    "Descripción",
    "Fecha prevista",
    "Prioridad",
    "Fecha/hora de apertura"
]

# Cantidad de campos que debe contener cada registro.
CANTIDAD_COLUMNAS = len(COLUMNAS_ESPERADAS)

# Definimos las columnas que no pueden estar vacías.
# Fecha prevista puede venir sin información.
CAMPOS_OBLIGATORIOS = [
    "ID",
    "Estado",
    "Descripción",
    "Prioridad",
    "Fecha/hora de apertura"
]

# Definimos la equivalencia entre los estados de ServiceDesk
# y los estados internos utilizados por Proyecto Aris.
ESTADOS_EQUIVALENTES = {
    "Activo": "Activo",
    "Asignado": "Asignado",
    "Pendiente de cliente": "Pendiente del cliente",
    "Pendiente del cliente": "Pendiente del cliente",
    "Vencido": "Vencido",
    "Garantia": "Garantia",
    "Solucionado": "Solucionado",
    "Resuelto": "Solucionado",
    "Completado": "Completado"
}

# ==================================================
# FUNCIÓN: LEER CSV
# ==================================================


# ==================================================
# FUNCIÓN: LEER Y CLASIFICAR CSV
# ==================================================

def leer_csv(archivo):

    # Comprobamos que el objeto recibido permita leer archivos.
    if not hasattr(archivo, "read"):
        raise TypeError("El archivo recibido no es válido.")

    # Leemos el contenido del archivo.
    contenido = archivo.read()

    # Convertimos el contenido binario a texto si es necesario.
    if isinstance(contenido, bytes):
        try:
            contenido = contenido.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("El archivo debe utilizar codificación UTF-8.")

    # Si el contenido ya es texto, eliminamos un posible BOM.
    elif isinstance(contenido, str):
        contenido = contenido.removeprefix("\ufeff")

    else:
        raise TypeError("El contenido del archivo no es válido.")

    # Creamos el lector utilizando punto y coma como separador.
    lector = csv.reader(
        io.StringIO(contenido),
        delimiter=";",
        quotechar='"',
        strict=True
    )

    # Ignoramos la primera fila, que contiene los encabezados.
    next(lector, None)

    # Creamos las listas para separar los registros válidos e inválidos.
    registros_validos = []
    registros_invalidos = []

    # Guardamos los códigos encontrados para detectar duplicados en el CSV.
    codigos_vistos = set()

    # Recorremos los registros comenzando después de los encabezados.
    for numero_fila, fila in enumerate(lector, start=2):

        # Eliminamos espacios sobrantes de cada campo.
        fila = [valor.strip() for valor in fila]

        # Ignoramos los registros completamente vacíos.
        if not fila or not any(fila):
            continue

        # Creamos una lista para almacenar los errores del registro.
        errores = []

        # Comprobamos si existen campos faltantes.
        if len(fila) < CANTIDAD_COLUMNAS:

            # Identificamos las columnas que faltan.
            columnas_faltantes = COLUMNAS_ESPERADAS[len(fila):]

            # Agregamos un error por cada columna faltante.
            for columna in columnas_faltantes:
                errores.append(
                    f"Falta el campo: {columna}."
                )

            # Completamos los campos faltantes con valores vacíos.
            fila.extend([""] * (CANTIDAD_COLUMNAS - len(fila)))

        # Comprobamos si existen campos adicionales.
        elif len(fila) > CANTIDAD_COLUMNAS:

            errores.append(
                f"El registro tiene campos adicionales. "
                f"Se esperaban {CANTIDAD_COLUMNAS} columnas."
            )

        # Organizamos los primeros seis campos en un diccionario.
        registro = {
            columna: fila[posicion]
            for posicion, columna in enumerate(COLUMNAS_ESPERADAS)
        }

        # Comprobamos si el código ya apareció anteriormente en el archivo.
        codigo = registro["ID"]

        if codigo:

            if codigo in codigos_vistos:
                errores.append(
                    f"El código de caso '{codigo}' está duplicado en el archivo."
                )

            else:
                codigos_vistos.add(codigo)

        # Validamos los campos obligatorios.
        for columna in CAMPOS_OBLIGATORIOS:

            # Comprobamos si el campo obligatorio está vacío.
            if not registro[columna]:
                errores.append(
                    f"El campo {columna} está vacío."
                )
        # Comprobamos que el estado recibido exista en las equivalencias.
        if registro["Estado"]:
            if registro["Estado"] not in ESTADOS_EQUIVALENTES:
                errores.append(
            f"El estado '{registro['Estado']}' no está reconocido."
        )
            else:
            # Convertimos el estado de ServiceDesk al estado interno.
                registro["Estado"] = ESTADOS_EQUIVALENTES[registro["Estado"]]

        # Validamos el formato de la fecha de apertura.
        if registro["Fecha/hora de apertura"]:

            try:

                # Comprobamos que la fecha tenga el formato esperado.
                datetime.strptime(
                    registro["Fecha/hora de apertura"],
                    "%d/%m/%y %H:%M:%S"
                )

            except ValueError:

                errores.append(
                    "La fecha de apertura tiene un formato inválido. "
                    "Se esperaba DD/MM/AA HH:MM:SS."
                )

        # Si encontramos errores, conservamos el registro como inválido.
        if errores:

            registros_invalidos.append({
                "numero_registro": numero_fila,
                "datos": registro,
                "errores": errores,
                "campos_adicionales": fila[CANTIDAD_COLUMNAS:]
            })


        # Si no encontramos errores, clasificamos el registro como válido.
        else:

            # Conservamos el número original de fila para identificar el registro.
            registro["numero_registro"] = numero_fila

            registros_validos.append(registro)

    # Comprobamos que el archivo contenga registros para procesar.
    if not registros_validos and not registros_invalidos:
        raise ValueError("El archivo no contiene casos para procesar.")

    # Devolvemos ambos grupos para continuar con el procesamiento.
    return {
        "validos": registros_validos,
        "invalidos": registros_invalidos
    }



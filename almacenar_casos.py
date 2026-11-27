
# almacenar_casos.py

# Importamos las herramientas necesarias para trabajar con fechas y horas.
from datetime import datetime, time, timedelta

# Importamos la función de conexión a la base temporal.
from conexion import conectar_temporal

import json

# ==================================================
# CONFIGURACIÓN
# ==================================================

# Hora en la que comienza la jornada laboral.
HORA_INICIO = time(6, 0)

# Hora en la que termina la jornada laboral.
HORA_FIN = time(18, 0)

# Cantidad de horas hábiles para cumplir un caso.
HORAS_CUMPLIMIENTO = 8

# Formato de fecha y hora recibido desde el CSV.
FORMATO_FECHA = "%d/%m/%y %H:%M:%S"


# ==================================================
# FUNCIÓN: COMPROBAR SI UN DÍA ES HÁBIL
# ==================================================

def es_dia_habil(fecha, festivos):

    # weekday() devuelve 5 para sábado y 6 para domingo.
    es_fin_de_semana = fecha.weekday() >= 5

    # Comprobamos si la fecha aparece en el calendario de festivos.
    es_festivo = fecha in festivos

    # El día solamente es hábil si no cumple ninguna de las condiciones.
    return not es_fin_de_semana and not es_festivo

# ==================================================
# FUNCIÓN: OBTENER LOS FESTIVOS
# ==================================================

def obtener_festivos(cursor):

    # Consultamos las fechas registradas en la tabla de festivos.
    cursor.execute("SELECT fecha FROM festivos")

    # Guardamos las fechas en un conjunto para facilitar su consulta.
    return {
        registro["fecha"] if isinstance(registro, dict) else registro[0]
        for registro in cursor.fetchall()
    }

# ==================================================
# FUNCIÓN: CALCULAR FECHA DE INICIO DE GESTIÓN
# ==================================================

def calcular_fecha_inicio_gestion(fecha_apertura, festivos):

    # Convertimos la fecha recibida del CSV a un objeto datetime.
    fecha = datetime.strptime(fecha_apertura, FORMATO_FECHA)

    # Obtenemos únicamente la hora de apertura.
    hora_apertura = fecha.time()

    # Si el caso se abrió antes de las 06:00,
    # proponemos comenzar ese mismo día a las 06:00.
    if hora_apertura < HORA_INICIO:

        fecha_inicio = datetime.combine(
            fecha.date(),
            HORA_INICIO
        )

    # Si se abrió a las 18:00 o después,
    # proponemos comenzar al día siguiente a las 06:00.
    elif hora_apertura >= HORA_FIN:

        fecha_siguiente = fecha.date() + timedelta(days=1)

        fecha_inicio = datetime.combine(
            fecha_siguiente,
            HORA_INICIO
        )

    # Si se abrió dentro del horario laboral,
    # conservamos la fecha y hora originales.
    else:

        fecha_inicio = fecha

    # Si el día propuesto no es hábil, avanzamos hasta el siguiente.
    while not es_dia_habil(fecha_inicio.date(), festivos):

        fecha_siguiente = fecha_inicio.date() + timedelta(days=1)

        fecha_inicio = datetime.combine(
            fecha_siguiente,
            HORA_INICIO
        )

    # Registramos una observación cuando fue necesario ajustar el inicio.
    if fecha_inicio != fecha:

        observacion = (
            "Inicio de gestión ajustado al siguiente horario hábil "
            "por apertura fuera de la jornada laboral o en un día no hábil."
        )

    else:

        observacion = None

    # Devolvemos la fecha calculada y su observación.
    return fecha_inicio, observacion


# ==================================================
# FUNCIÓN: CALCULAR FECHA DE VENCIMIENTO
# ==================================================

def calcular_fecha_vencimiento(fecha_inicio, festivos):

    # Convertimos las 8 horas de cumplimiento en un intervalo de tiempo.
    tiempo_restante = timedelta(hours=HORAS_CUMPLIMIENTO)

    # Comenzamos el conteo desde la fecha de inicio de gestión.
    fecha_actual = fecha_inicio

    # Continuamos mientras queden horas de cumplimiento por consumir.
    while tiempo_restante > timedelta(0):

        # Si encontramos un día no hábil, avanzamos al siguiente.
        if not es_dia_habil(fecha_actual.date(), festivos):

            fecha_siguiente = fecha_actual.date() + timedelta(days=1)

            fecha_actual = datetime.combine(
                fecha_siguiente,
                HORA_INICIO
            )

            continue

        # Si el horario laboral ya terminó, avanzamos al siguiente día.
        if fecha_actual.time() >= HORA_FIN:

            fecha_siguiente = fecha_actual.date() + timedelta(days=1)

            fecha_actual = datetime.combine(
                fecha_siguiente,
                HORA_INICIO
            )

            continue

        # Calculamos cuánto tiempo queda de la jornada actual.
        fin_jornada = datetime.combine(
            fecha_actual.date(),
            HORA_FIN
        )

        tiempo_disponible = fin_jornada - fecha_actual

        # Si el tiempo restante cabe dentro de la jornada,
        # calculamos directamente la fecha de vencimiento.
        if tiempo_restante <= tiempo_disponible:

            fecha_vencimiento = fecha_actual + tiempo_restante

            return fecha_vencimiento

        # Si no cabe, consumimos las horas disponibles del día.
        tiempo_restante -= tiempo_disponible

        # Pausamos el conteo y avanzamos al siguiente día calendario.
        fecha_siguiente = fecha_actual.date() + timedelta(days=1)

        fecha_actual = datetime.combine(
            fecha_siguiente,
            HORA_INICIO
        )


# ==================================================
# FUNCIÓN: ALMACENAR CASOS EN LA BASE TEMPORAL
# ==================================================


def almacenar_casos(resultado):

    # Separamos los registros válidos e inválidos recibidos.
    registros_validos = resultado["validos"]
    registros_invalidos = resultado["invalidos"].copy()

    # Comprobamos que existan registros para almacenar.
    if not registros_validos and not registros_invalidos:
        raise ValueError("No hay registros para almacenar.")

    # Inicializamos las variables de conexión.
    conexion = None
    cursor = None

    # Preparamos las listas de identificadores y resultados.
    ids_invalidos = []
    codigos_validos = []
    total_invalidos = 0

    try:

        # Establecemos conexión con la base de datos temporal.
        conexion = conectar_temporal()

        # Creamos el cursor para ejecutar instrucciones SQL.
        cursor = conexion.cursor()

        # Consultamos los festivos registrados en la base temporal.
        festivos = obtener_festivos(cursor)

        # Consultamos los códigos que ya existen en la tabla de casos.
        cursor.execute("SELECT codigo_caso FROM casos_temporales")

        # Guardamos los códigos existentes para facilitar su comparación.
        codigos_existentes = {
            fila[0] for fila in cursor.fetchall()
        }

        # Separamos los registros que ya existen en la base temporal.
        registros_validos_filtrados = []

        for registro in registros_validos:

            # Obtenemos el código del registro.
            codigo = registro["ID"]

            if codigo in codigos_existentes:

                # Convertimos el duplicado en un registro inválido.
                registros_invalidos.append({
                    "numero_registro": registro["numero_registro"],
                    "datos": {
                        "ID": registro["ID"],
                        "Estado": registro["Estado"],
                        "Descripción": registro["Descripción"],
                        "Fecha prevista": registro["Fecha prevista"],
                        "Prioridad": registro["Prioridad"],
                        "Fecha/hora de apertura": registro["Fecha/hora de apertura"]
                    },
                    "errores": [
                        f"El código de caso '{codigo}' ya existe en la base temporal."
                    ],
                    "campos_adicionales": []
                })

            else:

                # Conservamos los registros que pueden insertarse.
                registros_validos_filtrados.append(registro)

        # Actualizamos la lista de registros correctos.
        registros_validos = registros_validos_filtrados

        # Preparamos la consulta para insertar registros inválidos.
        consulta_invalidos = """
            INSERT INTO registros_invalidos (
                numero_registro,
                codigo_caso,
                estado,
                descripcion,
                fecha_prevista,
                prioridad,
                fecha_apertura,
                errores,
                campos_adicionales
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        # Insertamos un registro inválido y conservamos su identificador.
        def insertar_invalido(registro):

            datos = registro["datos"]

            valores = (
                registro["numero_registro"],
                datos.get("ID") or None,
                datos.get("Estado") or None,
                datos.get("Descripción") or None,
                datos.get("Fecha prevista") or None,
                datos.get("Prioridad") or None,
                datos.get("Fecha/hora de apertura") or None,
                json.dumps(registro["errores"], ensure_ascii=False),
                json.dumps(
                    registro.get("campos_adicionales", []),
                    ensure_ascii=False
                )
            )

            cursor.execute(consulta_invalidos, valores)
            ids_invalidos.append(cursor.lastrowid)

        # Guardamos primero todos los registros inválidos detectados.
        for registro in registros_invalidos:
            insertar_invalido(registro)

        # Confirmamos los registros inválidos independientemente de los correctos.
        if registros_invalidos:
            conexion.commit()

        # Preparamos la consulta para insertar casos correctos.
        consulta_casos = """
            INSERT INTO casos_temporales (
                codigo_caso,
                estado,
                descripcion,
                prioridad,
                fecha_apertura,
                fecha_inicio_gestion,
                fecha_vencimiento,
                observaciones
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        # Insertamos los casos correctos individualmente.
        for registro in registros_validos:

            try:

                # Obtenemos la fecha original de apertura.
                fecha_apertura = registro["Fecha/hora de apertura"]

                # Convertimos la fecha original a un objeto datetime.
                fecha_apertura_datetime = datetime.strptime(
                    fecha_apertura,
                    FORMATO_FECHA
                )

                # Calculamos cuándo debe comenzar la gestión del caso.
                fecha_inicio, observacion = calcular_fecha_inicio_gestion(
                    fecha_apertura,
                    festivos
                )

                # Calculamos el vencimiento acumulando 8 horas hábiles.
                fecha_vencimiento = calcular_fecha_vencimiento(
                    fecha_inicio,
                    festivos
                )

                # Organizamos los valores que se insertarán en MySQL.
                valores = (
                    registro["ID"],
                    registro["Estado"],
                    registro["Descripción"],
                    registro["Prioridad"],
                    fecha_apertura_datetime,
                    fecha_inicio,
                    fecha_vencimiento,
                    observacion
                )

                # Insertamos individualmente el caso correcto.
                cursor.execute(consulta_casos, valores)

                # Confirmamos este caso para protegerlo de errores posteriores.
                conexion.commit()

                # Guardamos el código del caso insertado correctamente.
                codigos_validos.append(registro["ID"])

            except Exception as error:

                # Revertimos únicamente la operación que acaba de fallar.
                conexion.rollback()

                # Convertimos el registro fallido en un registro inválido.
                registro_invalido = {
                    "numero_registro": registro["numero_registro"],
                    "datos": {
                        "ID": registro["ID"],
                        "Estado": registro["Estado"],
                        "Descripción": registro["Descripción"],
                        "Fecha prevista": registro["Fecha prevista"],
                        "Prioridad": registro["Prioridad"],
                        "Fecha/hora de apertura": registro["Fecha/hora de apertura"]
                    },
                    "errores": [
                        f"No fue posible insertar el caso: {error}"
                    ],
                    "campos_adicionales": []
                }

                # Guardamos el registro fallido en la tabla de inválidos.
                insertar_invalido(registro_invalido)

                # Confirmamos su almacenamiento.
                conexion.commit()

                # Aumentamos el total de registros inválidos.
                total_invalidos += 1

        # Calculamos la cantidad total de registros inválidos almacenados.
        total_invalidos += len(registros_invalidos)

        # Devolvemos las cantidades y los identificadores de esta carga.
        return {
            "validos": len(codigos_validos),
            "invalidos": total_invalidos,
            "codigos_validos": codigos_validos,
            "ids_invalidos": ids_invalidos
        }

    except Exception as error:

        # Revertimos únicamente las operaciones que sigan sin confirmar.
        if conexion is not None and conexion.is_connected():
            conexion.rollback()

        # Informamos que no fue posible completar el almacenamiento.
        raise RuntimeError(
            f"No fue posible almacenar los registros: {error}"
        ) from error

    finally:

        # Cerramos el cursor si llegó a crearse.
        if cursor is not None:
            cursor.close()

        # Cerramos la conexión si llegó a establecerse.
        if conexion is not None and conexion.is_connected():
            conexion.close()

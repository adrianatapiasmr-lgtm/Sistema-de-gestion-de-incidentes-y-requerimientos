
# Importamos las herramientas para manejar fechas, horas y duraciones.
from datetime import datetime, timedelta

# Importamos la conexión con la base de datos principal.
from conexion import conectar_principal


def recomendar_tecnicos(codigo_caso):
    """
    Consulta la disponibilidad de los técnicos y genera un ranking
    para el caso indicado, sin guardar ninguna asignación.
    """

    conexion = None
    cursor = None

    try:
        # Obtenemos la fecha y hora actuales.
        # ahora = datetime.now()
        # Simulamos un martes a las 10:00 a. m. para probar el algoritmo.
        # ahora = datetime(2026, 11, 24, 10, 0)
        ahora = datetime.now()


        # Convertimos el día actual al nombre utilizado en MySQL.
        dias_semana = {
            0: "Lunes",
            1: "Martes",
            2: "Miércoles",
            3: "Jueves",
            4: "Viernes",
            5: "Sábado",
            6: "Domingo"
        }

        # Obtenemos el día y la fecha de la simulación.
        dia_actual = dias_semana[ahora.weekday()]
        fecha_actual = ahora.date()

        # Convertimos la hora actual a una duración para compararla
        # correctamente con los valores TIME que devuelve MySQL.
        hora_actual = timedelta(
            hours=ahora.hour,
            minutes=ahora.minute,
            seconds=ahora.second
        )

        # Conectamos con la base de datos principal.
        conexion = conectar_principal()

        # Creamos un cursor con resultados almacenados en búfer.
        cursor = conexion.cursor(dictionary=True, buffered=True)

        # Consultamos el caso que se desea asignar.
        cursor.execute("""
            SELECT
                c.codigo_caso,
                c.nombre_sede,
                c.es_vip,
                c.estado
            FROM casos c
            LEFT JOIN asignaciones a
                ON c.codigo_caso = a.codigo_caso
            WHERE c.codigo_caso = %s
              AND c.estado = 'Activo'
              AND a.codigo_caso IS NULL
        """, (codigo_caso,))

        caso = cursor.fetchone()

        # Comprobamos que el caso siga pendiente de asignación.
        if not caso:
            return {
                "exito": False,
                "mensaje": "El caso no existe o ya no está pendiente de asignación.",
                "recomendaciones": []
            }

        # Comprobamos si la fecha actual corresponde a un festivo.
        cursor.execute("""
            SELECT id_festivo
            FROM festivos
            WHERE fecha = %s
        """, (fecha_actual,))

        festivo = cursor.fetchone()

        # Si es festivo, ningún técnico puede recibir asignaciones.
        if festivo:
            return {
                "exito": False,
                "mensaje": "Hoy es festivo. No hay técnicos disponibles para asignación.",
                "recomendaciones": []
            }

        # Consultamos los técnicos activos de la sede del caso,
        # sus horarios del día y la cantidad total de casos asignados.
        cursor.execute("""
            SELECT
                t.id_tecnico,
                t.nombre,
                t.es_vip,
                t.id_sede,
                s.nombre_sede,
                h.hora_inicio,
                h.hora_fin,
                COUNT(a.id_asignacion) AS carga
            FROM tecnicos t
            INNER JOIN sedes s
                ON t.id_sede = s.id_sede
            LEFT JOIN horarios_tecnicos h
                ON t.id_tecnico = h.id_tecnico
               AND h.dia_semana = %s
            LEFT JOIN asignaciones a
                ON t.id_tecnico = a.id_tecnico
            WHERE t.activo = TRUE
              AND s.nombre_sede = %s
            GROUP BY
                t.id_tecnico,
                t.nombre,
                t.es_vip,
                t.id_sede,
                s.nombre_sede,
                h.hora_inicio,
                h.hora_fin
            ORDER BY t.nombre ASC
        """, (dia_actual, caso["nombre_sede"]))

        tecnicos = cursor.fetchall()

        # Filtramos los técnicos que tienen horario vigente
        # y que todavía no alcanzan su capacidad máxima.
        disponibles = []

        for tecnico in tecnicos:

            # Comprobamos que tenga horario registrado para hoy.
            if not tecnico["hora_inicio"] or not tecnico["hora_fin"]:
                continue

            # Comprobamos que la hora actual esté dentro de su jornada.
            if not (
                tecnico["hora_inicio"] <= hora_actual < tecnico["hora_fin"]
            ):
                continue

            # No permitimos superar los diez casos asignados.
            if tecnico["carga"] >= 10:
                continue

            disponibles.append(tecnico)

        # Separamos los técnicos normales y VIP.
        normales = [
            tecnico for tecnico in disponibles
            if not bool(tecnico["es_vip"])
        ]

        vip = [
            tecnico for tecnico in disponibles
            if bool(tecnico["es_vip"])
        ]

        # Determinamos si los técnicos VIP pueden apoyar casos normales.
        permitir_apoyo_vip = any(
            tecnico["carga"] >= 9
            for tecnico in tecnicos
            if not bool(tecnico["es_vip"])
        )

        # Definimos los técnicos candidatos según el tipo de caso.
        if bool(caso["es_vip"]):

            # Los casos VIP solamente pueden asignarse a técnicos VIP.
            candidatos = vip

        else:

            # Los casos normales priorizan técnicos normales.
            candidatos = normales.copy()

            # Los VIP pueden apoyar cuando algún técnico normal
            # alcanza nueve casos asignados.
            if permitir_apoyo_vip:
                candidatos.extend(vip)

        # Ordenamos los candidatos desde la menor carga hasta la mayor.
        candidatos.sort(
            key=lambda tecnico: (
                tecnico["carga"],
                tecnico["nombre"]
            )
        )

        # Preparamos el ranking con la información necesaria para mostrarlo.
        recomendaciones = []

        for posicion, tecnico in enumerate(candidatos, start=1):

            recomendaciones.append({
                "posicion": posicion,
                "id_tecnico": tecnico["id_tecnico"],
                "id_sede": tecnico["id_sede"],
                "nombre": tecnico["nombre"],
                "es_vip": bool(tecnico["es_vip"]),
                "nombre_sede": tecnico["nombre_sede"],
                "carga": tecnico["carga"]
            })

        # Informamos si se encontraron técnicos disponibles.
        if not recomendaciones:
            mensaje = "No hay técnicos disponibles que cumplan las condiciones de asignación."
        else:
            mensaje = "Se generó el ranking de técnicos disponibles."

        return {
            "exito": True,
            "mensaje": mensaje,
            "recomendaciones": recomendaciones
        }

    except Exception as error:

        # Mostramos el error en la consola para facilitar su revisión.
        print(f"Error al generar recomendaciones: {error}")

        return {
            "exito": False,
            "mensaje": "No fue posible generar las recomendaciones.",
            "recomendaciones": []
        }

    finally:

        # Cerramos el cursor y la conexión si fueron creados.
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()

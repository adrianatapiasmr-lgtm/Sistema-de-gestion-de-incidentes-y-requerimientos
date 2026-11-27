DROP DATABASE mesa_servicio_v2; -> eliminar x DB
DROP DATABASE mesa_servicio_temporal; -> eliminar x DB

CREATE DATABASE IF NOT EXISTS mesa_servicio -> creación DB ignorando que ya exista

CREATE DATABASE mesa_servicio -> creación DB

USE mesa_servicio_v2;

SELECT
    codigo_caso,
    fecha_apertura,
    fecha_inicio_gestion,
    fecha_vencimiento
FROM casos
WHERE codigo_caso = 'PRUEBA001';


USE mesa_servicio_temporal;

SELECT *
FROM casos
WHERE codigo_caso = 'PRUEBA001';

USE mesa_servicio_temporal;

DESCRIBE registros_invalidos;

SELECT
    TABLE_SCHEMA,
    TABLE_NAME,
    COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'mesa_servicio_v2'
  AND TABLE_NAME = 'casos'
ORDER BY ORDINAL_POSITION;

SHOW CREATE TABLE casos;

USE mesa_servicio_v2;

-- Técnicos de prueba para la sede con ID 1.
INSERT INTO tecnicos (nombre, es_vip, activo, id_sede)
VALUES
    ('Carlos Pérez', FALSE, TRUE, 1),
    ('Adriana Tapias', TRUE, TRUE, 1),
    ('Andrés Ruiz', FALSE, FALSE, 1);

-- Técnicos de prueba para la sede con ID 2.
INSERT INTO tecnicos (nombre, es_vip, activo, id_sede)
VALUES
    ('Diana Torres', FALSE, TRUE, 2),
    ('Joel Villa', TRUE, TRUE, 2);


SELECT * FROM asignaciones;

SELECT codigo_caso, estado
FROM casos
WHERE codigo_caso = 'PRUEBA-ASIG-002';

USE mesa_servicio_v2;

-- Insertamos dos casos de prueba pendientes de asignación.
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
VALUES
(
    'PRUEBA-ASIG-031',
    'Activo',
    'Error al iniciar sesión en el sistema.',
    'Alta',
    NOW(),
    NOW(),
    DATE_ADD(NOW(), INTERVAL 8 HOUR),
    FALSE,
    'Sede Norte',
    'Caso de prueba para asignación manual.'
),
(
    'PRUEBA-ASIG-042',
    'Activo',
    'Problema de conexión con la red corporativa.',
    'Media',
    NOW(),
    NOW(),
    DATE_ADD(NOW(), INTERVAL 8 HOUR),
    TRUE,
    'Sede Centro',
    'Caso de prueba para asignación manual.'
);

USE mesa_servicio_v2;

-- Insertamos un caso normal de prueba para Sede Centro.
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
VALUES (
    'PRUEBA-ASIG-053',
    'Activo',
    'Prueba de asignación automática para un caso normal.',
    'Media',
    NOW(),
    NOW(),
    DATE_ADD(NOW(), INTERVAL 8 HOUR),
    FALSE,
    'Sede Centro',
    'Caso creado manualmente para validar el ranking de técnicos.'
);

SELECT
    t.id_tecnico,
    t.nombre,
    t.es_vip,
    t.activo,
    COUNT(a.id_asignacion) AS carga
FROM tecnicos t
INNER JOIN sedes s
    ON t.id_sede = s.id_sede
LEFT JOIN asignaciones a
    ON t.id_tecnico = a.id_tecnico
WHERE s.nombre_sede = 'Sede Centro'
GROUP BY
    t.id_tecnico,
    t.nombre,
    t.es_vip,
    t.activo
ORDER BY t.nombre;


USE mesa_servicio_v2;

-- Comparamos los horarios y datos de las técnicas de Sede Centro.
SELECT
    t.id_tecnico,
    t.nombre,
    t.es_vip,
    t.activo,
    s.nombre_sede,
    h.dia_semana,
    h.hora_inicio,
    h.hora_fin
FROM tecnicos t
INNER JOIN sedes s
    ON t.id_sede = s.id_sede
LEFT JOIN horarios_tecnicos h
    ON t.id_tecnico = h.id_tecnico
WHERE s.nombre_sede = 'Sede Centro'
  AND t.nombre IN ('Diana Torres', 'Laura Méndez')
ORDER BY t.nombre, h.dia_semana;

USE mesa_servicio_v2;

-- Registramos una nueva técnica normal para Sede Centro.
INSERT INTO tecnicos (
    nombre,
    es_vip,
    activo,
    id_sede
)
VALUES (
    'Madinson Villa',
    TRUE,
    FALSE,
    3
);

USE mesa_servicio_v2;

-- Registramos los horarios laborales de Laura Méndez.
INSERT INTO horarios_tecnicos (
    id_tecnico,
    dia_semana,
    hora_inicio,
    hora_fin
)
VALUES
    (6, 'Lunes',     '06:00:00', '18:00:00'),
    (6, 'Martes',    '06:00:00', '18:00:00'),
    (6, 'Miércoles','06:00:00', '18:00:00'),
    (6, 'Jueves',    '06:00:00', '18:00:00'),
    (6, 'Viernes',   '06:00:00', '18:00:00');
    
    USE mesa_servicio_v2;

-- Creamos un caso VIP para comprobar la selección exclusiva de técnicos VIP.
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
VALUES (
    'PRUEBA-ASIG-035',
    'Activo',
    'Prueba de asignación automática para un caso VIP.',
    'Alta',
    NOW(),
    NOW(),
    DATE_ADD(NOW(), INTERVAL 8 HOUR),
    TRUE,
    'Sede Centro',
    'Caso creado para comprobar la asignación exclusiva a técnicos VIP.'
);
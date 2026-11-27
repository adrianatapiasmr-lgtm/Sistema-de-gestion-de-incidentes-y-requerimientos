-- tabla de casos, BD que almacena toda la info de los casos

-- Creamos la base de datos de la nueva versión.
CREATE DATABASE IF NOT EXISTS mesa_servicio_v2
CHARACTER SET utf8mb4
COLLATE utf8mb4_0900_ai_ci;

-- Seleccionamos la base de datos.
USE mesa_servicio_v2;

-- Creamos la tabla de sedes.
CREATE TABLE IF NOT EXISTS sedes (

    -- Identificador único de la sede.
    id_sede INT AUTO_INCREMENT PRIMARY KEY,

    -- Nombre de la sede.
    nombre_sede VARCHAR(100) NOT NULL UNIQUE,

    -- Descripción opcional de la sede.
    descripcion VARCHAR(255) NULL

);

-- Registramos las sedes disponibles para los casos.
INSERT INTO sedes (nombre_sede)
VALUES
    ('Sede Norte'),
    ('Sede Centro'),
    ('Sede Sur');

-- Creamos la tabla de técnicos.
CREATE TABLE IF NOT EXISTS tecnicos (

    -- Identificador único del técnico.
    id_tecnico INT AUTO_INCREMENT PRIMARY KEY,

    -- Nombre completo del técnico.
    nombre VARCHAR(150) NOT NULL,

    -- Indica si el técnico puede recibir casos VIP.
    es_vip BOOLEAN NOT NULL DEFAULT FALSE,

    -- Indica si el técnico está habilitado para recibir asignaciones.
    activo BOOLEAN NOT NULL DEFAULT TRUE,

    -- Sede a la que pertenece el técnico.
    id_sede INT NOT NULL,

    -- Relacionamos el técnico con su sede.
    FOREIGN KEY (id_sede) REFERENCES sedes(id_sede)

);

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


-- Creamos la tabla de horarios de los técnicos.
CREATE TABLE IF NOT EXISTS horarios_tecnicos (

    -- Identificador único del horario.
    id_horario INT AUTO_INCREMENT PRIMARY KEY,

    -- Técnico al que pertenece el horario.
    id_tecnico INT NOT NULL,

    -- Día de la semana.
    dia_semana ENUM(
        'Lunes',
        'Martes',
        'Miércoles',
        'Jueves',
        'Viernes'
    ) NOT NULL,

    -- Hora de inicio de la jornada.
    hora_inicio TIME NOT NULL,

    -- Hora de finalización de la jornada.
    hora_fin TIME NOT NULL,

    -- Un técnico solamente puede tener un horario por día.
    UNIQUE (id_tecnico, dia_semana),

    -- La hora de finalización debe ser posterior al inicio.
    CHECK (hora_fin > hora_inicio),

    -- Relacionamos el horario con su técnico.
    FOREIGN KEY (id_tecnico) REFERENCES tecnicos(id_tecnico)

);

-- Insertamos horarios de lunes a viernes para los cinco técnicos.
INSERT INTO horarios_tecnicos (
    id_tecnico,
    dia_semana,
    hora_inicio,
    hora_fin
)
VALUES
-- Carlos Pérez (ID 1).
(1, 'Lunes', '06:00:00', '18:00:00'),
(1, 'Martes', '06:00:00', '18:00:00'),
(1, 'Miércoles', '06:00:00', '18:00:00'),
(1, 'Jueves', '06:00:00', '18:00:00'),
(1, 'Viernes', '06:00:00', '18:00:00'),

-- Adriana Tapias (ID 2).
(2, 'Lunes', '06:00:00', '18:00:00'),
(2, 'Martes', '06:00:00', '18:00:00'),
(2, 'Miércoles', '06:00:00', '18:00:00'),
(2, 'Jueves', '06:00:00', '18:00:00'),
(2, 'Viernes', '06:00:00', '18:00:00'),

-- Andrés Ruiz (ID 3).
(3, 'Lunes', '06:00:00', '18:00:00'),
(3, 'Martes', '06:00:00', '18:00:00'),
(3, 'Miércoles', '06:00:00', '18:00:00'),
(3, 'Jueves', '06:00:00', '18:00:00'),
(3, 'Viernes', '06:00:00', '18:00:00'),

-- Diana Torres (ID 4).
(4, 'Lunes', '06:00:00', '18:00:00'),
(4, 'Martes', '06:00:00', '18:00:00'),
(4, 'Miércoles', '06:00:00', '18:00:00'),
(4, 'Jueves', '06:00:00', '18:00:00'),
(4, 'Viernes', '06:00:00', '18:00:00'),

-- Joel Villa (ID 5).
(5, 'Lunes', '06:00:00', '18:00:00'),
(5, 'Martes', '06:00:00', '18:00:00'),
(5, 'Miércoles', '06:00:00', '18:00:00'),
(5, 'Jueves', '06:00:00', '18:00:00'),
(5, 'Viernes', '06:00:00', '18:00:00');

-- Creamos la tabla de casos.
CREATE TABLE IF NOT EXISTS casos (

    -- Identificador único del caso.
    codigo_caso VARCHAR(30) PRIMARY KEY,

    -- Estado actual del caso.
    estado ENUM(
        'Activo',
        'Asignado',
        'Pendiente del cliente',
        'Vencido',
        'Garantia',
        'Solucionado',
        'Completado'
    ) NOT NULL DEFAULT 'Activo',

    -- Descripción del caso.
    descripcion TEXT NOT NULL,

    -- Prioridad del caso.
    prioridad VARCHAR(30) NOT NULL,

    -- Fecha original de apertura.
    fecha_apertura DATETIME NOT NULL,

    -- Inicio del conteo de las horas hábiles.
    fecha_inicio_gestion DATETIME NOT NULL,

    -- Fecha límite calculada por Python.
    fecha_vencimiento DATETIME NOT NULL,

    -- Indica si el caso es VIP.
	es_vip BOOLEAN NOT NULL,

    -- Nombre de la sede a la que pertenece el caso.
    nombre_sede VARCHAR(100) NOT NULL,

    -- Observaciones generales.
    observaciones TEXT NULL,

    -- Fecha de registro en la base de datos.
    fecha_registro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Índices para facilitar las consultas.
    INDEX idx_estado (estado),
    INDEX idx_fecha_apertura (fecha_apertura),
    INDEX idx_fecha_vencimiento (fecha_vencimiento),
    INDEX idx_nombre_sede (nombre_sede)

);

-- Creamos la tabla de asignaciones.
CREATE TABLE IF NOT EXISTS asignaciones (

    -- Identificador único de la asignación.
    id_asignacion INT AUTO_INCREMENT PRIMARY KEY,

    -- Código del caso asignado.
    codigo_caso VARCHAR(30) NOT NULL UNIQUE,

    -- Técnico responsable del caso.
    id_tecnico INT NOT NULL,

    -- Fecha y hora en que se realizó la asignación.
    fecha_asignacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Relacionamos la asignación con su caso.
    FOREIGN KEY (codigo_caso) REFERENCES casos(codigo_caso),

    -- Relacionamos la asignación con su técnico.
    FOREIGN KEY (id_tecnico) REFERENCES tecnicos(id_tecnico)

);


-- Crear tabla de festivos
-- USE mesa_servicio_v2;

-- tabla festivos
CREATE TABLE IF NOT EXISTS festivos (
    id_festivo INT AUTO_INCREMENT PRIMARY KEY,
    fecha DATE NOT NULL UNIQUE,
    descripcion VARCHAR(100) NOT NULL
);

-- Inserción de días  festivos 2026 y 2027
INSERT INTO festivos (fecha, descripcion) VALUES
('2026-01-01', 'Año Nuevo'),
('2026-01-12', 'Día de los Reyes Magos'),
('2026-03-23', 'Día de San José'),
('2026-04-02', 'Jueves Santo'),
('2026-04-03', 'Viernes Santo'),
('2026-05-01', 'Día del Trabajo'),
('2026-05-18', 'Día de la Ascensión'),
('2026-06-08', 'Corpus Christi'),
('2026-06-15', 'Sagrado Corazón de Jesús'),
('2026-06-29', 'San Pedro y San Pablo'),
('2026-07-09', 'Nuestra Señora del Rosario de Chiquinquirá'),
('2026-07-20', 'Día de la Independencia'),
('2026-08-07', 'Batalla de Boyacá'),
('2026-08-17', 'Asunción de la Virgen'),
('2026-10-12', 'Día de la Diversidad Étnica y Cultural'),
('2026-11-02', 'Día de Todos los Santos'),
('2026-11-16', 'Independencia de Cartagena'),
('2026-12-08', 'Inmaculada Concepción'),
('2026-12-25', 'Navidad');
INSERT INTO festivos (fecha, descripcion) VALUES
('2027-01-01', 'Año Nuevo'),
('2027-01-11', 'Día de los Reyes Magos'),
('2027-03-22', 'Día de San José'),
('2027-03-25', 'Jueves Santo'),
('2027-03-26', 'Viernes Santo'),
('2027-05-01', 'Día del Trabajo'),
('2027-05-10', 'Día de la Ascensión'),
('2027-05-31', 'Corpus Christi'),
('2027-06-07', 'Sagrado Corazón de Jesús'),
('2027-07-05', 'San Pedro y San Pablo'),
('2027-07-12', 'Nuestra Señora del Rosario de Chiquinquirá'),
('2027-07-20', 'Día de la Independencia'),
('2027-08-07', 'Batalla de Boyacá'),
('2027-08-16', 'Asunción de la Virgen'),
('2027-10-18', 'Día de la Diversidad Étnica y Cultural'),
('2027-11-01', 'Día de Todos los Santos'),
('2027-11-15', 'Independencia de Cartagena'),
('2027-12-08', 'Inmaculada Concepción'),
('2027-12-25', 'Navidad');

-- Creamos la tabla para almacenar las credenciales de acceso.
CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(50) NOT NULL UNIQUE,
    contrasena VARCHAR(255) NOT NULL,
    rol VARCHAR(50) NOT NULL
);

-- Registramos el usuario inicial del sistema.
INSERT INTO usuarios (usuario, contrasena, rol)
VALUES (
    'Adriana',
    '1234',
    'Administrador'
);

-- CONSULTA: COMPROBAR LA ESTRUCTURA

DESCRIBE casos;

-- comprobar casos en la BD
USE mesa_servicio_v2;

USE mesa_servicio_v2;

SELECT
    id,
    CONCAT('[', usuario, ']') AS usuario,
    CONCAT('[', contrasena, ']') AS contrasena,
    rol,
    LENGTH(usuario) AS longitud_usuario,
    LENGTH(contrasena) AS longitud_contrasena
FROM usuarios;

-- Comprobar los técnicos registrados.
SELECT * FROM tecnicos;

-- Comprobar las sedes registradas.
SELECT * FROM sedes;

SELECT
    codigo_caso,
    estado,
    fecha_apertura,
    fecha_inicio_gestion,
    fecha_vencimiento,
    observaciones
FROM casos;

# ver todos los casos literal lol

USE mesa_servicio_v2;

DESCRIBE sedes;

-- Consultamos las tablas existentes.
SHOW TABLES;

SHOW INDEX FROM asignaciones;

SELECT
    codigo_caso,
    es_vip,
    nombre_sede,
    observaciones
FROM casos;
DESCRIBE casos;

SELECT
    CONSTRAINT_NAME,
    COLUMN_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'mesa_servicio_v2'
  AND TABLE_NAME = 'casos'
  AND COLUMN_NAME = 'id_sede';
  
  
SELECT
    t.nombre,
    s.nombre_sede,
    h.dia_semana,
    h.hora_inicio,
    h.hora_fin
FROM horarios_tecnicos h
INNER JOIN tecnicos t
    ON h.id_tecnico = t.id_tecnico
INNER JOIN sedes s
    ON t.id_sede = s.id_sede
ORDER BY t.id_tecnico, h.id_horario;

USE mesa_servicio_v2;

SELECT
    codigo_caso,
    estado
FROM casos
WHERE codigo_caso = 'mrprpy';

SELECT
    id_asignacion,
    codigo_caso,
    id_tecnico,
    fecha_asignacion
FROM asignaciones
WHERE codigo_caso = 'mrprpy';

SELECT
    a.id_asignacion,
    a.codigo_caso,
    t.nombre AS tecnico_asignado,
    a.fecha_asignacion,
    c.estado
FROM asignaciones a
INNER JOIN tecnicos t
    ON a.id_tecnico = t.id_tecnico
INNER JOIN casos c
    ON a.codigo_caso = c.codigo_caso
WHERE a.codigo_caso = 'PRUEBA-ASIG-031';


SELECT
    COUNT(*) AS total_asignaciones,
    SUM(c.estado <> 'Completado') AS casos_no_completados,
    SUM(c.estado = 'Completado') AS casos_completados
FROM asignaciones a
INNER JOIN casos c
    ON a.codigo_caso = c.codigo_caso;
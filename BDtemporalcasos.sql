-- La base de datos temporal


-- Creamos la base de datos temporal.
CREATE DATABASE IF NOT EXISTS mesa_servicio_temporal
CHARACTER SET utf8mb4
COLLATE utf8mb4_0900_ai_ci;

-- Seleccionamos la base de datos temporal.
USE mesa_servicio_temporal;

-- Creamos la tabla temporal de casos.
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
    -- Se completa manualmente durante la importación.
    es_vip BOOLEAN NULL,

    -- Nombre de la sede del caso.
    -- Se completa manualmente durante la importación.
    nombre_sede VARCHAR(100) NULL,

    -- Observaciones generales.
    observaciones TEXT NULL,

    -- Fecha de registro en la base de datos.
    fecha_registro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Índices para facilitar las consultas.
    INDEX idx_estado (estado),
    INDEX idx_fecha_apertura (fecha_apertura),
    INDEX idx_fecha_vencimiento (fecha_vencimiento)

);

-- Creamos la tabla para conservar los registros inválidos.
CREATE TABLE IF NOT EXISTS registros_invalidos (

    -- Identificador interno único de cada registro.
    id_registro INT AUTO_INCREMENT PRIMARY KEY,

    -- Número del registro dentro del archivo CSV.
    numero_registro INT NOT NULL,

    -- Datos originales recibidos desde el CSV.
    codigo_caso VARCHAR(30) NULL,
    estado VARCHAR(50) NULL,
    descripcion TEXT NULL,
    fecha_prevista VARCHAR(50) NULL,
    prioridad VARCHAR(30) NULL,
    fecha_apertura VARCHAR(50) NULL,
    
        -- Clasificación VIP del registro.
    -- Se completa manualmente cuando se corrige el registro.
    es_vip BOOLEAN NULL,

    -- Sede correspondiente al registro.
    -- Se completa manualmente cuando se corrige el registro.
    nombre_sede VARCHAR(100) NULL,

    -- Errores detectados durante la validación.
    errores JSON NOT NULL,

    -- Campos adicionales encontrados en el registro.
    campos_adicionales JSON NULL,

    -- Fecha y hora en que se almacenó el registro.
    fecha_registro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP

);


-- Creamos tabla de festivos
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

-- Comprobamos la estructura de la tabla.
DESCRIBE casos;

-- mirar contenido base de datos
USE mesa_servicio_temporal;

SELECT
    codigo_caso,
    estado,
    fecha_apertura,
    fecha_inicio_gestion,
    fecha_vencimiento,
    observaciones
FROM casos;
# comprobar casos activos

USE mesa_servicio_temporal;
SELECT * FROM casos;
	
USE mesa_servicio_temporal;
SELECT * FROM registros_invalidos;

SELECT *
FROM festivos
ORDER BY fecha;

SELECT * FROM registros_invalidos
WHERE codigo_caso = 'IM100002';

DESCRIBE casos;

SHOW CREATE TABLE casos;
SHOW CREATE TABLE registros_invalidos;

-- ModuLab · esquema de la base de datos (SQL Server 2019 o posterior)
-- Lo ejecuta sql/crear_base.py dentro de cada base (modulab y modulab_test).
-- Es idempotente: se puede correr varias veces sin perder datos.
-- {APP_USER} lo reemplaza el script por el usuario de la aplicación.

-- Perfiles de negocio: memoria entre sesiones. Sin datos de personas.
IF OBJECT_ID(N'dbo.perfiles', N'U') IS NULL
CREATE TABLE dbo.perfiles (
    codigo_negocio      NVARCHAR(9)    NOT NULL PRIMARY KEY,          -- NEG-XXXXX
    giro                NVARCHAR(100)  NULL,
    tamano              NVARCHAR(50)   NULL,
    presupuesto         DECIMAL(12,2)  NULL,
    necesidades         NVARCHAR(MAX)  NOT NULL DEFAULT N'[]' CHECK (ISJSON(necesidades) = 1),
    modulos_previos     NVARCHAR(MAX)  NOT NULL DEFAULT N'[]' CHECK (ISJSON(modulos_previos) = 1),
    notas_no_confiables NVARCHAR(MAX)  NULL,                          -- texto del dueño: dato, nunca instrucción
    creado              DATETIME2(0)   NOT NULL DEFAULT SYSDATETIME(),
    actualizado         DATETIME2(0)   NULL,
    CONSTRAINT ck_perfiles_codigo CHECK (codigo_negocio LIKE N'NEG-_____')
);
GO

-- Copia de cada versión anterior antes de sobrescribir un perfil (recortable).
IF OBJECT_ID(N'dbo.perfiles_historial', N'U') IS NULL
CREATE TABLE dbo.perfiles_historial (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    codigo_negocio  NVARCHAR(9)   NOT NULL REFERENCES dbo.perfiles(codigo_negocio),
    perfil_json     NVARCHAR(MAX) NOT NULL CHECK (ISJSON(perfil_json) = 1),
    guardado        DATETIME2(0)  NOT NULL DEFAULT SYSDATETIME()
);
GO

IF OBJECT_ID(N'dbo.conversaciones', N'U') IS NULL
CREATE TABLE dbo.conversaciones (
    id              BIGINT IDENTITY(1,1) PRIMARY KEY,
    sesion          NVARCHAR(64)  NOT NULL,
    codigo_negocio  NVARCHAR(9)   NULL,
    rol             NVARCHAR(20)  NOT NULL CHECK (rol IN (N'dueno', N'asistente', N'sistema')),
    contenido       NVARCHAR(MAX) NOT NULL,
    momento         DATETIME2(3)  NOT NULL DEFAULT SYSDATETIME()
);
GO

IF OBJECT_ID(N'dbo.trazas', N'U') IS NULL
CREATE TABLE dbo.trazas (
    id              BIGINT IDENTITY(1,1) PRIMARY KEY,
    ejecucion_id    NVARCHAR(32)  NOT NULL,
    agente          NVARCHAR(40)  NOT NULL,
    paso            INT           NOT NULL,
    herramienta     NVARCHAR(60)  NULL,
    datos           NVARCHAR(MAX) NOT NULL CHECK (ISJSON(datos) = 1),
    momento         DATETIME2(3)  NOT NULL DEFAULT SYSDATETIME()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_trazas_ejecucion')
    CREATE INDEX ix_trazas_ejecucion ON dbo.trazas(ejecucion_id);
GO

-- Cotizaciones emitidas: acción irreversible. La aplicación solo puede insertar y leer.
IF OBJECT_ID(N'dbo.cotizaciones_emitidas', N'U') IS NULL
CREATE TABLE dbo.cotizaciones_emitidas (
    folio           NVARCHAR(20)  NOT NULL PRIMARY KEY,               -- COT-2026-0001
    codigo_negocio  NVARCHAR(9)   NULL,
    fecha           DATETIME2(0)  NOT NULL DEFAULT SYSDATETIME(),
    vigencia        DATE          NOT NULL,
    modulos         NVARCHAR(MAX) NOT NULL CHECK (ISJSON(modulos) = 1),
    total           DECIMAL(12,2) NOT NULL CHECK (total >= 0),
    hash_contenido  CHAR(64)      NOT NULL,
    estado          NVARCHAR(20)  NOT NULL DEFAULT N'emitida' CHECK (estado = N'emitida'),
    CONSTRAINT ck_cotizaciones_folio CHECK (folio LIKE N'COT-[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]%')
);
GO

IF OBJECT_ID(N'dbo.solicitudes_especiales', N'U') IS NULL
CREATE TABLE dbo.solicitudes_especiales (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    sesion          NVARCHAR(64)  NULL,
    codigo_negocio  NVARCHAR(9)   NULL,
    giro            NVARCHAR(100) NULL,
    descripcion     NVARCHAR(500) NOT NULL,                           -- nunca lleva precio
    fecha           DATETIME2(0)  NOT NULL DEFAULT SYSDATETIME()
);
GO

IF OBJECT_ID(N'dbo.seq_folios', N'SO') IS NULL
    CREATE SEQUENCE dbo.seq_folios AS INT START WITH 1 INCREMENT BY 1 NO CYCLE;
GO

-- Permisos del usuario de la aplicación ------------------------------------------
GRANT SELECT, INSERT, UPDATE ON dbo.perfiles               TO [{APP_USER}];
GRANT SELECT, INSERT         ON dbo.perfiles_historial     TO [{APP_USER}];
GRANT SELECT, INSERT         ON dbo.conversaciones         TO [{APP_USER}];
GRANT SELECT, INSERT         ON dbo.trazas                 TO [{APP_USER}];
GRANT SELECT, INSERT         ON dbo.solicitudes_especiales TO [{APP_USER}];
GRANT SELECT, INSERT         ON dbo.cotizaciones_emitidas  TO [{APP_USER}];
DENY  UPDATE, DELETE         ON dbo.cotizaciones_emitidas  TO [{APP_USER}];
DENY  DELETE                 ON dbo.perfiles               TO [{APP_USER}];
DENY  DELETE                 ON dbo.perfiles_historial     TO [{APP_USER}];
GRANT UPDATE                 ON dbo.seq_folios             TO [{APP_USER}];  -- necesario para NEXT VALUE FOR
GO

-- =====================================================================
-- Proyecto Integrador - Airbnb Bogotá
-- Modelo dimensional (constelación de hechos) en PostgreSQL 12+
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS analytics;

-- ---------------------------------------------------------------------
-- DIMENSIONES
-- ---------------------------------------------------------------------

-- Dimensión Fecha (llave sustituta = AAAAMMDD, legible y estable)
CREATE TABLE analytics.dim_fecha (
    sk_fecha         INT PRIMARY KEY,                       -- formato AAAAMMDD
    fecha            DATE NOT NULL UNIQUE,
    anio             INT NOT NULL,
    trimestre        INT NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    mes              INT NOT NULL CHECK (mes BETWEEN 1 AND 12),
    dia              INT NOT NULL CHECK (dia BETWEEN 1 AND 31),
    dia_semana       VARCHAR(20) NOT NULL,
    es_fin_de_semana BOOLEAN NOT NULL
);

-- Dimensión Barrio / Localidad
CREATE TABLE analytics.dim_barrio (
    sk_barrio     BIGSERIAL PRIMARY KEY,
    nombre_barrio VARCHAR(150) NOT NULL UNIQUE,             -- llave natural
    localidad     VARCHAR(150),
    latitud_prom  NUMERIC(9,6),
    longitud_prom NUMERIC(9,6)
);

-- Dimensión Anfitrión
CREATE TABLE analytics.dim_anfitrion (
    sk_anfitrion   BIGSERIAL PRIMARY KEY,
    id_anfitrion   BIGINT NOT NULL UNIQUE,                  -- llave natural (host_id)
    nombre         VARCHAR(255),
    fecha_registro DATE,
    es_superhost   BOOLEAN
    -- SCD Tipo 2 opcional: fecha_inicio, fecha_fin, es_actual
);

-- Dimensión Listing (alojamiento)
CREATE TABLE analytics.dim_listing (
    sk_listing        BIGSERIAL PRIMARY KEY,
    id_listing        BIGINT NOT NULL UNIQUE,               -- llave natural (id)
    nombre            VARCHAR(500),
    tipo_alojamiento  VARCHAR(50)  NOT NULL,                -- room_type
    tipo_propiedad    VARCHAR(100),                         -- property_type
    capacidad         INT CHECK (capacidad IS NULL OR capacidad > 0),
    habitaciones      NUMERIC(4,1),
    camas             NUMERIC(4,1),
    calificacion      NUMERIC(5,2),                         -- review_scores_rating
    num_resenas_total INT CHECK (num_resenas_total IS NULL OR num_resenas_total >= 0),
    sk_anfitrion      BIGINT REFERENCES analytics.dim_anfitrion(sk_anfitrion)
);

-- ---------------------------------------------------------------------
-- HECHOS
-- ---------------------------------------------------------------------

-- Grano: un listing en un día específico.
-- Particionada por rango de sk_fecha (la llave de partición debe ir en la PK).
CREATE TABLE analytics.fact_calendario_diario (
    sk_listing     BIGINT NOT NULL REFERENCES analytics.dim_listing(sk_listing),
    sk_fecha       INT    NOT NULL REFERENCES analytics.dim_fecha(sk_fecha),
    sk_barrio      BIGINT REFERENCES analytics.dim_barrio(sk_barrio),
    precio         NUMERIC(14,2) NOT NULL CHECK (precio > 0),
    disponible     SMALLINT NOT NULL CHECK (disponible IN (0, 1)),
    noches_minimas INT,
    PRIMARY KEY (sk_listing, sk_fecha)
) PARTITION BY RANGE (sk_fecha);

-- Particiones mensuales (ajusten el rango a las fechas de su snapshot)
DO $$
DECLARE
    d DATE := DATE '2026-01-01';
    fin DATE := DATE '2028-01-01';
BEGIN
    WHILE d < fin LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS analytics.fact_calendario_%s
             PARTITION OF analytics.fact_calendario_diario
             FOR VALUES FROM (%s) TO (%s)',
            to_char(d, 'YYYYMM'),
            to_char(d, 'YYYYMMDD'),
            to_char(d + INTERVAL '1 month', 'YYYYMMDD')
        );
        d := (d + INTERVAL '1 month')::DATE;
    END LOOP;
END $$;

-- Partición por defecto para fechas fuera de los rangos anteriores
CREATE TABLE IF NOT EXISTS analytics.fact_calendario_default
    PARTITION OF analytics.fact_calendario_diario DEFAULT;

-- Grano: una reseña individual.
CREATE TABLE analytics.fact_resenas (
    sk_resena           BIGSERIAL PRIMARY KEY,
    id_resena           BIGINT NOT NULL UNIQUE,             -- llave natural
    sk_listing          BIGINT NOT NULL REFERENCES analytics.dim_listing(sk_listing),
    sk_fecha            INT    NOT NULL REFERENCES analytics.dim_fecha(sk_fecha),
    longitud_comentario INT CHECK (longitud_comentario IS NULL OR longitud_comentario >= 0)
);

-- ---------------------------------------------------------------------
-- ÍNDICES
-- ---------------------------------------------------------------------
CREATE INDEX idx_fcd_fecha   ON analytics.fact_calendario_diario (sk_fecha);
CREATE INDEX idx_fcd_barrio  ON analytics.fact_calendario_diario (sk_barrio);
CREATE INDEX idx_fres_listing ON analytics.fact_resenas (sk_listing);
CREATE INDEX idx_fres_fecha   ON analytics.fact_resenas (sk_fecha);
CREATE INDEX idx_listing_anfitrion ON analytics.dim_listing (sk_anfitrion);
CREATE INDEX idx_listing_tipo ON analytics.dim_listing (tipo_alojamiento);

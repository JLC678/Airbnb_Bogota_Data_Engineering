-- =====================================================================
-- Consultas de validación: una por pregunta analítica
-- =====================================================================

-- P1. Precio promedio por noche según barrio y tipo de alojamiento
SELECT b.nombre_barrio,
       l.tipo_alojamiento,
       COUNT(DISTINCT l.sk_listing)  AS num_listings,
       ROUND(AVG(f.precio), 0)       AS precio_promedio
FROM analytics.fact_calendario_diario f
JOIN analytics.dim_listing l ON l.sk_listing = f.sk_listing
JOIN analytics.dim_barrio  b ON b.sk_barrio  = f.sk_barrio
GROUP BY b.nombre_barrio, l.tipo_alojamiento
HAVING COUNT(DISTINCT l.sk_listing) >= 10          -- evita barrios con muy pocos datos
ORDER BY precio_promedio DESC
LIMIT 20;

-- P2. Estacionalidad: precio y disponibilidad por mes, fin de semana vs entre semana
-- Nota: "no disponible" mezcla reservas y bloqueos, por lo que es una ocupación aproximada.
SELECT d.anio,
       d.mes,
       d.es_fin_de_semana,
       ROUND(AVG(f.precio), 0)                        AS precio_promedio,
       ROUND(100.0 * AVG(1 - f.disponible), 1)        AS pct_no_disponible
FROM analytics.fact_calendario_diario f
JOIN analytics.dim_fecha d ON d.sk_fecha = f.sk_fecha
GROUP BY d.anio, d.mes, d.es_fin_de_semana
ORDER BY d.anio, d.mes, d.es_fin_de_semana;

-- P3a. Evolución del volumen de reseñas por año y mes (indicador de demanda)
SELECT d.anio,
       d.mes,
       COUNT(*) AS num_resenas
FROM analytics.fact_resenas r
JOIN analytics.dim_fecha d ON d.sk_fecha = r.sk_fecha
GROUP BY d.anio, d.mes
ORDER BY d.anio, d.mes;

-- P3b. ¿Se relaciona ser superhost con la calificación y el volumen de reseñas?
SELECT a.es_superhost,
       COUNT(*)                         AS num_listings,
       ROUND(AVG(l.calificacion), 2)    AS calificacion_promedio,
       ROUND(AVG(l.num_resenas_total))  AS resenas_promedio
FROM analytics.dim_listing l
JOIN analytics.dim_anfitrion a ON a.sk_anfitrion = l.sk_anfitrion
GROUP BY a.es_superhost
ORDER BY a.es_superhost;

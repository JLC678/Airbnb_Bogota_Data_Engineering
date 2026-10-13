# Proyecto Integrador: Datos de Airbnb en Bogotá
Universidad Católica de Colombia · Ingeniería de Datos

## Descripción
Pipeline RAW → STAGING → ANALÍTICA con modelo dimensional en PostgreSQL.

## Datos
Fuente: Inside Airbnb (Bogotá). Enlace a Drive con los datos: https://drive.google.com/drive/folders/12A2HGIOD-kJNZb5fAIJyT2YvlNmrTJPX?usp=sharing
Notebook de Colab: https://colab.research.google.com/drive/1u2CbNlTUMVdsBOIIHmFfYdcGhD1Cksv7?usp=sharing

## Cómo ejecutarlo
1. Poner listings, calendar y reviews (.csv.gz) en RAW/
2. python pipeline_airbnb_bogota.py
3. Ejecutar ANALYTICS/ddl_airbnb_bogota.sql en PostgreSQL
4. python cargar_postgres.py
5. Ejecutar ANALYTICS/consultas_analiticas.sql

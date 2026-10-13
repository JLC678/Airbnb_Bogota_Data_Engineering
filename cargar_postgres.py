"""
Carga los CSV de STAGING al esquema analytics de PostgreSQL.

Requisitos:  pip install pandas sqlalchemy psycopg2-binary
Antes de correrlo: haber ejecutado ddl_airbnb_bogota.sql en la base de datos.

CAMBIEN la cadena de conexión (usuario, clave, puerto y nombre de la base).
"""
import pandas as pd
from sqlalchemy import create_engine, text

URL = "postgresql+psycopg2://postgres:TU_CLAVE@localhost:5432/airbnb_bogota"
STG = "STAGING"
engine = create_engine(URL)

# Vaciar las tablas antes de cargar, para poder volver a ejecutar sin errores
with engine.begin() as con:
    con.execute(text(
        "TRUNCATE analytics.fact_resenas, analytics.fact_calendario_diario, "
        "analytics.dim_listing, analytics.dim_anfitrion, analytics.dim_barrio, "
        "analytics.dim_fecha RESTART IDENTITY CASCADE"))
print("Tablas vaciadas. Iniciando carga...")

# Orden obligatorio: primero dimensiones, luego hechos (por las llaves foráneas)
DIMENSIONES = [
    ("dim_fecha", ["fecha"]),
    ("dim_barrio", []),
    ("dim_anfitrion", ["fecha_registro"]),
    ("dim_listing", []),
]

for tabla, fechas in DIMENSIONES:
    df = pd.read_csv(f"{STG}/{tabla}.csv", parse_dates=fechas)
    df.to_sql(tabla, engine, schema="analytics", if_exists="append", index=False,
              chunksize=10_000, method="multi")
    print(f"{tabla}: {len(df):,} filas cargadas")

# Hechos: el calendario es grande, se carga por bloques
total = 0
for bloque in pd.read_csv(f"{STG}/fact_calendario_diario.csv", chunksize=100_000):
    bloque.to_sql("fact_calendario_diario", engine, schema="analytics",
                  if_exists="append", index=False, chunksize=10_000, method="multi")
    total += len(bloque)
    print(f"fact_calendario_diario: {total:,} filas...", end="\r")
print(f"\nfact_calendario_diario: {total:,} filas cargadas")

res = pd.read_csv(f"{STG}/fact_resenas.csv")
res.to_sql("fact_resenas", engine, schema="analytics", if_exists="append",
           index=False, chunksize=10_000, method="multi")
print(f"fact_resenas: {len(res):,} filas cargadas")

# Verificación rápida: conteo por tabla
with engine.connect() as con:
    for t in ["dim_fecha", "dim_barrio", "dim_anfitrion", "dim_listing",
              "fact_calendario_diario", "fact_resenas"]:
        n = con.execute(text(f"SELECT COUNT(*) FROM analytics.{t}")).scalar()
        print(f"  analytics.{t}: {n:,}")

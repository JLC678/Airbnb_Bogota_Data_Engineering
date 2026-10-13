"""
Pipeline RAW -> STAGING  |  Proyecto Integrador - Airbnb Bogotá

Entradas (carpeta RAW):  listings.csv.gz, calendar.csv.gz, reviews.csv.gz
Salidas (carpeta STAGING): dim_fecha, dim_barrio, dim_anfitrion, dim_listing,
                           fact_calendario_diario, fact_resenas, reporte_calidad.json

Ejecutar:  python pipeline_airbnb_bogota.py
IMPORTANTE: verifiquen que los nombres de columnas coinciden con SUS archivos
(df.columns) y ajusten los diccionarios si hace falta.
"""
import json
import os

import pandas as pd

RAW = "RAW"
STG = "STAGING"
CHUNK = 500_000
os.makedirs(STG, exist_ok=True)

reporte = {}


# ---------------------------------------------------------------- utilidades
def limpiar_precio(serie: pd.Series) -> pd.Series:
    """'$1,200,000.00' -> 1200000.0  (ajusten si su archivo usa otro formato)."""
    return pd.to_numeric(
        serie.astype(str).str.replace(r"[^\d.]", "", regex=True), errors="coerce"
    )


def a_bool(serie: pd.Series) -> pd.Series:
    """'t'/'f' -> True/False (otro valor -> nulo)."""
    return serie.map({"t": True, "f": False}).astype("boolean")


def perfilar(nombre: str, df: pd.DataFrame) -> None:
    reporte[f"perfil_{nombre}"] = {
        "filas": int(len(df)),
        "columnas": int(df.shape[1]),
        "duplicados_exactos": int(df.duplicated().sum()),
        "nulos_por_columna": {c: int(n) for c, n in df.isna().sum().items() if n > 0},
    }
    print(f"[PERFIL] {nombre}: {len(df):,} filas x {df.shape[1]} columnas")


# ------------------------------------------------------------------ listings
COLS_LISTINGS = {
    "id", "name", "host_id", "host_name", "host_since", "host_is_superhost",
    "neighbourhood_cleansed", "neighbourhood_group_cleansed", "latitude",
    "longitude", "property_type", "room_type", "accommodates", "bedrooms",
    "beds", "number_of_reviews", "review_scores_rating", "price",
}
lst = pd.read_csv(f"{RAW}/listings.csv.gz", usecols=lambda c: c in COLS_LISTINGS,
                  low_memory=False)
perfilar("listings", lst)

n0 = len(lst)
lst = lst.drop_duplicates(subset="id")
lst = lst.dropna(subset=["id", "room_type", "neighbourhood_cleansed"])  # contrato
reporte["listings_rechazados"] = int(n0 - len(lst))

# Precio base del anuncio (se usa si el calendario no trae precio por día)
lst["precio_listing"] = (limpiar_precio(lst["price"]) if "price" in lst.columns
                         else float("nan"))

# -- dim_barrio
agg_barrio = {"latitude": "mean", "longitude": "mean"}
if "neighbourhood_group_cleansed" in lst.columns:
    agg_barrio["neighbourhood_group_cleansed"] = "first"
dim_barrio = (lst.groupby("neighbourhood_cleansed", as_index=False).agg(agg_barrio)
              .rename(columns={"neighbourhood_cleansed": "nombre_barrio",
                               "neighbourhood_group_cleansed": "localidad",
                               "latitude": "latitud_prom",
                               "longitude": "longitud_prom"}))
if "localidad" not in dim_barrio.columns:
    dim_barrio["localidad"] = None
dim_barrio.insert(0, "sk_barrio", range(1, len(dim_barrio) + 1))

# -- dim_anfitrion
dim_anfitrion = (lst[["host_id", "host_name", "host_since", "host_is_superhost"]]
                 .dropna(subset=["host_id"])
                 .drop_duplicates(subset="host_id")
                 .rename(columns={"host_id": "id_anfitrion", "host_name": "nombre",
                                  "host_since": "fecha_registro",
                                  "host_is_superhost": "es_superhost"}))
dim_anfitrion["fecha_registro"] = pd.to_datetime(dim_anfitrion["fecha_registro"],
                                                 errors="coerce").dt.date
dim_anfitrion["es_superhost"] = a_bool(dim_anfitrion["es_superhost"])
dim_anfitrion.insert(0, "sk_anfitrion", range(1, len(dim_anfitrion) + 1))

# -- dim_listing
dim_listing = (lst.merge(dim_anfitrion[["sk_anfitrion", "id_anfitrion"]],
                         left_on="host_id", right_on="id_anfitrion", how="left")
               .rename(columns={"id": "id_listing", "name": "nombre",
                                "room_type": "tipo_alojamiento",
                                "property_type": "tipo_propiedad",
                                "accommodates": "capacidad",
                                "bedrooms": "habitaciones", "beds": "camas",
                                "review_scores_rating": "calificacion",
                                "number_of_reviews": "num_resenas_total"}))
dim_listing = dim_listing[["id_listing", "nombre", "tipo_alojamiento", "tipo_propiedad",
                           "capacidad", "habitaciones", "camas", "calificacion",
                           "num_resenas_total", "sk_anfitrion",
                           "neighbourhood_cleansed", "precio_listing"]]
dim_listing.insert(0, "sk_listing", range(1, len(dim_listing) + 1))

# mapa listing -> (sk_listing, sk_barrio) para los hechos
mapa = (dim_listing[["sk_listing", "id_listing", "neighbourhood_cleansed",
                     "precio_listing"]]
        .merge(dim_barrio[["sk_barrio", "nombre_barrio"]],
               left_on="neighbourhood_cleansed", right_on="nombre_barrio", how="left")
        [["id_listing", "sk_listing", "sk_barrio", "precio_listing"]])
dim_listing = dim_listing.drop(columns=["neighbourhood_cleansed", "precio_listing"])

dim_barrio.to_csv(f"{STG}/dim_barrio.csv", index=False)
dim_anfitrion.to_csv(f"{STG}/dim_anfitrion.csv", index=False)
dim_listing.to_csv(f"{STG}/dim_listing.csv", index=False)

# ------------------------------------------------------------ fact_calendario
ruta_fact = f"{STG}/fact_calendario_diario.csv"
if os.path.exists(ruta_fact):
    os.remove(ruta_fact)

# Detectar qué columnas trae realmente el calendario
cols_cal = list(pd.read_csv(f"{RAW}/calendar.csv.gz", nrows=0).columns)
print("[CALENDARIO] columnas encontradas:", cols_cal)
quiero = ["listing_id", "date", "available", "price", "minimum_nights"]
usar = [c for c in quiero if c in cols_cal]
tiene_precio = "price" in cols_cal
if not tiene_precio:
    print("[AVISO] El calendario NO trae 'price': se usará el precio base del "
          "anuncio (listings.price). El precio no variará por día.")
reporte["calendario_columnas"] = cols_cal
reporte["precio_fuente"] = "calendar.price" if tiene_precio else "listings.price"

leidas = rechazadas = escritas = huerfanas = imputadas = 0
fecha_min = fecha_max = None
primero = True
for ch in pd.read_csv(f"{RAW}/calendar.csv.gz", chunksize=CHUNK, usecols=usar):
    leidas += len(ch)
    ch["fecha"] = pd.to_datetime(ch["date"], errors="coerce")
    ch["precio"] = limpiar_precio(ch["price"]) if tiene_precio else float("nan")
    ch["disponible"] = a_bool(ch["available"]).astype("float")
    n_antes = len(ch)
    ch = ch.merge(mapa, left_on="listing_id", right_on="id_listing", how="inner")
    huerfanas += n_antes - len(ch)  # filas de calendario sin listing en dim_listing

    # Si no hay precio diario, usar el precio base del anuncio
    faltante = ch["precio"].isna()
    imputadas += int(faltante.sum())
    ch["precio"] = ch["precio"].fillna(ch["precio_listing"])

    # Contrato: precio > 0, fecha válida y disponible no nulo -> si no, se rechaza
    ok = (ch["precio"] > 0) & ch["fecha"].notna() & ch["disponible"].notna()
    rechazadas += int((~ok).sum())
    ch = ch[ok].copy()
    if ch.empty:
        continue

    ch["sk_fecha"] = ch["fecha"].dt.strftime("%Y%m%d").astype(int)
    ch["disponible"] = ch["disponible"].astype(int)
    if "minimum_nights" in ch.columns:
        ch = ch.rename(columns={"minimum_nights": "noches_minimas"})
    else:
        ch["noches_minimas"] = pd.NA
    fecha_min = ch["fecha"].min() if fecha_min is None else min(fecha_min, ch["fecha"].min())
    fecha_max = ch["fecha"].max() if fecha_max is None else max(fecha_max, ch["fecha"].max())

    salida = ch[["sk_listing", "sk_fecha", "sk_barrio", "precio", "disponible",
                 "noches_minimas"]].drop_duplicates(subset=["sk_listing", "sk_fecha"])
    salida.to_csv(ruta_fact, mode="a", index=False, header=primero)
    primero = False
    escritas += len(salida)

reporte["calendario"] = {"leidas": leidas, "sin_listing": huerfanas,
                       "rechazadas": rechazadas, "cargadas": escritas,
                       "precio_tomado_de_listing": imputadas}
print(f"[CALENDARIO] leidas={leidas:,} sin_listing={huerfanas:,} "
      f"rechazadas={rechazadas:,} cargadas={escritas:,}")

# ---------------------------------------------------------------- fact_resenas
rev = pd.read_csv(f"{RAW}/reviews.csv.gz", usecols=["listing_id", "id", "date", "comments"])
perfilar("reviews", rev)
n0 = len(rev)
rev["fecha"] = pd.to_datetime(rev["date"], errors="coerce")
rev = rev.drop_duplicates(subset="id").dropna(subset=["fecha"])
rev = rev.merge(mapa[["id_listing", "sk_listing"]], left_on="listing_id",
                right_on="id_listing", how="inner")
rev["sk_fecha"] = rev["fecha"].dt.strftime("%Y%m%d").astype(int)
rev["longitud_comentario"] = rev["comments"].fillna("").str.len()
fact_resenas = rev.rename(columns={"id": "id_resena"})[
    ["id_resena", "sk_listing", "sk_fecha", "longitud_comentario"]]
fact_resenas.insert(0, "sk_resena", range(1, len(fact_resenas) + 1))
fact_resenas.to_csv(f"{STG}/fact_resenas.csv", index=False)
reporte["resenas"] = {"leidas": int(n0), "cargadas": int(len(fact_resenas))}

# ------------------------------------------------------------------- dim_fecha
inicio = min(x for x in [fecha_min, rev["fecha"].min()] if x is not None)
fin = max(x for x in [fecha_max, rev["fecha"].max()] if x is not None)
fechas = pd.date_range(inicio.normalize(), fin.normalize(), freq="D")
dim_fecha = pd.DataFrame({"fecha": fechas})
dim_fecha["sk_fecha"] = dim_fecha["fecha"].dt.strftime("%Y%m%d").astype(int)
dim_fecha["anio"] = dim_fecha["fecha"].dt.year
dim_fecha["trimestre"] = dim_fecha["fecha"].dt.quarter
dim_fecha["mes"] = dim_fecha["fecha"].dt.month
dim_fecha["dia"] = dim_fecha["fecha"].dt.day
dim_fecha["dia_semana"] = dim_fecha["fecha"].dt.day_name()
dim_fecha["es_fin_de_semana"] = dim_fecha["fecha"].dt.dayofweek >= 5
dim_fecha = dim_fecha[["sk_fecha", "fecha", "anio", "trimestre", "mes", "dia",
                       "dia_semana", "es_fin_de_semana"]]
dim_fecha.to_csv(f"{STG}/dim_fecha.csv", index=False)

# --------------------------------------------------------------------- reporte
with open(f"{STG}/reporte_calidad.json", "w", encoding="utf-8") as f:
    json.dump(reporte, f, ensure_ascii=False, indent=2, default=str)
print("Pipeline terminado. Revisen STAGING/reporte_calidad.json")

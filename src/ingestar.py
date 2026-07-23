"""Convierte un archivo crudo del RNDC (.xlsx) en extracto Parquet liviano.

Parte del paso humano mensual: se ejecuta en Colab tras descargar el archivo
del portal (rndc.mintransporte.gov.co). Ver DECISIONS.md.

Uso:  python src/ingestar.py <ruta_crudos> <ruta_salida>
"""

import sys
import re
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)   # openpyxl: "no default style"

COLUMNAS = ["MES", "CONFIG_VEHICULO", "CODMUNICIPIOORIGEN", "MUNICIPIOORIGEN",
            "CODMUNICIPIODESTINO", "MUNICIPIODESTINO", "CODMERCANCIA", "MERCANCIA",
            "VIAJESTOTALES", "KILOGRAMOS", "KILOMETROS", "VALORESPAGADOS",
            "VIAJESVALORCERO", "VIAJESLIQUIDOS", "GALONES",
            "KILOMETROSREGRESO", "KILOGRAMOSREGRESO"]

NUMERICAS = ["VIAJESTOTALES", "KILOGRAMOS", "KILOMETROS", "VALORESPAGADOS",
             "VIAJESVALORCERO", "VIAJESLIQUIDOS", "GALONES"]

PATRON = re.compile(r"^EstadisticasRNDC_(\d{6})\.xlsx$")   # rechaza "…(1).xlsx"
FILAS_MINIMAS = 100_000       # los meses observados van de 166k a 203k


def validar(df, mes):
    """Verificaciones que deben pasar antes de versionar el extracto."""
    faltantes = set(COLUMNAS) - set(df.columns)
    if faltantes:
        raise RuntimeError(f"{mes}: esquema roto, faltan columnas {faltantes}")

    if len(df) < FILAS_MINIMAS:
        raise RuntimeError(f"{mes}: solo {len(df):,} filas (mínimo {FILAS_MINIMAS:,}) "
                           "— ¿descarga incompleta?")

    for col in NUMERICAS:
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise RuntimeError(f"{mes}: '{col}' no es numérica")
        if (df[col] < 0).any():
            raise RuntimeError(f"{mes}: valores negativos en '{col}' (imposible físico)")

    meses_dentro = df["MES"].unique()
    if len(meses_dentro) != 1 or str(meses_dentro[0]) != mes:
        raise RuntimeError(f"{mes}: el archivo contiene MES={meses_dentro} "
                           "— ¿archivo del mes equivocado?")

    nulos_merc = df["MERCANCIA"].isna().mean()
    if nulos_merc > 0.10:
        print(f"  ADVIERTE: {100*nulos_merc:.1f}% de MERCANCIA sin etiqueta")


def main(dir_crudos, dir_salida):
    salida = Path(dir_salida)
    salida.mkdir(parents=True, exist_ok=True)
    procesados = 0

    for ruta in sorted(Path(dir_crudos).glob("*.xlsx")):
        m = PATRON.match(ruta.name)
        if not m:
            print(f"  OMITE: {ruta.name} no calza el patrón EstadisticasRNDC_AAAAMM.xlsx")
            continue

        mes = m.group(1)
        destino = salida / f"fletes_{mes}.parquet"
        if destino.exists():
            continue                       # idempotente: no reprocesa

        print(f"Procesando {mes}...")
        df = pd.read_excel(ruta)[COLUMNAS]
        validar(df, mes)
        df.to_parquet(destino, index=False)
        print(f"  {len(df):,} filas → {destino.name} "
              f"({destino.stat().st_size/1e6:.1f} MB)")
        procesados += 1

    print(f"\nListo: {procesados} mes(es) nuevo(s) procesado(s).")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Uso: python src/ingestar.py <dir_crudos> <dir_salida>")
    main(sys.argv[1], sys.argv[2])

"""Construye el índice mensual de fletes por corredor a partir de los extractos Parquet.

Diseño en DECISIONS.md. La detección corre en modo SOMBRA: se calculan y
registran los z, pero no se emiten alertas hasta tener ~40 meses de historia.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

# ── CONTRATO v1 ──────────────────────────────────────────────────
CONFIG_PESADOS = "Tractocam"      # subcadena sin tilde (defensa contra "Tractocamión")
KM_MINIMO = 200
N_CORREDORES = 20
VOLATILIDAD_MAXIMA = 0.20         # excluye corredores con desv. de Δlog > 20%
MAD_MINIMO = 0.02                 # piso de escala (2%)
MIN_PERIODOS = 12                 # historia mínima para estimar la escala


def cargar(dir_parquet):
    archivos = sorted(Path(dir_parquet).glob("fletes_*.parquet"))
    if not archivos:
        raise RuntimeError(f"No hay extractos en {dir_parquet}")
    df = pd.concat([pd.read_parquet(f) for f in archivos], ignore_index=True)
    df["periodo"] = pd.to_datetime(df["MES"].astype(str), format="%Y%m")
    return df


def filtrar(df):
    """Filtros del contrato: pesados, con valor declarado, sin líquidos, larga distancia."""
    f = df[df["CONFIG_VEHICULO"].str.contains(CONFIG_PESADOS, case=False, na=False) &
           (df["VALORESPAGADOS"] > 0) &
           (df["VIAJESVALORCERO"] == 0) &
           (df["VIAJESLIQUIDOS"] == 0) &
           (df["KILOMETROS"] >= KM_MINIMO) &
           (df["CODMUNICIPIOORIGEN"] != df["CODMUNICIPIODESTINO"])].copy()
    f["corredor"] = f["MUNICIPIOORIGEN"] + " → " + f["MUNICIPIODESTINO"]
    return f


def flete_unitario(g):
    """$/ton-km del grupo: valor total / (toneladas × distancia de la ruta)."""
    return g["VALORESPAGADOS"].sum() / (g["KILOGRAMOS"].sum() / 1000 * g["KILOMETROS"].mean())


def construir_panel(f):
    top = (f.groupby("corredor")["VIAJESTOTALES"].sum()
           .sort_values(ascending=False).head(N_CORREDORES).index)
    sub = f[f["corredor"].isin(top)]
    panel = (sub.groupby(["periodo", "corredor"])
             .apply(flete_unitario, include_groups=False).unstack())
    viajes = (sub.groupby(["periodo", "corredor"])["VIAJESTOTALES"].sum().unstack())
    return panel, viajes


def z_sombra(resid):
    """z robusto del residuo, escala expandiente por corredor (solo pasado)."""
    def por_corredor(col):
        med = col.expanding(min_periods=MIN_PERIODOS).median().shift(1)
        mad = col.expanding(min_periods=MIN_PERIODOS).apply(
            lambda v: np.median(np.abs(v - np.median(v))), raw=False).shift(1)
        return 0.6745 * (col - med) / mad.clip(lower=MAD_MINIMO)
    return resid.apply(por_corredor)


def main():
    df = cargar("data/procesado")
    panel, viajes = construir_panel(filtrar(df))

    var = np.log(panel).diff().dropna(how="all")
    volatiles = var.std()[var.std() > VOLATILIDAD_MAXIMA].index.tolist()
    panel_v1 = panel.drop(columns=volatiles)
    var_v1 = var.drop(columns=volatiles)

    factor = var_v1.median(axis=1)                 # movimiento común del mercado
    resid = var_v1.sub(factor, axis=0)             # idiosincrático por corredor
    z = z_sombra(resid)

    ultimo = panel_v1.index[-1]
    corredores = {}
    for c in panel_v1.columns:
        corredores[c] = {
            "flete_ton_km": round(float(panel_v1.loc[ultimo, c]), 1),
            "variacion_pct": round(100 * float(var_v1.loc[ultimo, c]), 1),
            "residuo_pct": round(100 * float(resid.loc[ultimo, c]), 1),
            "viajes": int(viajes.loc[ultimo, c]),
            "z_sombra": (None if pd.isna(z.loc[ultimo, c])
                         else round(float(z.loc[ultimo, c]), 2)),
        }

    resultado = {
        "mes_analizado": ultimo.strftime("%Y-%m"),
        "meses_disponibles": len(panel_v1),
        "corredores_excluidos_por_volatilidad": volatiles,
        "factor_comun_pct": round(100 * float(factor.loc[ultimo]), 1),
        "detección": "modo sombra — sin alertas hasta ~40 meses (ver DECISIONS.md)",
        "corredores": corredores,
    }

    Path("data").mkdir(exist_ok=True)
    salida = Path("data") / f"indice_{ultimo:%Y%m}.json"
    with open(salida, "w") as fh:
        json.dump(resultado, fh, indent=2, ensure_ascii=False)

    print(f"Índice escrito en {salida} ({len(panel_v1)} meses, "
          f"{len(corredores)} corredores)")
    print(f"Factor común del mes: {resultado['factor_comun_pct']:+.1f}%")
    for c, d in sorted(corredores.items(),
                       key=lambda kv: abs(kv[1]["residuo_pct"]), reverse=True)[:5]:
        print(f"  {c[:45]:<45} {d['flete_ton_km']:>7.0f}  "
              f"var {d['variacion_pct']:+5.1f}%  resid {d['residuo_pct']:+5.1f}%")


if __name__ == "__main__":
    main()

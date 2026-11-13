"""Construye el índice mensual de fletes por corredor a partir de los extractos Parquet.

Diseño en DECISIONS.md. Desde nov 2026 el movimiento del mercado y de cada
corredor se mide sobre el PAGO POR VIAJE; el $/ton-km se conserva como nivel.
La detección corre en modo SOMBRA: se calculan y registran los z, pero no se
emiten alertas hasta tener ~40 meses de historia.

Uso:
    python src/calcular.py            # último mes disponible
    python src/calcular.py 2026-08    # un mes específico (con datos hasta ese mes)
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── CONTRATO v1 ──────────────────────────────────────────────────
CONFIG_PESADOS = "Tractocam"      # subcadena sin tilde (defensa contra "Tractocamión")
KM_MINIMO = 200
N_CORREDORES = 20
VOLATILIDAD_MAXIMA = 0.20         # excluye corredores con desv. de Δlog(pago por viaje) > 20%
CARGA_VARIABLE_MAXIMA = 0.30      # excluye corredores con desv. de Δlog(ton por viaje) > 30%:
                                  # su $/ton-km no es comparable (ver DECISIONS.md, nov 2026)
MAD_MINIMO = 0.02                 # piso de escala (2%)
MIN_PERIODOS = 12                 # historia mínima para estimar la escala
DENSIDAD_MINIMA = 10              # ton/viaje: un tractocamión con menos no transporta carga pesada creíble


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
    """Paneles mes × corredor: $/ton-km (nivel), pago por viaje, viajes y ton/viaje."""
    top = (f.groupby("corredor")["VIAJESTOTALES"].sum()
           .sort_values(ascending=False).head(N_CORREDORES).index)
    sub = f[f["corredor"].isin(top)]

    # Excluir corredores de baja densidad (carga voluminosa-ligera mal medida en $/ton-km)
    densidad = (sub.groupby("corredor")["KILOGRAMOS"].sum() / 1000 /
                sub.groupby("corredor")["VIAJESTOTALES"].sum())
    livianos = densidad[densidad < DENSIDAD_MINIMA].index.tolist()
    sub = sub[~sub["corredor"].isin(livianos)]

    g = sub.groupby(["periodo", "corredor"])
    panel = g.apply(flete_unitario, include_groups=False).unstack()
    viajes = g["VIAJESTOTALES"].sum().unstack()
    pago_viaje = (g["VALORESPAGADOS"].sum() / g["VIAJESTOTALES"].sum()).unstack()
    ton_viaje = (g["KILOGRAMOS"].sum() / 1000 / g["VIAJESTOTALES"].sum()).unstack()
    return panel, pago_viaje, viajes, ton_viaje, livianos


def z_sombra(resid):
    """z robusto del residuo, escala expandiente por corredor (solo pasado)."""
    def por_corredor(col):
        med = col.expanding(min_periods=MIN_PERIODOS).median().shift(1)
        mad = col.expanding(min_periods=MIN_PERIODOS).apply(
            lambda v: np.median(np.abs(v - np.median(v))), raw=False).shift(1)
        return 0.6745 * (col - med) / mad.clip(lower=MAD_MINIMO)
    return resid.apply(por_corredor)


def main(mes=None):
    df = cargar("data/procesado")
    if mes:
        corte = pd.Timestamp(f"{mes}-01")
        if corte not in set(df["periodo"]):
            raise RuntimeError(f"No hay datos para {mes}")
        df = df[df["periodo"] <= corte]          # el índice de un mes usa solo datos hasta ese mes

    panel, pago_viaje, viajes, ton_viaje, livianos = construir_panel(filtrar(df))

    # El movimiento se mide sobre el pago por viaje: no depende de cuánto cargó el camión.
    # Identidad: Δlog($/ton-km) = Δlog(pago por viaje) − Δlog(ton por viaje).
    var_viaje = np.log(pago_viaje).diff().dropna(how="all")
    var_tonkm = np.log(panel).diff()
    var_carga = np.log(ton_viaje).diff()

    volatiles = var_viaje.std()[var_viaje.std() > VOLATILIDAD_MAXIMA].index.tolist()
    carga_variable = var_carga.std()[var_carga.std() > CARGA_VARIABLE_MAXIMA].index.tolist()
    cols = [c for c in panel.columns if c not in volatiles and c not in carga_variable]
    var_v1 = var_viaje[cols]

    factor = var_v1.median(axis=1)                 # movimiento común del mercado (pago por viaje)
    resid = var_v1.sub(factor, axis=0)             # idiosincrático por corredor
    z = z_sombra(resid)

    ultimo = var_v1.index[-1]
    corredores = {}
    for c in cols:
        corredores[c] = {
            "flete_ton_km": round(float(panel.loc[ultimo, c]), 1),
            "pago_viaje": round(float(pago_viaje.loc[ultimo, c])),
            "variacion_viaje_pct": round(100 * float(var_viaje.loc[ultimo, c]), 1),
            "variacion_ton_km_pct": round(100 * float(var_tonkm.loc[ultimo, c]), 1),
            "residuo_pct": round(100 * float(resid.loc[ultimo, c]), 1),
            "viajes": int(viajes.loc[ultimo, c]),
            "densidad": round(float(ton_viaje.loc[ultimo, c]), 1),
            "variacion_carga_pct": round(100 * float(var_carga.loc[ultimo, c]), 1),
            "z_sombra": (None if pd.isna(z.loc[ultimo, c])
                         else round(float(z.loc[ultimo, c]), 2)),
        }

    resultado = {
        "mes_analizado": ultimo.strftime("%Y-%m"),
        "meses_disponibles": len(panel),
        "metrica_movimiento": "pago por viaje (desde nov 2026, ver DECISIONS.md)",
        "corredores_excluidos_por_volatilidad": volatiles,
        "corredores_excluidos_por_carga_variable": carga_variable,
        "factor_comun_pct": round(100 * float(factor.loc[ultimo]), 1),
        "detección": "modo sombra — sin alertas hasta ~40 meses (ver DECISIONS.md)",
        "corredores": corredores,
    }

    Path("data").mkdir(exist_ok=True)
    salida = Path("data") / f"indice_{ultimo:%Y%m}.json"
    with open(salida, "w") as fh:
        json.dump(resultado, fh, indent=2, ensure_ascii=False)

    print(f"Índice escrito en {salida} ({len(panel)} meses, "
          f"{len(corredores)} corredores)")
    print(f"Factor común del mes (pago por viaje): {resultado['factor_comun_pct']:+.1f}%")
    for c, d in sorted(corredores.items(),
                       key=lambda kv: abs(kv[1]["residuo_pct"]), reverse=True)[:5]:
        print(f"  {c[:45]:<45} viaje {d['variacion_viaje_pct']:+5.1f}%  "
              f"resid {d['residuo_pct']:+5.1f}%  carga {d['variacion_carga_pct']:+5.1f}%")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)

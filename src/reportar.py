"""Convierte el índice mensual en el boletín de fletes (Markdown).

Salida: reports/fletes_AAAAMM.md (histórico) y reports/fletes_ultimo.md (enlace estable).
La detección está en modo sombra: se reportan variaciones y factor común como
información, sin emitir alertas (ver DECISIONS.md).
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

VIAJES_MINIMOS_TITULAR = 500

def titular(factor, corredores):
    """Título declarativo: enuncia el hallazgo del mes, no el tema."""
    candidatos = {c: d for c, d in corredores.items()
                  if d["viajes"] >= VIAJES_MINIMOS_TITULAR}
    if not candidatos:
        candidatos = corredores      # respaldo por si ningún corredor supera el piso
    
    movs = sorted(corredores.items(), key=lambda kv: abs(kv[1]["residuo_pct"]),
                  reverse=True)
    c, d = movs[0]
    origen = c.split(" → ")[0].split()[0].title()
    destino = c.split(" → ")[1].split()[0].title()
    if abs(d["residuo_pct"]) < 5:
        return f"Fletes estables: el mercado se movió {factor:+.1f}% y ningún corredor se apartó del patrón"
    signo = "subió" if d["residuo_pct"] > 0 else "cayó"
    return (f"{origen}–{destino} {signo} {abs(d['variacion_pct']):.0f}% "
            f"mientras el mercado se movió {factor:+.1f}%")


def main():
    indice = sorted(Path("data").glob("indice_*.json"))[-1]
    with open(indice) as f:
        r = json.load(f)

    hoy = datetime.now(ZoneInfo("America/Bogota")).date()
    corredores = r["corredores"]
    factor = r["factor_comun_pct"]

    md = [f"# {titular(factor, corredores)}",
          f"### Índice de fletes terrestres — {r['mes_analizado']}",
          f"*Generado el {hoy}. Fuente: RNDC (Ministerio de Transporte), "
          f"{r['meses_disponibles']} meses de historia. Ver limitaciones abajo.*",
          "",
          f"**Movimiento general del mercado este mes: {factor:+.1f}%** "
          "(mediana de la variación de todos los corredores).",
          ""]

    # Tabla ordenada por residuo (quién se movió distinto del mercado)
    md += ["| Corredor | $/ton-km | Variación | vs. mercado | Viajes |",
           "|---|---:|---:|---:|---:|"]
    for c, d in sorted(corredores.items(),
                       key=lambda kv: abs(kv[1]["residuo_pct"]), reverse=True):
        origen, destino = [p.rsplit(" ", 1)[0].title() for p in c.split(" → ")]
        md.append(f"| {origen} → {destino} | {d['flete_ton_km']:,.0f} | "
                  f"{d['variacion_pct']:+.1f}% | {d['residuo_pct']:+.1f}% | "
                  f"{d['viajes']:,} |")

    md += ["",
           "**Cómo leer este boletín:**",
           "- *$/ton-km*: flete pagado por tonelada-kilómetro en tractocamiones "
           "de carga seca, viajes con valor declarado.",
           "- *Variación*: cambio del flete respecto al mes anterior.",
           "- *vs. mercado*: cuánto se movió el corredor por encima o por debajo "
           "del movimiento general (el residuo idiosincrático). Es la columna que "
           "señala corredores con dinámica propia.",
           "",
           "**Limitaciones.** Índice en construcción. La detección automática de "
           "anomalías está en calibración y se activará con más historia; por ahora "
           "las variaciones se reportan como información, no como alertas. El flete "
           "es un promedio ponderado y puede reflejar cambios en la mezcla de carga, "
           "no solo en el precio. Datos con ~2 meses de rezago de publicación.",
           "",
           f"*[Metodología y código](https://github.com/carlos-osorio/monitor-fletes)*"]

    texto = "\n".join(md)
    Path("reports").mkdir(exist_ok=True)
    (Path("reports") / f"fletes_{r['mes_analizado'].replace('-','')}.md").write_text(
        texto, encoding="utf-8")
    (Path("reports") / "fletes_ultimo.md").write_text(texto, encoding="utf-8")
    print(f"Boletín escrito: reports/fletes_ultimo.md")
    print(f"Titular: {titular(factor, corredores)}")


if __name__ == "__main__":
    main()

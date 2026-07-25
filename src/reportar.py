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
DENSIDAD_TITULAR = 12      # ton/viaje mínimas ese mes para poder titular

def describir_mov(pct):
    a = abs(pct)
    if a < 3:
        return "estable"
    return f"{'subió' if pct > 0 else 'bajó'} {a:.0f}%"

def titular(factor, corredores):
    candidatos = {
        c: d for c, d in corredores.items()
        if d["viajes"] >= VIAJES_MINIMOS_TITULAR
        and d.get("densidad", 99) >= DENSIDAD_TITULAR
    }
    if not candidatos:
        candidatos = corredores
    movs = sorted(candidatos.items(),
                  key=lambda kv: abs(kv[1]["residuo_pct"]), reverse=True)
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
          f"### Costo del transporte de carga por corredor — {r['mes_analizado']}",
          f"*Generado el {hoy}. Fuente: RNDC (Ministerio de Transporte), "
          f"{r['meses_disponibles']} meses de datos.*",
          "",
          f"**El costo de transportar carga se movió {describir_mov(factor)} "
          f"en promedio este mes.** La tabla muestra cada corredor y si se apartó "
          f"de ese movimiento general.",
          ""]

    md += ["| Corredor | Costo por tonelada movida 1 km | Cambio del mes | "
           "Comparado con el promedio | Viajes |",
           "|---|---:|---:|---:|---:|"]
    for c, d in sorted(corredores.items(),
                       key=lambda kv: abs(kv[1]["residuo_pct"]), reverse=True):
        origen, destino = [p.rsplit(" ", 1)[0].title() for p in c.split(" → ")]
        vs = d["residuo_pct"]
        comparado = ("igual que el promedio" if abs(vs) < 3
                     else f"{abs(vs):.0f}% {'más' if vs > 0 else 'menos'} que el promedio")
        md.append(f"| {origen} → {destino} | ${d['flete_ton_km']:,.0f} | "
                  f"{describir_mov(d['variacion_pct'])} | {comparado} | "
                  f"{d['viajes']:,} |")

    md += ["",
           "**Cómo leer la tabla:**",
           "- *Costo por tonelada movida 1 km*: lo que cuesta, en promedio, "
           "transportar una tonelada a lo largo de un kilómetro en ese corredor "
           "(camiones pesados de carga seca).",
           "- *Cambio del mes*: cuánto subió o bajó ese costo respecto al mes anterior.",
           "- *Comparado con el promedio*: si el corredor se movió más o menos que "
           "el conjunto del mercado. Un corredor que sube cuando todos suben no es "
           "noticia; uno que se mueve solo, sí.",
           "",
           "**Nota metodológica.** El costo se calcula sobre viajes con tarifa "
           "declarada, en tractocamiones de carga seca, en rutas de más de 200 km. "
           "Se excluyen corredores donde la carga es demasiado ligera o variable "
           "para que el costo por tonelada sea comparable. La detección automática "
           "de variaciones inusuales está en preparación y requiere más meses de "
           "datos; por ahora las cifras se presentan como información. Datos con "
           "unos dos meses de rezago. Metodología completa y código en el repositorio.",
           ""]
    # ... (escritura de archivos igual)

    texto = "\n".join(md)
    Path("reports").mkdir(exist_ok=True)
    (Path("reports") / f"fletes_{r['mes_analizado'].replace('-','')}.md").write_text(
        texto, encoding="utf-8")
    (Path("reports") / "fletes_ultimo.md").write_text(texto, encoding="utf-8")
    print(f"Boletín escrito: reports/fletes_ultimo.md")
    print(f"Titular: {titular(factor, corredores)}")


if __name__ == "__main__":
    main()

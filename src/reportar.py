"""Convierte el índice mensual en el boletín de fletes (Markdown y página web).

Salida: reports/fletes_AAAAMM.md (histórico); si el mes es el más reciente,
también reports/fletes_ultimo.md e index.html.
Detección en modo sombra: variaciones como información, sin alertas (DECISIONS.md).

Uso:
    python src/reportar.py            # último índice disponible
    python src/reportar.py 2026-08    # un mes específico (requiere data/indice_202608.json)
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

VIAJES_MINIMOS_TITULAR = 500
DENSIDAD_TITULAR = 12
UMBRAL_DESTACAR = 8        # % vs. mercado para mencionar un corredor en título/resumen


def describir_mov(pct):
    a = abs(pct)
    if a < 3:
        return "estable"
    return f"{'subió' if pct > 0 else 'bajó'} {a:.0f}%"


def estado_mercado(factor):
    if abs(factor) < 3:
        return "se mantuvo estable"
    return describir_mov(factor)


def titular(factor, corredores):
    candidatos = {
        c: d for c, d in corredores.items()
        if d["viajes"] >= VIAJES_MINIMOS_TITULAR
        and d.get("densidad", 99) >= DENSIDAD_TITULAR
    }
    if not candidatos:
        candidatos = corredores
    c, d = sorted(candidatos.items(),
                  key=lambda kv: abs(kv[1]["residuo_pct"]), reverse=True)[0]
    if abs(d["residuo_pct"]) < UMBRAL_DESTACAR:
        if abs(factor) < 3:
            return "El pago por viaje de la carga pesada se mantuvo estable este mes"
        return (f"El pago por viaje de la carga pesada {describir_mov(factor)} en promedio, "
                "sin corredores fuera del patrón")
    origen, destino = [nombre_municipio(p) for p in c.split(" → ")]
    return (f"{origen}–{destino}: el pago por viaje {describir_mov(d['variacion_viaje_pct'])} "
            f"mientras el mercado {estado_mercado(factor)}")


def resumen_mes(factor, corredores):
    destacados = [c for c, d in corredores.items()
                  if abs(d["residuo_pct"]) >= UMBRAL_DESTACAR
                  and d["viajes"] >= VIAJES_MINIMOS_TITULAR
                  and d.get("densidad", 99) >= DENSIDAD_TITULAR]
    base = f"En promedio, el pago por viaje {estado_mercado(factor)} este mes"
    if not destacados:
        return base + ", y ningún corredor importante se salió de ese patrón."
    return base + f". {len(destacados)} corredor(es) se movieron con dinámica propia; ver la tabla."


DEPARTAMENTOS = ["VALLE DEL CAUCA", "BOGOTA D. C.", "CUNDINAMARCA", "ANTIOQUIA",
                 "ATLANTICO", "BOLIVAR", "BOYACA", "SANTANDER", "MAGDALENA", "CESAR",
                 "CALDAS", "RISARALDA", "TOLIMA", "HUILA", "META", "NARIÑO", "CAUCA"]


def nombre_municipio(texto):
    """'BUENAVENTURA VALLE DEL CAUCA' -> 'Buenaventura'; 'BOGOTA BOGOTA D. C.' -> 'Bogota'."""
    t = texto.strip()
    for dep in DEPARTAMENTOS:
        if t.endswith(" " + dep):
            t = t[: -len(dep) - 1]
            break
    return t.title()


def describir_carga(d):
    txt = f"{d['densidad']:.1f} t"
    if abs(d.get("variacion_carga_pct", 0)) >= 3:
        txt += f" ({describir_mov(d['variacion_carga_pct'])})"
    return txt


def main(mes=None):
    indices = sorted(Path("data").glob("indice_*.json"))
    if not indices:
        raise RuntimeError("No hay índices en data/: correr primero src/calcular.py")
    if mes:
        indice = Path("data") / f"indice_{mes.replace('-', '')}.json"
        if not indice.exists():
            raise RuntimeError(f"No existe {indice}: correr primero src/calcular.py {mes}")
    else:
        indice = indices[-1]
    # La página principal solo se actualiza con el mes más reciente que tiene datos,
    # no con el índice más reciente generado (al regenerar un mes viejo pueden coincidir).
    ultimo_dato = sorted(Path("data/procesado").glob("fletes_*.parquet"))[-1].stem.split("_")[1]
    es_ultimo = indice.stem.split("_")[1] == ultimo_dato
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
          f"**{resumen_mes(factor, corredores)}**",
          ""]

    md += ["| Corredor | Costo por tonelada movida 1 km | Pago por viaje: cambio del mes | "
           "Comparado con el promedio | Carga por viaje | Viajes |",
           "|---|---:|---:|---:|---:|---:|"]
    for c, d in sorted(corredores.items(),
                       key=lambda kv: abs(kv[1]["residuo_pct"]), reverse=True):
        origen, destino = [nombre_municipio(p) for p in c.split(" → ")]
        vs = d["residuo_pct"]
        comparado = ("igual que el promedio" if abs(vs) < 3
                     else f"{abs(vs):.0f}% {'más' if vs > 0 else 'menos'} que el promedio")
        md.append(f"| {origen} → {destino} | ${d['flete_ton_km']:,.0f} | "
                  f"{describir_mov(d['variacion_viaje_pct'])} | {comparado} | "
                  f"{describir_carga(d)} | {d['viajes']:,} |")

    md += ["",
           "**Cómo leer la tabla:**",
           "- *Costo por tonelada movida 1 km*: lo que cuesta, en promedio, "
           "transportar una tonelada a lo largo de un kilómetro en ese corredor "
           "(camiones pesados de carga seca). Sirve para comparar corredores entre sí.",
           "- *Pago por viaje: cambio del mes*: cuánto subió o bajó lo que se paga por "
           "cada viaje respecto al mes anterior. Es la medida del precio del flete.",
           "- *Comparado con el promedio*: si el pago por viaje del corredor se movió más "
           "o menos que el conjunto del mercado. Un corredor que sube cuando todos suben "
           "no es noticia; uno que se mueve solo, sí.",
           "- *Carga por viaje*: toneladas promedio por camión y su cambio. Cuando los "
           "camiones van más cargados, el costo por tonelada-km baja aunque el pago por "
           "viaje no cambie; por eso el precio se mide por viaje.",
           "",
           "**Nota metodológica.** El costo se calcula sobre viajes con tarifa "
           "declarada, en tractocamiones de carga seca, en rutas de más de 200 km. "
           "Se excluyen corredores donde la carga es demasiado ligera o el pago es "
           "demasiado variable para ser comparable. Desde noviembre de 2026 el "
           "movimiento de cada corredor se mide sobre el pago por viaje y no sobre el "
           "costo por tonelada-km, que mezclaba cambios de precio con cambios en la carga "
           "de los camiones. La detección automática de variaciones inusuales está en "
           "preparación y requiere más meses de datos; por ahora las cifras se presentan "
           "como información. Datos con unos dos meses de rezago. Metodología y código "
           "en el repositorio.",
           "",
           f"*[Metodología y código](https://github.com/carlos-osorio/monitor-fletes)*"]

    texto = "\n".join(md)
    Path("reports").mkdir(exist_ok=True)
    (Path("reports") / f"fletes_{r['mes_analizado'].replace('-','')}.md").write_text(
        texto, encoding="utf-8")
    print(f"Boletín {r['mes_analizado']} escrito. Titular: {titular(factor, corredores)}")
    if not es_ultimo:
        print("Mes anterior al más reciente: no se actualizan fletes_ultimo.md ni index.html.")
        return
    (Path("reports") / "fletes_ultimo.md").write_text(texto, encoding="utf-8")
    # Versión web: index.html en la raíz, para GitHub Pages
    try:
        import markdown  # convierte Markdown a HTML
        cuerpo = markdown.markdown(texto, extensions=["tables"])
    except ImportError:
        cuerpo = f"<pre>{texto}</pre>"   # respaldo si no está la librería

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monitor de fletes — Colombia</title>
<style>
  body {{ max-width: 820px; margin: 2rem auto; padding: 0 1rem;
          font-family: system-ui, -apple-system, sans-serif; line-height: 1.5; color: #222; }}
  h1 {{ font-size: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: right; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ background: #f4f4f4; }}
  em {{ color: #666; }}
</style>
</head>
<body>
{cuerpo}
</body>
</html>"""
    Path("index.html").write_text(html, encoding="utf-8")




if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)

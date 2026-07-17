# Bitácora de decisiones — monitor-fletes

Módulo terrestre del observatorio de fricción logística. Índice de fletes
por tonelada-kilómetro sobre datos del RNDC. Formato: lo más reciente arriba.

---
## 2026-07-17 —Archivos de datos RNDC

Los archivos crudos .xlsx (~25 MB/mes) no se versionan en el repo por tamaño; viven en almacenamiento externo. El repo versiona extractos mensuales livianos en data/procesado/. La reducción crudo→extracto es el primer paso del pipeline.

---
## 2026-07-16 — Contrato v1

**Qué monitorea:** flete pagado ($/ton-km) en los ~15-20 corredores pesados
de mayor volumen. Filtros heredados de la exploración: tractocamiones, viajes
con valor declarado (VIAJESVALORCERO=0), sin líquidos (VIAJESLIQUIDOS=0),
distancia ≥ 200 km, origen ≠ destino.

**Cadencia:** mensual, con ingesta manual. El dato vivo solo existe en el
portal humano de Mintransporte (rndc.mintransporte.gov.co), con anti-bot; el
canal de datos.gov.co está congelado desde abril 2020. Por eso el sistema
tiene un paso humano de <10 min/mes: descargar el archivo del mes → data/crudo/.
De ahí en adelante, todo automático.

**Fórmula del flete unitario:** VALORESPAGADOS / ((KILOGRAMOS/1000) × KILOMETROS).
KILOMETROS verificado como distancia de la ruta (constante entre filas del
mismo corredor), no suma de viajes.

**Fuera de alcance v1:** brecha contra SICE-TAC (referencia sin verificar aún;
va a v1.5), retorno vacío (semántica de columnas REGRESO sin verificar),
tiempos logísticos, cualquier endpoint, y el cruce con SIPSA (v3 / línea de
investigación).

**Criterio de éxito:** 3 ciclos mensuales completos con el paso humano
tomando menos de 10 minutos.

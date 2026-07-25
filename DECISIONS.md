# Bitácora de decisiones — monitor-fletes

Módulo terrestre del observatorio de fricción logística. Índice de fletes
por tonelada-kilómetro sobre datos del RNDC. Formato: lo más reciente arriba.

---
## 2026-07-25 — Detección en modo sombra: v1 publica el índice sin alertar

**Contexto:** con 25 meses, el MAD expandiente por corredor es un estimador
inestable —los primeros z salían inflados (±9) por dispersiones espurias sobre
pocos puntos—. Un umbral k fijado hoy se ajustaría al ruido de estimación, no a
la señal.

**Decisión:** v1 calcula y guarda los z (campo `z_sombra` en el JSON) pero NO
emite alertas. La detección se activará con ~40 meses, recalibrando
empíricamente sobre la distribución acumulada.

**Porqué:** mismo principio que el pronóstico en sombra y el chequeo de
revisiones del monitor portuario —medir primero, actuar después—. Publicar
alertas mal calibradas costaría credibilidad ante un público técnico
(Fedetranscarga).

---

## 2026-07-25 — Objeto de detección: residuo idiosincrático, no nivel del flete

**Contexto:** la serie de fletes tiene tendencia fuerte (+40% en dos años); un
baseline de mediana móvil sobre nivel produce sesgo sistemático.

**Decisión:** se detecta sobre el residuo = variación mensual en log del corredor
MENOS la mediana de variaciones de todos los corredores ese mes (el factor común
del mercado). Escala robusta: MAD expandiente por corredor, con piso de 2% y
mínimo 12 meses de historia.

**Porqué:** Δlog induce estacionariedad (la variación es aprox. estacionaria, el
nivel no) y equivale a variación %. Descontar el factor común aísla lo
idiosincrático (modelo de factores / efectos fijos de tiempo); usar la mediana
como factor es robusto a corredores atípicos. MAD sobre desviación estándar por
su punto de ruptura del 50% y para evitar el enmascaramiento de outliers.

---

## 2026-07-25 — Exclusión de corredores por volatilidad y por densidad

**Contexto:** el $/ton-km no mide precio de mercado en dos casos: cuando la carga
no se captura bien en kilogramos (líquidos) y cuando el vehículo va con carga
ligera (el flete se paga por viaje, no por peso).

**Decisiones:**
- Se excluyen del índice los corredores con desviación de la variación mensual
  > 20% (saca Barrancabermeja→Barranquilla, 41% — líquidos).
- Se excluyen los corredores con densidad promedio < 10 ton/viaje: una tractomula
  (capacidad ~30-34 t) que viaja con menos va a pérdida o está mal registrada;
  esa carga es negocio de Turbo/NKR, no de tractocamión. Su $/ton-km no es
  interpretable como precio.

**Porqué:** mismo criterio que excluir viajes de valor cero —quitar donde la
métrica no mide lo que dice medir. Filtros por criterio, no por nombre: el
sistema excluye solo y deja constancia en el JSON.

---

## 2026-07-25 — El titular se protege aparte del índice (qué entra ≠ qué destaca)

**Contexto:** Tenjo pasa el filtro de densidad por su promedio (15,7 t) pero es
inestable mes a mes (p25 = 8,7; algunos viajes casi vacíos). En junio le tocó un
mes ligero y su $/ton-km saltó +22% por composición, no por precio —titulando
un falso hallazgo.

**Decisión:** el titular del boletín solo puede encabezarlo un corredor con
soporte

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

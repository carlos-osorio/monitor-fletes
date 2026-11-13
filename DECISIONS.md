# Bitácora de decisiones — monitor-fletes

Módulo terrestre del observatorio de fricción logística. Índice de fletes
por tonelada-kilómetro sobre datos del RNDC. Formato: lo más reciente arriba.

---
## 2026-11-13 — El movimiento se mide sobre el pago por viaje, no sobre $/ton-km

**Contexto:** el residuo en $/ton-km estaba dominado por la carga por viaje, no por
el precio. Sobre 28 meses y 19 corredores, la correlación entre el residuo en
$/ton-km y el cambio de toneladas por viaje fue de −0,80; el residuo tenía
autocorrelación mes a mes de −0,37 (firma de reversión: un mes liviano sube el
$/ton-km y el siguiente lo devuelve), y el 39% de los movimientos ≥ 8% se
revertía al mes siguiente. Tres titulares seguidos habrían narrado composición
como precio: julio (Barranquilla–Bogotá +20% en $/ton-km; ~+4% por viaje, el
trigo cayó de 91 a 17 viajes), septiembre (Buenaventura–Cota −22%; reversión del
salto de agosto) y octubre (Cartagena–Girardota −11%; +1% por viaje, la carga
pasó de 17,5 a 20,3 t/viaje).

**Decisión:** el factor común, el residuo, el z en sombra, el filtro de
volatilidad y el titular se calculan sobre el pago por viaje
(VALORESPAGADOS / VIAJESTOTALES). El $/ton-km se conserva como NIVEL, para
comparar corredores y para la futura brecha con SICE-TAC. El boletín agrega la
columna de carga por viaje, que explica los movimientos del $/ton-km.
Identidad: Δlog($/ton-km) = Δlog(pago por viaje) − Δlog(ton por viaje).

**Evidencia de que el pago es por viaje:** la elasticidad agrupada del pago por
viaje a la carga por viaje (sin factor común) es 0,07. Hay heterogeneidad: entre
−0,1 y 0,3 en la mayoría de corredores, y 0,57 (Cartagena→Madrid) y 0,62
(Bogotá→Cartagena) en dos. Con 29 meses no se ajusta por corredor; se revisa con
~40 meses, junto con la activación de la detección. Con $/viaje, la dispersión
del residuo baja de 7,6% a 4,4%, la autocorrelación de −0,37 a −0,14 y las
reversiones de 39% a 18%.

**Corredores con carga muy variable:** Barrancabermeja→Barranquilla, excluido
en julio por volatilidad (41% en $/ton-km, sospecha de líquidos), tiene solo
4,1% de volatilidad por viaje: su inestabilidad era de carga, no de precio.
Pero su carga por viaje oscila con desviación de 0,40 en Δlog (el siguiente
corredor tiene 0,14), así que su $/ton-km no es comparable con el de otros
corredores. Se agrega una regla explícita: se excluyen los corredores con
desviación de Δlog(ton por viaje) > 0,30. Hoy solo afecta a ese corredor.

**Otros cambios:** calcular.py y reportar.py aceptan un mes como argumento
(`python src/calcular.py 2026-08`), usando solo datos hasta ese mes. Así se
regeneró el boletín de agosto, que había quedado sin publicar al cargar agosto y
septiembre juntos. La página principal (index.html y fletes_ultimo.md) solo se
actualiza con el mes más reciente que tiene datos. Los boletines de julio y
septiembre publicados con la métrica anterior se conservan sin cambios.

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

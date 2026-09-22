# Definición de trabajo del IMOR

## Estado

Definición provisional, pendiente de validación contra los metadatos de la
serie seleccionada de la CNBV.

## Variable objetivo

El MVP pretende modelar el índice mensual de morosidad del crédito al consumo
de las Sofipos mexicanas, expresado en porcentaje:

\[
IMOR_t = \frac{CarteraVencida_t}{CarteraTotal_t}\times 100.
\]

La definición no se considerará cerrada hasta confirmar qué conceptos
contables integran ambos saldos, qué productos se clasifican como consumo y
qué instituciones forman parte del universo en cada mes.

## Reconstrucción del agregado

Si la CNBV no publica directamente el agregado sectorial, debe reconstruirse
con saldos por institución:

\[
IMOR_t =
\frac{\sum_j CarteraVencida_{j,t}}
     {\sum_j CarteraTotal_{j,t}}
\times 100.
\]

No se utilizará el promedio simple de los IMOR institucionales porque daría el
mismo peso a entidades con exposiciones muy diferentes.

## Unidad temporal

- Frecuencia objetivo: mensual.
- Convención de fecha propuesta: último día calendario del mes.
- Unidad: puntos porcentuales, con rango esperado de 0 a 100.
- Cada mes debe aparecer una sola vez en el agregado final.

La convención de fecha se confirmará después de revisar si la fuente representa
saldos de cierre, promedios u otra referencia temporal.

## Controles mínimos

La futura ingesta debe validar:

- numerador y denominador no negativos;
- denominador estrictamente positivo;
- `cartera_vencida <= cartera_total`;
- `0 <= imor_pct <= 100`;
- ausencia de duplicados institución-mes;
- reconciliación entre IMOR publicado y reconstruido cuando ambos existan;
- meses faltantes y cambios en la cobertura institucional.

## Riesgos pendientes

1. Cambios contables o regulatorios pueden romper la comparabilidad temporal.
2. Entradas, salidas o fusiones de Sofipos pueden mover el agregado por
   composición.
3. Programas de apoyo o reestructuras pueden alterar temporalmente la
   clasificación de cartera.
4. Revisiones posteriores de la CNBV pueden cambiar observaciones históricas.

Estos riesgos deben resolverse o declararse antes de congelar el conjunto de
modelado.

## Interpretación permitida

El IMOR es una medida agregada de calidad de cartera. No es una probabilidad de
incumplimiento individual, no identifica causalidad y no debe utilizarse para
aprobar o rechazar solicitantes.

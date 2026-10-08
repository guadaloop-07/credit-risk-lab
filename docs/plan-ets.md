# Plan de implementación de ETS

## Estado y decisión de fase

La evaluación documentada en
[el reporte de modelos](../reports/evaluacion-modelos.md) cierra la fase de
regresión dinámica OLS/HAC. En la prueba final de doce meses, su MAE fue de
0.529 puntos porcentuales frente a 0.314 de persistencia. No se harán nuevos
ajustes de variables, rezagos o regresiones para mejorar esa prueba ya
observada.

La siguiente fase explorará ETS, una familia de modelos de suavizamiento
exponencial que usa exclusivamente la historia del IMOR. Es una comparación
razonable: prueba si una dinámica temporal simple puede mejorar el pronóstico
sin atribuir capacidad predictiva a las variables macro de la regresión.

## Alcance predefinido

La primera implementación tendrá un único modelo principal: suavizamiento
exponencial simple (SES, por sus siglas en inglés), sin tendencia ni
estacionalidad. El nivel y el parámetro de suavizamiento se estimarán sólo con
cada ventana de entrenamiento disponible.

No se incluirán variables macroeconómicas, indicadores de régimen, escenarios
ni ajustes manuales de pronósticos. Tampoco se modelará estacionalidad anual:
la historia disponible tiene menos de diez ciclos anuales completos y no ofrece
base suficiente para estimarla de manera estable.

Un modelo Holt con tendencia amortiguada podrá agregarse después como
sensibilidad separada. No se elegirá entre SES y Holt con la prueba final;
cualquier comparación entre ellos se hará dentro del backtest expansivo.

## Datos y protocolo temporal

ETS recibirá la misma tabla analítica validada que persistencia y sólo usará:

| Campo | Uso |
|---|---|
| `mes_observacion` | Ordenar y etiquetar cada pronóstico mensual. |
| `imor_pct` | Serie objetivo para ajustar el nivel y generar el pronóstico a un mes. |

Se reutilizarán `crear_caracteristicas`, `separar_prueba_final` y las métricas
del módulo `riesgo_crediticio.modelos.backtest`. La partición de ETS se hará
sobre las filas con `IMOR t-1` disponible y con el mínimo de entrenamiento de
persistencia (96 observaciones). Con el corte actual eso implica 102 meses de
entrenamiento y 12 de prueba final.

El backtest será de origen rodante y ventana expansiva: para cada mes a
pronosticar se ajustará de nuevo ETS con la historia anterior a ese mes. El
IMOR observado del mes pronosticado nunca podrá formar parte del ajuste ni de
la selección de parámetros. La prueba final permanecerá separada hasta generar
la evaluación definitiva.

## Contrato de implementación

La implementación propuesta vivirá en
`src/riesgo_crediticio/modelos/ets.py` y expondrá funciones análogas a las de
la regresión dinámica:

| Componente | Responsabilidad |
|---|---|
| `ajustar_ets` | Ajustar SES con una serie de entrenamiento suficiente. |
| `pronosticar_ets` | Producir un pronóstico de un paso, su error y la etiqueta del modelo. |
| `ejecutar_backtest_ets` | Reajustar el modelo en cada corte expansivo. |
| `evaluar_ets` | Construir la partición, comparar ETS con persistencia y devolver métricas. |
| `guardar_evaluacion` | Escribir predicciones y un reporte JSON reproducibles bajo `data/interim/modelos/`. |

El comando de ejecución será:

```bash
make evaluar-ets
```

Generará, como mínimo, `predicciones_ets_backtest.parquet`,
`predicciones_ets_prueba.parquet` y `reporte_ets.json`. Las predicciones
conservarán las columnas `mes_observacion`, `imor_observado_pct`,
`prediccion_pct`, `error_pp`, `modelo` y `observaciones_entrenamiento` cuando
corresponda. No se recortarán silenciosamente predicciones fuera del intervalo
de 0 a 100; se marcarán y reportarán, igual que en la regresión.

`statsmodels` ya es una dependencia del proyecto, por lo que su componente de
suavizamiento exponencial puede emplearse sin ampliar las dependencias.

## Criterios de evaluación y decisión

La comparación publicará MAE, RMSE, sesgo y MASE para ETS y persistencia tanto
en el backtest como en la prueba final. La mejora porcentual se calculará con
el MAE de persistencia alineado al mismo conjunto de meses.

ETS sólo podrá presentarse como mejora predictiva si cumple simultáneamente:

1. Tiene menor MAE que persistencia en la prueba final.
2. No empeora el MAE en el backtest expansivo.
3. No tiene predicciones fuera del intervalo de 0 a 100 sin una explicación
   explícita.

Si no cumple esos criterios, persistencia seguirá siendo el modelo operativo y
ETS se documentará como resultado negativo reproducible. El resultado de doce
meses es una evidencia limitada; no se presentará como una prueba de
superioridad estructural ni se ajustará el modelo después de verlo.

## Pruebas de aceptación

La implementación deberá añadir pruebas automatizadas que verifiquen:

1. cada pronóstico usa únicamente observaciones anteriores al mes objetivo;
2. el backtest reestima el modelo en cada corte;
3. la prueba final conserva al menos doce meses y no modifica la partición de
   persistencia;
4. las métricas usan errores en puntos porcentuales y se comparan contra la
   persistencia alineada;
5. la interfaz de línea de comandos escribe los tres artefactos acordados;
6. muestras insuficientes o fechas inválidas producen errores claros.

Al terminar se ejecutarán `make verificar`, `make precommit` y
`make evaluar-ets` sobre el corte disponible. El reporte de modelos se
actualizará con los resultados sin reescribir la conclusión histórica de la
regresión dinámica.

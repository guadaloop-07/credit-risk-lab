# Laboratorio de riesgo crediticio

Laboratorio reproducible de estrés de morosidad del crédito al consumo en
México, con datos oficiales, validación temporal y escenarios macroeconómicos
interpretables.

## Estado

La primera fase de modelado está cerrada. El flujo de datos, el benchmark de
persistencia y la regresión dinámica OLS/HAC ya fueron evaluados con una prueba
temporal final. La regresión no superó a persistencia en el corte disponible,
por lo que persistencia permanece como la referencia predictiva del MVP.

La siguiente iteración propuesta es ETS (suavizamiento exponencial) univariado
del IMOR. Su alcance y criterios de evaluación están definidos antes de
implementarlo en el [plan de ETS](docs/plan-ets.md). La regresión se conserva
como experimento reproducible y sensibilidad interpretable; no debe usarse
como modelo operativo ni para inferencia causal.

## Desarrollo local

Requisitos:

- Python 3.12 o posterior;
- [`uv`](https://docs.astral.sh/uv/).

Preparar el entorno y registrar los hooks de pre-commit:

```bash
make setup
```

Ejecutar las verificaciones locales:

```bash
make verificar
make precommit
```

## Ingesta de datos

La ingesta descarga el Excel oficial de la CNBV configurado en
`config/series.yml`, valida que sea un XLSX y extrae explícitamente la única
fila agregada `IMOR consumo`. Ejecútala junto con el token de Banxico cargado
en el entorno:

```bash
make datos
```

Para reproducir una extracción previamente archivada o usar un CSV preparado,
indica un archivo local con `IMOR_CSV`. Si sus columnas no se llaman
`fecha`/`periodo` e `imor`, indica sus nombres exactos:

```bash
make datos IMOR_CSV=/ruta/al/archivo.csv IMOR_FECHA='Periodo' IMOR_VALOR='IMOR'
```

El comando descarga INPC, desempleo, TIIE e IMOR; guarda originales inmutables
bajo `data/raw/`, registra checksums y los metadatos HTTP disponibles en
`data/interim/` y genera
`data/processed/conjunto_analitico.parquet`. Estos artefactos no se versionan.

Después de la ingesta, valida la tabla antes de crear rezagos o ajustar modelos:

```bash
make validar
```

El reporte queda en `data/interim/reporte_calidad.json` e incluye grano
mensual, meses faltantes, duplicados, valores faltantes, rangos y antigüedad.

## Benchmark y backtest

Una vez aprobada la calidad, ejecuta el benchmark de persistencia y su
evaluación temporal:

```bash
make modelar
```

El comando crea rezagos de IMOR a un mes y de las variables macro a tres meses.
Para el benchmark conserva toda fila con IMOR rezagado disponible —aunque los
rezagos macro iniciales aún no existan—, reserva los últimos 24 meses para
prueba (o 12 si no mantiene 96 observaciones de entrenamiento) y ejecuta un
backtest expansivo dentro del entrenamiento. Guarda predicciones y métricas
MAE, RMSE, sesgo y MASE en
`data/interim/modelos/`. Este benchmark es la referencia para evaluar cualquier
modelo candidato, incluido ETS. La regresión dinámica usa únicamente casos
completos para sus rezagos macro y requiere al menos 84 observaciones de
entrenamiento (12 por cada uno de sus siete coeficientes), conservando una
prueba final mínima de 12 meses.

## Regresión dinámica

Para comparar la especificación dinámica OLS/HAC contra persistencia, ejecuta:

```bash
make evaluar-modelos
```

El comando reestima cada corte del backtest expansivo con IMOR `t-1`, variables
macro `t-3`, COVID y ruptura contable. Produce predicciones, coeficientes HAC,
residuos y diagnósticos en `data/interim/modelos/`; no recorta predicciones
fuera del rango de 0 a 100 y las reporta explícitamente. La evaluación quedó
cerrada: la regresión no superó a persistencia. Se mantiene este comando para
reproducir y actualizar el análisis, no para optimizar la especificación contra
la prueba final ya observada.

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para conocer las convenciones de
ramas, commits y pull requests.

## Documentación

- [Especificación detallada del MVP](docs/especificacion-mvp.md)
- [Reporte de evaluación de modelos](reports/evaluacion-modelos.md)
- [Plan de implementación de ETS](docs/plan-ets.md)
- [Catálogo y selección de fuentes](docs/fuentes.md)
- [Definición de trabajo del IMOR](docs/metodologia/definicion-imor.md)
- [Política de datos](data/README.md)

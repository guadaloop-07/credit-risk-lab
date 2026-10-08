# Laboratorio de riesgo crediticio

Laboratorio reproducible de estrés de morosidad del crédito al consumo en
México, con datos oficiales, validación temporal y escenarios macroeconómicos
interpretables.

## Estado

El proyecto se encuentra en preparación. El primer objetivo es construir un
MVP que relacione el índice de morosidad del crédito al consumo de las Sofipos
con desempleo, inflación y tasas reales, comparando un modelo interpretable
contra un benchmark de persistencia.

No se han generado resultados empíricos todavía.

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
`data/interim/modelos/`. Este benchmark es la referencia para evaluar la futura
regresión dinámica. La futura regresión usará únicamente casos completos para
sus rezagos macro y requerirá al menos 84 observaciones de entrenamiento (12
por cada uno de sus siete coeficientes), conservando una prueba final mínima de
12 meses.

## Regresión dinámica

Para comparar la especificación dinámica OLS/HAC contra persistencia, ejecuta:

```bash
make evaluar-modelos
```

El comando reestima cada corte del backtest expansivo con IMOR `t-1`, variables
macro `t-3`, COVID y ruptura contable. Produce predicciones, coeficientes HAC,
residuos y diagnósticos en `data/interim/modelos/`; no recorta predicciones
fuera del rango de 0 a 100 y las reporta explícitamente.

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para conocer las convenciones de
ramas, commits y pull requests.

## Documentación

- [Especificación detallada del MVP](docs/especificacion-mvp.md)
- [Catálogo y selección de fuentes](docs/fuentes.md)
- [Definición de trabajo del IMOR](docs/metodologia/definicion-imor.md)
- [Política de datos](data/README.md)

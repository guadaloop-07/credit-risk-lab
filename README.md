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

La CNBV publica una exportación oficial de su serie histórica. El lector acepta
el Excel de Sofipos y extrae explícitamente la única fila agregada `IMOR
consumo`; también acepta un CSV ya preparado. Ejecútalo junto con el token de
Banxico cargado en el entorno:

```bash
make datos IMOR_CSV=/ruta/a/sh_data_export_27.xlsx
```

Si usas un CSV cuyas columnas no se llaman `fecha`/`periodo` e `imor`, indica
sus nombres exactos:

```bash
make datos IMOR_CSV=/ruta/al/archivo.csv IMOR_FECHA='Periodo' IMOR_VALOR='IMOR'
```

El comando descarga INPC, desempleo y TIIE, guarda originales inmutables bajo
`data/raw/`, registra checksums en `data/interim/` y genera
`data/processed/conjunto_analitico.parquet`. Estos artefactos no se versionan.

Después de la ingesta, valida la tabla antes de crear rezagos o ajustar modelos:

```bash
make validar
```

El reporte queda en `data/interim/reporte_calidad.json` e incluye grano
mensual, meses faltantes, duplicados, valores faltantes, rangos y antigüedad.

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para conocer las convenciones de
ramas, commits y pull requests.

## Documentación

- [Especificación detallada del MVP](docs/especificacion-mvp.md)
- [Catálogo y selección de fuentes](docs/fuentes.md)
- [Definición de trabajo del IMOR](docs/metodologia/definicion-imor.md)
- [Política de datos](data/README.md)

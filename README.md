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

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para conocer las convenciones de
ramas, commits y pull requests.

## Documentación

- [Especificación detallada del MVP](docs/especificacion-mvp.md)
- [Catálogo y selección de fuentes](docs/fuentes.md)
- [Definición de trabajo del IMOR](docs/metodologia/definicion-imor.md)
- [Política de datos](data/README.md)

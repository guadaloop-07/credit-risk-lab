# Guía de contribución

## Idioma

La documentación, los issues, los pull requests, los commits, los docstrings y
los comentarios se escriben en español. Los identificadores de código usan
español sin acentos y siguen PEP 8. Se conservan en inglés los nombres propios
de herramientas y los términos técnicos sin una traducción clara.

## Preparación local

El proyecto requiere Python 3.12 o posterior y `uv`.

```bash
make setup
make verificar
```

`make setup` instala las dependencias bloqueadas en `uv.lock` y registra los
hooks de pre-commit. Para ejecutar todos los hooks manualmente:

```bash
make precommit
```

## Flujo de ramas

`main` debe permanecer desplegable y reproducible. Todo cambio se prepara en
una rama corta creada desde la versión más reciente de `main`:

- `feat/nombre-corto`: funcionalidad nueva;
- `fix/nombre-corto`: corrección;
- `docs/nombre-corto`: documentación;
- `test/nombre-corto`: pruebas;
- `chore/nombre-corto`: mantenimiento o herramientas.

Ejemplo:

```bash
git switch main
git pull --ff-only
git switch -c feat/ingesta-banxico
```

No se hacen pushes directos a `main`. Los cambios entran mediante pull request
y se integran con squash merge.

## Commits

Los commits usan un prefijo convencional y una descripción imperativa en
español:

```text
feat: agrega ingesta de series de Banxico
fix: corrige alineación mensual del desempleo
test: cubre rezagos de tres meses
docs: documenta definición del IMOR
chore: actualiza herramientas de calidad
```

Cada commit debe representar una unidad coherente. No se versionan datos
crudos, secretos, credenciales ni artefactos grandes.

## Pull requests

Un pull request debe:

1. resolver una sola unidad de trabajo;
2. explicar el motivo y el alcance;
3. identificar supuestos o cambios metodológicos;
4. incluir o actualizar pruebas;
5. actualizar la documentación afectada;
6. pasar el check requerido `CI / calidad`.

Los hallazgos analíticos deben distinguir claramente datos observados,
transformaciones, estimaciones y escenarios supuestos.

## Comandos de calidad

```bash
make formato     # Aplica correcciones seguras y formato.
make lint        # Verifica formato, lint y tipos.
make pruebas     # Ejecuta pytest.
make verificar   # Ejecuta lint y pruebas.
```

Los hooks locales ofrecen retroalimentación rápida, pero la integración
continua es la autoridad final para aceptar un cambio.

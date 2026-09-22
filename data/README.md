# Política de datos

Los datos del proyecto provienen de fuentes oficiales mexicanas. Esta carpeta
define dónde vive cada etapa sin versionar archivos grandes o potencialmente
cambiantes.

## Estructura prevista

```text
data/
├── raw/         # descargas originales e inmutables; ignorado por Git
├── interim/     # transformaciones intermedias; ignorado por Git
├── processed/   # tablas analíticas reproducibles; ignorado por Git
└── sample/      # muestras pequeñas y públicas para pruebas
```

Las carpetas ignoradas se crearán automáticamente cuando exista una ingesta
que las utilice. No se versionan directorios vacíos.

## Reglas

1. Un archivo en `raw/` no se modifica después de descargarse.
2. Cada descarga registra fuente, URL, fecha de consulta y checksum SHA-256.
3. `interim/` y `processed/` deben reconstruirse desde código.
4. `sample/` sólo contiene datos públicos, pequeños y suficientes para pruebas.
5. No se versionan credenciales, tokens, datos personales ni extractos cuya
   licencia impida redistribuirlos.
6. Ningún archivo mayor a 1 MB debe entrar al repositorio sin una decisión
   explícita y documentada.

## Manifiesto de descarga

Cuando comience la ingesta, cada ejecución producirá un manifiesto con al menos:

```text
serie
proveedor
url
fecha_descarga_utc
ruta_local
sha256
tamanio_bytes
```

El manifiesto no sustituye los metadatos metodológicos de
[`config/series.yml`](../config/series.yml).

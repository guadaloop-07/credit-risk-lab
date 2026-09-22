# Catálogo y selección de fuentes

## Propósito

Este documento registra la selección de las cuatro series del MVP. Su función
es separar hechos verificados de decisiones pendientes antes de automatizar
descargas o ajustar modelos.

El archivo legible por máquina es [`config/series.yml`](../config/series.yml).
Ambos documentos deben actualizarse en el mismo pull request cuando cambie una
definición de datos.

## Estado de selección

| Serie interna | Proveedor | Identificador oficial | Cobertura | Descarga estable | Estado |
|---|---|---|---|---|---|
| `imor_consumo_sofipos` | CNBV | Pendiente | Pendiente | Pendiente | Por validar |
| `inpc` | INEGI | Pendiente | Pendiente | Pendiente | Por validar |
| `desempleo_desestacionalizado` | INEGI | Pendiente | Pendiente | Pendiente | Por validar |
| `tasa_nominal_fondeo` | Banxico | Pendiente | Pendiente | Pendiente | Por validar |

`Pendiente` significa que el dato todavía no se ha confirmado en metadatos
oficiales. No debe sustituirse con un identificador inferido por nombre o por
una fuente secundaria.

## Criterios de aceptación

Una serie puede cambiar a estado `validada` cuando se haya documentado:

1. nombre e identificador oficial;
2. URL institucional y mecanismo estable de descarga;
3. definición, unidad y frecuencia originales;
4. cobertura temporal y meses faltantes;
5. rezago de publicación;
6. política de revisiones históricas;
7. transformación necesaria para el modelo;
8. cambios metodológicos o rupturas conocidas;
9. condiciones de uso o atribución;
10. una muestra descargada que pueda validarse manualmente.

## Decisiones por fuente

### CNBV: IMOR de consumo de Sofipos

Fuente candidata: [Portafolio de Información de la
CNBV](https://portafolioinfo.cnbv.gob.mx/Paginas/Inicio.aspx).

Antes de implementar la ingesta se debe confirmar:

- si existe un agregado sectorial mensual directamente descargable;
- si los saldos de cartera vigente, vencida y total son reconciliables;
- qué instituciones y productos integran el agregado de consumo;
- si hay cambios de definición asociados con normas contables;
- cómo se tratan instituciones que entran o salen del sector.

Si el agregado se reconstruye, se calculará como razón de saldos y nunca como
promedio simple de los IMOR institucionales.

### INEGI: inflación

Se seleccionará una serie mensual del INPC. La inflación interanual se
calculará como:

\[
\pi_t = \left(\frac{INPC_t}{INPC_{t-12}} - 1\right)\times 100.
\]

La transformación se reconciliará contra una publicación oficial para una
muestra de meses antes de aceptarla.

### INEGI: desempleo

Se busca una tasa de desocupación mensual desestacionalizada con población de
referencia y metodología claramente documentadas. La auditoría debe cubrir los
periodos de interrupción o cambio operativo de la encuesta durante la pandemia.

No se interpolarán meses faltantes como parte de la ingesta. Una eventual
imputación sería una decisión metodológica posterior y requeriría sensibilidad.

### Banxico: tasa nominal de fondeo

Fuente candidata: [Sistema de Información Económica de
Banxico](https://www.banxico.org.mx/SieInternet/).

La serie debe tener cobertura suficiente para el periodo común del IMOR. Si su
frecuencia es diaria, se documentará si el valor mensual es promedio, cierre u
otra agregación. La tasa real ex post se aproximará inicialmente como tasa
nominal menos inflación interanual.

## Evidencia y trazabilidad

Cada validación debe conservar:

- fecha y hora de consulta;
- URL exacta;
- archivo original o muestra permitida;
- checksum SHA-256;
- nota de lectura de metadatos;
- responsable de la decisión.

No se registrarán resultados empíricos en este documento. Los hallazgos
pertenecerán al reporte analítico una vez construido el pipeline.

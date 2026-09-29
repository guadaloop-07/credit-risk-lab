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
| `imor_consumo_sofipos` | CNBV | `sh_data_export_27.xlsx` / `IMOR consumo` / Total SOFIPOS | Ene-2017 a jul-2026 en descarga validada | [Excel oficial](https://portafolioinfdoctos.cnbv.gob.mx/Documentacion/minfo/CSV/series_historicas/sofipos/sh_data_export_27.xlsx) | Validada |
| `inpc` | INEGI | `865541`; tabulado `CA57_2018A` | Ene-1970 a ago-2026 en descarga validada | [Descarga CSV oficial](https://www.inegi.org.mx/app/tabulados/inp/default.aspx?nc=ca57_2018a&opc=t) | Validada |
| `desempleo_desestacionalizado` | INEGI | `444884`; tabulado `622`, Total nacional | Desde ene-2008 | Servicio público del tabulado | Validada |
| `tasa_nominal_fondeo` | Banxico | SIE `SF283`, cuadro `CF113` | Ene-1995 a ago-2026 | Cuadro SIE exportable | Validada |

`Validada con restricción` significa que se confirmó la fuente, definición y
consulta oficial, pero falta una primera descarga archivada o una interfaz de
archivo/API estable para automatizarla. No debe sustituirse una restricción por
un identificador inferido ni por una fuente secundaria.

La validación se realizó el 28 de septiembre de 2026. Las fechas de cobertura
son las que publicaban los portales en esa fecha y se deben recalcular con cada
extracción.

## Decisiones aprobadas

1. Se usará el IMOR sectorial agregado publicado por CNBV sólo si la primera
   exportación permite verificar su definición y reconciliarla contra los
   saldos disponibles. No se replicará automáticamente la exclusión de una
   institución utilizada por Banxico.
2. Se conservará toda la muestra y se incorporará una marca de ruptura desde
   enero de 2022 por IFRS 9, con sensibilidad por régimen.
3. La tasa nominal será la TIIE a 28 días promedio mensual, serie SIE `SF283`.
4. El token de Banxico se cargará localmente como `BANXICO_API_TOKEN`; nunca
   se versionará ni se imprimirá en registros. Las dos series INEGI
   seleccionadas se descargan desde el servicio público de sus tabulados.

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

La fuente seleccionada es el [Portafolio de Información de la
CNBV](https://portafolioinfo.cnbv.gob.mx/Paginas/Inicio.aspx), sección
Sofipos, consulta **Serie Histórica**. El tablero enlaza al [Excel oficial de
exportación](https://portafolioinfdoctos.cnbv.gob.mx/Documentacion/minfo/CSV/series_historicas/sofipos/sh_data_export_27.xlsx).
La descarga validada contiene la fila única **IMOR consumo** para **Total
SOFIPOS**, de enero de 2017 a julio de 2026. La ingesta guarda el Excel sin
alterarlo y extrae sólo esa fila.

El [recuadro de Banxico de diciembre de
2025](https://www.banxico.org.mx/publicaciones-y-prensa/reportes-sobre-el-sistema-financiero/recuadros/%7BBF224D96-2D2C-22A1-328E-2D98D71E3532%7D.pdf)
confirma que emplea datos mensuales de IMOR de consumo publicados por la CNBV,
desde junio de 2009 hasta agosto de 2025. También advierte que omitió una
institución por problemas financieros y de gobernanza; esa exclusión no se
adopta automáticamente en este proyecto.

La descarga confirma que existe un agregado sectorial mensual directamente
usable. Aún se deben documentar los componentes institucionales y cualquier
cambio de definición asociado con normas contables.

Si el agregado se reconstruye, se calculará como razón de saldos y nunca como
promedio simple de los IMOR institucionales.

En la primera descarga se guardarán el CSV/XLS original, fecha de consulta y
checksum. Si los saldos necesarios no están disponibles en la exportación, se
detendrá la automatización y se usará una reconstrucción institucional sólo
después de validar los conceptos contables.

### INEGI: inflación

Se seleccionó el INPC general nacional, selector `865541` del tabulado
`CA57_2018A`, con base en la segunda quincena de julio de 2018 = 100. INEGI
actualizó la canasta y los ponderadores en agosto de 2024 mediante índices
encadenados. La ingesta usa el botón oficial **Descarga CSV** del
[tabulado vigente](https://www.inegi.org.mx/app/tabulados/inp/default.aspx?nc=ca57_2018a&opc=t),
no el endpoint `628194`, que dejó de actualizarse en julio de 2024.

La inflación interanual se calculará como:

\[
\pi_t = \left(\frac{INPC_t}{INPC_{t-12}} - 1\right)\times 100.
\]

La transformación se reconciliará contra una publicación oficial para una
muestra de meses antes de aceptarla.

### INEGI: desempleo

Se seleccionó la tasa de desocupación nacional, total, desestacionalizada del
[tabulado 622 de INEGI](https://www.inegi.org.mx/app/tabulados/default.html?nc=622&opc=t).
Su unidad es porcentaje respecto de la PEA y la fuente atribuye el cálculo a
métodos econométricos aplicados a la ENOE. La primera descarga debe conservar
las notas metodológicas, cobertura y fecha de actualización antes de congelar
la tabla analítica.

La auditoría debe cubrir los periodos de interrupción o cambio operativo de la
encuesta durante la pandemia.

No se interpolarán meses faltantes como parte de la ingesta. Una eventual
imputación sería una decisión metodológica posterior y requeriría sensibilidad.

### Banxico: tasa nominal de fondeo

Se seleccionó la TIIE a 28 días como tasa promedio mensual: serie SIE `SF283`
del [cuadro CF113](https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do?accion=consultarCuadro&idCuadro=CF113&locale=es).
El cuadro la publica mensualmente en porcentajes y, al validarla, cubría desde
enero de 1995. Así se evita una agregación diaria adicional y se preserva la
frecuencia del modelo.

El recuadro de Banxico citado arriba usa la TIIE real de fondeo como proxy de
la tasa del crédito otorgado por Sofipos. Para el MVP, `SF283` es una proxy
reproducible y de cobertura larga, no una medida observada del costo de fondeo
de cada Sofipo. Banxico indica un cambio metodológico de la TIIE a 28 días a
partir del 1 de enero de 2025; se documentará como ruptura potencial.

La tasa real ex post se aproximará inicialmente como tasa nominal menos
inflación interanual.

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

## Próximo corte vertical

El siguiente cambio debe descargar una muestra pequeña de cada una de las
cuatro fuentes, archivarla fuera de Git junto con su checksum y verificar las
columnas y fechas. Sólo entonces se implementará la ingesta idempotente. La
restricción principal sigue siendo CNBV: no se debe automatizar Power BI hasta
confirmar que su exportación contiene los saldos o el IMOR sectorial requeridos.

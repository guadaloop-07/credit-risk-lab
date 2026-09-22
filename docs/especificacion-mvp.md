# Laboratorio mexicano de estrés de riesgo crediticio

## Especificación detallada del MVP

## 1. Resumen ejecutivo

Este proyecto construirá un laboratorio reproducible para estudiar la
morosidad del crédito al consumo en las Sociedades Financieras Populares
(Sofipos) mexicanas y estimar cómo podría cambiar bajo escenarios
macroeconómicos adversos.

El MVP usará exclusivamente información pública mexicana proveniente de la
Comisión Nacional Bancaria y de Valores (CNBV), el Banco de México (Banxico) y
el Instituto Nacional de Estadística y Geografía (INEGI). Su núcleo será un
modelo mensual interpretable que relacione el índice de morosidad (IMOR) del
crédito al consumo con desempleo, inflación y tasas de interés reales.

El producto final no será un score individual ni una implementación
regulatoria. Será un ejercicio de monitoreo y pruebas de estrés de cartera a
nivel agregado, con validación fuera de muestra, supuestos trazables y una
implementación pequeña pero profesional.

Pregunta central:

> ¿Cómo se relaciona la morosidad del crédito al consumo de las Sofipos con
> el desempleo, la inflación y las tasas reales, y cuánto podría aumentar bajo
> escenarios macroeconómicos adversos?

El proyecto debe poder completarse sin infraestructura en la nube, bases de
datos operacionales, servicios web ni frontend.

## 2. Objetivos

### 2.1 Objetivo principal

Construir un flujo reproducible que:

1. descargue o ingiera series mensuales oficiales mexicanas;
2. valide su calidad, frecuencia y definiciones;
3. construya un conjunto analítico sin fuga temporal;
4. compare un modelo econométrico interpretable contra un benchmark ingenuo;
5. evalúe ambos modelos fuera de muestra;
6. traduzca tres escenarios macroeconómicos en trayectorias ilustrativas de
   morosidad;
7. produzca un reporte breve, visual y completamente trazable.

### 2.2 Objetivos de aprendizaje

El MVP debe demostrar:

- integración de fuentes públicas heterogéneas;
- diseño temporal y prevención de fuga de información;
- modelado econométrico con series mensuales;
- evaluación contra un benchmark competitivo;
- interpretación financiera de coeficientes y escenarios;
- tratamiento explícito de cambios metodológicos y periodos atípicos;
- pruebas automatizadas de transformaciones y cálculos críticos;
- comunicación honesta de supuestos, incertidumbre y limitaciones.

## 3. Alcance

### 3.1 Incluido

- Una cartera: crédito al consumo de Sofipos mexicanas.
- Una variable objetivo: IMOR mensual agregado del sector.
- Tres factores macroeconómicos:
  - desempleo desestacionalizado;
  - inflación anual;
  - tasa de interés real.
- Un benchmark de persistencia.
- Una regresión dinámica interpretable.
- Validación temporal fuera de muestra.
- Tres escenarios macroeconómicos de 12 meses.
- Un reporte generado desde código.
- Pruebas unitarias para la lógica analítica esencial.

### 3.2 Excluido

- Datos de otros países.
- Scoring individual o decisiones de aprobación.
- Microdatos de ENIF.
- Carteras sintéticas a nivel préstamo.
- Vintages, roll rates y matrices de migración individuales.
- Análisis de supervivencia.
- XGBoost, SHAP u otros modelos complejos.
- Estimación individual de PD, LGD o EAD.
- Implementación de IFRS 9 o ECL regulatorio.
- Pronósticos macroeconómicos propios.
- Inferencia causal.
- MLflow, PostgreSQL, API, frontend, Docker o servicios en la nube.
- Dashboard interactivo.

Estas exclusiones son parte del diseño y no deben agregarse antes de cumplir
la definición de terminado.

## 4. Propuesta de valor

El usuario conceptual es un analista de riesgo que necesita:

- monitorear el deterioro de una cartera de consumo;
- entender qué variables macro están asociadas con la morosidad;
- contrastar un modelo contra una regla sencilla;
- cuantificar sensibilidades bajo escenarios adversos;
- reproducir cada cifra desde sus fuentes.

El valor del proyecto no consiste en afirmar que predice perfectamente el
IMOR. Consiste en mostrar una cadena analítica disciplinada desde datos
regulatorios hasta una decisión de monitoreo, incluyendo la posibilidad de
concluir que el modelo no mejora un benchmark simple.

## 5. Datos

El catálogo operativo vive en [`config/series.yml`](../config/series.yml) y su
proceso de selección se documenta en [`docs/fuentes.md`](fuentes.md).

### 5.1 IMOR de consumo de Sofipos

Fuente candidata: [Portafolio de Información de la
CNBV](https://portafolioinfo.cnbv.gob.mx/Paginas/Inicio.aspx).

Definición de trabajo:

\[
IMOR_t = \frac{CarteraVencida_t}{CarteraTotal_t}\times 100.
\]

Si el agregado debe reconstruirse desde instituciones:

\[
IMOR_t =
\frac{\sum_j CarteraVencida_{j,t}}
     {\sum_j CarteraTotal_{j,t}}
\times 100.
\]

No se usará el promedio simple de IMOR institucionales. La definición
completa y sus pendientes se encuentran en
[`docs/metodologia/definicion-imor.md`](metodologia/definicion-imor.md).

### 5.2 Inflación

Fuente candidata: INPC mensual de INEGI.

\[
Inflacion_t =
\left(\frac{INPC_t}{INPC_{t-12}} - 1\right)\times 100.
\]

La transformación debe reconciliarse contra una publicación oficial para una
muestra de meses.

### 5.3 Desempleo

Fuente candidata: tasa de desocupación mensual desestacionalizada de
ENOE/INEGI. Se documentará la población de referencia, revisiones y
comparabilidad durante la pandemia. No se interpolarán faltantes durante la
ingesta.

### 5.4 Tasa nominal y tasa real

Fuente candidata: [Sistema de Información Económica de
Banxico](https://www.banxico.org.mx/SieInternet/).

Se elegirá una tasa con cobertura suficiente y una justificación económica
como proxy de fondeo. La tasa real ex post se aproximará como:

\[
TasaReal_t = TasaNominal_t - Inflacion_t.
\]

Esta aproximación no equivale a una tasa real esperada.

### 5.5 Benchmark metodológico

El proyecto tomará como referencia el recuadro de Banxico
[*Determinantes de la morosidad de la cartera de consumo para las
Sofipos*](https://www.banxico.org.mx/publicaciones-y-prensa/reportes-sobre-el-sistema-financiero/recuadros/%7BBF224D96-2D2C-22A1-328E-2D98D71E3532%7D.pdf),
publicado en diciembre de 2025. Ese documento usa datos mensuales de junio de
2009 a agosto de 2025 y factores macroeconómicos rezagados tres meses. Sirve
como fundamento y punto de comparación, no como sustituto de la validación
propia.

## 6. Contrato de datos

Cada serie debe registrar:

| Campo | Descripción |
|---|---|
| `nombre_serie` | Nombre interno estable |
| `proveedor` | CNBV, Banxico o INEGI |
| `identificador` | Identificador oficial |
| `url_fuente` | Página institucional |
| `url_descarga` | Mecanismo reproducible de descarga |
| `fecha_descarga` | Fecha y hora de recuperación |
| `frecuencia_origen` | Frecuencia publicada |
| `frecuencia_modelo` | Frecuencia mensual |
| `unidad_origen` | Unidad publicada |
| `unidad_modelo` | Unidad analítica |
| `transformacion` | Regla reproducible |
| `rezago_publicacion` | Disponibilidad conocida o supuesta |
| `politica_revisiones` | Tratamiento de revisiones |
| `notas` | Rupturas y advertencias |

Contrato mínimo de la tabla analítica:

```text
mes_observacion          fecha mensual única, creciente y sin duplicados
imor_pct                 porcentaje, 0 <= valor <= 100
desempleo_pct            porcentaje, 0 <= valor <= 100
inflacion_interanual_pct porcentaje
tasa_nominal_pct         porcentaje
tasa_real_pct            porcentaje
indicador_covid          0 o 1
ruptura_contable         0 o 1, sólo si se confirma un cambio relevante
```

La tabla de modelado añadirá rezagos sin sobrescribir columnas observadas.

## 7. Diseño temporal

La unidad será el mes calendario, normalizado preferentemente al último día
del mes. La especificación principal usará:

```text
IMOR en t
    <- desempleo observado en t-3
    <- inflación observada en t-3
    <- tasa real observada en t-3
    <- IMOR observado en t-1
```

Reglas obligatorias:

- ordenar antes de crear rezagos;
- alinear rezagos por mes calendario, no por posición;
- verificar que `t-3` sea exactamente tres meses anterior;
- no rellenar valores con información futura;
- tomar decisiones de especificación sólo con entrenamiento;
- reservar los últimos 24 meses completos como prueba final, si la muestra lo
  permite;
- registrar la fecha máxima disponible de cada serie.

El MVP usará datos históricos revisados, no vintages de publicación en tiempo
real. No debe presentarse como backtest con información disponible en tiempo
real.

## 8. Auditoría de calidad

Antes de ajustar modelos se generará un reporte que cubra:

- rango temporal y número de observaciones;
- meses faltantes y duplicados;
- unidades y rangos;
- cambios abruptos;
- cobertura institucional del IMOR;
- revisiones o rupturas metodológicas;
- impacto de la pandemia;
- trazabilidad hasta los archivos originales.

Dos riesgos requieren atención expresa:

1. Los datos laborales y de cartera pueden ser no comparables durante
   2020–2021.
2. IFRS 9 u otros cambios regulatorios pueden modificar la definición del IMOR.

Ante una ruptura material se mostrará una sensibilidad por régimen, una
exclusión justificada o una conclusión explícita de no comparabilidad.

## 9. Modelos

### 9.1 Persistencia

\[
\widehat{IMOR}_{t}=IMOR_{t-1}.
\]

Es el benchmark obligatorio porque una serie persistente puede dar una falsa
impresión de valor a un modelo más complejo.

### 9.2 Regresión dinámica

\[
IMOR_t = \alpha
+ \rho IMOR_{t-1}
+ \beta_1 TasaReal_{t-3}
+ \beta_2 Inflacion_{t-3}
+ \beta_3 Desempleo_{t-3}
+ \delta Covid_t
+ \gamma Ruptura_t
+ \varepsilon_t.
\]

`Covid_t` y `Ruptura_t` sólo se incluirán si se definen antes de observar el
resultado final y tienen justificación documental.

La estimación principal usará OLS con errores estándar HAC/Newey–West. Se
reportarán coeficientes, intervalos, residuos, autocorrelación, estabilidad y
desempeño fuera de muestra.

No se eliminarán variables sólo por falta de significancia. La especificación
debe mantenerse parsimoniosa y guiada por la pregunta económica.

### 9.3 Diagnósticos

Como mínimo:

- residuos y su autocorrelación;
- heterocedasticidad;
- multicolinealidad;
- sensibilidad con y sin pandemia;
- predicciones fuera del rango de 0 a 100.

No se ocultarán valores imposibles mediante recorte silencioso. Si aparecen,
se reportarán y podrá evaluarse el logit de `IMOR/100` como sensibilidad.

## 10. Evaluación

### 10.1 Partición final

- Reservar los últimos 24 meses completos como prueba.
- No consultar sus métricas durante la selección.
- Si quedan menos de 96 observaciones de entrenamiento, reducir la prueba a 12
  meses y documentar la decisión.

### 10.2 Backtest

Usar una ventana expansiva con pronóstico a un mes dentro del periodo de
entrenamiento. No realizar una búsqueda extensa de hiperparámetros.

### 10.3 Métricas

Para persistencia y regresión:

- MAE en puntos porcentuales de IMOR;
- RMSE;
- sesgo medio;
- MASE o mejora frente a persistencia;
- error por periodo.

La conclusión debe responder si la regresión supera la persistencia, si la
mejora es estable y si el modelo conserva valor para sensibilidad aunque no
mejore el pronóstico.

## 11. Escenarios

Cada escenario tendrá nombre, narrativa, fecha base, horizonte de 12 meses,
trayectorias, unidades, shocks, autor y advertencias. Vivirá en YAML o CSV,
fuera del código.

Parámetros iniciales sujetos a revisión antes de congelar el MVP:

| Escenario | Desempleo | Inflación | Tasa real | Narrativa |
|---|---:|---:|---:|---|
| Base | Sin shock | Sin shock | Sin shock | Convergencia a niveles recientes |
| Moderado | +1.0 pp | +2.0 pp | +1.5 pp | Presión transitoria sobre ingreso y costo financiero |
| Severo | +2.5 pp | +4.0 pp | +3.0 pp | Deterioro laboral y condiciones restrictivas persistentes |

Los shocks son diferencias frente a la trayectoria base. Se aplicarán
gradualmente durante tres meses y permanecerán el resto del horizonte.

Para cada escenario se reportará:

- trayectoria mensual del IMOR;
- diferencia en puntos porcentuales y porcentaje frente a base;
- mes de máximo deterioro;
- contribución mecánica aproximada de cada factor.

### 11.1 Incertidumbre

Se simularán al menos 1,000 trayectorias con semilla fija. Cada una extraerá
coeficientes de una normal multivariada definida por los estimadores y su
matriz HAC. Se reportarán percentiles 10, 50 y 90.

Las bandas representarán sólo incertidumbre paramétrica condicionada al
escenario; no error de proceso, incertidumbre macro total ni cambios
estructurales futuros.

## 12. Visualizaciones

Máximo seis figuras principales:

1. IMOR histórico con pandemia y rupturas.
2. Variables macro estandarizadas.
3. Observado frente a pronósticos fuera de muestra.
4. Error fuera de muestra a través del tiempo.
5. Coeficientes con intervalos.
6. IMOR por escenario con bandas.

Cada figura incluirá título informativo, unidad, periodo, fuente y nota
metodológica cuando sea necesaria.

## 13. Estructura objetivo

La estructura crecerá conforme aparezca lógica real; no se crearán carpetas
vacías para anticipar fases futuras.

```text
credit-risk-lab/
├── README.md
├── CONTRIBUTING.md
├── pyproject.toml
├── uv.lock
├── Makefile
├── config/
│   ├── series.yml
│   └── escenarios.yml          # cuando comience esa fase
├── data/
│   ├── README.md
│   └── sample/
├── docs/
│   ├── especificacion-mvp.md
│   ├── fuentes.md
│   └── metodologia/
├── src/riesgo_crediticio/
│   ├── datos/                   # al implementar la ingesta
│   ├── modelos/                 # al implementar el benchmark
│   ├── escenarios/              # al implementar el motor
│   └── reportes/                # al generar resultados
├── tests/
│   └── fixtures/
└── reports/                         # al generar resultados
```

## 14. Tecnología

- Python 3.12 o superior;
- `uv` para entorno y dependencias;
- pandas, NumPy y PyArrow cuando comience la ingesta;
- statsmodels para regresión y errores HAC;
- scikit-learn sólo para métricas;
- Matplotlib y Seaborn;
- PyYAML;
- pytest, Ruff, mypy y pre-commit.

No se requiere DuckDB para el volumen esperado.

## 15. Comandos previstos

Los comandos se agregarán cuando exista la funcionalidad correspondiente:

```bash
make setup
make datos
make validar
make reporte
make pruebas
```

La descarga deberá ser idempotente: un archivo existente con el mismo
contenido no se modificará innecesariamente.

## 16. Pruebas

### 16.1 Datos

- fechas mensuales únicas y ordenadas;
- meses faltantes y duplicados;
- rangos y unidades;
- reconciliación del IMOR agregado;
- fallo explícito ante cambios inesperados de esquema.

### 16.2 Transformaciones

- inflación interanual;
- tasa real en unidades consistentes;
- rezagos por mes calendario;
- ausencia de información futura;
- partición entrenamiento/prueba sin traslape.

### 16.3 Modelado

- persistencia correcta;
- métricas contra ejemplos manuales;
- ventanas expansivas sin fuga;
- predicciones reproducibles.

### 16.4 Escenarios

- horizonte de 12 meses;
- shocks en unidades correctas;
- base con shock cero;
- severo no menor que moderado;
- rezagos correctos;
- semilla reproducible;
- advertencia ante IMOR fuera de 0–100.

## 17. Reporte final

El reporte responderá:

1. ¿Qué cartera y periodo se analizaron?
2. ¿Qué problemas de calidad o comparabilidad existen?
3. ¿La regresión mejora la persistencia fuera de muestra?
4. ¿Qué variables muestran una asociación estable?
5. ¿Cuánto cambia el IMOR bajo cada escenario?
6. ¿Qué resultados dependen de supuestos?
7. ¿Qué no puede concluirse?

No se redactarán hallazgos antes de ejecutar el análisis.

## 18. Riesgos y mitigaciones

| Riesgo | Consecuencia | Mitigación |
|---|---|---|
| Pocas observaciones | Coeficientes inestables | Modelo parsimonioso y validación temporal |
| Alta persistencia | Buen ajuste aparente | Benchmark y rezago del IMOR |
| Autocorrelación | Inferencia optimista | Errores HAC y diagnósticos |
| Multicolinealidad | Coeficientes difíciles de separar | Pocas variables e incertidumbre |
| Pandemia | Ruptura no representativa | Indicador y sensibilidad |
| Cambios contables | Serie no homogénea | Metadatos y sensibilidad por régimen |
| Cambio de instituciones | Efecto composición | Agregado ponderado y cobertura |
| Datos revisados | Backtest favorable | Declarar que no es tiempo real |
| Escenarios arbitrarios | Falsa precisión | Archivos versionados y sensibilidad |
| Correlación como causalidad | Recomendaciones incorrectas | Lenguaje explícito de asociación |

## 19. Plan de trabajo

### Hito 0: fuentes y definiciones — 3 a 5 horas

- localizar series y metadatos;
- fijar identificadores y URLs;
- confirmar la definición de IMOR;
- identificar rupturas;
- completar `config/series.yml`.

Criterio de salida: cada serie tiene fuente, unidad, frecuencia, cobertura y
transformación verificadas.

### Hito 1: flujo de datos — 4 a 6 horas

- implementar ingesta;
- normalizar fechas y unidades;
- construir variables y rezagos;
- generar Parquet analítico;
- producir reporte de calidad;
- agregar pruebas.

Criterio de salida: el conjunto analítico se reproduce con un comando.

### Hito 2: modelos y backtest — 4 a 6 horas

- implementar persistencia;
- estimar regresión dinámica;
- ejecutar backtest expansivo;
- evaluar prueba final;
- generar diagnósticos.

Criterio de salida: comparación fuera de muestra reproducible.

### Hito 3: escenarios y reporte — 4 a 7 horas

- definir escenarios versionados;
- generar trayectorias recursivas;
- simular incertidumbre;
- crear figuras;
- redactar conclusiones y limitaciones.

Criterio de salida: cada resultado identifica datos, modelo y supuestos.

Tiempo total esperado: 15 a 24 horas, más contingencia por dificultades en
las fuentes de la CNBV.

## 20. Definición de terminado

El MVP estará terminado cuando:

- use exclusivamente fuentes oficiales mexicanas;
- documente series y transformaciones;
- reproduzca el conjunto analítico con un comando;
- conserve un periodo final fuera del ajuste;
- compare regresión contra persistencia;
- reporte MAE, RMSE, sesgo y mejora frente al benchmark;
- documente pandemia, cambios contables y composición;
- versione escenarios fuera del código;
- muestre escenarios con incertidumbre;
- pruebe fechas, rezagos, métricas y shocks;
- reproduzca resultados desde un entorno limpio;
- distinga observaciones, estimaciones y supuestos;
- evite afirmaciones causales, regulatorias o individuales.

El MVP puede ser exitoso aunque la regresión no supere la persistencia. En ese
caso, el hallazgo será que los factores macro aportan sensibilidad, pero no
capacidad predictiva incremental suficiente.

## 21. Extensiones no comprometidas

Sólo después de cerrar el MVP se evaluará:

1. panel por Sofipo;
2. otros productos o sectores;
3. ENIF como módulo de vulnerabilidad;
4. IGAE, empleo formal o salarios reales;
5. modelos ARIMAX o de corrección de errores;
6. cartera sintética calibrada;
7. aplicación web o dashboard.

Ninguna extensión debe bloquear la publicación del MVP.

## 22. Reglas de implementación

1. Inspeccionar el repositorio y sus instrucciones antes de modificarlo.
2. Preservar cambios del usuario.
3. Completar primero el hito 0.
4. No descargar datos grandes sin verificar fuente y condiciones de uso.
5. Presentar identificadores y disponibilidad antes de automatizar descargas.
6. Construir un corte vertical con una muestra pequeña.
7. No fabricar observaciones, identificadores ni resultados.
8. Mantener notebooks exploratorios y mover lógica estable a `src/`.
9. Ejecutar pruebas al terminar cada hito.
10. Distinguir siempre lo observado, calculado, estimado y supuesto.
11. Detener ampliaciones no requeridas para la definición de terminado.

## 23. Mensaje de presentación

El README final debe abrir con la pregunta de riesgo:

> ¿Qué tan sensible es la morosidad del crédito al consumo de las Sofipos
> mexicanas al estrés laboral y financiero, y agrega valor un modelo macro
> interpretable frente a conservar la última tasa observada?

La narrativa final debe comunicar un problema mexicano concreto, fuentes
oficiales, un benchmark exigente, validación fuera de muestra, escenarios
transparentes y conclusiones proporcionales a la evidencia.

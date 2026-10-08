"""Regresión dinámica OLS/HAC y comparación temporal contra persistencia."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd
import statsmodels.api as sm  # type: ignore[import-untyped]
import statsmodels.stats.diagnostic as diagnostico_sm  # type: ignore[import-untyped]
import statsmodels.stats.outliers_influence as influencia_sm  # type: ignore[import-untyped]
from statsmodels.stats.stattools import durbin_watson  # type: ignore[import-untyped]

from riesgo_crediticio.modelos.backtest import (
    COLUMNAS_REGRESION_DINAMICA,
    MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA,
    ErrorModelo,
    Metricas,
    _escala_mase,
    calcular_metricas,
    crear_caracteristicas,
    preparar_regresion_dinamica,
    pronosticar_persistencia,
    separar_prueba_final,
)

PREDICTORES = COLUMNAS_REGRESION_DINAMICA[1:]
MAX_REZAGOS_HAC = 3


@dataclass(frozen=True)
class EvaluacionRegresion:
    """Predicciones, coeficientes, residuos y reporte de la regresión dinámica."""

    predicciones_backtest: pd.DataFrame
    predicciones_prueba: pd.DataFrame
    coeficientes: pd.DataFrame
    residuos: pd.DataFrame
    reporte: dict[str, Any]


def _raiz_proyecto() -> Path:
    return Path(__file__).resolve().parents[3]


def _matriz_predictores(tabla: pd.DataFrame) -> pd.DataFrame:
    """Construye la matriz de diseño con intercepto y orden fijo de columnas."""
    return cast(
        pd.DataFrame, sm.add_constant(tabla[list(PREDICTORES)], has_constant="add")
    )


def ajustar_regresion_dinamica(tabla: pd.DataFrame) -> Any:
    """Ajusta OLS con covarianza HAC/Newey-West y rezago máximo preespecificado."""
    if len(tabla) < MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA:
        raise ErrorModelo(
            "La regresión dinámica requiere al menos "
            f"{MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA} observaciones de entrenamiento."
        )
    modelo = sm.OLS(tabla["imor_pct"], _matriz_predictores(tabla), hasconst=True)
    return modelo.fit(cov_type="HAC", cov_kwds={"maxlags": MAX_REZAGOS_HAC})


def pronosticar_regresion_dinamica(ajuste: Any, tabla: pd.DataFrame) -> pd.DataFrame:
    """Genera pronósticos a un mes sin recortar valores fuera de rango."""
    predicciones = pd.Series(
        ajuste.predict(_matriz_predictores(tabla)), index=tabla.index
    )
    resultado = (
        tabla[["mes_observacion", "imor_pct"]]
        .copy()
        .rename(columns={"imor_pct": "imor_observado_pct"})
    )
    resultado["prediccion_pct"] = predicciones
    resultado["error_pp"] = (
        resultado["prediccion_pct"] - resultado["imor_observado_pct"]
    )
    resultado["fuera_rango_0_100"] = ~resultado["prediccion_pct"].between(0, 100)
    resultado["modelo"] = "regresion_dinamica_ols_hac"
    return resultado.reset_index(drop=True)


def _metricas_comparadas(
    predicciones: pd.DataFrame,
    escala_mase: float,
    mae_persistencia: float,
) -> Metricas:
    """Calcula métricas y mejora porcentual frente a persistencia alineada."""
    metricas = calcular_metricas(predicciones, escala_mase)
    if not math.isfinite(mae_persistencia) or mae_persistencia <= 0:
        raise ErrorModelo(
            "No se puede comparar contra persistencia con MAE no positivo."
        )
    metricas["mejora_vs_persistencia_pct"] = (
        100 * (mae_persistencia - metricas["mae_pp"]) / mae_persistencia
    )
    return metricas


def ejecutar_backtest_regresion(tabla: pd.DataFrame) -> pd.DataFrame:
    """Reestima OLS/HAC para cada pronóstico de un paso de ventana expansiva."""
    if len(tabla) <= MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA:
        raise ErrorModelo(
            "El entrenamiento no deja observaciones para el backtest de regresión."
        )
    predicciones: list[pd.DataFrame] = []
    for indice in range(MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA, len(tabla)):
        ajuste = ajustar_regresion_dinamica(tabla.iloc[:indice])
        pronostico = pronosticar_regresion_dinamica(ajuste, tabla.iloc[[indice]])
        pronostico["observaciones_entrenamiento"] = indice
        predicciones.append(pronostico)
    return pd.concat(predicciones, ignore_index=True)


def extraer_coeficientes(ajuste: Any) -> pd.DataFrame:
    """Convierte estimadores HAC e intervalos de confianza a una tabla portable."""
    intervalos = ajuste.conf_int()
    return pd.DataFrame(
        {
            "termino": ajuste.params.index,
            "estimacion": ajuste.params.values,
            "error_estandar_hac": ajuste.bse.values,
            "intervalo_inferior": intervalos.iloc[:, 0].values,
            "intervalo_superior": intervalos.iloc[:, 1].values,
            "valor_p": ajuste.pvalues.values,
        }
    )


def diagnosticar_regresion(ajuste: Any) -> dict[str, object]:
    """Reporta autocorrelación, heterocedasticidad y multicolinealidad visibles."""
    residuales = ajuste.resid
    matriz = ajuste.model.exog
    _, valor_p_bp, _, _ = diagnostico_sm.het_breuschpagan(residuales, matriz)
    nombres = list(ajuste.model.exog_names)
    vif = {
        nombre: float(influencia_sm.variance_inflation_factor(matriz, indice))
        for indice, nombre in enumerate(nombres)
        if nombre != "const"
    }
    return {
        "durbin_watson": float(durbin_watson(residuales)),
        "breusch_pagan_valor_p": float(valor_p_bp),
        "vif": vif,
    }


def _sensibilidad_sin_pandemia(entrenamiento: pd.DataFrame) -> dict[str, object]:
    """Ajusta sensibilidad sin COVID sólo cuando conserva el mínimo acordado."""
    sin_pandemia = entrenamiento.loc[entrenamiento["indicador_covid"] == 0].copy()
    if len(sin_pandemia) < MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA:
        return {
            "estado": "no_estimado",
            "filas": len(sin_pandemia),
            "motivo": (
                "Excluir la pandemia no conserva el mínimo de "
                f"{MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA} observaciones."
            ),
        }
    return {
        "estado": "estimado",
        "filas": len(sin_pandemia),
        "coeficientes": extraer_coeficientes(
            ajustar_regresion_dinamica(sin_pandemia)
        ).to_dict("records"),
    }


def evaluar_regresion_dinamica(tabla: pd.DataFrame) -> EvaluacionRegresion:
    """Evalúa la especificación dinámica contra persistencia fuera de muestra."""
    dinamica = preparar_regresion_dinamica(crear_caracteristicas(tabla))
    particion = separar_prueba_final(
        dinamica, minimo_entrenamiento=MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA
    )
    ajuste = ajustar_regresion_dinamica(particion.entrenamiento)
    predicciones_prueba = pronosticar_regresion_dinamica(ajuste, particion.prueba)
    predicciones_backtest = ejecutar_backtest_regresion(particion.entrenamiento)
    persistencia_prueba = pronosticar_persistencia(particion.prueba)
    persistencia_backtest = pronosticar_persistencia(
        particion.entrenamiento.iloc[MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA:]
    )
    escala_mase = _escala_mase(particion.entrenamiento)
    metricas_prueba_persistencia = calcular_metricas(persistencia_prueba, escala_mase)
    metricas_backtest_persistencia = calcular_metricas(
        persistencia_backtest, escala_mase
    )
    residuos = pd.DataFrame(
        {
            "mes_observacion": particion.entrenamiento["mes_observacion"],
            "imor_observado_pct": particion.entrenamiento["imor_pct"],
            "ajuste_pct": ajuste.fittedvalues,
            "residuo_pp": ajuste.resid,
        }
    )
    reporte: dict[str, Any] = {
        "modelo": "regresion_dinamica_ols_hac",
        "especificacion": {
            "respuesta": "imor_pct_t",
            "predictores": list(PREDICTORES),
            "max_rezagos_hac": MAX_REZAGOS_HAC,
            "minimo_entrenamiento": MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA,
        },
        "particion_final": {
            "meses_prueba": particion.meses_prueba,
            "filas_entrenamiento": len(particion.entrenamiento),
            "filas_prueba": len(particion.prueba),
            "inicio_entrenamiento": particion.entrenamiento["mes_observacion"]
            .min()
            .date()
            .isoformat(),
            "fin_entrenamiento": particion.entrenamiento["mes_observacion"]
            .max()
            .date()
            .isoformat(),
            "inicio_prueba": particion.prueba["mes_observacion"]
            .min()
            .date()
            .isoformat(),
            "fin_prueba": particion.prueba["mes_observacion"].max().date().isoformat(),
        },
        "backtest_expansivo": {
            "filas": len(predicciones_backtest),
            "metricas_regresion": _metricas_comparadas(
                predicciones_backtest,
                escala_mase,
                metricas_backtest_persistencia["mae_pp"],
            ),
            "metricas_persistencia": metricas_backtest_persistencia,
        },
        "prueba_final": {
            "metricas_regresion": _metricas_comparadas(
                predicciones_prueba,
                escala_mase,
                metricas_prueba_persistencia["mae_pp"],
            ),
            "metricas_persistencia": metricas_prueba_persistencia,
            "predicciones_fuera_rango_0_100": int(
                predicciones_prueba["fuera_rango_0_100"].sum()
            ),
        },
        "diagnosticos_entrenamiento": diagnosticar_regresion(ajuste),
        "sensibilidad_sin_pandemia": _sensibilidad_sin_pandemia(
            particion.entrenamiento
        ),
    }
    return EvaluacionRegresion(
        predicciones_backtest=predicciones_backtest,
        predicciones_prueba=predicciones_prueba,
        coeficientes=extraer_coeficientes(ajuste),
        residuos=residuos,
        reporte=reporte,
    )


def guardar_evaluacion(resultado: EvaluacionRegresion, directorio: Path) -> None:
    """Guarda todos los artefactos de evaluación sin versionar resultados."""
    directorio.mkdir(parents=True, exist_ok=True)
    resultado.predicciones_backtest.to_parquet(
        directorio / "predicciones_regresion_backtest.parquet", index=False
    )
    resultado.predicciones_prueba.to_parquet(
        directorio / "predicciones_regresion_prueba.parquet", index=False
    )
    resultado.coeficientes.to_parquet(
        directorio / "coeficientes_hac.parquet", index=False
    )
    resultado.residuos.to_parquet(
        directorio / "residuos_regresion.parquet", index=False
    )
    (directorio / "reporte_regresion_dinamica.json").write_text(
        json.dumps(resultado.reporte, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def ejecutar(args: argparse.Namespace) -> Path:
    """Evalúa la regresión dinámica a partir del conjunto analítico."""
    entrada = Path(args.entrada).resolve()
    if not entrada.is_file():
        raise ErrorModelo(f"No existe el conjunto analítico: {entrada}")
    directorio = Path(args.directorio_salida).resolve()
    guardar_evaluacion(evaluar_regresion_dinamica(pd.read_parquet(entrada)), directorio)
    return directorio


def argumentos() -> argparse.ArgumentParser:
    """Construye la interfaz de línea de comandos de la regresión dinámica."""
    raiz = _raiz_proyecto()
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument(
        "--entrada",
        type=Path,
        default=raiz / "data" / "processed" / "conjunto_analitico.parquet",
    )
    analizador.add_argument(
        "--directorio-salida",
        type=Path,
        default=raiz / "data" / "interim" / "modelos",
    )
    return analizador


def main() -> None:
    """Ejecuta la comparación y muestra el directorio de artefactos."""
    try:
        salida = ejecutar(argumentos().parse_args())
    except ErrorModelo as error:
        raise SystemExit(f"Error de modelado: {error}") from error
    print(f"Evaluación de regresión dinámica generada: {salida}")


if __name__ == "__main__":
    main()

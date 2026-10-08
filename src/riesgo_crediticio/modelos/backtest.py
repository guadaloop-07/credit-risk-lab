"""Benchmark de persistencia y evaluación temporal reproducible del IMOR."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import pandas as pd

COLUMNAS_REQUERIDAS = (
    "mes_observacion",
    "imor_pct",
    "tasa_real_pct",
    "inflacion_interanual_pct",
    "desempleo_pct",
    "indicador_covid",
    "ruptura_contable",
)
COLUMNAS_REZAGADAS = {
    "imor_pct": 1,
    "tasa_real_pct": 3,
    "inflacion_interanual_pct": 3,
    "desempleo_pct": 3,
}
COLUMNAS_REGRESION_DINAMICA = (
    "imor_pct",
    "imor_lag_1",
    "tasa_real_lag_3",
    "inflacion_interanual_lag_3",
    "desempleo_lag_3",
    "indicador_covid",
    "ruptura_contable",
)
MINIMO_ENTRENAMIENTO_PERSISTENCIA = 96
MINIMO_ENTRENAMIENTO_REGRESION_DINAMICA = 84
MESES_PRUEBA_PREFERIDOS = 24
MESES_PRUEBA_REDUCIDOS = 12


class ErrorModelo(RuntimeError):
    """Indica que la tabla no permite una evaluación temporal válida."""


class Metricas(TypedDict):
    """Métricas de error expresadas en puntos porcentuales de IMOR."""

    mae_pp: float
    rmse_pp: float
    sesgo_pp: float
    mase: float
    mejora_vs_persistencia_pct: float


@dataclass(frozen=True)
class ParticionTemporal:
    """Separación cronológica entre entrenamiento y prueba final."""

    entrenamiento: pd.DataFrame
    prueba: pd.DataFrame
    meses_prueba: int


@dataclass(frozen=True)
class EvaluacionPersistencia:
    """Predicciones y reporte del benchmark de persistencia."""

    predicciones_backtest: pd.DataFrame
    predicciones_prueba: pd.DataFrame
    reporte: dict[str, object]


def _raiz_proyecto() -> Path:
    return Path(__file__).resolve().parents[3]


def crear_caracteristicas(tabla: pd.DataFrame) -> pd.DataFrame:
    """Crea rezagos preespecificados sin descartar historia útil para persistencia."""
    faltantes = sorted(set(COLUMNAS_REQUERIDAS).difference(tabla.columns))
    if faltantes:
        raise ErrorModelo(f"Faltan columnas requeridas: {', '.join(faltantes)}.")

    resultado = tabla.copy()
    resultado["mes_observacion"] = pd.to_datetime(
        resultado["mes_observacion"], errors="coerce"
    )
    if resultado["mes_observacion"].isna().any():
        raise ErrorModelo("mes_observacion contiene fechas no válidas.")
    if resultado["mes_observacion"].duplicated().any():
        raise ErrorModelo("mes_observacion contiene meses duplicados.")

    resultado = resultado.sort_values("mes_observacion", ignore_index=True)
    for columna, rezago in COLUMNAS_REZAGADAS.items():
        resultado[f"{columna.removesuffix('_pct')}_lag_{rezago}"] = resultado[
            columna
        ].shift(rezago)

    resultado = resultado.dropna(subset=["imor_pct", "imor_lag_1"]).reset_index(
        drop=True
    )
    if resultado.empty:
        raise ErrorModelo("No quedan observaciones con IMOR rezagado disponible.")
    return resultado


def preparar_regresion_dinamica(caracteristicas: pd.DataFrame) -> pd.DataFrame:
    """Conserva los casos completos requeridos por la especificación dinámica."""
    faltantes = sorted(set(COLUMNAS_REGRESION_DINAMICA).difference(caracteristicas))
    if faltantes:
        raise ErrorModelo(
            f"Faltan columnas para la regresión dinámica: {', '.join(faltantes)}."
        )
    resultado = caracteristicas.dropna(subset=COLUMNAS_REGRESION_DINAMICA).reset_index(
        drop=True
    )
    if resultado.empty:
        raise ErrorModelo("No hay casos completos para la regresión dinámica.")
    return resultado


def separar_prueba_final(
    tabla: pd.DataFrame,
    minimo_entrenamiento: int = MINIMO_ENTRENAMIENTO_PERSISTENCIA,
) -> ParticionTemporal:
    """Reserva 24 meses finales o 12 si se conserva el mínimo indicado."""
    for meses_prueba in (MESES_PRUEBA_PREFERIDOS, MESES_PRUEBA_REDUCIDOS):
        if len(tabla) - meses_prueba >= minimo_entrenamiento:
            return ParticionTemporal(
                entrenamiento=tabla.iloc[:-meses_prueba].copy(),
                prueba=tabla.iloc[-meses_prueba:].copy(),
                meses_prueba=meses_prueba,
            )
    raise ErrorModelo(
        "La muestra no permite reservar prueba final y conservar el mínimo de "
        f"{minimo_entrenamiento} observaciones de entrenamiento."
    )


def pronosticar_persistencia(tabla: pd.DataFrame) -> pd.DataFrame:
    """Pronostica IMOR a un mes con la última observación disponible."""
    if "imor_lag_1" not in tabla or tabla["imor_lag_1"].isna().any():
        raise ErrorModelo("La persistencia requiere el rezago imor_lag_1 completo.")
    resultado = tabla[["mes_observacion", "imor_pct", "imor_lag_1"]].copy()
    resultado = resultado.rename(
        columns={"imor_pct": "imor_observado_pct", "imor_lag_1": "prediccion_pct"}
    )
    resultado["error_pp"] = (
        resultado["prediccion_pct"] - resultado["imor_observado_pct"]
    )
    resultado["modelo"] = "persistencia"
    return resultado


def _escala_mase(entrenamiento: pd.DataFrame) -> float:
    escala = float(entrenamiento["imor_pct"].diff().abs().dropna().mean())
    if not math.isfinite(escala) or escala <= 0:
        raise ErrorModelo("No se puede calcular MASE: la escala ingenua es nula.")
    return escala


def calcular_metricas(predicciones: pd.DataFrame, escala_mase: float) -> Metricas:
    """Calcula errores de pronóstico sin alterar las predicciones originales."""
    if predicciones.empty:
        raise ErrorModelo("No hay predicciones para calcular métricas.")
    errores = predicciones["error_pp"].astype(float)
    mae = float(errores.abs().mean())
    return {
        "mae_pp": mae,
        "rmse_pp": math.sqrt(float((errores**2).mean())),
        "sesgo_pp": float(errores.mean()),
        "mase": mae / escala_mase,
        "mejora_vs_persistencia_pct": 0.0,
    }


def ejecutar_backtest_expansivo(
    entrenamiento: pd.DataFrame,
    minimo_entrenamiento: int = MINIMO_ENTRENAMIENTO_PERSISTENCIA,
) -> pd.DataFrame:
    """Evalúa pronósticos de un paso con una ventana de entrenamiento expansiva."""
    if len(entrenamiento) <= minimo_entrenamiento:
        raise ErrorModelo(
            "El entrenamiento no deja observaciones para el backtest expansivo."
        )
    predicciones = pronosticar_persistencia(entrenamiento.iloc[minimo_entrenamiento:])
    predicciones["observaciones_entrenamiento"] = range(
        minimo_entrenamiento, len(entrenamiento)
    )
    return predicciones


def evaluar_persistencia(tabla: pd.DataFrame) -> EvaluacionPersistencia:
    """Genera benchmark, backtest expansivo y evaluación final fuera de muestra."""
    caracteristicas = crear_caracteristicas(tabla)
    particion = separar_prueba_final(caracteristicas)
    escala_mase = _escala_mase(particion.entrenamiento)
    predicciones_backtest = ejecutar_backtest_expansivo(particion.entrenamiento)
    predicciones_prueba = pronosticar_persistencia(particion.prueba)
    reporte: dict[str, object] = {
        "modelo": "persistencia",
        "definicion": "prediccion_t = imor_observado_t-1",
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
            "minimo_entrenamiento": MINIMO_ENTRENAMIENTO_PERSISTENCIA,
            "metricas": calcular_metricas(predicciones_backtest, escala_mase),
        },
        "prueba_final": {
            "metricas": calcular_metricas(predicciones_prueba, escala_mase),
        },
    }
    return EvaluacionPersistencia(
        predicciones_backtest=predicciones_backtest,
        predicciones_prueba=predicciones_prueba,
        reporte=reporte,
    )


def guardar_evaluacion(resultado: EvaluacionPersistencia, directorio: Path) -> None:
    """Escribe predicciones y reporte en artefactos no versionados reconstruibles."""
    directorio.mkdir(parents=True, exist_ok=True)
    resultado.predicciones_backtest.to_parquet(
        directorio / "predicciones_persistencia_backtest.parquet", index=False
    )
    resultado.predicciones_prueba.to_parquet(
        directorio / "predicciones_persistencia_prueba.parquet", index=False
    )
    (directorio / "reporte_persistencia.json").write_text(
        json.dumps(resultado.reporte, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def ejecutar(args: argparse.Namespace) -> Path:
    """Evalúa persistencia a partir del conjunto analítico y guarda artefactos."""
    entrada = Path(args.entrada).resolve()
    if not entrada.is_file():
        raise ErrorModelo(f"No existe el conjunto analítico: {entrada}")
    directorio = Path(args.directorio_salida).resolve()
    guardar_evaluacion(evaluar_persistencia(pd.read_parquet(entrada)), directorio)
    return directorio


def argumentos() -> argparse.ArgumentParser:
    """Construye la interfaz de línea de comandos del benchmark."""
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
    """Ejecuta el benchmark y muestra el directorio de artefactos."""
    try:
        salida = ejecutar(argumentos().parse_args())
    except ErrorModelo as error:
        raise SystemExit(f"Error de modelado: {error}") from error
    print(f"Evaluación de persistencia generada: {salida}")


if __name__ == "__main__":
    main()

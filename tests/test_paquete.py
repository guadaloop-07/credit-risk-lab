"""Pruebas mínimas de la configuración del paquete."""

from riesgo_crediticio import __version__


def test_version_inicial() -> None:
    """La versión importada debe coincidir con la versión inicial."""
    assert __version__ == "0.1.0"

"""Prueba de conexión estándar del conector aws_cloudwatch.

Firma estándar Ruvic: def test_connection() -> tuple[bool, str]
- Lee la configuración EXCLUSIVAMENTE de las env vars RUVIC_AWS_CLOUDWATCH_*.
- Nunca lanza excepciones; retorna (ok, mensaje).

Ejecutable también como script para pruebas locales:
    python test_connection.py
"""

from __future__ import annotations


def test_connection() -> tuple[bool, str]:
    """Verifica acceso a CloudWatch listando alarmas, usando las env vars
    RUVIC_AWS_CLOUDWATCH_*."""
    try:
        from ruvic_aws_cloudwatch_connector import (
            CloudWatchAuthError,
            CloudWatchClient,
            CloudWatchDataError,
            CloudWatchNetworkError,
        )
    except ImportError:
        return (
            False,
            "La librería ruvic-aws-cloudwatch-connector no está instalada. "
            "Instala con: pip install git+https://github.com/Dgirto/"
            "AWS-CloudWatch.git#subdirectory=lib",
        )

    try:
        client = CloudWatchClient()  # valida que existan las env vars
    except ValueError as exc:
        return False, str(exc)

    try:
        client.ping()
    except CloudWatchAuthError as exc:
        return False, f"Autenticación fallida: {exc}"
    except CloudWatchNetworkError as exc:
        return False, f"Error de red: {exc}"
    except CloudWatchDataError as exc:
        return False, f"Error de datos: {exc}"
    except Exception as exc:  # red de seguridad: jamás propagar
        return False, f"Error inesperado: {exc}"

    return (True, f"Conexión exitosa a AWS CloudWatch en {client.config.region}")


if __name__ == "__main__":
    ok, message = test_connection()
    print(f"{'OK' if ok else 'FALLO'}: {message}")
    raise SystemExit(0 if ok else 1)

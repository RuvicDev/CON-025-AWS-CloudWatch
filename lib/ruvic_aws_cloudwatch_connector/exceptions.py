"""Excepciones propias del conector AWS CloudWatch.

Separan los tres tipos de fallo que el usuario debe distinguir:
autenticación, red/servidor y datos. Nunca exponemos excepciones
crípticas del SDK subyacente.
"""


class CloudWatchConnectorError(Exception):
    """Error base del conector."""


class CloudWatchAuthError(CloudWatchConnectorError):
    """Credenciales inválidas o permisos IAM insuficientes."""


class CloudWatchNetworkError(CloudWatchConnectorError):
    """No se pudo alcanzar el servicio (red, timeout, error temporal de AWS)."""


class CloudWatchDataError(CloudWatchConnectorError):
    """La operación es válida pero el recurso/parámetro es inválido."""

"""Conector Ruvic de solo lectura para AWS CloudWatch."""

from .client import CloudWatchClient
from .config import ENV_PREFIX, CloudWatchConfig
from .exceptions import (
    CloudWatchAuthError,
    CloudWatchConnectorError,
    CloudWatchDataError,
    CloudWatchNetworkError,
)
from .logging_utils import setup_logging

__all__ = [
    "ENV_PREFIX",
    "CloudWatchAuthError",
    "CloudWatchClient",
    "CloudWatchConfig",
    "CloudWatchConnectorError",
    "CloudWatchDataError",
    "CloudWatchNetworkError",
    "setup_logging",
]

__version__ = "1.0.0"

"""Cliente de solo lectura para AWS CloudWatch.

Capacidades:
- get_metric_statistics():  consultar métricas (ej. CPUUtilization de EC2).
- get_recent_logs():        leer las entradas más recientes de un log group.
- list_active_alarms():     listar las alarmas actualmente en estado ALARM.

Las credenciales SIEMPRE provienen de variables de entorno
RUVIC_AWS_CLOUDWATCH_* (ver config.CloudWatchConfig.from_env). Prohibido
hardcodearlas.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    EndpointConnectionError,
)

from .config import CloudWatchConfig
from .exceptions import (
    CloudWatchAuthError,
    CloudWatchConnectorError,
    CloudWatchDataError,
    CloudWatchNetworkError,
)
from .logging_utils import get_logger

_AUTH_ERROR_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "UnrecognizedClientException",
    "InvalidClientTokenId",
    "InvalidSignatureException",
}
_NOT_FOUND_ERROR_CODES = {"ResourceNotFoundException"}
_VALID_STATS = {"Average", "Sum", "Minimum", "Maximum", "SampleCount"}
_MAX_LOG_LIMIT = 500
_MAX_ALARM_LIMIT = 100


def _validate_limit(limit: Any, max_limit: int) -> int:
    try:
        return max(1, min(int(limit), max_limit))
    except (TypeError, ValueError) as exc:
        raise CloudWatchDataError(f"limit inválido: {limit!r}. Debe ser un número entero.") from exc


def _wrap_client_error(exc: ClientError, not_found_message: str) -> CloudWatchConnectorError:
    """Traduce un error de la API de AWS a una excepción propia, sin dejar
    escapar nunca el tipo crudo del SDK."""
    code = exc.response.get("Error", {}).get("Code", "")
    if code in _AUTH_ERROR_CODES:
        return CloudWatchAuthError(
            "Credenciales inválidas o sin permiso IAM suficiente para esta "
            "operación. Revisa la policy adjunta al usuario o rol."
        )
    if code in _NOT_FOUND_ERROR_CODES:
        return CloudWatchDataError(not_found_message)
    if code == "InvalidParameterValueException":
        return CloudWatchDataError(f"Parámetro inválido: {exc}")
    return CloudWatchDataError(f"Error de datos ({code}): {exc}")


class CloudWatchClient:
    """Cliente de solo lectura para métricas, logs y alarmas de AWS
    CloudWatch en la región configurada.

    Args:
        config: configuración de conexión. Si se omite, se lee de las
            variables de entorno RUVIC_AWS_CLOUDWATCH_* (comportamiento
            estándar en el runtime de la plataforma).

    Ejemplo:
        >>> client = CloudWatchClient()     # lee RUVIC_AWS_CLOUDWATCH_* del entorno
        >>> client.list_active_alarms()
        [{'name': 'cpu-alta-produccion', 'state': 'ALARM', ...}]
    """

    def __init__(self, config: CloudWatchConfig | None = None) -> None:
        self.config = config or CloudWatchConfig.from_env()
        self._logger = get_logger()
        self._cloudwatch_client: Any = None
        self._logs_client: Any = None

    # ------------------------------------------------------------------ #
    # Conexión
    # ------------------------------------------------------------------ #

    def _boto_config(self) -> BotoConfig:
        return BotoConfig(
            connect_timeout=self.config.connect_timeout,
            read_timeout=max(self.config.connect_timeout, 30),
            retries={"max_attempts": 2, "mode": "standard"},
        )

    def _get_cloudwatch_client(self) -> Any:
        if self._cloudwatch_client is not None:
            return self._cloudwatch_client
        self._cloudwatch_client = boto3.client(
            "cloudwatch",
            aws_access_key_id=self.config.access_key_id,
            aws_secret_access_key=self.config.secret_access_key,
            region_name=self.config.region,
            config=self._boto_config(),
        )
        return self._cloudwatch_client

    def _get_logs_client(self) -> Any:
        if self._logs_client is not None:
            return self._logs_client
        self._logs_client = boto3.client(
            "logs",
            aws_access_key_id=self.config.access_key_id,
            aws_secret_access_key=self.config.secret_access_key,
            region_name=self.config.region,
            config=self._boto_config(),
        )
        return self._logs_client

    def ping(self) -> bool:
        """Verifica la conexión listando hasta 1 alarma.

        Returns:
            True si la conexión funciona.

        Raises:
            CloudWatchAuthError / CloudWatchNetworkError / CloudWatchDataError.
        """
        try:
            self._get_cloudwatch_client().describe_alarms(MaxRecords=1)
        except ClientError as exc:
            raise _wrap_client_error(exc, "No se pudieron listar alarmas.") from exc
        except (EndpointConnectionError, BotoCoreError) as exc:
            raise CloudWatchNetworkError(
                f"No se pudo conectar al servicio CloudWatch en la región "
                f"{self.config.region!r} (timeout {self.config.connect_timeout}s). "
                "Verifica la región y el acceso de red."
            ) from exc
        self._logger.info("Ping exitoso a CloudWatch en %s", self.config.region)
        return True

    # ------------------------------------------------------------------ #
    # Capacidad 1: consultar métricas
    # ------------------------------------------------------------------ #

    def get_metric_statistics(
        self,
        namespace: str,
        metric_name: str,
        dimensions: dict[str, str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        period: int = 300,
        statistic: str = "Average",
    ) -> list[dict[str, Any]]:
        """Consulta los datapoints de una métrica de CloudWatch.

        Args:
            namespace: espacio de nombres del servicio (ej. "AWS/EC2",
                "AWS/RDS", "AWS/Lambda").
            metric_name: nombre de la métrica (ej. "CPUUtilization").
            dimensions: filtros de la métrica (ej.
                {"InstanceId": "i-0abcd1234"}). Opcional.
            start_time: inicio del rango (UTC). Default: hace 1 hora.
            end_time: fin del rango (UTC). Default: ahora.
            period: tamaño del intervalo en segundos (default 300 = 5 min).
            statistic: "Average", "Sum", "Minimum", "Maximum" o
                "SampleCount" (default "Average").

        Returns:
            Lista de dicts: {"timestamp", "value", "unit"}, ordenados
            cronológicamente.

        Ejemplo:
            >>> client.get_metric_statistics("AWS/EC2", "CPUUtilization",
            ...     {"InstanceId": "i-0abcd1234"})
            [{'timestamp': '2026-07-17T10:00:00Z', 'value': 23.5, 'unit': 'Percent'}]
        """
        if not isinstance(statistic, str) or statistic not in _VALID_STATS:
            raise CloudWatchDataError(
                f"statistic debe ser uno de: {', '.join(sorted(_VALID_STATS))}."
            )
        now = datetime.now(timezone.utc)
        end_time = end_time or now
        start_time = start_time or (end_time - timedelta(hours=1))
        dim_list = [{"Name": k, "Value": v} for k, v in (dimensions or {}).items()]

        client = self._get_cloudwatch_client()
        try:
            response = client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dim_list,
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=[statistic],
            )
        except ClientError as exc:
            raise _wrap_client_error(
                exc, f"No se encontró la métrica {namespace}/{metric_name}."
            ) from exc
        except (EndpointConnectionError, BotoCoreError) as exc:
            raise CloudWatchNetworkError(f"No se pudo consultar la métrica: {exc}") from exc

        result = sorted(
            (
                {
                    "timestamp": dp["Timestamp"].isoformat(),
                    "value": dp[statistic],
                    "unit": dp.get("Unit"),
                }
                for dp in response.get("Datapoints", [])
            ),
            key=lambda d: d["timestamp"],
        )
        self._logger.info(
            "Se obtuvieron %d datapoints de %s/%s", len(result), namespace, metric_name
        )
        return result

    # ------------------------------------------------------------------ #
    # Capacidad 2: leer logs recientes
    # ------------------------------------------------------------------ #

    def get_recent_logs(self, log_group: str, limit: int = 50) -> list[dict[str, Any]]:
        """Lee las entradas más recientes del log stream más reciente de
        un log group.

        Args:
            log_group: nombre completo del log group (ej.
                "/aws/lambda/mi-funcion", "/ecs/mi-servicio").
            limit: máximo de líneas de log a retornar (default 50, máximo 500).

        Returns:
            Lista de dicts: {"timestamp", "message"}, ordenados del más
            antiguo al más reciente.

        Ejemplo:
            >>> client.get_recent_logs("/aws/lambda/procesar-pedido", limit=20)
            [{'timestamp': '2026-07-17T10:00:00Z', 'message': 'START RequestId: ...'}]
        """
        if log_group is not None and not isinstance(log_group, str):
            raise CloudWatchDataError(f"log_group debe ser un string, no {type(log_group).__name__}.")
        log_group = (log_group or "").strip()
        if not log_group:
            raise CloudWatchDataError("log_group no puede estar vacío.")
        limit = _validate_limit(limit, _MAX_LOG_LIMIT)
        logs_client = self._get_logs_client()
        try:
            streams = logs_client.describe_log_streams(
                logGroupName=log_group,
                orderBy="LastEventTime",
                descending=True,
                limit=1,
            )
            stream_names = [s["logStreamName"] for s in streams.get("logStreams", [])]
            if not stream_names:
                return []
            events = logs_client.get_log_events(
                logGroupName=log_group,
                logStreamName=stream_names[0],
                limit=limit,
                startFromHead=False,
            )
        except ClientError as exc:
            raise _wrap_client_error(
                exc, f"El log group {log_group!r} no existe o no es accesible."
            ) from exc
        except (EndpointConnectionError, BotoCoreError) as exc:
            raise CloudWatchNetworkError(f"No se pudieron obtener los logs: {exc}") from exc

        result = [
            {"timestamp": event["timestamp"], "message": event["message"].rstrip("\n")}
            for event in events.get("events", [])
        ]
        self._logger.info('Obtenidas %d líneas de log de "%s"', len(result), log_group)
        return result

    # ------------------------------------------------------------------ #
    # Capacidad 3: listar alarmas activas
    # ------------------------------------------------------------------ #

    def list_active_alarms(self, limit: int = 100) -> list[dict[str, Any]]:
        """Lista las alarmas que están actualmente en estado ALARM.

        Args:
            limit: máximo de alarmas a retornar (default 100, máximo 100).

        Returns:
            Lista de dicts: {"name", "state", "reason", "namespace",
            "metric_name", "state_updated"}.

        Ejemplo:
            >>> client.list_active_alarms()
            [{'name': 'cpu-alta-produccion', 'state': 'ALARM', 'namespace': 'AWS/EC2', ...}]
        """
        limit = _validate_limit(limit, _MAX_ALARM_LIMIT)
        client = self._get_cloudwatch_client()
        try:
            response = client.describe_alarms(StateValue="ALARM", MaxRecords=limit)
        except ClientError as exc:
            raise _wrap_client_error(exc, "No se pudieron listar las alarmas.") from exc
        except (EndpointConnectionError, BotoCoreError) as exc:
            raise CloudWatchNetworkError(f"No se pudieron listar alarmas: {exc}") from exc

        result = [
            {
                "name": alarm["AlarmName"],
                "state": alarm["StateValue"],
                "reason": alarm.get("StateReason", ""),
                "namespace": alarm.get("Namespace"),
                "metric_name": alarm.get("MetricName"),
                "state_updated": alarm["StateUpdatedTimestamp"].isoformat(),
            }
            for alarm in response.get("MetricAlarms", [])
        ]
        self._logger.info("Se listaron %d alarmas activas", len(result))
        return result

---
name: aws-cloudwatch
description: >
  Usa la librería ruvic_aws_cloudwatch_connector para consultar métricas,
  logs y alarmas de AWS en modo solo lectura - consultar datapoints de
  una métrica (get_metric_statistics), leer las entradas más recientes de
  un log group (get_recent_logs) y listar las alarmas actualmente activas
  (list_active_alarms). Úsala cuando el usuario pida revisar métricas,
  logs o el estado de alarmas de sus recursos en AWS.
triggers:
- cloudwatch
- aws cloudwatch
- métricas
- alarmas
- logs de aws
---

# Conector AWS CloudWatch (ruvic_aws_cloudwatch_connector)

Librería Python de solo lectura para métricas, logs y alarmas de AWS CloudWatch. Está **preinstalada en el runtime** cuando el conector está configurado (si no, instálala con `pip install git+https://github.com/Dgirto/AWS-CloudWatch.git#subdirectory=lib`).

## Regla crítica de credenciales

El código generado **NUNCA hardcodea credenciales**. Siempre se leen de variables de entorno, disponibles cuando el conector `aws_cloudwatch` está configurado:

| Variable | Contenido |
|----------|-----------|
| `RUVIC_AWS_CLOUDWATCH_ACCESS_KEY_ID` | Access Key ID de IAM |
| `RUVIC_AWS_CLOUDWATCH_SECRET_ACCESS_KEY` | Secret Access Key |
| `RUVIC_AWS_CLOUDWATCH_REGION` | Región de AWS (ej. `us-east-1`) |
| `RUVIC_AWS_CLOUDWATCH_CONNECT_TIMEOUT` | (opcional) timeout en segundos |

Si estas variables NO existen, el conector no está configurado: no generes código que lo use; indica al usuario que lo configure en **Settings → Conectores**.

## Conexión (siempre igual)

```python
from ruvic_aws_cloudwatch_connector import CloudWatchClient

client = CloudWatchClient()  # lee RUVIC_AWS_CLOUDWATCH_* del entorno automáticamente
```

## Capacidad 1 — Consultar métricas

```python
from datetime import datetime, timedelta, timezone

datapoints = client.get_metric_statistics(
    "AWS/EC2", "CPUUtilization",
    dimensions={"InstanceId": "i-0abcd1234"},
    start_time=datetime.now(timezone.utc) - timedelta(hours=6),
    statistic="Average",
)
for dp in datapoints:
    print(dp["timestamp"], dp["value"], dp["unit"])
```

`namespace`/`metric_name` siguen la convención de CloudWatch (`AWS/EC2`, `AWS/RDS`, `AWS/Lambda`, etc.). Sin `start_time`/`end_time`, trae la última hora. `statistic` acepta `"Average"`, `"Sum"`, `"Minimum"`, `"Maximum"` o `"SampleCount"`.

## Capacidad 2 — Leer logs recientes

```python
logs = client.get_recent_logs("/aws/lambda/procesar-pedido", limit=50)
for entry in logs:
    print(entry["message"])
```

Lee el log stream más reciente de un log group completo (formato `/aws/lambda/...`, `/ecs/...`, etc.).

## Capacidad 3 — Listar alarmas activas

```python
alarms = client.list_active_alarms()
for alarm in alarms:
    print(f"{alarm['name']}: {alarm['reason']}")
```

Solo retorna alarmas actualmente en estado `ALARM` (no `OK` ni `INSUFFICIENT_DATA`).

## Manejo de errores

```python
from ruvic_aws_cloudwatch_connector import (
    CloudWatchAuthError, CloudWatchDataError, CloudWatchNetworkError,
)

try:
    alarms = client.list_active_alarms()
except CloudWatchAuthError:
    print("Credenciales inválidas o sin permiso IAM sobre CloudWatch")
except CloudWatchNetworkError:
    print("No se pudo alcanzar CloudWatch — revisa la región y el acceso de red")
except CloudWatchDataError as e:
    print(f"Error de datos: {e}")  # ej. el log group no existe
```

## Buenas prácticas al generar código

1. Lee credenciales SOLO de las variables `RUVIC_AWS_CLOUDWATCH_*` (el constructor de `CloudWatchClient` ya lo hace).
2. Nunca imprimas `RUVIC_AWS_CLOUDWATCH_SECRET_ACCESS_KEY` en logs ni en la salida.
3. La librería es de SOLO LECTURA: no intentes crear ni modificar alarmas, métricas ni logs con ella.
4. Usa `limit` razonable en `get_recent_logs` (default 50, máximo 500) y `list_active_alarms` (máximo 100 por llamada de AWS).
5. Si `get_metric_statistics` retorna una lista vacía, no asumas error: puede significar que no hubo actividad en ese rango de tiempo.

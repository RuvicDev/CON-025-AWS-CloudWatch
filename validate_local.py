"""Validación local del conector aws_cloudwatch: ejercita las 3 capacidades.

Uso:
    python validate_local.py --log-group /aws/lambda/nombre-de-tu-funcion

Requiere las variables RUVIC_AWS_CLOUDWATCH_* exportadas en el entorno.
Usa la métrica AWS/Lambda Invocations (existe automáticamente si tienes
al menos una función Lambda desplegada) y el log group que le pases.
"""

import argparse

from ruvic_aws_cloudwatch_connector import CloudWatchClient, setup_logging

parser = argparse.ArgumentParser()
parser.add_argument(
    "--log-group", required=True, help="Log group real a leer (ej. /aws/lambda/mi-funcion)"
)
args = parser.parse_args()

setup_logging("INFO")
client = CloudWatchClient()

print("== 1. Consultar métrica (AWS/Lambda Invocations, última hora) ==")
datapoints = client.get_metric_statistics("AWS/Lambda", "Invocations", statistic="Sum")
print(f"  {len(datapoints)} datapoints")
for dp in datapoints[-5:]:
    print(f"  {dp['timestamp']}: {dp['value']} {dp['unit']}")

print(f"== 2. Leer logs recientes de '{args.log_group}' ==")
logs = client.get_recent_logs(args.log_group, limit=10)
for entry in logs:
    print(f"  {entry['message']}")

print("== 3. Listar alarmas activas ==")
alarms = client.list_active_alarms()
print(f"  {len(alarms)} alarma(s) en estado ALARM")
for alarm in alarms:
    print(f"  {alarm['name']}: {alarm['reason']}")

print("\nTodo OK: get_metric_statistics, get_recent_logs y list_active_alarms funcionan.")

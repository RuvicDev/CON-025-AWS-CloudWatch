# Conector AWS CloudWatch (CON-025)

Conector Ruvic de solo lectura para métricas, logs y alarmas de AWS
CloudWatch. Permite consultar datapoints de una métrica, leer las
entradas más recientes de un log group y listar las alarmas actualmente
activas.

## Instalación

```bash
pip install git+https://github.com/Dgirto/AWS-CloudWatch.git#subdirectory=lib
```

Python 3.10+. Dependencia única: `boto3>=1.34,<2.0`.

## Permisos requeridos en AWS

Crea un usuario IAM dedicado (no reutilizar credenciales root ni de otra
aplicación) con una policy de solo lectura:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:DescribeAlarms"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:DescribeLogStreams", "logs:GetLogEvents"],
      "Resource": "arn:aws:logs:*:*:log-group:*:*"
    }
  ]
}
```

- `cloudwatch:GetMetricStatistics`: necesario para
  `cloudwatch.get_metric_statistics`.
- `cloudwatch:DescribeAlarms`: necesario para
  `cloudwatch.list_active_alarms`.
- `logs:DescribeLogStreams` y `logs:GetLogEvents`: necesarios para
  `cloudwatch.get_logs`. Restringe el Resource a un prefijo de log groups
  específico (ej. `arn:aws:logs:*:*:log-group:/aws/lambda/ruvic-*:*`) si
  quieres limitar qué logs puede leer el agente.
- No se otorgan permisos de escritura ni de administración
  (`cloudwatch:PutMetricAlarm`, `cloudwatch:DeleteAlarms`,
  `logs:PutLogEvents`, `logs:DeleteLogGroup`, etc.).

## Variables de entorno (`RUVIC_AWS_CLOUDWATCH_*`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `RUVIC_AWS_CLOUDWATCH_ACCESS_KEY_ID` | Sí | Access Key ID de IAM |
| `RUVIC_AWS_CLOUDWATCH_SECRET_ACCESS_KEY` | Sí | Secret Access Key |
| `RUVIC_AWS_CLOUDWATCH_REGION` | Sí | Región de AWS (ej. `us-east-1`) |
| `RUVIC_AWS_CLOUDWATCH_CONNECT_TIMEOUT` | No (default `10`) | Timeout de conexión en segundos |

## Pruebas locales

Con una cuenta de AWS real (usa cualquier recurso existente que genere
métricas, como una función Lambda ya desplegada):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ./lib

export RUVIC_AWS_CLOUDWATCH_ACCESS_KEY_ID=tu-access-key
export RUVIC_AWS_CLOUDWATCH_SECRET_ACCESS_KEY=tu-secret-key
export RUVIC_AWS_CLOUDWATCH_REGION=us-east-1

python test_connection.py
python validate_local.py --log-group /aws/lambda/nombre-de-tu-funcion
```

Prueba también los casos de error (credenciales incorrectas, log group
inexistente, métrica sin datos) y verifica que los mensajes sean claros.

## Notas de integración

- El conector es de solo lectura: nunca llama a `PutMetricAlarm`,
  `PutMetricData`, `DeleteAlarms` ni `PutLogEvents`.
- `get_metric_statistics` usa la API clásica `GetMetricStatistics` (no
  `GetMetricData`), más simple para consultas puntuales de una sola
  métrica con dimensiones.
- `get_recent_logs` lee solo el log stream más reciente del log group
  (no agrega múltiples streams); es suficiente para revisar la actividad
  más reciente de un recurso.
- `list_active_alarms` solo retorna alarmas en estado `ALARM`; no incluye
  `OK` ni `INSUFFICIENT_DATA`.

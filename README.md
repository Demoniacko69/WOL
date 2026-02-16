# WOL Server (Docker + FastAPI)

Servidor web listo para produccion para enviar paquetes Wake-On-LAN en tu red local.

## Caracteristicas

- API REST completa para WOL y gestion de dispositivos.
- UI web simple en `/`.
- Persistencia con SQLite (`/data/devices.db`) con volumen Docker.
- Scheduler interno con cron (`/schedules`).
- Autenticacion HTTP Basic opcional por variables de entorno.
- Rate limiting basico configurable.
- Logging estructurado JSON (accesos, wake, errores).
- Soporte para multiples direcciones broadcast.
- Endpoint opcional de apagado remoto (`/shutdown/{id}`) via `shutdown_url` del dispositivo.

## Estructura

```text
wolserver/
  app/
    __init__.py
    config.py
    database.py
    logging_config.py
    main.py
    rate_limit.py
    schemas.py
    security.py
    wol.py
    templates/
      index.html
  data/
  .dockerignore
  Dockerfile
  docker-compose.yml
  requirements.txt
  README.md
```

## Variables de entorno

- `PORT` (default: `7070`): puerto HTTP del servicio.
- `DEFAULT_BROADCAST` (default: `255.255.255.255`): uno o varios broadcast separados por coma.
- `ENABLE_AUTH` (`true|false`, default: `false`): activa autenticacion Basic.
- `AUTH_USER` / `AUTH_PASS`: credenciales cuando `ENABLE_AUTH=true`.
- `ENABLE_RATE_LIMIT` (`true|false`, default: `true`).
- `RATE_LIMIT_REQUESTS` (default: `60`): maximo de requests por ventana por IP.
- `RATE_LIMIT_WINDOW_SECONDS` (default: `60`): ventana de rate limit en segundos.
- `LOG_LEVEL` (`DEBUG|INFO|WARNING|ERROR`, default: `INFO`).
- `DB_PATH` (default: `/data/devices.db`): ruta SQLite.

## Build y ejecucion

Desde `wolserver/`:

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Abrir:

- UI: `http://localhost:7070/`
- Docs OpenAPI: `http://localhost:7070/docs`

## API principal

### 1) Wake directo

```bash
curl -X POST http://localhost:7070/wake \
  -H "Content-Type: application/json" \
  -d '{"mac":"AA:BB:CC:DD:EE:FF","broadcast":"192.168.1.255"}'
```

Con multiples broadcast:

```bash
curl -X POST http://localhost:7070/wake \
  -H "Content-Type: application/json" \
  -d '{"mac":"AA:BB:CC:DD:EE:FF","broadcast":["192.168.1.255","10.0.0.255"]}'
```

### 2) Dispositivos

Listar:

```bash
curl http://localhost:7070/devices
```

Agregar:

```bash
curl -X POST http://localhost:7070/devices \
  -H "Content-Type: application/json" \
  -d '{
    "name":"NAS",
    "mac":"AA:BB:CC:DD:EE:FF",
    "ip":"192.168.1.50",
    "broadcasts":["192.168.1.255"],
    "shutdown_url":"http://192.168.1.50:5001/shutdown"
  }'
```

Eliminar:

```bash
curl -X DELETE http://localhost:7070/devices/1
```

Estado online/offline (ping):

```bash
curl http://localhost:7070/status/1
```

### 3) Scheduler (cron)

Crear programacion (ejemplo: 07:00 de lunes a viernes):

```bash
curl -X POST http://localhost:7070/schedules \
  -H "Content-Type: application/json" \
  -d '{"device_id":1,"cron":"0 7 * * 1-5"}'
```

Listar:

```bash
curl http://localhost:7070/schedules
```

Eliminar:

```bash
curl -X DELETE http://localhost:7070/schedules/1
```

### 4) Apagado remoto opcional

```bash
curl -X POST http://localhost:7070/shutdown/1
```

Esto solo funciona si el host destino expone un endpoint de apagado y se configuro `shutdown_url` en ese dispositivo.

## Ejemplo con autenticacion

Si `ENABLE_AUTH=true`, agrega `-u user:pass`:

```bash
curl -u admin:change-me http://localhost:7070/devices
```

## Nota de red y Wake-On-LAN

- WOL requiere que el equipo destino tenga Wake-On-LAN habilitado en BIOS/UEFI y en el sistema operativo/NIC.
- En algunas redes Docker bridge/NAT bloquea o altera broadcasts.
- Si no despierta equipos, usa `network_mode: host` (Linux) en `docker-compose.yml`.
- Verifica tambien firewall de red y del host destino.

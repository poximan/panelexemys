# src/app.py
import os
import threading
import time
from werkzeug.serving import is_running_from_reloader
from flask import request, Response
import dash
import requests
from .web import dash_config
from queue import Queue

from src.servicios.tcp.tcp_api import start_api_monitor
from src.servicios.mqtt.mqtt_client_manager import MqttClientManager

from src.servicios.mqtt import mqtt_event_bus
from src.servicios.mqtt.mqtt_rpc import MqttRequestRouter

from src.servicios.email.estado_email import start_email_health_monitor
from src.alarmas.notif_manager import NotifManager
from src.logger import Logosaurio
import config


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# instancia de logger de aplicacion
logger_app = Logosaurio()

api_key = os.getenv("MENSAGELO_API_KEY")

DEFAULT_PORT = "8051"
APP_HOST = os.getenv("PANELEXEMYS_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("PANELEXEMYS_PORT") or os.getenv("PORT") or DEFAULT_PORT)
DEBUG_MODE = _env_bool("PANELEXEMYS_DEBUG", False)
USE_RELOADER = _env_bool("PANELEXEMYS_USE_RELOADER", DEBUG_MODE)
AUTO_START_MQTT = (not USE_RELOADER) or is_running_from_reloader()

# servidor dash
app = dash.Dash(
    __name__,
    routes_pathname_prefix="/dash/",
    requests_pathname_prefix="/dash/",
    suppress_callback_exceptions=True,  # opcional pero util en apps multipagina
)
server = app.server


@server.before_request
def log_user_ip():
    """
    registra ip origen y ruta http para trazabilidad
    """
    ip_addr = request.remote_addr
    if ip_addr != "127.0.0.1":
        logger_app.log(
            f"Solicitud HTTP de la IP: {ip_addr} para la ruta: {request.path}",
            origen="APP/HTTP",
        )


@server.route("/repohttp/", defaults={"path": ""})
@server.route("/repohttp/<path:path>")
def proxy_repohttp(path: str):
    """
    Proxy interno: expone repohttp únicamente a través de panelexemys.
    """
    base_url = "http://repohttp:8080"
    url = f"{base_url}/{path}"
    if request.query_string:
        query = request.query_string.decode("utf-8", errors="ignore")
        url = f"{url}?{query}"
    try:
        proxied = requests.get(url, timeout=5)
    except requests.RequestException as exc:
        try:
            logger_app.log(f"Fallo consultando repohttp ({url}): {exc}", origen="APP/HTTP")
        except Exception:
            pass
        return Response("Repositorio HTTP no disponible", status=502, mimetype="text/plain")

    headers = {
        key: value
        for key, value in proxied.headers.items()
        if key.lower() not in {"content-encoding", "transfer-encoding", "connection"}
    }
    return Response(proxied.content, status=proxied.status_code, headers=headers)


# cola de mensajes y cliente mqtt
message_queue = Queue()
mqtt_client_manager = MqttClientManager(logger_app)

# Provide the external queue explicitly (contract hard)
mqtt_client_manager.set_message_queue(message_queue)

# exponer manager al event bus de publicaciones
mqtt_event_bus.set_manager(mqtt_client_manager)

# router rpc mqtt (suscribe y procesa requests en la cola)
rpc_router = MqttRequestRouter(logger_app, mqtt_client_manager, api_key, message_queue)

# configurar vistas y callbacks dash
dash_config.configure_dash_app(
    app,
    mqtt_client_manager,
    message_queue,
    auto_start_mqtt=AUTO_START_MQTT,
)


def _load_grd_exclusion_ids(logger: Logosaurio) -> set:
    """
    Lee la lista de GRD a excluir de alarmas individuales.
    """
    exclusion_path = os.path.join(os.path.dirname(__file__), "alarmas", "grd_exclusion_list.txt")
    excluded: set[int] = set()
    try:
        with open(exclusion_path, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    excluded.add(int(line))
                except ValueError:
                    logger.log(f"Entrada invalida en grd_exclusion_list: '{line}'", origen="ALRM/INIT")
    except FileNotFoundError:
        logger.log("No se encontro grd_exclusion_list.txt. No habra exclusiones.", origen="ALRM/INIT")
    except Exception as exc:
        logger.log(f"ERROR leyendo grd_exclusion_list.txt: {exc}", origen="ALRM/INIT")
    else:
        if excluded:
            logger.log(f"GRD excluidos de alarmas: {sorted(excluded)}", origen="ALRM/INIT")
    return excluded


def _start_alarm_manager(logger: Logosaurio) -> None:
    """
    Inicializa NotifManager en un hilo en segundo plano.
    """
    excluded_ids = _load_grd_exclusion_ids(logger)
    interval = max(1, int(getattr(config, "ALARM_CHECK_INTERVAL_SECONDS", 20)))
    manager = NotifManager(logger, excluded_ids, api_key)

    def alarm_loop() -> None:
        while True:
            try:
                manager.run_alarm_processing()
            except Exception as exc:
                logger.log(f"ERROR en ciclo de NotifManager: {exc}", origen="ALRM/LOOP")
            time.sleep(interval)

    threading.Thread(target=alarm_loop, name="notif-manager", daemon=True).start()


if __name__ == "__main__":

    if not is_running_from_reloader():
        logger_app.log(
            "1: Es el proceso principal. Realizando tareas de inicializacion...",
            origen="APP",
        )

        # cliente mqtt
        if AUTO_START_MQTT:
            logger_app.log("2: Lanzando cliente MQTT...", origen="APP")
            threading.Thread(target=mqtt_client_manager.start, daemon=True).start()
        else:
            logger_app.log(
                "2: Lanzando cliente MQTT... (omitido en proceso reloader).",
                origen="APP",
            )

        # orquestador modbus (grds y reles)
        logger_app.log("3: Lanzando monitor TCP (modem)...", origen="APP")
        threading.Thread(
            target=start_api_monitor,
            args=(logger_app, "200.63.163.36", 40000, mqtt_client_manager),
            daemon=True,
        ).start()

        # router rpc mqtt (escucha app/req/#)
        logger_app.log("4: Iniciando RPC sobre MQTT...", origen="APP")
        threading.Thread(target=rpc_router.start, daemon=True).start()

        # monitor smtp (actualiza observar.json -> server_email_estado)
        logger_app.log("5: Lanzando monitor servidor email (SMTP NOOP)...", origen="APP")
        threading.Thread(
            target=start_email_health_monitor,
            args=(logger_app, mqtt_client_manager),
            daemon=True,
        ).start()

        # Monitoreo Proxmox y Charito ahora via servicios HTTP (UI usa clientes web)

    else:
        logger_app.log("Es el reloader, se omite init pesado.", origen="APP")

    if not is_running_from_reloader():
        logger_app.log("6: Lanzando gestor de alarmas...", origen="APP")
        _start_alarm_manager(logger_app)

    logger_app.log("Iniciando servidor Dash...", origen="APP")
    app.run_server(
        debug=DEBUG_MODE,
        use_reloader=USE_RELOADER,
        host=APP_HOST,
        port=APP_PORT,
    )

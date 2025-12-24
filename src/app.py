# src/app.py
import os
import threading
import time
from flask import request, Response
from werkzeug.middleware.proxy_fix import ProxyFix
import dash
import requests
from .web import dash_config
from queue import Queue

from src.servicios.mqtt.mqtt_client_manager import MqttClientManager

from src.servicios.mqtt import mqtt_event_bus
from src.servicios.mqtt.mqtt_rpc import MqttRequestRouter

from src.servicios.email.estado_email import start_email_health_monitor
from src.alarmas.notif_manager import NotifManager
from src.logger import Logosaurio
import config


# instancia de logger de aplicacion
logger_app = Logosaurio()

api_key = os.getenv("MENSAGELO_API_KEY")

DEFAULT_PORT = "8051"
APP_HOST = os.getenv("PANELEXEMYS_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("PANELEXEMYS_PORT") or os.getenv("PORT") or DEFAULT_PORT)
DEBUG_MODE = False
USE_RELOADER = False
AUTO_START_MQTT = True
_services_lock = threading.Lock()
_services_started = False

# servidor dash
app = dash.Dash(
    __name__,
    routes_pathname_prefix="/dash/",
    requests_pathname_prefix="/dash/",
    suppress_callback_exceptions=True,  # opcional pero util en apps multipagina
)
server = app.server
server.wsgi_app = ProxyFix(server.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)


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
    Proxy interno: expone repohttp unicamente a traves de panelexemys.
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


def _start_background_services():
    """
    Inicializa servicios permanentes (MQTT, RPC, monitor email y alarmas) una sola vez.
    """
    global _services_started
    if _services_started:
        return
    with _services_lock:
        if _services_started:
            return

        logger_app.log("Inicializando servicios de panelexemys...", origen="APP")

        if AUTO_START_MQTT:
            logger_app.log("Lanzando cliente MQTT...", origen="APP")
            threading.Thread(target=mqtt_client_manager.start, daemon=True).start()
        else:
            logger_app.log("Cliente MQTT configurado para no auto iniciar.", origen="APP")

        logger_app.log("Iniciando RPC sobre MQTT...", origen="APP")
        threading.Thread(target=rpc_router.start, daemon=True).start()

        logger_app.log("Lanzando monitor servidor email (SMTP NOOP)...", origen="APP")
        threading.Thread(
            target=start_email_health_monitor,
            args=(logger_app, mqtt_client_manager),
            daemon=True,
        ).start()

        logger_app.log("Lanzando gestor de alarmas...", origen="APP")
        _start_alarm_manager(logger_app)

        _services_started = True


_start_background_services()


if __name__ == "__main__":
    logger_app.log("Iniciando servidor Dash...", origen="APP")
    app.run_server(
        debug=DEBUG_MODE,
        use_reloader=USE_RELOADER,
        host=APP_HOST,
        port=APP_PORT,
    )




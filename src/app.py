# src/app.py
import threading
from werkzeug.serving import is_running_from_reloader
from flask import request
import dash
from .web import dash_config
from queue import Queue

from src.persistencia.dao.dao_grd import grd_dao as dao_grd
from src.persistencia.dao.dao_reles import reles_dao as dao_reles
import src.persistencia.ddl_esquema as ddl
import src.persistencia.sim_poblar as poblador

from src.servicios.modbus.main_observer import start_modbus_orchestrator
from src.servicios.tcp.tcp_api import start_api_monitor
from src.servicios.mqtt.mqtt_client_manager import MqttClientManager

from src.servicios.mqtt import mqtt_event_bus
from src.servicios.mqtt.mqtt_rpc import MqttRequestRouter

from src.servicios.email.estado_email import start_email_health_monitor
from src.logger import Logosaurio
import config

# instancia de logger de aplicacion
logger_app = Logosaurio()

# asegurar esquema de base de datos
ddl.create_database_schema()

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
    if ip_addr != '127.0.0.1':
        logger_app.log(f"Solicitud HTTP de la IP: {ip_addr} para la ruta: {request.path}", origen="APP/HTTP")

# cola de mensajes y cliente mqtt
message_queue = Queue()
mqtt_client_manager = MqttClientManager(logger_app, message_queue)

# exponer manager al event bus de publicaciones
mqtt_event_bus.set_manager(mqtt_client_manager)

# router rpc mqtt (suscribe y procesa requests en la cola)
rpc_router = MqttRequestRouter(logger_app, mqtt_client_manager, message_queue)

# configurar vistas y callbacks dash
dash_config.configure_dash_app(app, mqtt_client_manager, message_queue)

if __name__ == '__main__':

    if not is_running_from_reloader():
        logger_app.log("1º: Es el proceso principal. Realizando tareas de inicializacion...", origen="APP")
        
        # asegurar grds configurados
        logger_app.log("2º: Asegurando equipos GRD en BD...", origen="APP")
        for grd_id, description in config.GRD_DESCRIPTIONS.items():
            dao_grd.insert_grd_description(grd_id, description)

        # asegurar reles configurados
        logger_app.log("3º: Asegurando reles en BD...", origen="APP")
        for rele_id, description in config.ESCLAVOS_MB.items():
            if not description.strip().upper().startswith("NO APLICA"):
                dao_reles.insert_rele_description(rele_id, description)

        # poblar datos historicos de ejemplo si corresponde
        if config.POBLAR_BD:
            logger_app.log("Poblando BD con historicos de ejemplo...", origen="APP")
            poblador.populate_database_conditionally()
        else:
            logger_app.log("No se poblara la base de datos con datos de ejemplo.", origen="APP")
        
        # orquestador modbus (grds y reles)
        logger_app.log("4º: Lanzando orquestador Modbus...", origen="APP")
        threading.Thread(target=start_modbus_orchestrator, args=(logger_app,), daemon=True).start()

        # monitor tcp del modem
        logger_app.log("5º: Lanzando monitor TCP (modem)...", origen="APP")
        threading.Thread(target=start_api_monitor, args=(logger_app, "200.63.163.36", 40000,), daemon=True).start()

        # cliente mqtt
        logger_app.log("6º: Lanzando cliente MQTT...", origen="APP")
        threading.Thread(target=mqtt_client_manager.start, daemon=True).start()

        # router rpc mqtt (escucha app/req/#)
        logger_app.log("7º: Iniciando RPC sobre MQTT...", origen="APP")
        threading.Thread(target=rpc_router.start, daemon=True).start()

        # monitor smtp (actualiza observar.json -> server_email_estado)
        logger_app.log("8º: Lanzando monitor servidor email (SMTP NOOP)...", origen="APP")
        threading.Thread(target=start_email_health_monitor, args=(logger_app,), daemon=True).start()

    else:
        logger_app.log("Es el reloader, se omite init pesado.", origen="APP")
    
    logger_app.log("Iniciando servidor Dash...", origen="APP")
    app.run_server(debug=True, host='0.0.0.0', port=8051)
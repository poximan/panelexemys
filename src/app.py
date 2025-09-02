import threading
from werkzeug.serving import is_running_from_reloader
import dash
from . import dash_config
from flask import request
from queue import Queue

from src.persistencia.dao_grd import grd_dao as dao_grd
from src.persistencia.dao_reles import reles_dao as dao_reles
import src.persistencia.ddl_esquema as ddl
import src.persistencia.sim_poblar as poblador

from src.observador.main_observer import start_modbus_orchestrator
from src.observador.tcp_api import start_api_monitor
from src.notificador.alarm_notifier import AlarmNotifier
from src.observador.mqtt_client_manager import MqttClientManager

# NUEVO: bus de publicaciones y RPC
from src.observador import mqtt_event_bus
from src.observador.mqtt_rpc import MqttRequestRouter

from src.logger import Logosaurio
import config

logger_app = Logosaurio()

ddl.create_database_schema()

app = dash.Dash(__name__, assets_folder='assets')
app.config['suppress_callback_exceptions'] = True
server = app.server

@server.before_request
def log_user_ip():
    ip_addr = request.remote_addr
    if ip_addr != '127.0.0.1':
        logger_app.log(f"Solicitud HTTP de la IP: {ip_addr} para la ruta: {request.path}", origen="APP/HTTP")

message_queue = Queue()
mqtt_client_manager = MqttClientManager(logger_app, message_queue)

# Exponer el manager al event bus publish-only
mqtt_event_bus.set_manager(mqtt_client_manager)

# Router de RPC sobre MQTT
rpc_router = MqttRequestRouter(logger_app, mqtt_client_manager, message_queue)

dash_config.configure_dash_app(app, mqtt_client_manager, message_queue)

if __name__ == '__main__':

    if not is_running_from_reloader():
        logger_app.log("1º: Es el proceso principal. Realizando tareas de inicializacion...", origen="APP")
        
        logger_app.log("2º: Asegurando equipos GRD en BD...", origen="APP")
        for grd_id, description in config.GRD_DESCRIPTIONS.items():
            dao_grd.insert_grd_description(grd_id, description)

        logger_app.log("3º: Asegurando reles en BD...", origen="APP")
        for rele_id, description in config.ESCLAVOS_MB.items():
            if not description.strip().upper().startswith("NO APLICA"):
                dao_reles.insert_rele_description(rele_id, description)

        if config.POBLAR_BD:
            logger_app.log("Poblando BD con historicos de ejemplo...", origen="APP")
            poblador.populate_database_conditionally()
        else:
            logger_app.log("No se poblara la base de datos con datos de ejemplo.", origen="APP")
        
        logger_app.log("4º: Lanzando orquestador Modbus...", origen="APP")
        threading.Thread(target=start_modbus_orchestrator, args=(logger_app,), daemon=True).start()

        logger_app.log("5º: Lanzando monitor TCP (modem)...", origen="APP")
        threading.Thread(target=start_api_monitor, args=(logger_app, "200.63.163.36", 40000,), daemon=True).start()

        logger_app.log("6º: Lanzando notificador de alarmas...", origen="APP")
        alarm_notifier_instance = AlarmNotifier(logger=logger_app)
        threading.Thread(target=alarm_notifier_instance.start_observer_loop, daemon=True).start()

        logger_app.log("7º: Lanzando cliente MQTT...", origen="APP")
        threading.Thread(target=mqtt_client_manager.start, daemon=True).start()

        # Arrancar el router RPC (se suscribe a app/req/# y atiende por message_queue)
        logger_app.log("8º: Iniciando RPC sobre MQTT...", origen="APP")
        threading.Thread(target=rpc_router.start, daemon=True).start()

    else:
        logger_app.log("Es el reloader, se omite init pesado.", origen="APP")
    
    logger_app.log("Iniciando servidor Dash...", origen="APP")
    app.run_server(debug=True, host='0.0.0.0', port=8051)
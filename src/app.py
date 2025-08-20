import threading
from werkzeug.serving import is_running_from_reloader # Importa para detectar el proceso del reloader
import dash
from . import dash_config
from flask import request

from src.persistencia.dao_grd import grd_dao as dao_grd 
from src.persistencia.dao_reles import reles_dao as dao_reles 
import src.persistencia.ddl_esquema as ddl 
import src.persistencia.sim_poblar as poblador 

from src.observador.main_observer import start_modbus_orchestrator 
from src.observador.actividad_tcp import test_tcp_connection 
from src.notificador.alarm_notifier import AlarmNotifier
from src.componentes.broker_view import mqtt_client_manager 

from src.logger import Logosaurio
import config

logger_app = Logosaurio()

# Asegurate de que el esquema de la base de datos este creado antes de iniciar la aplicacion
ddl.create_database_schema()

# Crea una instancia de la aplicacion Dash
app = dash.Dash(__name__, assets_folder='assets')

app.config['suppress_callback_exceptions'] = True

server = app.server

@server.before_request
def log_user_ip():
    """
    Función que se ejecuta antes de cada solicitud HTTP
    y registra la IP del cliente.
    """
    ip_addr = request.remote_addr
    if ip_addr != '127.0.0.1': 
        logger_app.log(f"Solicitud HTTP de la IP: {ip_addr} para la ruta: {request.path}", origen="APP/HTTP")

# Configura el layout y los callbacks de la aplicacion usando la funcion de dash_config
dash_config.configure_dash_app(app)

# --- Ejecucion de la aplicacion ---
if __name__ == '__main__':

    if not is_running_from_reloader():
        logger_app.log("1º: Es el proceso principal. Realizando tareas de inicializacion...", origen="APP")

        logger_app.log("Iniciando aplicación. Creando logger central...", origen="APP")
        
        logger_app.log("2º: Asegurando que los equipos definidos en config.GRD_DESCRIPTIONS existan en BD...", origen="APP")
        for grd_id, description in config.GRD_DESCRIPTIONS.items():
            dao_grd.insert_grd_description(grd_id, description)
        logger_app.log("Equipos GRD iniciales asegurados en la base de datos.", origen="APP")

        logger_app.log("3º: Asegurando que los reles definidos en config.ESCLAVOS_MB existan en BD...", origen="APP")
        for rele_id, description in config.ESCLAVOS_MB.items():
            if not description.strip().upper().startswith("NO APLICA"):
                dao_reles.insert_rele_description(rele_id, description)
        logger_app.log("Reles iniciales asegurados en la base de datos.", origen="APP")

        if config.POBLAR_BD:
            logger_app.log("Procediendo a poblar la base de datos con datos historicos...", origen="APP")
            poblador.populate_database_conditionally()
        else:
            logger_app.log("No se poblara la base de datos con datos de ejemplo.", origen="APP")
        
        logger_app.log("4º: Lanzando el orquestador Modbus en un hilo separado...", origen="APP")
        modbus_orchestrator_thread = threading.Thread(
            target=start_modbus_orchestrator,
            args=(logger_app,)
            )
        modbus_orchestrator_thread.daemon = True
        modbus_orchestrator_thread.start()

        # --- Nuevo hilo para el monitor de actividad TCP ---
        logger_app.log("5º: Lanzando el monitor de actividad TCP en un hilo separado...", origen="APP")
        # Definimos las constantes de la conexion
        TCP_TEST_HOST = "200.63.163.36"
        TCP_TEST_PORT = 40000
        # Lanzamos el hilo, pasándole los parámetros a la función test_tcp_connection
        tcp_monitor_thread = threading.Thread(
            target=test_tcp_connection,
            args=(TCP_TEST_HOST, TCP_TEST_PORT)
        )
        tcp_monitor_thread.daemon = True
        tcp_monitor_thread.start()

        logger_app.log("6º: Lanzando el notificador de alarmas en un hilo separado...", origen="APP")
        alarm_notifier_instance = AlarmNotifier(logger=logger_app)
        alarm_thread = threading.Thread(
            target=alarm_notifier_instance.start_observer_loop,
            daemon=True
        )
        alarm_thread.start()

        # Iniciar el cliente MQTT en un hilo de fondo
        logger_app.log("7º: Lanzando el cliente MQTT en un hilo de fondo...", origen="APP")
        mqtt_thread = threading.Thread(target=mqtt_client_manager.start)
        mqtt_thread.daemon = True
        mqtt_thread.start()

    else:
        logger_app.log("Es el proceso del reloader. La inicializacion de la BD y los observadores se omiten.", origen="APP")
    
    logger_app.log("Iniciando servidor Dash...", origen="APP")
    app.run_server(debug=True, host='0.0.0.0', port=8051)
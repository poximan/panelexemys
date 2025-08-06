import threading # Para ejecutar los observadores en hilos separados
from werkzeug.serving import is_running_from_reloader # Importa para detectar el proceso del reloader
import dash
from . import dash_config # Importa el modulo de configuracion de Dash
from flask import request, send_from_directory

from src.persistencia.dao_grd import grd_dao as dao_grd # Necesario para insertar las descripciones de GRD
from src.persistencia.dao_reles import reles_dao as dao_reles # Importa el DAO para relés
import src.persistencia.ddl_esquema as ddl # Importa el modulo para crear el esquema
import src.persistencia.sim_poblar as poblador # Importa el modulo de poblamiento

from src.observador.main_observer import start_modbus_orchestrator 
from src.notificador.alarm_notifier import AlarmNotifier

from src.logger import Logosaurio
import config # Importa la configuracion

logger_app = Logosaurio()

# Asegurate de que el esquema de la base de datos este creado antes de iniciar la aplicacion
ddl.create_database_schema()

# Crea una instancia de la aplicacion Dash
app = dash.Dash(__name__, assets_folder='assets')

"""
Cuando Dash inicia, escanea todo el app.layout para identificar todos los componentes y sus IDs.
Si un callback se registra para interactuar con un componente (ya sea como Input, Output o State), Dash espera que ese componente este presente
en el layout inicial.
En una SPA, el dashboard_layout no es el app.layout completo desde el principio; es un html.Div que se inserta dinamicamente despues 
de que el usuario navega.
Al establecer suppress_callback_exceptions=True, le dices a Dash: "Esta bien si no encuentras todos los componentes de los callbacks 
en el layout inicial. Espera a que se carguen dinamicamente".
"""
app.config['suppress_callback_exceptions'] = True

# Esta linea es necesaria para Gunicorn o despliegues de produccion
server = app.server

# Definir la ruta segura para el archivo SVG
SECURE_SVG_DIRECTORY = r'Z:\info general\01 - Comunicaciones, Automatismos e Instrumentación\doc interna'

@server.route('/secure-svg/<path:filename>')
def serve_secure_svg(filename):
    """
    Sirve archivos SVG desde una ubicación de red segura.
    Solo permite el acceso a archivos dentro de SECURE_SVG_DIRECTORY.
    """
    try:
        return send_from_directory(SECURE_SVG_DIRECTORY, filename)
    except Exception as e:
        logger_app.log(f"Error al servir SVG seguro: {e}", origen="HTTP/SVG")
        return "Error al cargar el diagrama de topología.", 404

"""
plotly usa dash para su parte grafica, que a su vez usa flash como microframework para http.
en este sentido, implementamos un decorador @server.before_request para  registra una función
que se ejecutará antes que la solicitud llegue al servidor.
"""
@server.before_request
def log_user_ip():
    """
    Función que se ejecuta antes de cada solicitud HTTP
    y registra la IP del cliente.
    """
    ip_addr = request.remote_addr

    # Si la IP es la del host local, salir
    if ip_addr == '127.0.0.1' or ip_addr == '172.17.0.1' :
        return
    
    # Registra la IP, el método HTTP y la ruta de la solicitud
    logger_app.log(f"Solicitud HTTP de la IP: {ip_addr} para la ruta: {request.path}", origen="HTTP/GET")

# Configura el layout y los callbacks de la aplicacion usando la funcion de dash_config
dash_config.configure_dash_app(app)

# --- Ejecucion de la aplicacion ---
if __name__ == '__main__':

    # Esta logica se ejecutara solo en el proceso principal (no en el reloader).
    if not is_running_from_reloader():
        print("1º: Es el proceso principal. Realizando tareas de inicializacion...")

        # 1. Crear una única instancia de Logosaurio para toda la aplicación        
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

        # Logica de poblamiento de datos historicos (si esta activada en config.py)
        if config.POBLAR_BD:
            logger_app.log("Procediendo a poblar la base de datos con datos historicos...", origen="APP")
            poblador.populate_database_conditionally()
        else:
            logger_app.log("No se poblara la base de datos con datos de ejemplo.", origen="APP")
        
        # Lanzar el orquestador modbus
        logger_app.log("4º: Lanzando el orquestador Modbus en un hilo separado...", origen="APP")
        modbus_orchestrator_thread = threading.Thread(
            target=start_modbus_orchestrator,
            args=(logger_app,)
            )
        modbus_orchestrator_thread.daemon = True # Permite que el hilo termine si el programa principal lo hace
        modbus_orchestrator_thread.start()

        # Lanzar el notificador de alarmas en un hilo separado
        logger_app.log("5º: Lanzando el notificador de alarmas en un hilo separado...", origen="APP")
        alarm_notifier_instance = AlarmNotifier(logger=logger_app)
        alarm_thread = threading.Thread(
            target=alarm_notifier_instance.start_observer_loop,
            daemon=True # Permite que el hilo termine si el programa principal lo hace
        )
        alarm_thread.start()

    else:
        # Mensaje para el proceso del reloader (cuando debug=True)
        logger_app.log("Es el proceso del reloader. La inicializacion de la BD y los observadores se omiten.", origen="APP")
    
    logger_app.log("Iniciando servidor Dash...", origen="APP")
    app.run_server(debug=True, host='0.0.0.0', port=8051)
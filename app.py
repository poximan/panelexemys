import threading        # Para ejecutar los observadores en hilos separados
from werkzeug.serving import is_running_from_reloader # Importa para detectar el proceso del reloader
import dash
import dash_config                              # Importa el mÃ³dulo de configuraciÃ³n de Dash
from persistencia.dao_grd import grd_dao as dao # Necesario para insertar las descripciones de GRD
import persistencia.ddl_esquema as ddl          # Importa el mÃ³dulo para crear el esquema
import persistencia.sim_poblar as poblador      # Importa el mÃ³dulo de poblamiento
from observador.main_observer import start_modbus_orchestrator 
import notificador.alarm_notifier as notif      # Importa el nuevo mÃ³dulo del notificador de alarmas
import config                                   # Importa la configuraciÃ³n

# AsegÃºrate de que el esquema de la base de datos estÃ© creado antes de iniciar la aplicaciÃ³n
ddl.create_database_schema()

# Crea una instancia de la aplicaciÃ³n Dash
app = dash.Dash(__name__, assets_folder='assets')

"""
Cuando Dash inicia, escanea todo el app.layout para identificar todos los componentes y sus IDs.
Si un callback se registra para interactuar con un componente (ya sea como Input, Output o State), Dash espera que ese componente estÃ© presente
en el layout inicial.
En una SPA, el dashboard_layout no es el app.layout completo desde el principio; es un html.Div que se inserta dinÃ¡micamente despuÃ©s 
de que el usuario navega.
Al establecer suppress_callback_exceptions=True, le dices a Dash: "EstÃ¡ bien si no encuentras todos los componentes de los callbacks 
en el layout inicial. Espera a que se carguen dinÃ¡micamente".
"""
app.config['suppress_callback_exceptions'] = True

# Esta lÃ­nea es necesaria para Gunicorn o despliegues de producciÃ³n
server = app.server

# Configura el layout y los callbacks de la aplicaciÃ³n usando la funciÃ³n de dash_config
dash_config.configure_dash_app(app)

# --- EjecuciÃ³n de la aplicaciÃ³n ---
if __name__ == '__main__':
    # Esta lÃ³gica se ejecutarÃ¡ solo en el proceso principal (no en el reloader).
    if not is_running_from_reloader():
        print("Es el proceso principal. Realizando tareas de inicializacion...")

        # Asegurando que los equipos definidos en config.GRD_DESCRIPTIONS existan en la tabla 'grd'.
        print("Asegurando que los equipos definidos en config.GRD_DESCRIPTIONS existan en la tabla 'grd'...")
        for grd_id, description in config.GRD_DESCRIPTIONS.items():
            dao.insert_grd_description(grd_id, description)
        print("Equipos GRD iniciales asegurados en la base de datos.")

        # LÃ³gica de poblamiento de datos histÃ³ricos (si estÃ¡ activada en config.py)
        if config.POBLAR_BD:
            print("POBLAR_BD es True. Procediendo a poblar la base de datos con datos histÃ³ricos...")
            poblador.populate_database_conditionally()
        else:
            print("POBLAR_BD es False. No se poblara la base de datos con datos de ejemplo.")
        
        # larnzar el orquestador modbus
        print("Lanzando el orquestador Modbus en un hilo separado...")
        modbus_orchestrator_thread = threading.Thread(target=start_modbus_orchestrator)
        modbus_orchestrator_thread.daemon = True # Permite que el hilo termine si el programa principal lo hace
        modbus_orchestrator_thread.start()

        # Lanzar el notificador de alarmas en un hilo separado
        print("Lanzando el notificador de alarmas en un hilo separado...")
        alarm_thread = threading.Thread(target=notif.start_alarm_observer)
        alarm_thread.daemon = True # Permite que el hilo termine si el programa principal lo hace
        alarm_thread.start()

    else:
        # Mensaje para el proceso del reloader (cuando debug=True)
        print("Es el proceso del reloader. La inicializacion de la BD y los observadores se omiten.")
    
    print("Iniciando servidor Dash...")
    app.run_server(debug=True, host='0.0.0.0')
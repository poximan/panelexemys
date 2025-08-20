import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
from queue import Queue
from src.observador.mqtt_client_manager import MqttClientManager
from src.logger import Logosaurio
import config

# Inicializar componentes globales
# La cola se utiliza para comunicar mensajes del hilo MQTT a la aplicacion Dash
message_queue = Queue()
logger = Logosaurio()
mqtt_client_manager = MqttClientManager(logger, message_queue)

# Nombre del archivo de estado (debe coincidir con el del MqttDriver)
STATUS_FILE = "./src/componentes/estado_broker.txt"

# --- Layout de la pagina "Broker" ---
def get_broker_layout():
    """
    Define el layout de la página "Broker" con dos columnas y un indicador de estado.
    """
    return html.Div(children=[
        html.H1("Broker MQTT", className='main-title'),
        
        # Indicador de estado del broker
        html.Div(className="status-indicator-wrapper", children=[
            html.Span("Estado de la conexión:"),
            html.Div(id='broker-status-indicator', className='status-circle status-disconnected')
        ]),

        html.Div(className='broker-grid-container', children=[
            # Columna de Publicaciones
            html.Div(className='broker-panel', children=[
                html.H3("Publicaciones", className='text-xl font-semibold mb-4'),
                
                html.P("Haz clic para publicar un mensaje de prueba.", className='text-gray-600 mb-4'),
                html.Div(className='flex flex-col space-y-4', children=[
                    html.Button(
                        'Publicar en ' + config.MQTT_ESTADO_EXEMYS,
                        id='btn-publish-estados',
                        n_clicks=0,
                        className='bg-blue-500 text-white font-bold py-2 px-4 rounded hover:bg-blue-700 transition duration-300'
                    ),
                    html.Button(
                        'Publicar en ' + config.MQTT_ESTADO_EMAIL,
                        id='btn-publish-control',
                        n_clicks=0,
                        className='bg-green-500 text-white font-bold py-2 px-4 rounded hover:bg-green-700 transition duration-300'
                    ),
                    html.Button(
                        'Publicar en ' + config.MQTT_TOPIC_SENSOR,
                        id='btn-publish-sensor',
                        n_clicks=0,
                        className='bg-purple-500 text-white font-bold py-2 px-4 rounded hover:bg-purple-700 transition duration-300'
                    ),
                    html.Div(id='output-publish-status', style={'display': 'none'}) # Un output "fantasma" para activar el callback
                ])
            ]),
            # Columna de Suscripciones
            html.Div(className='broker-panel', children=[
                html.H3("Suscripciones", className='text-xl font-semibold mb-4'),
                html.P("Mensajes recibidos de los tópicos suscritos.", className='text-gray-600 mb-4'),
                html.Div(id='subscription-display', className='bg-gray-100 p-4 rounded h-96 overflow-y-scroll space-y-2 text-sm font-mono', children=[
                    html.P("Esperando mensajes...", className='text-gray-400')
                ])
            ]),
        ]),
        # dcc.Interval para refrescar la vista de suscripciones cada 1 segundo
        dcc.Interval(
            id='interval-component',
            interval=config.DASHBOARD_REFRESH_INTERVAL_MS, # en milisegundos
            n_intervals=0
        ),
        # dcc.Interval para refrescar el estado del broker cada 500ms
        dcc.Interval(
            id='broker-status-interval',
            interval=config.DASHBOARD_REFRESH_INTERVAL_MS,
            n_intervals=0
        )
    ])

# --- Callbacks para la pagina "Broker" ---
def register_broker_callbacks(app: dash.Dash):
    """
    Registra los callbacks para la página del broker.
    """
    # Callback para manejar las publicaciones
    @app.callback(
        Output('output-publish-status', 'children'),
        [
            Input('btn-publish-estados', 'n_clicks'),
            Input('btn-publish-control', 'n_clicks'),
            Input('btn-publish-sensor', 'n_clicks')
        ],
        prevent_initial_call=True
    )
    def handle_publish(n1, n2, n3):
        ctx = dash.callback_context
        if not ctx.triggered:
            return ""

        button_id = ctx.triggered[0]['prop_id'].split('.')[0]

        topic = ""
        payload = ""

        if button_id == 'btn-publish-estados':
            topic = config.MQTT_ESTADO_EXEMYS
            payload = "Estado: OK"
        elif button_id == 'btn-publish-control':
            topic = config.MQTT_ESTADO_EMAIL
            payload = "Comando: ON"
        elif button_id == 'btn-publish-sensor':
            topic = config.MQTT_TOPIC_SENSOR
            payload = "Temperatura: 25.5C"
        
        # Publica el mensaje usando el cliente global
        mqtt_client_manager.publish(topic, payload)
        
        return ""

    # Callback para refrescar la lista de suscripciones
    @app.callback(
        Output('subscription-display', 'children'),
        [Input('interval-component', 'n_intervals')],
        [State('subscription-display', 'children')]
    )
    def update_subscriptions(n, current_children):
        new_messages = []
        while not message_queue.empty():
            msg = message_queue.get()
            new_messages.append(
                html.Div(f"[{msg['topic']}] {msg['payload']}", className='bg-gray-200 p-2 rounded')
            )
        
        if not new_messages:
            return current_children
        
        updated_children = new_messages + (current_children if isinstance(current_children, list) else [current_children])
        
        return updated_children[:50]

    @app.callback(
        Output('broker-status-indicator', 'className'),
        [Input('broker-status-interval', 'n_intervals')]
    )
    def update_broker_status(n):
        status = "desconectado"
        try:
            with open(STATUS_FILE, "r") as f:
                status = f.read().strip()
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.log(f"Error al leer el archivo de estado: {e}", origen="NOTIF/DASH")

        if status == 'conectado':
            return 'status-circle status-connected'
        elif status == 'conectando':
            return 'status-circle status-connecting'
        else:
            return 'status-circle status-disconnected'
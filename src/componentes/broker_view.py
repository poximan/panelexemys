import os
import threading
from queue import Queue
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import config

message_queue: Queue | None = None
mqtt_client_manager = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(SCRIPT_DIR, 'estado_broker.txt')


def get_broker_layout():
    status_interval_ms = getattr(config, 'BROKER_STATUS_REFRESH_INTERVAL_MS', 3000)

    return html.Div(children=[
        html.H1("Broker MQTT", className='main-title'),

        html.Div(className="status-indicator-wrapper", children=[
            html.Span("Estado de la conexion:"),
            html.Div(id='broker-status-indicator', className='status-circle status-disconnected')
        ]),

        html.Div(className='broker-grid-container', children=[
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
                    html.Div(id='output-publish-status', style={'display': 'none'})
                ])
            ]),
            html.Div(className='broker-panel', children=[
                html.H3("Suscripciones", className='text-xl font-semibold mb-4'),
                html.P("Mensajes recibidos de los topicos (incluyendo los publicados por esta interfaz).", className='text-gray-600 mb-4'),
                html.Div(id='subscription-display', className='bg-gray-100 p-4 rounded h-96 overflow-y-scroll space-y-2 text-sm font-mono', children=[
                    html.P("Esperando mensajes...", className='text-gray-400')
                ])
            ]),
        ]),

        dcc.Interval(id='interval-component', interval=config.DASHBOARD_REFRESH_INTERVAL_MS, n_intervals=0),
        dcc.Interval(id='broker-status-interval', interval=status_interval_ms, n_intervals=0)
    ])


def initialize_broker_components(manager, queue):
    """
    Se asignan las referencias compartidas. Adicionalmente se intenta
    sincronizar la cola entre el manager y la vista para evitar inconsistencias.
    """
    global mqtt_client_manager, message_queue
    mqtt_client_manager = manager
    message_queue = queue

    # Si el manager expone set_message_queue o msg_queue, sincronizamos
    try:
        if mqtt_client_manager is not None:
            if hasattr(mqtt_client_manager, 'set_message_queue'):
                mqtt_client_manager.set_message_queue(message_queue)
            elif hasattr(mqtt_client_manager, 'msg_queue'):
                # Forzar que ambos usen exactamente la misma cola
                mqtt_client_manager.msg_queue = message_queue
    except Exception:
        # no queremos que un fallo aqui rompa la inicializacion de la UI
        pass


def register_broker_callbacks(app: dash.Dash):

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

        if button_id == 'btn-publish-estados':
            topic, payload = config.MQTT_ESTADO_EXEMYS, "Estado: OK"
        elif button_id == 'btn-publish-control':
            topic, payload = config.MQTT_ESTADO_EMAIL, "Comando: ON"
        elif button_id == 'btn-publish-sensor':
            topic, payload = config.MQTT_TOPIC_SENSOR, "Temperatura: 25.5C"
        else:
            return ""

        if mqtt_client_manager is None:
            return "NO_MQTT_MANAGER"

        # Consultar estado via la API del manager (get_connection_status fue añadida)
        status = mqtt_client_manager.get_connection_status() if mqtt_client_manager else 'desconectado'
        if status != 'conectado':
            # intentar reconectar en hilo distinto para no bloquear la UI
            threading.Thread(target=mqtt_client_manager.start, daemon=True).start()
            return "RECONNECTING"

        mqtt_client_manager.publish(topic, payload)
        return "PUBLISHED"

    @app.callback(
        Output('subscription-display', 'children'),
        [Input('interval-component', 'n_intervals')],
        [State('subscription-display', 'children')]
    )
    def update_subscriptions(n, current_children):
        # Preferir la cola compartida 'message_queue' si esta disponible,
        # si no, intentar usar la cola que pueda exponer el manager
        q = message_queue
        if q is None and mqtt_client_manager is not None and hasattr(mqtt_client_manager, 'msg_queue'):
            q = mqtt_client_manager.msg_queue

        if q is None:
            return current_children

        new_messages = []
        # consumir la cola sin bloquear
        while True:
            try:
                topic, payload = q.get_nowait()
            except Exception:
                break
            new_messages.append(
                html.Div(f"[{topic}] {payload}", className='bg-gray-200 p-2 rounded')
            )

        if not new_messages:
            return current_children

        existing = current_children if isinstance(current_children, list) else [current_children]
        return (new_messages + existing)[:50]

    @app.callback(
        Output('broker-status-indicator', 'className'),
        [Input('broker-status-interval', 'n_intervals')]
    )
    def update_broker_status(n):
        status = "desconectado"
        if mqtt_client_manager is not None:
            # usar get_connection_status para obtener un string
            try:
                status = mqtt_client_manager.get_connection_status()
            except Exception:
                status = 'desconectado'

        if status == 'conectado':
            return 'status-circle status-connected'
        elif status == 'conectando':
            return 'status-circle status-connecting'
        else:
            return 'status-circle status-disconnected'
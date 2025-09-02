import os
import threading
from queue import Queue, Empty
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import json
import config

message_queue: Queue | None = None
mqtt_client_manager = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(SCRIPT_DIR, 'estado_broker.txt')  # reservado si querés persistir algo


def get_broker_layout():
    status_interval_ms = getattr(config, 'BROKER_STATUS_REFRESH_INTERVAL_MS', 3000)
    dash_interval_ms = getattr(config, 'DASHBOARD_REFRESH_INTERVAL_MS', 5000)

    return html.Div(children=[
        html.H1("Broker MQTT", className='main-title'),

        html.Div(className="status-indicator-wrapper", children=[
            html.Span("Estado de la conexión:"),
            html.Div(id='broker-status-indicator', className='status-circle status-disconnected')
        ]),

        html.Div(className='broker-grid-container', children=[
            html.Div(className='broker-panel', children=[
                html.H3("Publicaciones (snapshots retenidos)", className='text-xl font-semibold mb-4'),
                html.P("Publica snapshots con QoS/retain de acuerdo a config.py", className='text-gray-600 mb-4'),
                html.Div(className='flex flex-col space-y-4', children=[
                    html.Div(children=[
                        html.Div([
                            html.Strong("Grado global → "),
                            html.Code(config.MQTT_TOPIC_GRADO)
                        ], className='mb-1'),
                        dcc.Textarea(
                            id='payload-grado',
                            value=json.dumps({"porcentaje": 0.0, "total": 0, "conectados": 0}, ensure_ascii=False),
                            style={'width': '100%', 'height': 90}
                        ),
                        html.Button(
                            'Publicar GRADO (retain)',
                            id='btn-publish-grado',
                            n_clicks=0,
                            className='bg-blue-600 text-white font-bold py-2 px-4 rounded hover:bg-blue-700 transition duration-300'
                        ),
                    ], className='space-y-2'),

                    html.Div(children=[
                        html.Div([
                            html.Strong("GRDs desconectados → "),
                            html.Code(config.MQTT_TOPIC_GRDS)
                        ], className='mb-1'),
                        dcc.Textarea(
                            id='payload-grds',
                            value=json.dumps({"items": []}, ensure_ascii=False),
                            style={'width': '100%', 'height': 110}
                        ),
                        html.Button(
                            'Publicar GRDs (retain)',
                            id='btn-publish-grds',
                            n_clicks=0,
                            className='bg-emerald-600 text-white font-bold py-2 px-4 rounded hover:bg-emerald-700 transition duration-300'
                        ),
                    ], className='space-y-2'),

                    html.Div(children=[
                        html.Div([
                            html.Strong("Estado MÓDEM/routeo → "),
                            html.Code(config.MQTT_TOPIC_MODEM_CONEXION)
                        ], className='mb-1'),
                        dcc.Input(
                            id='payload-modem',
                            value=json.dumps({"estado": "conectado"}, ensure_ascii=False),
                            style={'width': '100%'}
                        ),
                        html.Button(
                            'Publicar MÓDEM (retain)',
                            id='btn-publish-modem',
                            n_clicks=0,
                            className='bg-purple-600 text-white font-bold py-2 px-4 rounded hover:bg-purple-700 transition duration-300'
                        ),
                    ], className='space-y-2'),

                    html.Div(id='output-publish-status', style={'display': 'none'})
                ])
            ]),
            html.Div(className='broker-panel', children=[
                html.H3("Suscripciones", className='text-xl font-semibold mb-4'),
                html.P(
                    "Mensajes recibidos de los tópicos (incluye retained y los publicados desde esta interfaz).",
                    className='text-gray-600 mb-4'
                ),
                html.Div(
                    id='subscription-display',
                    className='bg-gray-100 p-4 rounded h-96 overflow-y-scroll space-y-2 text-sm font-mono',
                    children=[html.P("Esperando mensajes...", className='text-gray-400')]
                )
            ]),
        ]),

        dcc.Interval(id='interval-component', interval=dash_interval_ms, n_intervals=0),
        dcc.Interval(id='broker-status-interval', interval=status_interval_ms, n_intervals=0)
    ])


def initialize_broker_components(manager, queue):
    """
    Inyecta referencias compartidas. Si el manager expone set_message_queue/msg_queue,
    se fuerza a que comparta la misma cola que esta vista.
    """
    global mqtt_client_manager, message_queue
    mqtt_client_manager = manager
    message_queue = queue

    try:
        if mqtt_client_manager is not None:
            if hasattr(mqtt_client_manager, 'set_message_queue'):
                mqtt_client_manager.set_message_queue(message_queue)
            elif hasattr(mqtt_client_manager, 'msg_queue'):
                mqtt_client_manager.msg_queue = message_queue
    except Exception:
        pass


def _ensure_connected():
    """Si no está conectado, dispara reconnect en un thread para no bloquear Dash."""
    if mqtt_client_manager is None:
        return False
    try:
        status = mqtt_client_manager.get_connection_status()
    except Exception:
        status = 'desconectado'
    if status == 'conectado':
        return True
    threading.Thread(target=mqtt_client_manager.start, daemon=True).start()
    return False


def register_broker_callbacks(app: dash.Dash):

    @app.callback(
        Output('output-publish-status', 'children'),
        [
            Input('btn-publish-grado', 'n_clicks'),
            Input('btn-publish-grds', 'n_clicks'),
            Input('btn-publish-modem', 'n_clicks')
        ],
        [
            State('payload-grado', 'value'),
            State('payload-grds', 'value'),
            State('payload-modem', 'value'),
        ],
        prevent_initial_call=True
    )
    def handle_publish(n_grado, n_grds, n_modem, v_grado, v_grds, v_modem):
        ctx = dash.callback_context
        if not ctx.triggered:
            return ""

        if mqtt_client_manager is None:
            return "NO_MQTT_MANAGER"

        # reconexión no bloqueante si hace falta
        connected = _ensure_connected()
        if not connected:
            return "RECONNECTING"

        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        qos = int(getattr(config, 'MQTT_PUBLISH_QOS_STATE', 1))
        retain = bool(getattr(config, 'MQTT_PUBLISH_RETAIN_STATE', True))

        try:
            if button_id == 'btn-publish-grado':
                # validar json
                json.loads(v_grado)
                mqtt_client_manager.publish(config.MQTT_TOPIC_GRADO, v_grado, qos=qos, retain=retain)
                return "PUBLISHED_GRADO"

            if button_id == 'btn-publish-grds':
                json.loads(v_grds)
                mqtt_client_manager.publish(config.MQTT_TOPIC_GRDS, v_grds, qos=qos, retain=retain)
                return "PUBLISHED_GRDS"

            if button_id == 'btn-publish-modem':
                json.loads(v_modem)
                mqtt_client_manager.publish(config.MQTT_TOPIC_MODEM_CONEXION, v_modem, qos=qos, retain=retain)
                return "PUBLISHED_MODEM"

            return ""
        except json.JSONDecodeError:
            return "PAYLOAD_INVALID_JSON"
        except Exception as e:
            return f"PUBLISH_ERROR: {e}"

    @app.callback(
        Output('subscription-display', 'children'),
        [Input('interval-component', 'n_intervals')],
        [State('subscription-display', 'children')]
    )
    def update_subscriptions(_n, current_children):
        # cola compartida (vista/manager)
        q = message_queue
        if q is None and mqtt_client_manager is not None and hasattr(mqtt_client_manager, 'msg_queue'):
            q = mqtt_client_manager.msg_queue

        if q is None:
            return current_children

        new_blocks = []
        while True:
            try:
                topic, payload = q.get_nowait()
            except Empty:
                break
            except Exception:
                break

            # pretty-print si es JSON
            try:
                pretty = json.dumps(json.loads(payload), ensure_ascii=False, indent=2)
            except Exception:
                pretty = payload

            new_blocks.append(
                html.Div([
                    html.Div(f"[{topic}]", className='font-semibold'),
                    html.Pre(pretty, className='bg-white p-2 rounded overflow-x-auto')
                ], className='bg-gray-200 p-2 rounded')
            )

        if not new_blocks:
            return current_children

        existing = current_children if isinstance(current_children, list) else [current_children]
        # mantenemos hasta 50 bloques
        return (new_blocks + existing)[:50]

    @app.callback(
        Output('broker-status-indicator', 'className'),
        [Input('broker-status-interval', 'n_intervals')]
    )
    def update_broker_status(_n):
        status = "desconectado"
        if mqtt_client_manager is not None:
            try:
                status = mqtt_client_manager.get_connection_status()
            except Exception:
                status = 'desconectado'

        if status == 'conectado':
            return 'status-circle status-connected'
        if status == 'conectando':
            return 'status-circle status-connecting'
        return 'status-circle status-disconnected'
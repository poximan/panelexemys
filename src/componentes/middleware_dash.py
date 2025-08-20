from dash import html, dcc, no_update
from dash.dependencies import Input, Output
import dash_daq as daq
import json
import os
import config

from src.componentes.middleware_kpi import get_kpi_panel_layout
from src.componentes.middleware_histograma import get_controls_and_graph_layout
from src.componentes.middleware_tabla import get_main_data_table_layout

# Rutas para el archivo JSON de estado
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
OBSERVAR_FILE_PATH = os.path.join(project_root, 'src', 'observador', 'observar.json')

def get_dashboard(db_grd_descriptions, initial_grd_value):
    """
    Define el layout para el dashboard principal.
    
    NOTA: Las llamadas para registrar callbacks han sido movidas a un
    lugar centralizado para seguir las buenas practicas de Dash.
    """
    return html.Div(children=[
        html.H1("Middleware Exemys", className='main-title', style={'fontFamily': 'Inter, sans-serif'}),

        # Contenedor para la nueva fila con la dirección IP y el enlace
        html.Div(
            className='kpi-panel-container',
            style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'},
            children=[
                # Este div contiene la IP y el texto dinámico y sigue la misma estetica que los demas KPI's
                html.Div(
                    className='kpi-item',
                    style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between', 'width': '100%'},
                    children=[
                        html.P(
                            children=[
                                "estado [200.63.163.36:40000] = ",
                                # Nuevo elemento Span para mostrar el estado de la conexión
                                html.Span(
                                    id='tcp-status-text',
                                    children="desconocido", # Estado inicial
                                    style={'marginLeft': '5px', 'fontWeight': 'bold'}
                                )
                            ], 
                            style={'fontSize': '1.2rem', 'fontFamily': 'Inter, sans-serif', 'margin': '0', 'marginRight': 'auto'}
                        ),
                        html.A(
                            "Visitar MODEM",
                            href="http://192.168.11.1/wizard01.htm",
                            target="_blank",
                            className='modem-link',
                            style={'margin': '0'}
                        ),
                    ]
                )
            ]
        ),

        # Panel de Indicadores KPI (delegado)
        get_kpi_panel_layout(),

        # dcc.Store para mantener el estado de la ventana de tiempo y el numero de pagina.
        dcc.Store(id='time-window-state', data={'time_window': '1sem', 'page_number': 0, 'current_grd_id': initial_grd_value}),

        # Controles y Grafico Principal (delegado)
        get_controls_and_graph_layout(db_grd_descriptions, initial_grd_value),

        # Titulo y Contenedor para la tabla de detalles de registros (delegado)
        get_main_data_table_layout(),

        # Componente Interval para refrescar la pagina automaticamente
        dcc.Interval(
            id='interval-component',
            interval=config.DASHBOARD_REFRESH_INTERVAL_MS,
            n_intervals=0
        )
    ])

def register_dashboard_callbacks(app):
    """
    Registra los callbacks del dashboard, incluyendo la actualización del estado de la conexión TCP.
    """
    @app.callback(
        Output('tcp-status-text', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_tcp_status(n_intervals):
        """
        Lee el estado de la conexión TCP desde el archivo observar.json y actualiza el texto.
        """
        try:
            if not os.path.exists(OBSERVAR_FILE_PATH):
                return "desconectado"
            
            with open(OBSERVAR_FILE_PATH, 'r') as f:
                data = json.load(f)
                status = data.get('ip200_estado', 'desconectado')
                return status
        except (IOError, json.JSONDecodeError):
            return "desconectado"
        except Exception as e:
            print(f"Error al leer el estado TCP: {e}")
            return "error"
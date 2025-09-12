from dash import html, dcc
from dash.dependencies import Input, Output
import dash_daq as daq
from src.utils.paths import load_observar_key
import config

from src.web.dashboard.middleware_kpi import get_kpi_panel_layout
from src.web.dashboard.middleware_histograma import get_controls_and_graph_layout
from src.web.dashboard.middleware_tabla import get_main_data_table_layout

def get_dashboard(db_grd_descriptions, initial_grd_value):
    """
    define layout del dashboard principal
    """
    return html.Div(children=[
        html.H1("Middleware Exemys", className='main-title', style={'fontFamily': 'Inter, sans-serif'}),

        html.Div(
            className='kpi-panel-container',
            style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'},
            children=[
                html.Div(
                    className='kpi-item',
                    style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between', 'width': '100%'},
                    children=[
                        html.P(
                            children=[
                                "estado [200.63.163.36:40000] = ",
                                html.Span(
                                    id='tcp-status-text',
                                    children="desconocido",
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

        get_kpi_panel_layout(),

        dcc.Store(id='time-window-state', data={'time_window': '1sem', 'page_number': 0, 'current_grd_id': initial_grd_value}),

        get_controls_and_graph_layout(db_grd_descriptions, initial_grd_value),

        get_main_data_table_layout(),

        dcc.Interval(
            id='interval-component',
            interval=config.DASHBOARD_REFRESH_INTERVAL_MS,
            n_intervals=0
        )
    ])

def register_dashboard_callbacks(app):
    """
    registra callbacks del dashboard
    """
    @app.callback(
        Output('tcp-status-text', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_tcp_status(_n_intervals):
        """
        actualiza texto de estado tcp leyendo observar.json -> ip200_estado
        """
        try:
            status = str(load_observar_key("ip200_estado", "desconectado"))
            return status
        except Exception:
            return "desconectado"
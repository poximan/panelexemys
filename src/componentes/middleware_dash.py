from dash import html, dcc
import dash_daq as daq
# Importa las funciones de layout y registro de callbacks de los nuevos archivos
from src.componentes.middleware_kpi import get_kpi_panel_layout, register_kpi_panel_callbacks
from src.componentes.middleware_histograma import get_controls_and_graph_layout, register_controls_and_graph_callbacks
from src.componentes.middleware_tabla import get_main_data_table_layout, register_main_data_table_callbacks
import config # Importacion corregida: necesario para config.DASHBOARD_REFRESH_INTERVAL_MS


def get_dashboard(db_grd_descriptions, initial_grd_value):
    """
    Define el layout para la pestaña 'Reles MiCOM'.
    Incluye un BooleanSwitch de dash_daq para controlar la observacion de reles,
    un area de estado, y un contenedor para las tablas de fallas.
    """
    return html.Div(children=[
        html.H1("Middleware Exemys", className='main-title', style={'fontFamily': 'Inter, sans-serif'}),

        html.A(
            "Visitar MODEM",
            href="http://192.168.11.1/wizard01.htm",
            target="_blank",  # Abre el enlace en una nueva pestaña
            className='modem-link', # Añadimos una clase para posibles estilos CSS
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
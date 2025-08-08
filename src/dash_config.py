import dash
from dash import dcc, html
from dash.dependencies import Input, Output
from src.persistencia.dao_grd import grd_dao
import config

from src.componentes.middleware_dash import get_dashboard
from src.componentes.reles_panel import get_reles_micom_layout, register_reles_micom_callbacks
from src.componentes.mantenimiento import get_mantenimiento_layout, register_mantenimiento_callbacks
from src.componentes.middleware_kpi import register_kpi_panel_callbacks
from src.componentes.middleware_histograma import register_controls_and_graph_callbacks
from src.componentes.middleware_tabla import register_main_data_table_callbacks
from src.componentes.broker_view import get_broker_layout, register_broker_callbacks # NUEVO: Importa la vista y callbacks del broker

def configure_dash_app(app: dash.Dash):
    """
    Configura el layout y los callbacks de la aplicacion Dash para una estructura SPA.
    """
    db_grd_descriptions = grd_dao.get_all_grds_with_descriptions()
    initial_grd_value = list(db_grd_descriptions.keys())[0] if db_grd_descriptions else None

    # --- Definicion de Layouts para cada "pagina" ---
    dashboard_layout = get_dashboard(db_grd_descriptions, initial_grd_value)
    reles_micom_layout = get_reles_micom_layout()
    mantenimiento_layout = get_mantenimiento_layout()
    broker_layout = get_broker_layout() # NUEVO: Obtiene el layout del broker

    # --- Layout Principal de la Aplicacion (Shell de la SPA) ---
    app.layout = html.Div(className='main-app-container', children=[
        dcc.Location(id='url', refresh=False),
        html.Div(className='navbar', children=[
            dcc.Link('Dashboard', href='/dash', className='nav-link'),
            dcc.Link('Reles MiCOM', href='/reles', className='nav-link'),
            dcc.Link('Mantenimiento', href='/mantenimiento', className='nav-link'),
            dcc.Link('Broker', href='/broker', className='nav-link') # NUEVO: Enlace al broker
        ]),
        html.Hr(className='navbar-separator'),
        html.Div(id='page-content')
    ])

    # --- Registro de Callbacks de Dash ---
    @app.callback(Output('page-content', 'children'),
                  [Input('url', 'pathname')])
    def display_page(pathname):
        if pathname == '/reles':
            return reles_micom_layout
        elif pathname == '/mantenimiento':
            return mantenimiento_layout
        elif pathname == '/broker': # NUEVO: Ruteo para la pagina del broker
            return broker_layout
        else:
            return dashboard_layout

    # Registrar TODOS los callbacks de cada panel/pagina en un solo lugar
    register_reles_micom_callbacks(app)
    register_mantenimiento_callbacks(app)
    register_kpi_panel_callbacks(app, config)
    register_controls_and_graph_callbacks(app)
    register_main_data_table_callbacks(app)
    register_broker_callbacks(app)
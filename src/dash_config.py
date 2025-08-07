import dash
from dash import dcc, html
from dash.dependencies import Input, Output
from src.persistencia.dao_grd import grd_dao
import config

from src.componentes.middleware_dash import get_dashboard
from src.componentes.reles_panel import get_reles_micom_layout, register_reles_micom_callbacks
from src.componentes.mantenimiento import get_mantenimiento_layout, register_mantenimiento_callbacks
# Importamos las funciones de registro de callbacks que antes estaban en middleware_dash.py
from src.componentes.middleware_kpi import register_kpi_panel_callbacks
from src.componentes.middleware_histograma import register_controls_and_graph_callbacks
from src.componentes.middleware_tabla import register_main_data_table_callbacks


def configure_dash_app(app: dash.Dash):
    """
    Configura el layout y los callbacks de la aplicacion Dash para una estructura SPA.
    Esta funcion toma una instancia de `dash.Dash` y le añade la interfaz y la logica general,
    delegando la construccion de paneles especificos a otros modulos.
    """

    # Obtener GRD IDs y descripciones de la base de datos una vez para el layout inicial
    db_grd_descriptions = grd_dao.get_all_grds_with_descriptions()
    initial_grd_value = list(db_grd_descriptions.keys())[0] if db_grd_descriptions else None

    # --- Definicion de Layouts para cada "pagina" ---
    # get_dashboard ya no necesita 'app' como parametro, solo los datos
    dashboard_layout = get_dashboard(db_grd_descriptions, initial_grd_value)
    # Layout para la Pagina de "Reles MiCOM" (delegado al nuevo modulo)
    reles_micom_layout = get_reles_micom_layout()
    # Layout para la Pagina de "Mantenimiento" (delegado al nuevo modulo)
    mantenimiento_layout = get_mantenimiento_layout()

    # --- Layout Principal de la Aplicacion (Shell de la SPA) ---
    app.layout = html.Div(className='main-app-container', children=[
        # Componente dcc.Location para rastrear la URL
        dcc.Location(id='url', refresh=False),

        # Enlaces de navegacion
        html.Div(className='navbar', children=[
            dcc.Link('Dashboard', href='/dash', className='nav-link'),
            dcc.Link('Reles MiCOM', href='/reles', className='nav-link'),
            dcc.Link('Mantenimiento', href='/mantenimiento', className='nav-link')
        ]),
        html.Hr(className='navbar-separator'), # Separador visual

        # Contenedor donde se cargara el contenido de la pagina actual
        html.Div(id='page-content')
    ])

    # --- Registro de Callbacks de Dash ---
    # Callback principal para manejar la navegacion de la SPA
    @app.callback(Output('page-content', 'children'),
                  [Input('url', 'pathname')])
    def display_page(pathname):
        if pathname == '/reles':
            return reles_micom_layout
        elif pathname == '/mantenimiento':
            return mantenimiento_layout
        else: # Si no es /reles o /mantenimiento, o cualquier otra ruta, mostramos el dashboard por defecto
            return dashboard_layout

    # Registrar TODOS los callbacks de cada panel/pagina en un solo lugar
    register_reles_micom_callbacks(app)
    register_mantenimiento_callbacks(app)
    # NUEVO: Registro de los callbacks del dashboard
    register_kpi_panel_callbacks(app, config)
    register_controls_and_graph_callbacks(app)
    register_main_data_table_callbacks(app)
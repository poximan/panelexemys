import dash
from dash import dcc, html
from dash.dependencies import Input, Output
from src.persistencia.dao_grd import grd_dao
import config

# Importa las funciones de layout y registro de callbacks de los nuevos archivos
from src.componentes.middleware_kpi import get_kpi_panel_layout, register_kpi_panel_callbacks
from src.componentes.middleware_histograma import get_controls_and_graph_layout, register_controls_and_graph_callbacks
from src.componentes.middleware_tabla import get_main_data_table_layout, register_main_data_table_callbacks
from src.componentes.reles_panel import get_reles_micom_layout, register_reles_micom_callbacks
from src.componentes.mantenimiento import get_mantenimiento_layout, register_mantenimiento_callbacks


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

    # Layout para el Dashboard Principal
    dashboard_layout = html.Div(children=[
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

    # Layout para la Pagina de "Reles MiCOM" (delegado al nuevo modulo)
    reles_micom_layout = get_reles_micom_layout()

    # Layout para la Pagina de "Mantenimiento" (delegado al nuevo modulo) # <-- ¡NUEVO LAYOUT!
    mantenimiento_layout = get_mantenimiento_layout()

    # --- Layout Principal de la Aplicacion (Shell de la SPA) ---
    app.layout = html.Div(className='main-app-container', children=[
        # Componente dcc.Location para rastrear la URL
        dcc.Location(id='url', refresh=False),

        # Enlaces de navegacion
        html.Div(className='navbar', children=[
            dcc.Link('Dashboard', href='/dash', className='nav-link'),
            dcc.Link('Reles MiCOM', href='/reles', className='nav-link'),
            dcc.Link('Mantenimiento', href='/mantenimiento', className='nav-link') # <-- ¡NUEVO ENLACE!
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

    # Registrar los callbacks especificos de cada panel/pagina
    # Estos callbacks deben ser registrados una sola vez al inicio de la aplicacion.
    register_kpi_panel_callbacks(app, config)
    register_controls_and_graph_callbacks(app)
    register_main_data_table_callbacks(app)
    register_reles_micom_callbacks(app)
    register_mantenimiento_callbacks(app)
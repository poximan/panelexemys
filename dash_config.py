# dash_config.py
import dash
from dash import dcc, html
from dash.dependencies import Input, Output # Necesitamos Output aquÃ­ para el callback de la URL
from persistencia.dao_grd import grd_dao
import config

# Importa las funciones de layout y registro de callbacks de los nuevos archivos
from componentes.kpi_panel import get_kpi_panel_layout, register_kpi_panel_callbacks
from componentes.controls_and_graph import get_controls_and_graph_layout, register_controls_and_graph_callbacks
from componentes.main_data_table import get_main_data_table_layout, register_main_data_table_callbacks


def configure_dash_app(app: dash.Dash):
    """
    Configura el layout y los callbacks de la aplicaciÃ³n Dash para una estructura SPA.
    Esta funciÃ³n toma una instancia de `dash.Dash` y le aÃ±ade la interfaz y la lÃ³gica.
    """

    # Obtener GRD IDs y descripciones de la base de datos una vez para el layout inicial
    db_grd_descriptions = grd_dao.get_all_grds_with_descriptions()
    initial_grd_value = list(db_grd_descriptions.keys())[0] if db_grd_descriptions else None

    # --- DefiniciÃ³n de Layouts para cada "pÃ¡gina" ---

    # Layout para el Dashboard Principal
    dashboard_layout = html.Div(children=[
        html.H1("Middleware Exemys", className='main-title', style={'fontFamily': 'Inter, sans-serif'}),

        html.A(
            "Visitar MODEM",
            href="http://192.168.11.1/wizard01.htm",
            target="_blank",  # Abre el enlace en una nueva pestaÃ±a
            className='modem-link', # AÃ±adimos una clase para posibles estilos CSS
        ),

        # Panel de Indicadores KPI
        get_kpi_panel_layout(),

        # dcc.Store para mantener el estado de la ventana de tiempo y el nÃºmero de pÃ¡gina.
        dcc.Store(id='time-window-state', data={'time_window': '1sem', 'page_number': 0, 'current_grd_id': initial_grd_value}),

        # Controles y GrÃ¡fico Principal
        get_controls_and_graph_layout(db_grd_descriptions, initial_grd_value),

        # TÃ­tulo y Contenedor para la tabla de detalles de registros (ahora al pie)
        get_main_data_table_layout(),

        # Componente Interval para refrescar la pÃ¡gina automÃ¡ticamente
        dcc.Interval(
            id='interval-component',
            interval=config.DASHBOARD_REFRESH_INTERVAL_MS,
            n_intervals=0
        )
    ])

    # Layout para la PÃ¡gina de "Acerca de" (o futura nueva pÃ¡gina)
    # Por ahora, solo un tÃ­tulo como pediste.
    about_layout = html.Div(children=[
        html.H1("Esta es la pÃ¡gina de Acerca de", className='main-title'),
        html.P("AquÃ­ irÃ¡ el contenido de la segunda pÃ¡gina.")
    ], className='main-container') # Usamos main-container para que herede estilos base


    # --- Layout Principal de la AplicaciÃ³n (Shell de la SPA) ---
    app.layout = html.Div(className='main-app-container', children=[
        # Componente dcc.Location para rastrear la URL
        dcc.Location(id='url', refresh=False),

        # Enlaces de navegaciÃ³n
        html.Div(className='navbar', children=[
            dcc.Link('Dashboard', href='/dash', className='nav-link'),
            dcc.Link('Reles MiCOM', href='/reles', className='nav-link')
        ]),
        html.Hr(className='navbar-separator'), # Separador visual

        # Contenedor donde se cargarÃ¡ el contenido de la pÃ¡gina actual
        html.Div(id='page-content')
    ])

    # --- Registro de Callbacks de Dash ---
    # Callback principal para manejar la navegaciÃ³n de la SPA
    @app.callback(Output('page-content', 'children'),
                  [Input('url', 'pathname')])
    def display_page(pathname):
        if pathname == '/reles':
            return about_layout
        else: # Si no es /about, o cualquier otra ruta, mostramos el dashboard por defecto
            return dashboard_layout

    # Registrar los callbacks especÃ­ficos del dashboard
    # Estos callbacks deben ser registrados una sola vez al inicio de la aplicaciÃ³n.
    register_kpi_panel_callbacks(app, config)
    register_controls_and_graph_callbacks(app)
    register_main_data_table_callbacks(app)
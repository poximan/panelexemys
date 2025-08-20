import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
from src.persistencia.dao_grd import grd_dao
import config
from flask import request

from src.componentes.middleware_dash import get_dashboard, register_dashboard_callbacks
from src.componentes.reles_panel import get_reles_micom_layout, register_reles_micom_callbacks
from src.componentes.mantenimiento import get_mantenimiento_layout, register_mantenimiento_callbacks
from src.componentes.middleware_kpi import register_kpi_panel_callbacks
from src.componentes.middleware_histograma import register_controls_and_graph_callbacks
from src.componentes.middleware_tabla import register_main_data_table_callbacks
from src.componentes.broker_view import get_broker_layout, register_broker_callbacks

# Definir la clave de acceso para las paginas de administrador
ADMIN_KEY = '12345' # ¡IMPORTANTE! Cambia esto por una clave secreta y segura en producción.

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
    broker_layout = get_broker_layout()

    # Layout para el acceso con clave
    access_prompt_layout = html.Div(id='access-prompt-container', className='access-prompt', children=[
        html.H1("🔑 Acceso Requerido", style={'textAlign': 'center', 'marginTop': '50px'}),
        dcc.Input(id='admin-key-input', type='password', placeholder='Clave de acceso', className='key-input'),
        html.Button('Acceder', id='submit-key-button', n_clicks=0, className='key-button'),
        html.Div(id='access-feedback', style={'textAlign': 'center', 'color': 'red', 'marginTop': '10px'})
    ])

    # --- Layout Principal de la Aplicacion (Shell de la SPA) ---
    app.layout = html.Div(className='main-app-container', children=[
        dcc.Location(id='url', refresh=False),
        dcc.Store(id='auth-status', data={'is_admin': False}),
        
        # El menú de navegación ahora muestra todos los enlaces de forma estática
        html.Div(className='navbar', id='navbar-links-container', children=[
            dcc.Link('Dashboard', href='/dash', className='nav-link'),
            dcc.Link('Reles MiCOM', href='/reles', className='nav-link'),
            dcc.Link('Mantenimiento', href='/mantenimiento', className='nav-link'),
            dcc.Link('Broker', href='/broker', className='nav-link')
        ]),
        html.Hr(className='navbar-separator'),
        
        html.Div(id='page-content')
    ])

    # --- Callback para manejar la autenticación con clave secreta ---
    # Este callback solo actualiza el estado de autenticación.
    @app.callback(
        Output('auth-status', 'data'),
        Output('access-feedback', 'children'),
        Input('submit-key-button', 'n_clicks'),
        State('admin-key-input', 'value')
    )
    def authenticate(n_clicks, key_value):
        if n_clicks > 0:
            if key_value == ADMIN_KEY:
                # Clave correcta
                return {'is_admin': True}, "✅ Acceso concedido. Redirigiendo..."
            else:
                # Clave incorrecta
                return {'is_admin': False}, "❌ Clave incorrecta."
        
        # Estado inicial
        return dash.no_update, ""

    # --- Callback para mostrar el contenido de la pagina ---
    @app.callback(
        Output('page-content', 'children'),
        [Input('url', 'pathname'), Input('auth-status', 'data')]
    )
    def display_page(pathname, auth_data):
        is_admin = auth_data['is_admin']
        
        if pathname == '/reles':
            return reles_micom_layout
        elif pathname == '/mantenimiento':
            # Si el usuario no está autenticado, muestra el formulario de acceso
            if not is_admin:
                return access_prompt_layout
            return mantenimiento_layout
        elif pathname == '/broker':
            # Si el usuario no está autenticado, muestra el formulario de acceso
            if not is_admin:
                return access_prompt_layout
            return broker_layout
        else:
            return dashboard_layout

    # Registrar TODOS los callbacks de cada panel/pagina en un solo lugar
    register_dashboard_callbacks(app)
    register_kpi_panel_callbacks(app, config)
    register_controls_and_graph_callbacks(app)
    register_main_data_table_callbacks(app)
    register_reles_micom_callbacks(app)
    register_mantenimiento_callbacks(app)
    register_broker_callbacks(app)
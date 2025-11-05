import dash
from dash import dcc, html
from queue import Queue
from dash.dependencies import Input, Output
from src.persistencia.dao.dao_grd import grd_dao
import config

from src.web.dashboard.middleware_dash import get_dashboard, register_dashboard_callbacks
from src.web.dashboard.middleware_kpi import register_kpi_panel_callbacks
from src.web.dashboard.middleware_histograma import register_controls_and_graph_callbacks
from src.web.dashboard.middleware_tabla import register_main_data_table_callbacks
from src.web.reles_panel import get_reles_micom_layout, register_reles_micom_callbacks
from src.web.mantenimiento import get_mantenimiento_layout, register_mantenimiento_callbacks
from src.web.email import get_email_layout, register_email_callbacks
from src.web.broker.broker_view import (
    get_broker_layout,
    register_broker_callbacks,
    initialize_broker_components,
)
from src.web.proxmox import get_proxmox_layout, register_proxmox_callbacks
from src.web.charito import get_charito_layout, register_charito_callbacks


BASE = "/dash"


def configure_dash_app(app: dash.Dash, mqtt_client_manager, message_queue: Queue) -> None:
    """
    Configura el layout y los callbacks de la aplicación Dash para una estructura SPA.
    """
    db_grd_descriptions = grd_dao.get_all_grds_with_descriptions()
    initial_grd_value = list(db_grd_descriptions.keys())[0] if db_grd_descriptions else None

    initialize_broker_components(mqtt_client_manager, message_queue)

    dashboard_layout = get_dashboard(db_grd_descriptions, initial_grd_value)
    reles_micom_layout = get_reles_micom_layout()
    mantenimiento_layout = get_mantenimiento_layout()
    email_layout = get_email_layout()
    broker_layout = get_broker_layout()
    proxmox_layout = get_proxmox_layout()
    charito_layout = get_charito_layout()

    app.layout = html.Div(
        className="main-app-container",
        children=[
            dcc.Location(id="url", refresh=False),
            html.Div(
                className="navbar",
                id="navbar-links-container",
                children=[
                    dcc.Link("Dashboard", href=f"{BASE}", className="nav-link"),
                    dcc.Link("Reles MiCOM", href=f"{BASE}/reles", className="nav-link"),
                    dcc.Link("Mantenimiento", href=f"{BASE}/mantenimiento", className="nav-link"),
                    dcc.Link("Email", href=f"{BASE}/email", className="nav-link"),
                    dcc.Link("Broker", href=f"{BASE}/broker", className="nav-link"),
                    dcc.Link("Proxmox", href=f"{BASE}/proxmox", className="nav-link"),
                    dcc.Link("Charito", href=f"{BASE}/charito", className="nav-link"),
                ],
            ),
            html.Hr(className="navbar-separator"),
            html.Div(id="page-content"),
        ],
    )

    @app.callback(Output("page-content", "children"), Input("url", "pathname"))
    def display_page(pathname: str):
        if pathname == f"{BASE}/reles":
            return reles_micom_layout
        if pathname == f"{BASE}/mantenimiento":
            return mantenimiento_layout
        if pathname == f"{BASE}/email":
            return email_layout
        if pathname == f"{BASE}/broker":
            return broker_layout
        if pathname == f"{BASE}/proxmox":
            return proxmox_layout
        if pathname == f"{BASE}/charito":
            return charito_layout
        if pathname == BASE or pathname == f"{BASE}/":
            return dashboard_layout
        return html.Div("Ruta no encontrada", className="error-page")

    register_dashboard_callbacks(app)
    register_kpi_panel_callbacks(app, config)
    register_controls_and_graph_callbacks(app)
    register_main_data_table_callbacks(app)
    register_reles_micom_callbacks(app)
    register_mantenimiento_callbacks(app)
    register_email_callbacks(app)
    register_broker_callbacks(app)
    register_proxmox_callbacks(app)
    register_charito_callbacks(app)

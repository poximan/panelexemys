from __future__ import annotations

import dash
from dash import html, dcc
from dash.dependencies import Input, Output

import config
from src.web.clients.modbus_client import modbus_client

PUBLIC_BASE_URL = config.PUBLIC_BASE_URL

PORT_MAPPINGS = [
    {
        "servicio": "panelexemys",
        "interno": "cont-panelexemys:8052 (http)",
        "externo": f"{PUBLIC_BASE_URL}/dash/",
        "localhost": "http://localhost:8052",
    },
    {
        "servicio": "pve-service",
        "interno": "cont-pve-service:8083 (http)",
        "externo": f"{PUBLIC_BASE_URL}/pve/api/pve/state",
        "localhost": "http://localhost:8083/api/pve/state",
    },
    {
        "servicio": "modbus-mw-service",
        "interno": "cont-modbus-mw-service:8084 (http)",
        "externo": f"{PUBLIC_BASE_URL}/api/",
        "localhost": "http://localhost:8084",
    },
    {
        "servicio": "router-telef-service",
        "interno": "cont-router-telef-service:8086 (http)",
        "externo": f"{PUBLIC_BASE_URL}/router/status",
        "localhost": "http://localhost:8086/status",
    },
    {
        "servicio": "scada-citec-service",
        "interno": "cont-scada-citec-service:8094 (http)",
        "externo": f"{PUBLIC_BASE_URL}/scada/",
        "localhost": "http://localhost:8094",
    },
]


def get_mantenimiento_layout() -> html.Div:
    """
    Layout de la pestaña de mantenimiento con estado del GE, topología, mapeos de puertos e iframe del repositorio.
    """
    return html.Div(
        children=[
            html.H1("Mantenimiento", className="main-title"),
            html.Div(
                children=[
                    html.H2("Grupo Electrogeno", className="sub-title"),
                    html.Div(
                        className="ge-status-card",
                        children=[
                            html.Div(id="ge-emar-led", className="status-circle ge-led-unknown"),
                            html.Div(id="ge-emar-text", className="ge-status-text", children="GE sin datos"),
                        ],
                    ),
                ],
                style={"marginBottom": "32px"},
            ),
            html.Div(
                children=[
                    html.H2("Topologia de red", className="sub-title"),
                    html.Div(
                        className="magnifier-container",
                        children=[
                            html.Img(
                                src="./assets/topologia.png",
                                alt="Diagrama de Topologia de la Aplicacion",
                                className="magnifier-image",
                            ),
                            html.Div(className="magnifier-loupe"),
                        ],
                        style={"width": "100%", "margin": "0 auto", "position": "relative"},
                    ),
                ],
                style={"textAlign": "center", "marginBottom": "32px"},
            ),
            html.Div(
                children=[
                    html.H2("Mapeo de puertos (docker <-> localhost <-> https)", className="sub-title"),
                    html.Table(
                        className="port-mapping-table",
                        children=[
                            html.Thead(
                                html.Tr(
                                    [
                                        html.Th("servicio"),
                                        html.Th("docker interno"),
                                        html.Th("https publico"),
                                        html.Th("localhost pruebas"),
                                    ]
                                )
                            ),
                            html.Tbody(
                                [
                                    html.Tr(
                                        [
                                            html.Td(item["servicio"]),
                                            html.Td(item["interno"]),
                                            html.Td(item["externo"]),
                                            html.Td(item["localhost"]),
                                        ]
                                    )
                                    for item in PORT_MAPPINGS
                                ]
                            ),
                        ],
                    ),
                ],
                style={"marginBottom": "32px"},
            ),
            dcc.Interval(
                id="ge-emar-interval",
                interval=config.DASH_REFRESH_SECONDS,
                n_intervals=0,
            ),
        ]
    )


def register_mantenimiento_callbacks(app: dash.Dash) -> None:
    @app.callback(
        Output("ge-emar-text", "children"),
        Output("ge-emar-led", "className"),
        Input("ge-emar-interval", "n_intervals"),
    )
    def _refresh_ge_status(_tick: int):
        try:
            data = modbus_client.get_ge_status()
            estado = str(data.get("estado", "desconocido")).strip().lower()
        except Exception:
            estado = "desconocido"

        estado_map = {
            "marcha": "GE en marcha",
            "parado": "GE parado",
            "desconocido": "GE sin datos",
        }
        led_map = {
            "marcha": "status-circle ge-led-marcha",
            "parado": "status-circle ge-led-parado",
            "desconocido": "status-circle ge-led-unknown",
        }
        return estado_map.get(estado, estado_map["desconocido"]), led_map.get(estado, led_map["desconocido"])

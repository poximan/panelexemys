from __future__ import annotations

import dash
from dash import html, dcc
from dash.dependencies import Input, Output

import config
from src.web.clients.modbus_client import modbus_client


def get_mantenimiento_layout() -> html.Div:
    """
    Layout de la pestaña de mantenimiento con estado del GE, topología e iframe del repositorio.
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
                    html.H2("Repositorio HTTP interno", className="sub-title"),
                    html.Iframe(
                        src="/repohttp/",
                        className="repohttp-frame",
                        style={
                            "width": "100%",
                            "height": "640px",
                            "border": "1px solid #d9d9d9",
                            "borderRadius": "8px",
                            "backgroundColor": "#ffffff",
                        },
                        title="Repositorio HTTP",
                    ),
                ],
                style={"marginTop": "24px"},
            ),
            dcc.Interval(
                id="ge-emar-interval",
                interval=getattr(config, "DASH_REFRESH_SECONDS", 10000),
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

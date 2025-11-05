from __future__ import annotations

import dash
from dash import html


def get_mantenimiento_layout() -> html.Div:
    """
    Retorna el layout HTML de la nueva página de mantenimiento.
    Mantiene la topología de red e incorpora el repositorio HTTP embebido.
    """
    return html.Div(
        children=[
            html.H1("Mantenimiento", className="main-title"),
            html.Div(
                children=[
                    html.H2("Topología de red", className="sub-title"),
                    html.Div(
                        className="magnifier-container",
                        children=[
                            html.Img(
                                src="./assets/topologia.png",
                                alt="Diagrama de Topología de la Aplicación",
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
        ]
    )


def register_mantenimiento_callbacks(_app: dash.Dash) -> None:
    """
    La página de mantenimiento no requiere callbacks dinámicos por el momento.
    Se deja el hook para mantener compatibilidad con la inicialización centralizada.
    """
    return None

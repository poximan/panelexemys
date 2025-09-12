import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import time
from src.alarmas import email_sender
from src.utils.paths import load_observar
import config

# Definicion del layout para la pagina de Mantenimiento
def get_mantenimiento_layout():
    """
    Retorna el layout HTML para la pagina de Mantenimiento.
    """
    return html.Div(children=[
        html.H1("Panel de Mantenimiento", className='main-title'),

        # Estado servidor de correo (smtp/ping_local/ping_remoto)
        html.Div(className='kpi-item', children=[
            html.H2("Estado servidor de correo", className='sub-title'),
            html.Table(
                id='email-health-table',
                className='data-table',
                children=[
                    html.Thead(html.Tr([
                        html.Th("SMTP (post.servicoop.com)", className="table-header-cell"),
                        html.Th("Ping local (servicoop.com.ar)", className="table-header-cell"),
                        html.Th("Ping remoto (email.servicoop.com)", className="table-header-cell"),
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td("desconocido", id="cell-smtp", className="table-data-cell"),
                            html.Td("desconocido", id="cell-ping-local", className="table-data-cell"),
                            html.Td("desconocido", id="cell-ping-remoto", className="table-data-cell"),
                        ])
                    ])
                ]
            ),
            dcc.Interval(
                id='email-health-interval',
                interval=config.DASHBOARD_REFRESH_INTERVAL_MS,
                n_intervals=0
            ),
        ], style={'marginBottom': '24px'}),

        html.Div(className='button-container', children=[
            html.Button(
                'Probar Email',
                id='btn-probar-email',
                n_clicks=0,
                className='button-primary'
            ),
            html.Div(id='output-probar-email', style={'marginTop': '10px'})
        ], style={'textAlign': 'center', 'marginTop': '20px'}),

        html.Div(
            children=[
                html.H2("Topologia de red", className='sub-title'),
                html.Div(
                    className='magnifier-container',
                    children=[
                        html.Img(
                            src='/assets/topologia.png',
                            alt='Diagrama de Topologia de la Aplicacion',
                            className='magnifier-image'
                        ),
                        html.Div(className='magnifier-loupe')
                    ],
                    style={
                        'width': '100%',
                        'margin': '0 auto',
                        'position': 'relative'
                    }
                )
            ],
            style={'textAlign': 'center'}
        ),
    ])

# Registro de callbacks para la pagina de Mantenimiento
def register_mantenimiento_callbacks(app: dash.Dash):
    """
    Registra callbacks de prueba de email y de actualizacion del estado de correo.
    """
    @app.callback(
        Output('output-probar-email', 'children'),
        Input('btn-probar-email', 'n_clicks')
    )
    def handle_probar_email(n_clicks):
        if n_clicks > 0:
            test_recipient = config.ALARM_EMAIL_RECIPIENT
            test_subject = "Email de Prueba desde Panel de Mantenimiento"
            test_body = (
                f"Este es un email de prueba enviado desde el Panel de Mantenimiento "
                f"de la aplicacion Middleware Exemys Dash. Fecha y Hora: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            sent_successfully = email_sender.send_alarm_email(
                recipients=test_recipient,
                subject=test_subject,
                body=test_body
            )

            if sent_successfully:
                return html.Div([
                    html.P("Email de prueba enviado con exito.", className='info-message', style={'color': 'green'}),
                    html.P(f"Enviado a: {test_recipient}", style={'fontSize': '14px'})
                ])
            else:
                return html.Div([
                    html.P("Error al enviar el email de prueba. Revisar logs para mas detalles.", className='info-message', style={'color': 'red'}),
                    html.P(f"Intento de envio a: {test_recipient}", style={'fontSize': '14px'})
                ])
        return ""

    @app.callback(
        Output('cell-smtp', 'children'),
        Output('cell-ping-local', 'children'),
        Output('cell-ping-remoto', 'children'),
        Input('email-health-interval', 'n_intervals')
    )
    def update_email_health(_n):
        """
        Lee observar.json y actualiza la fila con los tres estados.
        """
        data = load_observar()
        estados = data.get("server_email_estado", {}) if isinstance(data, dict) else {}

        smtp = estados.get("smtp", "desconocido")
        ping_local = estados.get("ping_local", "desconocido")
        ping_remoto = estados.get("ping_remoto", "desconocido")

        return smtp, ping_local, ping_remoto
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import time # Importar para time.strftime

# MODIFICACIÓN: Importar el servicio de envio de email y la configuracion
from src.notificador import email_sender
import config

# Definicion del layout para la pagina de Mantenimiento
def get_mantenimiento_layout():
    """
    Retorna el layout HTML para la pagina de Mantenimiento.
    """
    return html.Div(children=[
        html.H1("Panel de Mantenimiento", className='main-title'),

        html.Div(className='button-container', children=[
            html.Button(
                'Probar Email',
                id='btn-probar-email',
                n_clicks=0,
                className='button-primary' # Clase CSS para estilos
            ),
            html.Div(id='output-probar-email', style={'marginTop': '10px'}) # Para mostrar mensajes de respuesta
        ], style={'textAlign': 'center', 'marginTop': '20px'}),

        html.Div(
            children=[
                html.H2("Topología de red", className='sub-title'),
                html.Img(
                    src='/assets/topologia.png',  # Ruta al archivo SVG en la carpeta assets
                    alt='Diagrama de Topología de la Aplicación',
                    style={
                        'width': '100%',  # Ajusta el ancho para que sea responsivo
                        'height': 'auto', # Mantiene la relación de aspecto
                        'display': 'block', # Centra la imagen                        
                        'border-radius': '8px', # Esquinas redondeadas
                        'box-shadow': '0 4px 8px rgba(0, 0, 0, 0.1)' # Sombra suave
                    }
                )
            ],
            style={'textAlign': 'center', 'marginTop': '30px', 'marginBottom': '30px'}
        ),
    ])

# Registro de callbacks para la pagina de Mantenimiento
def register_mantenimiento_callbacks(app: dash.Dash):
    """
    Registra los callbacks especificos para la pagina de Mantenimiento.
    Ahora el boton intentara enviar un email real.
    """
    @app.callback(
        Output('output-probar-email', 'children'),
        Input('btn-probar-email', 'n_clicks')
    )
    def handle_probar_email(n_clicks):
        if n_clicks > 0:
            # Definir destinatario, asunto y cuerpo del email de prueba
            test_recipient = config.ALARM_EMAIL_RECIPIENT
            test_subject = "Email de Prueba desde Panel de Mantenimiento"
            test_body = (
                f"Este es un email de prueba enviado desde el Panel de Mantenimiento "
                f"de la aplicacion Middleware Exemys Dash. Fecha y Hora: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # Intentar enviar el email usando el servicio email_sender
            sent_successfully = email_sender.send_alarm_email(
                recipients=test_recipient,
                subject=test_subject,
                body=test_body
            )

            # Retornar el mensaje de exito o error
            if sent_successfully:
                return html.Div([
                    html.P("Email de prueba enviado con exito.", className='info-message', style={'color': 'green'}),
                    html.P(f"Enviado a: {test_recipient}", style={'fontSize': '14px'})
                ])
            else:
                return html.Div([
                    html.P("Error al enviar el email de prueba. Revisa los logs de la consola para mas detalles.", className='info-message', style={'color': 'red'}),
                    html.P(f"Intento de envio a: {test_recipient}", style={'fontSize': '14px'})
                ])
        return "" # No mostrar nada inicialmente
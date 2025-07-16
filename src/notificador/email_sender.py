import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import config

def send_alarm_email(recipients: list[str] | str, subject: str, body: str) -> bool:
    """
    Envía un correo electrónico de alarma utilizando el módulo smtplib.
    Ahora acepta una lista de destinatarios o una cadena individual.

    Args:
        recipients (list[str] | str): Una lista de direcciones de correo electrónico
                                      o una cadena con una única dirección.
        subject (str): El asunto principal del correo.
        body (str): El cuerpo del mensaje del correo.

    Returns:
        bool: True si el correo se envió con éxito a todos los destinatarios, False en caso contrario.
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_subject = f"{config.ALARM_EMAIL_SUBJECT_PREFIX}{subject}"

    # Asegurarse de que recipients sea siempre una lista
    if isinstance(recipients, str):
        recipients_list = [recipients]
    elif isinstance(recipients, list):
        recipients_list = recipients
    else:
        print(f"ERROR: Tipo de destinatario no válido. Debe ser str o list[str]. Se recibió: {type(recipients)}")
        return False

    if not recipients_list:
        print(f"ADVERTENCIA: No se especificaron destinatarios para el email con asunto: '{full_subject}'.")
        return False

    # Prepara el mensaje del correo
    msg = MIMEText(body)
    msg['Subject'] = full_subject
    msg['From'] = config.ALARM_EMAIL_SENDER
    # Unir la lista de destinatarios con comas para el encabezado 'To'
    msg['To'] = ", ".join(recipients_list) 

    server = None
    sent_successfully = False # Flag para rastrear el éxito del envío

    try:
        if config.SMTP_USE_TLS:
            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT_SECONDS)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT_SECONDS)
        
        server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        
        # send_message es la forma más moderna y recomendada con objetos MIME
        server.send_message(msg) 
        server.quit()
        sent_successfully = True

        print(f"\n--- Email de Alarma ENVIADO ({current_time}) ---")
        print(f"PARA: {', '.join(recipients_list)}")
        print(f"ASUNTO: {full_subject}")
        print("--------------------------")

    except smtplib.SMTPConnectError as e:
        print(f"\n--- ERROR al Conectar SMTP ({current_time}) ---")
        print(f"No se pudo conectar al servidor SMTP en {config.SMTP_SERVER}:{config.SMTP_PORT}.")
        print(f"Error: {e}")
        print("Asegúrate de que el servidor SMTP sea accesible y que el puerto sea correcto.")
        print("--------------------------")
    except smtplib.SMTPAuthenticationError as e:
        print(f"\n--- ERROR de Autenticación SMTP ({current_time}) ---")
        print(f"Las credenciales (usuario/contraseña) no fueron aceptadas para {config.SMTP_USERNAME}.")
        print(f"ASUNTO: {full_subject}")
        print(f"Error: {e}")
        print("Asegúrate de que las credenciales en config.py sean correctas y que la cuenta permita el envío de correos desde aplicaciones.")
        print("--------------------------")
    except smtplib.SMTPException as e:
        print(f"\n--- ERROR SMTP General ({current_time}) ---")
        print(f"Ocurrió un error SMTP inesperado al enviar el email a {', '.join(recipients_list)}.")
        print(f"ASUNTO: {full_subject}")
        print(f"Error: {e}")
        print("Revisa la configuración de tu servidor SMTP y los permisos de la cuenta.")
        print("--------------------------")
    except Exception as e:
        print(f"\n--- ERROR General al Enviar Email de Alarma ({current_time}) ---")
        print(f"No se pudo enviar el email a {', '.join(recipients_list)}.")
        print(f"ASUNTO: {full_subject}")
        print(f"Error: {e}")
        print("--------------------------")
    finally:
        if server:
            try:
                # server.quit() ya se llama en el bloque try si el envío es exitoso.
                # Solo llamar si no se salió aún debido a una excepción antes del quit().
                if not sent_successfully: 
                    server.quit()
            except Exception:
                pass # Ignorar errores al cerrar si ya hubo un problema o si el servidor ya está cerrado

    return sent_successfully
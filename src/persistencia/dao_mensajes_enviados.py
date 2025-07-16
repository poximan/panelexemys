import sqlite3
from .dao_base import get_db_connection, db_lock # Asegúrate de que db_lock esté definido y funcione correctamente

class MensajesEnviadosDAO:
    def insert_sent_message(self, subject: str, body: str, timestamp: str, message_type: str, recipients: str | list[str], success: bool):
        """
        Inserta un registro de un email que se intentó enviar en la tabla 'mensajes_enviados'.
        La columna 'recipient' almacenará todos los destinatarios como una cadena separada por comas.

        Args:
            subject (str): El asunto del email.
            body (str): El cuerpo del mensaje del email.
            timestamp (str): La estampa de tiempo del momento de la inserción (formato YYYY-MM-DD HH:MM:SS).
            message_type (str): Un identificador del tipo de mensaje (ej. 'global_connectivity_alarm', 'individual_grd_alarm_X').
            recipients (str | list[str]): El/los destinatario(s) del email. Se convertirá a una cadena única.
            success (bool): True si el email se envió con éxito, False en caso contrario.
        """
        conn = None
        
        # Convertir la lista de destinatarios en una sola cadena separada por comas
        if isinstance(recipients, list):
            recipients_str = ", ".join(recipients)
        else:
            recipients_str = recipients # Ya es una cadena

        with db_lock:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO mensajes_enviados (subject, body, timestamp, message_type, recipient, success)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (subject, body, timestamp, message_type, recipients_str, 1 if success else 0) # SQLite usa 1 para True, 0 para False
                )
                conn.commit()
                print(f"Registro de email insertado en DB. Asunto: '{subject}'. Destinatario(s): '{recipients_str}'")
            except sqlite3.Error as e:
                print(f"ERROR al insertar registro de email en DB: {e}")
            finally:
                if conn:
                    conn.close()

# Instancia de la clase para usar sus métodos
mensajes_enviados_dao = MensajesEnviadosDAO()
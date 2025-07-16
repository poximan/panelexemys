from datetime import datetime
from typing import Optional

class Logosaurio:
    """
    Un servicio simple para registrar mensajes con una estampa de tiempo.
    Evita registrar mensajes consecutivos que sean idénticos para mantener los logs limpios.
    """
    def __init__(self):
        self._last_message: Optional[str] = None

    def log(self, message: str, origen: str = "ORIG_DESC"):
        """
        Imprime un mensaje formateado con la estampa de tiempo actual,
        solo si es diferente al último mensaje registrado.
        """
        current_message = f"[{origen}] - {message}"
        
        # Comprueba si el mensaje actual es igual al último
        if current_message == self._last_message:
            return  # No hace nada si el mensaje es el mismo

        # Si el mensaje es diferente, lo registra y actualiza la variable
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] - {current_message}")
        self._last_message = current_message
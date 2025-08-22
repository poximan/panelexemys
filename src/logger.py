from datetime import datetime
from typing import Dict, Optional

class Logosaurio:
    """
    Un servicio simple para registrar mensajes con una estampa de tiempo.
    Evita registrar mensajes consecutivos que sean idénticos para cada origen,
    manteniendo los logs limpios y enfocados en los cambios de estado.
    """
    def __init__(self):
        # Almacena el ultimo mensaje registrado para cada origen.
        # La clave es el origen (str) y el valor es el ultimo mensaje (str).
        self._last_messages_by_origin: Dict[str, Optional[str]] = {}

    def log(self, message: str, origen: str = "ORIG_DESC"):
        """
        Imprime un mensaje formateado con la estampa de tiempo actual,
        solo si es diferente al ultimo mensaje registrado para ese origen.

        Args:
            message (str): El mensaje a registrar.
            origen (str): La fuente del mensaje (e.g., "APP", "OBS/TCP", "MODBUS").
        """
        # Obtenemos el ultimo mensaje para el origen actual
        last_message_for_origin = self._last_messages_by_origin.get(origen)
        
        # Comparamos el mensaje actual con el ultimo de su origen
        if message == last_message_for_origin:
            return  # No hace nada si el mensaje es el mismo

        # Si el mensaje es diferente, lo registramos y actualizamos el diccionario
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] - [{origen}] - {message}")
        
        self._last_messages_by_origin[origen] = message
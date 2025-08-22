import json
import os
import time
from .tcp_actividad.method.tcp import tcp
from .tcp_actividad.logs import logs
from src.logger import Logosaurio 

class check_host:
    def __init__(self, logger: Logosaurio):
        self.tcp_class = tcp(logger)
        self.logs_class = logs(logger)

    def check_host_run(self, target: str, max_nodes: int) -> bool:
        """
        Hardcodea los valores y ejecuta el chequeo TCP.
        Devuelve el estado de la conexión.
        """
        return self.tcp_class.tcp_run(target=target, max_nodes=max_nodes)

def start_api_monitor(logger: Logosaurio, host: str, port: int):
    """
    Función que se ejecuta en el hilo para monitorear la conexión.
    """
    while True:
        try:
            check_host_instance = check_host(logger)
            connection_ok = check_host_instance.check_host_run(target=f"{host}:{port}", max_nodes=3)
            
            current_status = "conectado" if connection_ok else "desconectado"

            logger.log(f"Estado de la conexión: {current_status}", origen="TCP/API")
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            observar_file_path = os.path.join(script_dir, 'observar.json')

            try:
                if os.path.exists(observar_file_path):
                    with open(observar_file_path, 'r') as f:
                        content = f.read().strip()
                        data = json.loads(content) if content else {}
                else:
                    data = {}

                data['ip200_estado'] = current_status
                
                with open(observar_file_path, 'w') as f:
                    json.dump(data, f, indent=4)
                    
            except (IOError, json.JSONDecodeError) as e:
                logger.log(f"ERROR al guardar el estado en {observar_file_path}: {e}", origen="TCP/API")

        except Exception as e:
            logger.log(f"Error inesperado en el monitor TCP: {e}", origen="TCP/API")
                
        time.sleep(120)
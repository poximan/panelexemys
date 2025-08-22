import time
from .. import reqapi
from .. import logs
from src.logger import Logosaurio # Importa la clase Logosaurio

class tcp():
    def __init__(self, logger: Logosaurio): # La clase ahora acepta el logger
        self.reqapi_class = reqapi.reqapi(logger)
        self.logs_class = logs.logs(logger)

    def _tcp_get_res(self, request_id: str, timeout: int = 30) -> dict | None:
        stime = time.time()
        while time.time() - stime < timeout:
            tcp_res: dict = self.reqapi_class.reqapi_ch_get_result(request_id)
            self.logs_class.logs_load_process_print()
            if all(tcp_res.get(key) is not None for key in tcp_res.keys()):
                return tcp_res
        return None
    
    def _tcp_get_req(self, target: str, max_nodes: int) -> dict:
        return self.reqapi_class.reqapi_ch_get_request(target, "tcp", max_nodes)

    def tcp_run(self, target: str, max_nodes: int) -> bool:
        """
        Inicia y monitorea el chequeo TCP.
        Devuelve True si al menos un nodo se conecta con éxito, False en caso contrario.
        """
        self.logs_class.logs_console_print("tcp", "info", "runned")
        tcp_req: dict = self._tcp_get_req(target, max_nodes)
        
        if not tcp_req.get("request_id"):
            self.logs_class.logs_console_print("tcp", "info", "no 'tcp' get information, reached api limit")
            return False

        tcp_res: dict = self._tcp_get_res(tcp_req["request_id"])
        
        if not tcp_res:
            self.logs_class.logs_console_print("tcp", "info", "no 'tcp' result information, reached timeout")
            return False
            
        # Verificar si hay al menos un resultado exitoso
        for node, result in tcp_res.items():
            if result and result[0] and result[0].get("time") is not None:
                self.logs_class.logs_console_print("tcp", "info", f"connection successful from {node}")
                return True
        
        self.logs_class.logs_console_print("tcp", "info", "no nodes connected successfully")
        return False
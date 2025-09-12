import json
import requests
from src.logger import Logosaurio # Importa la clase Logosaurio

class reqapi():
    def __init__(self, logger: Logosaurio):
        # Almacena la instancia del logger para usarla en los métodos
        self.logger = logger 

    def reqapi_ia_get_result(self, target: str) -> dict[str, int, float]:
        self.logger.log(f"Consultando ip-api para el objetivo: {target}", origen="REQ/API")
        return json.loads(requests.get(f"http://ip-api.com/json/{target}").text)
    
    def reqapi_ch_post_request(self, target: str) -> str:
        self.logger.log(f"Enviando solicitud POST a check-host para WHOIS: {target}", origen="REQ/API")
        return requests.post("https://check-host.net/ip-info/whois", data={"host": target}).text
    
    def reqapi_ch_get_request(self, target: str, method: str, max_nodes: int) -> dict[str, dict[list[str]]]:
        self.logger.log(f"Obteniendo solicitud para {method} en {target} con {max_nodes} nodos.", origen="REQ/API")
        return json.loads(requests.get(f"https://check-host.net/check-{method}?host={target}&max_nodes={max_nodes}",
                                        headers={"Accept": "application/json"}).text)

    def reqapi_ch_get_result(self, request_id: int) -> dict:
        self.logger.log(f"Obteniendo resultados de check-host con ID: {request_id}", origen="REQ/API")
        return json.loads(requests.get(f"https://check-host.net/check-result/{request_id}").text)
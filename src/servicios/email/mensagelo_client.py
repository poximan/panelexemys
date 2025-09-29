import json
import time
from typing import List, Optional, Tuple
import requests
import config

class MensageloError(Exception):
    pass

class MensageloClient:
    """
    Cliente HTTP minimal para el microservicio mensagelo.
    Solo usa la API asincronica (/send_async) para encolar envios.
    El exito se define como "pedido tomado" (HTTP 202 y ok=true, queued=true).
    """

    def __init__(self,
                 base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 timeout_seconds: Optional[int] = None,
                 max_retries: Optional[int] = None,
                 backoff_initial: Optional[float] = None,
                 backoff_max: Optional[float] = None):
        self.base_url = (base_url or config.MENSAGELO_BASE_URL).rstrip("/")
        self.api_key = api_key or config.MENSAGELO_API_KEY
        self.timeout = timeout_seconds or int(config.MENSAGELO_TIMEOUT_SECONDS)
        self.max_retries = max_retries if max_retries is not None else int(config.MENSAGELO_MAX_RETRIES)
        self.backoff_initial = backoff_initial if backoff_initial is not None else float(config.MENSAGELO_BACKOFF_INITIAL)
        self.backoff_max = backoff_max if backoff_max is not None else float(config.MENSAGELO_BACKOFF_MAX)

        self._send_async_url = f"{self.base_url}/send_async"
        self._headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }

    def enqueue_email(self,
                      recipients: List[str],
                      subject: str,
                      body: str,
                      message_type: Optional[str] = None) -> Tuple[bool, str]:
        """
        Envia un POST a /send_async. Retorna (ok, msg).
        ok=True si el servicio acepto el encolado (HTTP 202 y {"ok":true,"queued":true}).
        No espera a que el email sea efectivamente entregado por SMTP.
        Implementa reintento con backoff exponencial simple.
        """
        payload = {
            "recipients": recipients,
            "subject": subject,
            "body": body,
            "message_type": message_type,
        }

        attempt = 0
        backoff = self.backoff_initial

        while True:
            attempt += 1
            try:
                resp = requests.post(
                    self._send_async_url,
                    headers=self._headers,
                    data=json.dumps(payload, ensure_ascii=False),
                    timeout=self.timeout,
                )
            except requests.RequestException as e:
                # fallo de red o timeout
                if attempt <= self.max_retries:
                    time.sleep(min(backoff, self.backoff_max))
                    backoff = min(backoff * 2.0, self.backoff_max)
                    continue
                return False, f"error de red o timeout tras {attempt} intentos: {e}"

            # HTTP recibido
            if resp.status_code == 202:
                # esperado: {"ok":true, "queued":true, "message":"..."}
                try:
                    data = resp.json()
                except ValueError:
                    return False, "respuesta 202 sin JSON valido"
                ok = bool(data.get("ok")) and bool(data.get("queued"))
                msg = str(data.get("message", ""))
                return ok, msg or "pedido aceptado"
            elif resp.status_code in (401, 403):
                return False, "no autorizado: ver API key"
            elif resp.status_code in (429, 503):
                # sobrecarga/cola llena: reintentar con backoff
                if attempt <= self.max_retries:
                    time.sleep(min(backoff, self.backoff_max))
                    backoff = min(backoff * 2.0, self.backoff_max)
                    continue
                try:
                    err = resp.json().get("detail", "")
                except Exception:
                    err = resp.text
                return False, f"servicio saturado: {err}"
            else:
                # otros codigos: no reintentar salvo que quieras ser mas agresivo
                try:
                    err = resp.json()
                except Exception:
                    err = resp.text
                return False, f"error http {resp.status_code}: {err}"
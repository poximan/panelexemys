import time
import subprocess
import platform
from typing import Literal, Dict, Optional

import requests

from src.utils.paths import update_observar_key
from src.logger import Logosaurio
import config

Estado = Literal["conectado", "desconectado", "desconocido"]


def _mensagelo_smtp_check(logger: Logosaurio) -> Estado:
    """
    Consulta a mensagelo el endpoint /smtppostserv para validar el SMTP real
    (por ejemplo post.servicoop.com) sin hacer NOOP directo desde este proceso.

    Respuestas:
      - "conectado" si status=http200 y body.status=="ok"
      - "desconectado" si status no 200 o body.status!="ok"
      - "desconocido" si faltan parametros de config
    """
    base_url: Optional[str] = getattr(config, "MENSAGELO_BASE_URL", None)
    api_key: Optional[str] = getattr(config, "MENSAGELO_API_KEY", None)
    timeout: int = int(getattr(config, "MENSAGELO_TIMEOUT_SECONDS", 5))

    if not base_url or not api_key:
        return "desconocido"

    url = f"{base_url.rstrip('/')}/smtppostserv"
    headers = {"X-API-Key": api_key}

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            try:
                data = resp.json() or {}
            except Exception:
                data = {}
            return "conectado" if str(data.get("status", "")).lower() == "ok" else "desconectado"
        else:
            # servicio responde pero indica problema
            return "desconectado"
    except requests.Timeout:
        try:
            logger.log("mensagelo /smtppostserv timeout", origen="EMAIL/CHK")
        except Exception:
            pass
        return "desconectado"
    except Exception as e:
        try:
            logger.log(f"mensagelo /smtppostserv excepcion: {e}", origen="EMAIL/CHK")
        except Exception:
            pass
        return "desconocido"


def _ping_host(host: str, logger: Logosaurio) -> Estado:
    """
    Ejecuta un ping con un intento y timeout corto a nivel SO.
    Controla el tiempo total del subproceso para evitar bloqueos.
    """
    if not host:
        return "desconocido"

    system = platform.system().lower()
    if "windows" in system:
        cmd = ["ping", "-n", "1", "-w", "2000", host]
    else:
        cmd = ["ping", "-c", "1", "-W", "2", host]

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
        return "conectado" if res.returncode == 0 else "desconectado"
    except subprocess.TimeoutExpired:
        try:
            logger.log(f"Ping {host} timeout", origen="EMAIL/CHK")
        except Exception:
            pass
        return "desconectado"
    except Exception as e:
        try:
            logger.log(f"Ping {host} excepcion: {e}", origen="EMAIL/CHK")
        except Exception:
            pass
        return "desconocido"


def _build_status(logger: Logosaurio) -> Dict[str, Estado]:
    """
    Calcula los tres estados y retorna el diccionario a persistir.
    smtp: estado del SMTP verificado via mensagelo /smtppostserv
    ping_local: ping a dominio local
    ping_remoto: ping al host SMTP (post.servicoop.com)
    """
    estado_smtp = _mensagelo_smtp_check(logger)
    estado_ping_local = _ping_host("servicoop.com.ar", logger)
    estado_ping_remoto = _ping_host("post.servicoop.com", logger)

    return {
        "smtp": estado_smtp,
        "ping_local": estado_ping_local,
        "ping_remoto": estado_ping_remoto,
    }


def start_email_health_monitor(logger: Logosaurio) -> None:
    """
    Bucle de monitoreo cada 300 s. Actualiza observar.json -> server_email_estado
    con subclaves smtp, ping_local y ping_remoto.
    """
    while True:
        try:
            estados = _build_status(logger)
            update_observar_key("server_email_estado", estados)
            try:
                logger.log(f"server_email_estado: {estados}", origen="EMAIL/CHK")
            except Exception:
                pass
        except Exception as e:
            try:
                logger.log(f"persistencia observar.json error: {e}", origen="EMAIL/CHK")
            except Exception:
                pass
        finally:
            time.sleep(300)
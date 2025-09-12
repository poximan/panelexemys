import time
import smtplib
import socket
import subprocess
import platform
from typing import Literal, Dict

from src.utils.paths import update_observar_key
from src.logger import Logosaurio
import config

Estado = Literal["conectado", "desconectado", "desconocido"]


def _smtp_noop_check(logger: Logosaurio) -> Estado:
    """
    Ejecuta una verificacion SMTP: EHLO, STARTTLS si corresponde, login si hay credenciales y NOOP.
    Retorna el estado estandarizado.
    """
    host = getattr(config, "SMTP_SERVER", None)
    port = int(getattr(config, "SMTP_PORT", 587))
    username = getattr(config, "SMTP_USERNAME", None)
    password = getattr(config, "SMTP_PASSWORD", None)
    use_tls = bool(getattr(config, "SMTP_USE_TLS", True))
    timeout = int(getattr(config, "SMTP_TIMEOUT_SECONDS", 30))

    if not host or not port:
        return "desconocido"

    try:
        if use_tls:
            client = smtplib.SMTP(host, port, timeout=timeout)
            client.ehlo()
            client.starttls()
            client.ehlo()
        else:
            client = smtplib.SMTP_SSL(host, port, timeout=timeout)

        if username:
            client.login(username, password or "")

        code, _ = client.noop()
        try:
            client.quit()
        except Exception:
            pass

        return "conectado" if 200 <= code < 400 else "desconectado"
    except (smtplib.SMTPException, OSError, socket.error) as e:
        try:
            logger.log(f"SMTP NOOP error: {e}", origen="EMAIL/CHK")
        except Exception:
            pass
        return "desconectado"
    except Exception as e:
        try:
            logger.log(f"SMTP NOOP excepcion: {e}", origen="EMAIL/CHK")
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
        # -n 1: un eco, -w 2000: timeout 2000 ms por eco
        cmd = ["ping", "-n", "1", "-w", "2000", host]
    else:
        # -c 1: un eco, -W 2: timeout 2 s por eco
        cmd = ["ping", "-c", "1", "-W", "2", host]

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,  # corta bloqueos del proceso ping o de resolucion
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
    """
    estado_smtp = _smtp_noop_check(logger)
    estado_ping_local = _ping_host("servicoop.com", logger)
    estado_ping_remoto = _ping_host("mail.servicoop.com", logger)

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
            # garantiza el periodo aunque haya fallos en la iteracion
            time.sleep(300)
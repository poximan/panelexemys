# Event bus publish-only limitado a los topicos consumidos por el cliente movil.
# - exemys/estado/grado          (retain): resumen global
# - exemys/estado/grds           (retain): detalle de desconectados
# - exemys/estado/conexion_modem (retain): estado del modem
# - exemys/estado/email          (retain): salud del servidor de correo
# - exemys/estado/proxmox      (retain): snapshot de Proxmox
# - exemys/eventos/email         (no retain): eventos individuales de envio

import json
from datetime import datetime
from typing import Any, Iterable, Optional, List, Dict
import config
from src.persistencia.dao.dao_historicos import historicos_dao

_manager = None  # instancia de MqttClientManager

def set_manager(manager) -> None:
    global _manager
    _manager = manager

def _safe_publish(topic: str, payload: Any, qos: int, retain: bool) -> None:
    if _manager is None:
        return
    try:
        _manager.publish(topic, payload, qos=qos, retain=retain)
    except Exception:
        pass

def _format_grd_items(rows: Iterable[dict]) -> List[Dict[str, Any]]:
    items = []
    for row in rows:
        last_ts = row.get("last_disconnected_timestamp")
        iso_ts = last_ts.strftime("%Y-%m-%dT%H:%M:%S") if last_ts else None
        items.append(
            {
                "id": int(row.get("id_grd", 0)),
                "nombre": row.get("description") or "",
                "ultima_caida": iso_ts or "",
            }
        )
    return items

def _build_grds_snapshot(ts: Optional[str] = None, items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    timestamp = ts or datetime.now().isoformat(timespec="seconds")
    payload_items = items if items is not None else _format_grd_items(historicos_dao.get_all_disconnected_grds())
    return {"items": payload_items, "ts": timestamp}

# ---------------- estados (retain=True) ----------------

def publish_exemys_grd_change(
    grd_id: Optional[int] = None,
    value: Optional[int] = None,
    ts: Optional[str] = None,
    snapshot: Optional[dict] = None,
) -> None:
    """
    Publica el snapshot completo de GRDs desconectados utilizando el esquema
    esperado por la app movil. Los argumentos quedan opcionales para
    compatibilidad retro (se prioriza 'snapshot' si se provee).
    """
    payload = snapshot if snapshot is not None else _build_grds_snapshot(ts=ts)
    _safe_publish(
        config.MQTT_TOPIC_GRDS,
        json.dumps(payload, ensure_ascii=False),
        qos=config.MQTT_PUBLISH_QOS_STATE,
        retain=config.MQTT_PUBLISH_RETAIN_STATE,
    )

def publish_exemys_global_summary(porcentaje: float, total: int, conectados: int) -> None:
    """
    Resumen global de conectividad (mismo topico).
    payload: {"type":"global","porcentaje":..,"total":..,"conectados":..}
    """
    obj = {"type": "global", "porcentaje": round(float(porcentaje), 2), "total": int(total), "conectados": int(conectados)}
    _safe_publish(
        config.MQTT_TOPIC_GRADO,
        json.dumps(obj, ensure_ascii=False),
        qos=config.MQTT_PUBLISH_QOS_STATE,
        retain=config.MQTT_PUBLISH_RETAIN_STATE,
    )

def publish_sensor_modem_state(estado: str) -> None:
    """
    Estado del modem/routeo (retain).
    payload: {"type":"modem","estado":"conectado"|"desconectado"}
    """
    obj = {"type": "modem", "estado": str(estado)}
    _safe_publish(
        config.MQTT_TOPIC_MODEM_CONEXION,
        json.dumps(obj, ensure_ascii=False),
        qos=config.MQTT_PUBLISH_QOS_STATE,
        retain=config.MQTT_PUBLISH_RETAIN_STATE,
    )

def publish_email_state(payload: dict) -> None:
    """
    Publica el estado agregado del servidor de correo (retain).
    payload: {"smtp":"conectado","ping_local":"conectado","ping_remoto":"desconectado","ts":"..."}
    """
    _safe_publish(
        config.MQTT_TOPIC_EMAIL_ESTADO,
        json.dumps(payload, ensure_ascii=False),
        qos=config.MQTT_PUBLISH_QOS_STATE,
        retain=config.MQTT_PUBLISH_RETAIN_STATE,
    )

def publish_proxmox_state(payload: dict) -> None:
    """
    Publica el snapshot de estado de Proxmox (retain).
    payload: {"ts":"...","status":"online|offline","node":"...","vms":[...],"missing":[...],"error":str|None}
    """
    _safe_publish(
        getattr(config, "MQTT_TOPIC_PROXMOX_ESTADO", "exemys/estado/proxmox"),
        json.dumps(payload, ensure_ascii=False),
        qos=config.MQTT_PUBLISH_QOS_STATE,
        retain=config.MQTT_PUBLISH_RETAIN_STATE,
    )

# ---------------- eventos (retain=False) ----------------

def publish_email_event(subject: str, ok: bool) -> None:
    """
    Evento de envio de email/alarma (no retain).
    payload: {"type":"email","subject":"...","ok":true|false,"ts":"..."}
    """
    obj = {
        "type": "email",
        "subject": subject,
        "ok": bool(ok),
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    _safe_publish(
        config.MQTT_TOPIC_EMAIL_EVENT,
        json.dumps(obj, ensure_ascii=False),
        qos=config.MQTT_PUBLISH_QOS_EVENT,
        retain=config.MQTT_PUBLISH_RETAIN_EVENT,
    )

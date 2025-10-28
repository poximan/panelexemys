"""
Monitor de salud de VMs Proxmox (PVE).

Replica la logica del script PowerShell `salud.ps1` pero en Python nativo,
consultando la API REST de Proxmox y persistiendo los resultados en
`observar.json` para que el frontend los consuma.
"""

from __future__ import annotations

import time
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

import requests
import urllib3

from src.logger import Logosaurio
from src.utils.paths import update_observar_key
from src.servicios.pve import proxmox_history
from src.servicios.mqtt import mqtt_event_bus
import config

# La API de laboratorio usa certificados self-signed.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _as_token_header(raw_token: str) -> str:
    """
    Normaliza el valor configurado para el header Authorization.
    Permite configurar tanto "PVEAPIToken=user@realm!tokenid=secret"
    como solo "user@realm!tokenid=secret".
    """
    token = (raw_token or "").strip()
    if not token:
        return ""
    if token.lower().startswith("pveapitoken"):
        return token
    return f"PVEAPIToken={token}"


def _uptime_human(seconds: int) -> str:
    """
    Devuelve una representacion amigable (Xd Yh Zm) del uptime en segundos.
    """
    if seconds <= 0:
        return "0m"
    days, remainder = divmod(seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, _ = divmod(remainder, 60)
    parts: List[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _gb(value_bytes: float) -> float:
    """
    Convierte bytes a GB con un decimal.
    """
    if not value_bytes:
        return 0.0
    return round(value_bytes / (1024 ** 3), 1)


def _fetch_qemu_data(base_url: str, node: str, headers: Dict[str, str], timeout: int, verify_ssl: bool) -> List[Dict[str, Any]]:
    """
    Consulta la API de Proxmox y retorna la lista de VMs QEMU del nodo indicado.
    """
    if not base_url or not node:
        raise ValueError("Configuracion de Proxmox incompleta (URL o nodo vacios)")

    url = f"{base_url.rstrip('/')}/nodes/{node}/qemu"
    response = requests.get(url, headers=headers, timeout=timeout, verify=verify_ssl)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("Respuesta inesperada de Proxmox: falta la clave 'data'")
    return data


def _safe_pct(used: float, total: float) -> float | None:
    """
    Calcula porcentaje usado (0-100) si hay denominador.
    """
    if not total:
        return None
    try:
        return round((used / total) * 100.0, 2)
    except Exception:
        return None


def _fetch_vm_status(
    base_url: str,
    node: str,
    vmid: int,
    headers: Dict[str, str],
    timeout: int,
    verify_ssl: bool,
) -> Dict[str, Any]:
    """
    Obtiene informacion detallada de una VM individual (status/current).
    """
    url = f"{base_url.rstrip('/')}/nodes/{node}/qemu/{vmid}/status/current"
    response = requests.get(url, headers=headers, timeout=timeout, verify=verify_ssl)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise ValueError(f"Respuesta inesperada para status/current VM {vmid}")
    return data


def _build_snapshot(
    qemu_list: Iterable[Dict[str, Any]],
    vm_ids: Iterable[int],
    base_url: str,
    node: str,
    headers: Dict[str, str],
    timeout: int,
    verify_ssl: bool,
    logger: Logosaurio,
    prev_counters: Dict[int, Tuple[float, float]],
    poll_interval_seconds: int,
) -> Tuple[List[Dict[str, Any]], List[int], Dict[int, Tuple[float, float]]]:
    """
    Filtra la lista de VMs obtenidas quedandose solo con los VMIDs solicitados.
    Ademas calcula los VMIDs faltantes.
    """
    vm_by_id = {int(item.get("vmid")): item for item in qemu_list if "vmid" in item}
    snapshot: List[Dict[str, Any]] = []
    missing: List[int] = []
    updated_counters: Dict[int, Tuple[float, float]] = {}

    for vmid in vm_ids:
        raw = vm_by_id.get(int(vmid))
        if not raw:
            missing.append(int(vmid))
            continue

        mem_used_raw = float(raw.get("mem") or 0.0)
        mem_max_raw = float(raw.get("maxmem") or 0.0)
        uptime_seconds = int(raw.get("uptime") or 0)

        raw_disk_used = float(raw.get("disk") or 0.0)
        raw_disk_total = float(raw.get("maxdisk") or 0.0)
        raw_disk_read = float(raw.get("diskread") or 0.0)
        raw_disk_write = float(raw.get("diskwrite") or 0.0)
        disk_error: str | None = None
        status_data: Dict[str, Any] | None = None
        try:
            status_data = _fetch_vm_status(
                base_url=base_url,
                node=node,
                vmid=int(vmid),
                headers=headers,
                timeout=timeout,
                verify_ssl=verify_ssl,
            )
        except Exception as exc:
            disk_error = str(exc)
            try:
                logger.log(f"No se pudo obtener status/disk de VM {vmid}: {exc}", origen="PVE/MON")
            except Exception:
                pass

        if isinstance(status_data, dict):
            raw_disk_used = float(status_data.get("disk") or raw_disk_used or 0.0)
            raw_disk_total = float(status_data.get("maxdisk") or raw_disk_total or 0.0)
            raw_disk_read = float(status_data.get("diskread") or raw_disk_read or 0.0)
            raw_disk_write = float(status_data.get("diskwrite") or raw_disk_write or 0.0)

        prev_read, prev_write = prev_counters.get(int(vmid), (raw_disk_read, raw_disk_write))
        delta_read = max(0.0, raw_disk_read - prev_read)
        delta_write = max(0.0, raw_disk_write - prev_write)
        interval = max(1, poll_interval_seconds)
        read_rate_bps = delta_read / interval
        write_rate_bps = delta_write / interval

        disk_used_gb = _gb(raw_disk_used)
        disk_total_gb = _gb(raw_disk_total)
        disk_usage_pct = _safe_pct(raw_disk_used, raw_disk_total)

        updated_counters[int(vmid)] = (raw_disk_read, raw_disk_write)

        snapshot.append(
            {
                "vmid": int(raw.get("vmid")),
                "name": raw.get("name") or f"VM-{vmid}",
                "status": raw.get("status") or "desconocido",
                "cpus": int(raw.get("cpus") or 0),
                "cpu_usage_pct": round(float(raw.get("cpu") or 0.0) * 100.0, 2),
                "mem_used_gb": _gb(mem_used_raw),
                "mem_total_gb": _gb(mem_max_raw),
                "mem_usage_pct": _safe_pct(mem_used_raw, mem_max_raw),
                "uptime_seconds": uptime_seconds,
                "uptime_human": _uptime_human(uptime_seconds),
                "disk_used_gb": disk_used_gb,
                "disk_total_gb": disk_total_gb,
                "disk_usage_pct": disk_usage_pct,
                "disk_read_bytes": raw_disk_read,
                "disk_write_bytes": raw_disk_write,
                "disk_read_rate_bps": read_rate_bps,
                "disk_write_rate_bps": write_rate_bps,
                "status_detail_error": disk_error,
            }
        )

    snapshot.sort(key=lambda item: item["vmid"])
    missing.sort()
    return snapshot, missing, updated_counters


def _collect_status(logger: Logosaurio, prev_counters: Dict[int, Tuple[float, float]], poll_interval_seconds: int) -> Tuple[Dict[str, Any], Dict[int, Tuple[float, float]]]:
    """
    Obtiene y arma el snapshot actual de Proxmox.
    """
    raw_token = getattr(config, "PVE_API_TOKEN", "")
    headers = {}
    token_header = _as_token_header(raw_token)
    if token_header:
        headers["Authorization"] = token_header

    timeout = int(getattr(config, "PVE_HTTP_TIMEOUT_SECONDS", 8))
    verify_ssl = bool(getattr(config, "PVE_VERIFY_SSL", False))
    base_url = getattr(config, "PVE_BASE_URL", "")
    node = getattr(config, "PVE_NODE_NAME", "")
    vm_ids = list(getattr(config, "PVE_VHOST_IDS", [101, 102])) or []

    qemu_list = _fetch_qemu_data(base_url, node, headers, timeout, verify_ssl)
    vms, missing, updated_counters = _build_snapshot(
        qemu_list=qemu_list,
        vm_ids=vm_ids,
        base_url=base_url,
        node=node,
        headers=headers,
        timeout=timeout,
        verify_ssl=verify_ssl,
        logger=logger,
        prev_counters=prev_counters,
        poll_interval_seconds=poll_interval_seconds,
    )

    snapshot = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "vms": vms,
        "missing": missing,
        "error": None,
    }
    if missing:
        logger.log(f"PVE faltantes en respuesta: {missing}", origen="PVE/MON")
    return snapshot, updated_counters


def _build_mqtt_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convierte el snapshot interno en el payload JSON publicado por MQTT.
    """
    node_name = getattr(config, "PVE_NODE_NAME", "")
    status = "offline" if snapshot.get("error") else "online"
    payload = {
        "ts": snapshot.get("ts"),
        "node": node_name,
        "status": status,
        "error": snapshot.get("error"),
        "missing": list(snapshot.get("missing") or []),
        "vms": [],
    }

    for item in snapshot.get("vms") or []:
        try:
            vmid = int(item.get("vmid"))
        except Exception:
            vmid = int(item.get("vmid") or 0)

        name = item.get("name") or f"VM {vmid}"
        status_raw = str(item.get("status") or "desconocido")
        cpus = int(item.get("cpus") or 0)
        cpu_pct = float(item.get("cpu_usage_pct") or 0.0)
        mem_used = float(item.get("mem_used_gb") or 0.0)
        mem_total = float(item.get("mem_total_gb") or 0.0)
        mem_pct_raw = item.get("mem_usage_pct")
        mem_pct = float(mem_pct_raw) if mem_pct_raw is not None else None
        disk_used = float(item.get("disk_used_gb") or 0.0)
        disk_total = float(item.get("disk_total_gb") or 0.0)
        disk_read_bytes = float(item.get("disk_read_bytes") or 0.0)
        disk_write_bytes = float(item.get("disk_write_bytes") or 0.0)
        disk_read_rate = float(item.get("disk_read_rate_bps") or 0.0)
        disk_write_rate = float(item.get("disk_write_rate_bps") or 0.0)
        disk_pct_raw = item.get("disk_usage_pct")
        disk_pct = float(disk_pct_raw) if disk_pct_raw is not None else None

        if mem_pct is None and mem_total > 0:
            mem_pct = (mem_used / mem_total) * 100.0
        if disk_pct is None and disk_total > 0:
            disk_pct = (disk_used / disk_total) * 100.0

        payload["vms"].append(
            {
                "vmid": vmid,
                "name": name,
                "status": status_raw,
                "status_display": status_raw.upper(),
                "cpus": cpus,
                "cpu_pct": round(cpu_pct, 2),
                "mem_used_gb": round(mem_used, 2),
                "mem_total_gb": round(mem_total, 2),
                "mem_pct": round(mem_pct, 2) if mem_pct is not None else None,
                "disk_used_gb": round(disk_used, 2),
                "disk_total_gb": round(disk_total, 2),
                "disk_pct": round(disk_pct, 2) if disk_pct is not None else None,
                "disk_read_bytes": round(disk_read_bytes, 2),
                "disk_write_bytes": round(disk_write_bytes, 2),
                "disk_read_rate_bps": round(disk_read_rate, 2),
                "disk_write_rate_bps": round(disk_write_rate, 2),
                "uptime_human": item.get("uptime_human") or "0m",
            }
        )

    return payload


def start_proxmox_monitor(logger: Logosaurio) -> None:
    """
    Hilo de monitoreo principal. Actualiza observar.json en cada iteracion.
    """
    interval = int(getattr(config, "PVE_POLL_INTERVAL_SECONDS", 20))
    if interval < 5:
        interval = 5

    history_hours = int(getattr(config, "PVE_HISTORY_HOURS", 72) or 72)
    poll_seconds = interval
    publish_factor = max(1, int(getattr(config, "PVE_MQTT_PUBLISH_FACTOR", 5) or 5))
    publish_interval_seconds = max(1, publish_factor * poll_seconds)
    last_ts: str | None = None
    last_publish_monotonic = 0.0
    last_published_payload: Dict[str, Any] | None = None
    last_disk_counters: Dict[int, Tuple[float, float]] = {}

    while True:
        try:
            snapshot, last_disk_counters = _collect_status(
                logger,
                last_disk_counters,
                poll_seconds,
            )
            proxmox_history.update_history(snapshot, poll_seconds=poll_seconds, hours=history_hours)
        except Exception as exc:  # pragma: no cover - monitoreo defensivo
            snapshot = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "vms": [],
                "missing": list(getattr(config, "PVE_VHOST_IDS", [101, 102])),
                "error": str(exc),
            }
            try:
                logger.log(f"ERROR consultando Proxmox: {exc}", origen="PVE/MON")
            except Exception:
                pass
        else:
            snapshot.setdefault("error", None)

        payload = _build_mqtt_payload(snapshot)
        now_monotonic = time.monotonic()
        previous_payload = last_published_payload or {}
        elapsed = now_monotonic - last_publish_monotonic

        should_publish = False
        if last_publish_monotonic == 0.0:
            should_publish = True
        elif payload.get("status") != previous_payload.get("status"):
            should_publish = True
        elif elapsed >= publish_interval_seconds:
            should_publish = True

        if should_publish:
            try:
                mqtt_event_bus.publish_proxmox_state(payload)
            except Exception:
                pass
            else:
                last_publish_monotonic = now_monotonic
                last_published_payload = deepcopy(payload)

        if not update_observar_key("proxmox_estado", snapshot):
            try:
                logger.log("No se pudo persistir proxmox_estado en observar.json", origen="PVE/MON")
            except Exception:
                pass

        current_ts = snapshot.get("ts")
        if current_ts != last_ts:
            try:
                resumen = f"ts={current_ts} vms={len(snapshot.get('vms', []))}"
                logger.log(f"Snapshot Proxmox actualizado ({resumen})", origen="PVE/MON")
            except Exception:
                pass
            last_ts = current_ts

        time.sleep(interval)


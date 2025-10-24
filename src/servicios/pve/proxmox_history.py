from __future__ import annotations

import json
import math
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Tuple

import config
from src.utils import paths


_HISTORY_LOCK = threading.RLock()


def _get_history_path() -> str:
    """
    Devuelve la ruta absoluta al archivo de historia.
    """
    base_dir = paths.get_data_dir()
    os.makedirs(base_dir, exist_ok=True)
    filename = getattr(config, "PVE_HISTORY_FILENAME", "proxmox_history.json")
    return os.path.join(base_dir, filename)


def _read_history() -> Dict[str, Any]:
    """
    Lee el archivo de historia (si existe) y devuelve el dict.
    """
    history_path = _get_history_path()
    if not os.path.exists(history_path):
        return {"meta": {}, "vms": {}}
    try:
        with open(history_path, "r", encoding="utf-8") as fh:
            content = fh.read().strip()
            if not content:
                return {"meta": {}, "vms": {}}
            return json.loads(content)
    except Exception:
        return {"meta": {}, "vms": {}}


def _write_history(data: Dict[str, Any]) -> None:
    """
    Persiste el dict en disco de forma atomica.
    """
    history_path = _get_history_path()
    tmp_path = f"{history_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp_path, history_path)


def calculate_max_entries(hours: int, poll_seconds: int) -> int:
    """
    Calcula la cantidad maxima de muestras que entran en la ventana de historia.
    """
    hrs = max(1, int(hours or 1))
    poll = max(1, int(poll_seconds or 1))
    return int(math.ceil((hrs * 3600) / poll))


def _prepare_entry(snapshot_ts: str, vm: Dict[str, Any]) -> Dict[str, float]:
    """
    Arma la entrada historica para una VM puntual.
    """
    cpu = float(vm.get("cpu_usage_pct") or 0.0)
    mem = float(vm.get("mem_usage_pct") or 0.0)
    disk_raw = vm.get("disk_usage_pct")
    disk = float(disk_raw) if disk_raw is not None else 0.0
    return {
        "ts": snapshot_ts,
        "cpu": round(cpu, 2),
        "mem": round(mem, 2),
        "disk": round(disk, 2),
    }


def update_history(snapshot: Dict[str, Any], poll_seconds: int, hours: int) -> Tuple[Dict[str, Any], int]:
    """
    Actualiza el archivo historico con el ultimo snapshot.

    Retorna el dict actualizado y el maximo de entradas utilizado.
    """
    snapshot_ts = snapshot.get("ts")
    if not snapshot_ts:
        snapshot_ts = datetime.now().isoformat(timespec="seconds")

    max_entries = calculate_max_entries(hours, poll_seconds)

    with _HISTORY_LOCK:
        history = _read_history()
        history.setdefault("meta", {})
        history.setdefault("vms", {})
        history["meta"].update(
            {
                "hours": hours,
                "poll_seconds": poll_seconds,
                "max_entries": max_entries,
            }
        )

        vms_section = history["vms"]
        for vm in snapshot.get("vms", []):
            try:
                vmid = str(int(vm.get("vmid")))
            except Exception:
                continue

            entry = _prepare_entry(snapshot_ts, vm)
            vm_record = vms_section.setdefault(
                vmid, {"name": vm.get("name") or vmid, "history": []}
            )
            vm_record["name"] = vm.get("name") or vm_record.get("name") or vmid
            history_list: List[Dict[str, Any]] = vm_record.get("history") or []
            history_list.insert(0, entry)
            if len(history_list) > max_entries:
                history_list = history_list[:max_entries]
            vm_record["history"] = history_list

        _write_history(history)
        return history, max_entries


def load_history_for_dashboard() -> Tuple[Dict[int, Dict[str, Any]], Dict[str, Any]]:
    """
    Carga la historia y la prepara para el dashboard (claves enteras, listas FIFO).
    """
    with _HISTORY_LOCK:
        history = _read_history()

    result: Dict[int, Dict[str, Any]] = {}
    vms_section = history.get("vms", {})
    for vmid_str, data in vms_section.items():
        try:
            vmid = int(vmid_str)
        except Exception:
            continue
        entries = data.get("history") or []
        prepared = {
            "cpu_pct": [],
            "mem_pct": [],
            "disk_pct": [],
        }
        for item in reversed(entries):
            ts = item.get("ts")
            if not ts:
                continue
            prepared["cpu_pct"].append({"ts": ts, "value": item.get("cpu", 0.0)})
            prepared["mem_pct"].append({"ts": ts, "value": item.get("mem", 0.0)})
            prepared["disk_pct"].append({"ts": ts, "value": item.get("disk", 0.0)})
        result[vmid] = {
            "name": data.get("name"),
            "history": prepared,
        }

    return result, history.get("meta", {})

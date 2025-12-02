from datetime import timedelta
from typing import Any, Dict, List

from src.logger import Logosaurio
from src.utils import timebox
import config


class NotifProxmoxHost:
    """
    Supervisa la disponibilidad del hipervisor Proxmox.
    """

    def __init__(self, logger: Logosaurio):
        self.logger = logger
        self.state: Dict[str, Any] = {
            "start_time": None,
            "triggered": False,
            "last_error": "",
        }

    def evaluate_condition(self, snapshot: Dict[str, Any]) -> bool:
        """
        Retorna True si debe dispararse la alarma de hipervisor no disponible.
        """
        error_text = ""
        if isinstance(snapshot, dict):
            raw_error = snapshot.get("error")
            if raw_error:
                error_text = str(raw_error)

        offline = bool(error_text)
        now = timebox.utc_now()
        min_duration = timedelta(minutes=config.ALARM_MIN_SUSTAINED_DURATION_MINUTES)

        if offline:
            if self.state["start_time"] is None:
                self.state["start_time"] = now
                self.state["last_error"] = error_text
                self.logger.log(
                    f"Alarma potencial: hipervisor Proxmox inalcanzable. Motivo: {error_text}",
                    origen="NOTIF/PVE_HOST",
                )
            else:
                self.state["last_error"] = error_text or self.state.get("last_error", "")

            if not self.state["triggered"] and now - self.state["start_time"] >= min_duration:
                self.state["triggered"] = True
                return True
        else:
            if self.state["start_time"] is not None:
                self.logger.log("Alarma de hipervisor Proxmox resuelta.", origen="NOTIF/PVE_HOST")
            self.state = {"start_time": None, "triggered": False, "last_error": ""}

        return False

    def get_last_error(self) -> str:
        return self.state.get("last_error") or ""


class NotifProxmoxVm:
    """
    Supervisa el estado individual de las VMs de Proxmox configuradas.
    """

    def __init__(self, logger: Logosaurio):
        self.logger = logger
        self.vm_states: Dict[int, Dict[str, Any]] = {}

    def evaluate_condition(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Retorna una lista de VMs que deben disparar alarma.
        """
        if not isinstance(snapshot, dict):
            return []

        if snapshot.get("error"):
            # Cuando el hipervisor esta caido, se delega la alarma al monitor global.
            return []

        configured_ids = [int(vmid) for vmid in getattr(config, "PVE_VHOST_IDS", [])]
        vm_map: Dict[int, Dict[str, Any]] = {}
        for item in snapshot.get("vms", []) or []:
            try:
                vmid = int(item.get("vmid"))
            except Exception:
                continue
            vm_map[vmid] = item

        alerts: List[Dict[str, Any]] = []
        now = timebox.utc_now()
        min_duration = timedelta(minutes=config.ALARM_MIN_SUSTAINED_DURATION_MINUTES)

        for vmid in configured_ids:
            vm_info = vm_map.get(vmid)
            if vm_info:
                status_raw = str(vm_info.get("status", "desconocido")).lower()
                name = vm_info.get("name") or f"VM {vmid}"
            else:
                status_raw = "sin datos"
                name = f"VM {vmid}"

            is_running = status_raw == "running"
            state = self.vm_states.setdefault(
                vmid,
                {
                    "start_time": None,
                    "triggered": False,
                    "name": name,
                    "status": status_raw,
                },
            )
            state["name"] = name
            state["status"] = status_raw

            if not is_running:
                if state["start_time"] is None:
                    state["start_time"] = now
                    self.logger.log(
                        f"Alarma potencial: VM {vmid} ({name}) en estado '{status_raw}'. Iniciando conteo.",
                        origen="NOTIF/PVE_VM",
                    )

                if not state["triggered"] and now - state["start_time"] >= min_duration:
                    state["triggered"] = True
                    alerts.append(
                        {
                            "vmid": vmid,
                            "name": name,
                            "status": status_raw,
                            "status_display": status_raw.upper(),
                        }
                    )
            else:
                if state["start_time"] is not None:
                    self.logger.log(
                        f"Alarma Proxmox resuelta: VM {vmid} ({name}) regresó a estado RUNNING.",
                        origen="NOTIF/PVE_VM",
                    )
                state["start_time"] = None
                state["triggered"] = False

        # Limpiar estados de VMs que ya no están configuradas
        obsolete_ids = [vmid for vmid in list(self.vm_states.keys()) if vmid not in configured_ids]
        for vmid in obsolete_ids:
            del self.vm_states[vmid]

        return alerts

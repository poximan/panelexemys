import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import config
from src.utils.paths import load_charo_state, save_charo_state


class CharoMonitor:
    """
    Escucha el tópico de métricas de charo-daemon y persiste el último estado
    de cada instancia en data/charo.json para consumo del dashboard.
    """

    def __init__(self, logger, mqtt_manager):
        self.logger = logger
        self._lock = threading.RLock()
        self._instances: Dict[str, Dict[str, Any]] = {}

        self._topic_prefix = getattr(config, "MQTT_TOPIC_CHARO_METRICS", "charodaemon/metrics")
        self._ttl_seconds = int(getattr(config, "CHARITO_INSTANCE_TTL_SECONDS", 3600))

        self._bootstrap_from_disk()

        try:
            mqtt_manager.subscribe(self._topic_prefix, qos=1)
        except Exception as exc:
            self._log(f"No se pudo suscribir a {self._topic_prefix}: {exc}")

        mqtt_manager.register_prefix_listener(self._topic_prefix, self._handle_message)

    def _handle_message(self, topic: str, payload: str) -> None:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            self._log(f"Payload JSON inválido en {topic}: {exc}")
            return

        instance_id_raw = data.get("instanceId")
        if not isinstance(instance_id_raw, str):
            self._log(f"Payload sin instanceId en {topic}: {payload}")
            return

        instance_id = instance_id_raw.strip()
        if not instance_id:
            self._log(f"instanceId vacío en payload de {topic}")
            return

        normalized = self._normalize_payload(instance_id, data)

        with self._lock:
            self._instances[instance_id] = normalized
            self._prune_stale_locked()
            self._persist_locked(normalized["receivedAt"])

    def _normalize_payload(self, instance_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {
            "instanceId": instance_id,
            "generatedAt": data.get("generatedAt"),
            "samples": self._safe_int(data.get("samples")),
            "windowSeconds": self._safe_int(data.get("windowSeconds")),
            "averageCpuLoad": self._safe_float(data.get("averageCpuLoad")),
            "averageCpuTemperatureCelsius": self._safe_float(data.get("averageCpuTemperatureCelsius"), -1.0),
            "averageMemoryUsageRatio": self._safe_float(data.get("averageMemoryUsageRatio")),
            "averageFreeMemoryBytes": self._safe_int(data.get("averageFreeMemoryBytes")),
            "averageTotalMemoryBytes": self._safe_int(data.get("averageTotalMemoryBytes")),
            "latestSample": data.get("latestSample") if isinstance(data.get("latestSample"), dict) else {},
        }
        received_at = datetime.utcnow().replace(microsecond=0, tzinfo=timezone.utc).isoformat()
        normalized["receivedAt"] = received_at
        return normalized

    def _prune_stale_locked(self) -> None:
        if self._ttl_seconds <= 0:
            return
        cutoff = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(seconds=self._ttl_seconds)
        to_remove = []
        for instance_id, info in self._instances.items():
            seen = self._parse_timestamp(info.get("receivedAt"))
            if seen is not None and seen < cutoff:
                to_remove.append(instance_id)
        for instance_id in to_remove:
            self._instances.pop(instance_id, None)
            self._log(f"Instancia {instance_id} eliminada por inactividad (> {self._ttl_seconds}s)")

    def _bootstrap_from_disk(self) -> None:
        existing = load_charo_state()
        if not isinstance(existing, dict):
            return
        items = existing.get("items")
        if not isinstance(items, list):
            items = []
        with self._lock:
            for item in items:
                if not isinstance(item, dict):
                    continue
                inst_id_raw = item.get("instanceId")
                if not isinstance(inst_id_raw, str) or not inst_id_raw.strip():
                    continue
                inst_id = inst_id_raw.strip()
                self._instances[inst_id] = item
            self._prune_stale_locked()
            ts_value = existing.get("ts") if isinstance(existing.get("ts"), str) else None
            self._persist_locked(ts_value)

    def _persist_locked(self, timestamp_hint: Optional[str]) -> None:
        latest_ts = timestamp_hint
        if latest_ts is None:
            latest_ts = _select_latest_timestamp(self._instances.values())
        snapshot = {
            "ts": latest_ts,
            "items": [dict(item) for item in self._instances.values()],
        }
        if not save_charo_state(snapshot):
            self._log("No se pudo persistir el estado de charo.json")

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        if not isinstance(value, str) or not value:
            return None
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value).astimezone(timezone.utc)
        except ValueError:
            return None

    def _log(self, message: str) -> None:
        try:
            self.logger.log(message, origen="CHARITO")
        except Exception:
            pass


def _select_latest_timestamp(items) -> Optional[str]:
    latest_dt: Optional[datetime] = None
    latest_iso: Optional[str] = None
    for item in items:
        if not isinstance(item, dict):
            continue
        candidate = item.get("receivedAt") or item.get("generatedAt")
        dt = CharoMonitor._parse_timestamp(candidate)
        if dt is None:
            continue
        if latest_dt is None or dt > latest_dt:
            latest_dt = dt
            latest_iso = _format_iso(dt)
    return latest_iso


def _format_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    normalized = dt.astimezone(timezone.utc).replace(microsecond=0)
    iso = normalized.isoformat()
    if iso.endswith("+00:00"):
        iso = iso[:-6] + "Z"
    return iso

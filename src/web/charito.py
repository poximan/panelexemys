import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import dash
from dash import dcc, html
from dash.dependencies import Input, Output

import config
from src.utils.paths import load_charo_state

REFRESH_INTERVAL_MS = getattr(config, "CHARITO_REFRESH_INTERVAL_MS", 10 * 1000)
STALE_THRESHOLD_SECONDS = getattr(config, "CHARITO_STALE_THRESHOLD_SECONDS", 180)

def _get_local_tz():
    try:
        return ZoneInfo(getattr(config, "APP_TIMEZONE", "America/Argentina/Buenos_Aires"))
    except Exception:
        try:
            offset_min = int(getattr(config, "APP_UTC_OFFSET_MINUTES", -180))
            return timezone(timedelta(minutes=offset_min))
        except Exception:
            return timezone.utc

LOCAL_TZ = _get_local_tz()


def get_charito_layout() -> html.Div:
    return html.Div(
        className="charito-container",
        children=[
            html.H1("Charito", className="main-title"),
            html.Div(
                id="charito-last-update",
                className="info-message",
                style={"textAlign": "center", "marginBottom": "12px"},
                children="Ultima actualizacion: N/D",
            ),
            html.Div(
                id="charito-status",
                className="info-message",
                children="Sin datos recibidos de charo-daemon.",
            ),
            html.Div(
                id="charito-grid",
                className="charito-grid",
                children=[_build_placeholder_card("Esperando la primera actualizacion...")],
            ),
            dcc.Interval(id="charito-interval", interval=REFRESH_INTERVAL_MS, n_intervals=0),
        ],
    )


def register_charito_callbacks(app: dash.Dash) -> None:
    @app.callback(
        Output("charito-grid", "children"),
        Output("charito-last-update", "children"),
        Output("charito-status", "children"),
        Input("charito-interval", "n_intervals"),
    )
    def update_charito_cards(_n: int):
        state = load_charo_state()
        charito_state = state if isinstance(state, dict) else {}
        items = []
        if isinstance(charito_state, dict):
            raw_items = charito_state.get("items", [])
            if isinstance(raw_items, list):
                items = [item for item in raw_items if isinstance(item, dict)]

        items.sort(key=lambda item: str(item.get("instanceId", "")).lower())
        instance_count = len(items)

        if instance_count == 0:
            cards = [_build_placeholder_card("Sin datos recibidos de charo-daemon.")]
        else:
            cards = [_build_charito_card(item) for item in items]

        state_timestamp = charito_state.get("ts") if isinstance(charito_state, dict) else None
        last_update_text = _format_last_update_text(state_timestamp)
        status_message = _build_status_only_message(instance_count)
        return cards, last_update_text, status_message

def _build_placeholder_card(message: str) -> html.Div:
    return html.Div(
        className="proxmox-card charito-card charito-card-placeholder",
        children=[
            html.Div(message, className="charito-placeholder-text"),
        ],
    )


def _build_charito_card(item: Dict[str, Any]) -> html.Div:
    instance_id = str(item.get("instanceId") or "")
    received_at = item.get("receivedAt") or item.get("ts")
    window_seconds = _safe_int(item.get("windowSeconds") or item.get("windowDurationSeconds") or 0)
    sample_count = _safe_int(item.get("sampleCount") or item.get("samples") or 0)

    # Averages over the window
    avg_cpu_raw = _safe_float(item.get("averageCpuLoad"), default=-1.0)
    avg_cpu_pct = _clamp_pct(avg_cpu_raw * 100.0) if avg_cpu_raw >= 0.0 else -1.0
    avg_mem_ratio = _safe_float(item.get("averageMemoryUsageRatio"), default=-1.0)
    avg_free_bytes = _safe_int(item.get("averageFreeMemoryBytes"))
    avg_total_bytes = _safe_int(item.get("averageTotalMemoryBytes"))
    avg_used_bytes = max(avg_total_bytes - avg_free_bytes, 0)
    if avg_mem_ratio < 0.0 and avg_total_bytes > 0:
        avg_mem_ratio = avg_used_bytes / max(avg_total_bytes, 1)
    avg_mem_pct = _clamp_pct(avg_mem_ratio * 100.0) if avg_mem_ratio >= 0.0 else -1.0
    avg_temp = _safe_float(item.get("averageCpuTemperatureCelsius"), default=-1.0)

    # Latest sample
    latest_sample = item.get("latestSample", {}) if isinstance(item.get("latestSample"), dict) else {}
    latest_cpu_pct: Optional[float] = None
    latest_temp = -1.0
    latest_timestamp = None
    latest_mem_text = "N/D"
    latest_mem_pct: float = -1.0
    if isinstance(latest_sample, dict):
        cpu_load = _safe_float(latest_sample.get("cpuLoad"), default=-1.0)
        latest_cpu_pct = _clamp_pct(cpu_load * 100.0) if cpu_load >= 0.0 else -1.0
        latest_temp = _safe_float(latest_sample.get("cpuTemperatureCelsius"), default=-1.0)
        latest_timestamp = latest_sample.get("timestamp")

        latest_total = _safe_int(latest_sample.get("totalMemoryBytes"))
        latest_free = _safe_int(latest_sample.get("freeMemoryBytes"))
        latest_used = max(latest_total - latest_free, 0)
        if latest_total > 0:
            latest_mem_pct = _clamp_pct((latest_used / latest_total) * 100.0)
        latest_mem_text = _format_memory(latest_used, latest_total, latest_mem_pct)

    # Processes monitored (from latestSample.watchedProcesses)
    processes = []
    if isinstance(latest_sample, dict):
        raw_procs = latest_sample.get("watchedProcesses")
        if isinstance(raw_procs, list):
            for p in raw_procs:
                if isinstance(p, dict):
                    name = str(p.get("processName") or "").strip()
                    running_raw = p.get("running")
                    running_state = _parse_bool(running_raw)
                    if name:
                        processes.append({"name": name, "running": running_state})

    avg_mem_text = _format_memory(avg_used_bytes, avg_total_bytes, avg_mem_pct)

    stale = _is_stale(received_at)
    card_classes = ["proxmox-card", "charito-card"]
    if stale:
        card_classes.append("charito-card-stale")

    local_received = _format_local_timestamp(received_at)
    relative_received = _relative_time(received_at)
    latest_local = _format_local_timestamp(latest_timestamp)
    latest_relative = _relative_time(latest_timestamp)

    received_label_parts = ["Recibido"]
    if relative_received:
        received_label_parts.append(relative_received)
    received_label = " ".join(received_label_parts).strip()
    if local_received != "N/D":
        received_label += f" ({local_received})"

    latest_label_parts = ["Capturada"]
    if latest_relative:
        latest_label_parts.append(latest_relative)
    latest_label = " ".join(latest_label_parts).strip()
    if latest_local != "N/D":
        latest_label += f" ({latest_local})"

    return html.Div(
        className=" ".join(card_classes),
        children=[
            html.Div(
                className="charito-card-header",
                children=[
                    html.Div(
                        className="charito-card-title-block",
                        children=[
                            html.Div(instance_id, className="charito-card-title"),
                            html.Div(
                                f"Ventana {window_seconds}s - {sample_count} muestras",
                                className="charito-card-subtitle",
                            ),
                            html.Span(
                                "Desactualizado" if stale else "En linea",
                                className="charito-status-badge charito-status-badge--stale" if stale else "charito-status-badge",
                            ),
                        ],
                    ),
                    html.Div(
                        received_label,
                        className="charito-last-seen",
                        title=local_received,
                    ),
                ],
            ),
            html.Div(
                className="charito-section",
                children=[
                    html.Div("Promedio de la ventana", className="charito-section-title"),
                    _build_progress_row("CPU promedio", avg_cpu_pct, None),
                    _build_temperature_row("Temp CPU promedio", avg_temp),
                    _build_progress_row("RAM promedio", avg_mem_pct, avg_mem_text),
                ],
            ),
            html.Div(
                className="charito-section",
                children=[
                    html.Div("Ultima muestra", className="charito-section-title"),
                    _build_metric_pairs(
                        [
                            ("CPU actual", _format_percent(latest_cpu_pct)),
                            ("Temp actual", _format_temperature(latest_temp)),
                            ("RAM actual", latest_mem_text),
                        ]
                    ),
                    _build_process_row(processes),
                    html.Div(
                        latest_label,
                        className="charito-last-sample",
                        title=latest_local,
                    ),
                ],
            ),
        ],
    )

def _build_status_message(count: int, ts: Any) -> html.Div:
    if count == 0:
        return html.Div(
            "Sin datos recientes de charo-daemon.",
            className="info-message",
        )
    return html.Div(
        f"Instancias activas: {count}",
        className="info-message",
    )


def _build_progress_row(label: str, pct: float, detail: str | None) -> html.Div:
    if pct < 0:
        width = "0%"
        display_value = detail or "N/D"
        fill_color = "#bdc3c7"
    else:
        width = f"{pct:.0f}%"
        display_value = detail or f"{pct:.0f}%"
        fill_color = _usage_fill_color(pct)

    fill_style = {
        "width": width,
        "background": fill_color,
        "height": "100%",
        "borderRadius": "999px",
        "transition": "width 0.4s ease",
    }

    return html.Div(
        className="proxmox-usage-row",
        children=[
            html.Div(
                className="proxmox-usage-header",
                children=[
                    html.Span(label, className="proxmox-usage-label"),
                    html.Span(display_value, className="proxmox-usage-value"),
                ],
            ),
            html.Div(
                className="proxmox-progress-track",
                children=[html.Div(className="proxmox-progress-fill", style=fill_style)],
            ),
        ],
    )


def _build_temperature_row(label: str, value: float) -> html.Div:
    display = _format_temperature(value)
    return html.Div(
        className="charito-metric-row",
        children=[
            html.Span(label, className="proxmox-usage-label"),
            html.Span(display, className="proxmox-usage-value"),
        ],
    )


def _build_metric_pairs(pairs: List[Tuple[str, str]]) -> html.Div:
    children = []
    for label, value in pairs:
        children.append(
            html.Div(
                className="charito-metric",
                children=[
                    html.Div(label, className="charito-metric-label"),
                    html.Div(value, className="charito-metric-value"),
                ],
            )
        )
    return html.Div(className="charito-metric-pair", children=children)


def _build_process_row(processes: List[Dict[str, Any]]) -> html.Div:
    if not processes:
        # Show an unobtrusive placeholder when there are no processes
        return html.Div(
            className="charito-process-row",
            children=[html.Span("Sin procesos monitoreados", className="charito-process-empty")],
        )

    items: List[html.Div] = []
    for proc in processes:
        name = str(proc.get("name") or "").strip()
        state = proc.get("running")  # True / False / None
        if state is True:
            tile_class = "charito-process-tile charito-process-tile--ok"
            label_state = "activo"
        elif state is False:
            tile_class = "charito-process-tile charito-process-tile--down"
            label_state = "detenido"
        else:
            tile_class = "charito-process-tile charito-process-tile--unknown"
            label_state = "!datos"

        title = f"{name} - {label_state}"
        items.append(
            html.Div(
                className="charito-process-item",
                children=[
                    html.Div(className=tile_class, children=[
                        html.Div(name, className="charito-process-title"),
                        html.Div(label_state, className="charito-process-state"),
                    ])
                ],
                title=title,
            )
        )

    return html.Div(className="charito-process-row", children=items)


def _parse_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "1", "yes", "y", "on"}:
            return True
        if v in {"false", "0", "no", "n", "off"}:
            return False
    return None


def _format_memory(used_bytes: int, total_bytes: int, pct: float) -> str:
    if total_bytes <= 0:
        return "N/D"
    used_gb = used_bytes / (1024 ** 3)
    total_gb = total_bytes / (1024 ** 3)
    return f"{used_gb:.1f} / {total_gb:.1f} GB ({int(round(pct))}%)" if pct >= 0 else f"{used_gb:.1f} / {total_gb:.1f} GB"


def _usage_fill_color(pct: float) -> str:
    if pct >= 85:
        return "#e74c3c"
    if pct >= 70:
        return "#f39c12"
    return "#2ecc71"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp_pct(value: float) -> float:
    if not math.isfinite(value):
        return -1.0
    if value < 0:
        return 0.0
    if value > 100:
        return 100.0
    return value


def _format_percent(value: Optional[float]) -> str:
    if value is None or value < 0:
        return "N/D"
    return f"{value:.0f}%"


def _format_temperature(value: float) -> str:
    if value < 0:
        return "N/D"
    return f"{value:.1f} Â°C"


def _relative_time(ts: Any) -> str:
    dt = _parse_iso(ts)
    if not dt:
        return ""
    now = datetime.now(timezone.utc)
    delta = now - dt
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return f"hace {seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"hace {minutes}m"
    hours = minutes // 60
    if hours < 24:
        remaining_minutes = minutes % 60
        return f"hace {hours}h {remaining_minutes}m"
    days = hours // 24
    return f"hace {days}d"


def _parse_iso(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _is_stale(ts: Any) -> bool:
    dt = _parse_iso(ts)
    if not dt:
        return True
    now = datetime.now(timezone.utc)
    delta = now - dt
    return delta.total_seconds() > STALE_THRESHOLD_SECONDS



def _format_local_timestamp(value: Any) -> str:
    dt = _parse_iso(value)
    if not dt:
        return "N/D"
    local_dt = dt.astimezone(LOCAL_TZ)
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")


def _format_last_update_text(ts: Any) -> str:
    """Formatea el texto de Ultima actualizacion sin relativo."""
    local_ts = _format_local_timestamp(ts)
    return f"Ultima actualizacion: {local_ts}"


def _build_status_only_message(count: int) -> html.Div:
    if count == 0:
        return html.Div(
            "Sin datos recientes de charo-daemon.",
            className="info-message",
        )
    return html.Div(
        f"Instancias activas: {count}",
        className="info-message",
    )









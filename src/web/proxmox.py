import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import dash_daq as daq
import plotly.graph_objects as go
from datetime import datetime
from typing import Any, Dict, List

from src.utils.paths import load_observar
from src.servicios.pve import proxmox_history
import config


DEFAULT_VIEW = getattr(config, "PVE_DASHBOARD_VIEW", "history").lower()


def _build_placeholder_card(message: str) -> html.Div:
    return html.Div(
        className="proxmox-card proxmox-card-placeholder",
        children=[
            html.Div(message, className="proxmox-card-placeholder-text"),
        ],
    )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_pct(value: Any) -> float:
    pct = _safe_float(value)
    if pct < 0:
        return 0.0
    if pct > 100:
        return 100.0
    return pct


def _format_pct(value: Any) -> str:
    try:
        if value is None:
            return "N/D"
        return f"{float(value):.2f}%"
    except Exception:
        return "N/D"


def _status_colors(status: Any) -> Dict[str, str]:
    normalized = str(status or "").strip().lower()
    if normalized == "running":
        return {"dot": "#27ae60", "text": "#1d7d46"}
    if normalized == "stopped":
        return {"dot": "#e74c3c", "text": "#a83223"}
    return {"dot": "#95a5a6", "text": "#566573"}


def _usage_fill_color(pct: float | None) -> str:
    if pct is None:
        return "#bdc3c7"
    if pct >= 85:
        return "#e74c3c"
    if pct >= 70:
        return "#f39c12"
    return "#2ecc71"


def _build_usage_row(
    label: str,
    used: Any,
    total: Any,
    unit: str = "GB",
    pct_override: Any | None = None,
) -> html.Div:
    used_val = _safe_float(used)
    total_val = _safe_float(total)

    pct: float | None
    if pct_override is not None:
        pct = _clamp_pct(pct_override)
    elif total_val > 0:
        pct = _clamp_pct((used_val / total_val) * 100.0)
    else:
        pct = None

    if pct is None or total_val <= 0:
        display_value = "N/D"
        bar_width = "0%"
    else:
        display_value = f"{used_val:.1f} / {total_val:.1f} {unit} ({pct:.0f}%)"
        bar_width = f"{pct:.0f}%"

    fill_style = {
        "width": bar_width,
        "background": _usage_fill_color(pct),
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


def _format_capacity(used: Any, total: Any) -> str:
    used_val = _safe_float(used)
    total_val = _safe_float(total)
    if total_val <= 0:
        return "N/D"
    return f"{used_val:.1f} / {total_val:.1f} GB"


_HISTORY_METRICS = [
    ("cpu_pct", "CPU uso", "#2980b9", "rgba(41, 128, 185, 0.25)"),
    ("mem_pct", "Memoria", "#8e44ad", "rgba(142, 68, 173, 0.25)"),
    ("disk_pct", "Disco", "#16a085", "rgba(22, 160, 133, 0.25)"),
]


def _parse_history_series(history: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    if not isinstance(history, dict):
        return points
    raw_series = history.get(key, [])
    if not isinstance(raw_series, list):
        return points
    for item in raw_series:
        if not isinstance(item, dict):
            continue
        ts_raw = item.get("ts")
        value_raw = item.get("value")
        if ts_raw is None or value_raw is None:
            continue
        try:
            dt = datetime.fromisoformat(str(ts_raw))
            value = float(value_raw)
        except Exception:
            continue
        points.append({"dt": dt, "value": value})
    points.sort(key=lambda entry: entry["dt"])
    return points


def _build_history_chart(
    vmid: Any,
    metric_key: str,
    label: str,
    color: str,
    fill_color: str,
    history: Dict[str, Any],
    subtitle: str | None = None,
) -> html.Div:
    series = _parse_history_series(history, metric_key)
    fig = go.Figure()

    if series:
        x_values = [point["dt"] for point in series]
        y_values = [point["value"] for point in series]
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="lines",
                line={"color": color, "width": 2},
                fill="tozeroy",
                fillcolor=fill_color,
                hovertemplate="%{y:.2f}%<br>%{x|%Y-%m-%d %H:%M}<extra></extra>",
            )
        )
        fig.update_yaxes(range=[0, 100])
    else:
        fig.add_annotation(
            text="Sin datos",
            showarrow=False,
            font={"color": "#95a5a6"},
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
        )
        fig.update_yaxes(range=[0, 100])

    fig.update_layout(
        margin=dict(l=0, r=4, t=8, b=36),
        height=220,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            showgrid=False,
            tickformat="%Y-%m-%d %H:%M",
            color="#7f8c8d",
            tickfont=dict(size=11),
        ),
        yaxis=dict(showgrid=False, color="#7f8c8d"),
        uirevision=f"vm-{vmid}-{metric_key}",
    )

    return html.Div(
        className="proxmox-history-chart",
        children=[
            html.Div(
                [
                    html.Span(label, className="proxmox-history-label"),
                    html.Span(subtitle or "", className="proxmox-history-subtitle"),
                ],
                className="proxmox-history-title",
            ),
            dcc.Graph(
                id=f"proxmox-history-{vmid}-{metric_key}",
                figure=fig,
                className="proxmox-history-figure",
                config={"displayModeBar": False, "responsive": True},
            ),
        ],
    )


def _build_history_cards(vms: List[Dict[str, Any]], history_meta: Dict[str, Any]) -> List[html.Div]:
    cards: List[html.Div] = []
    for vm in sorted(vms, key=lambda item: item.get("vmid", 0)):
        name = vm.get("name", "N/D")
        vmid = vm.get("vmid", "N/D")
        status_raw = vm.get("status", "desconocido")
        status_text = str(status_raw).upper()
        status_colors = _status_colors(status_raw)
        uptime = vm.get("uptime_human", "0m")
        cpus = vm.get("cpus", "N/D")
        mem_used = vm.get("mem_used_gb")
        mem_total = vm.get("mem_total_gb")
        disk_used = vm.get("disk_used_gb")
        disk_total = vm.get("disk_total_gb")
        warning = vm.get("status_detail_error")
        history = vm.get("history") or {}

        charts = []
        for key, label, color, fill in _HISTORY_METRICS:
            subtitle = ""
            if key == "mem_pct":
                subtitle = _format_capacity(mem_used, mem_total)
            elif key == "disk_pct":
                subtitle = _format_capacity(disk_used, disk_total)
            charts.append(
                _build_history_chart(
                    vmid,
                    key,
                    label,
                    color,
                    fill,
                    history,
                    subtitle=subtitle,
                )
            )

        cards.append(
            html.Div(
                className="proxmox-card proxmox-card-history",
                children=[
                    html.Div(
                        className="proxmox-card-header",
                        children=[
                            html.Div(
                                className="proxmox-card-title",
                                children=[
                                    html.Span(f"VM {vmid}", className="proxmox-card-vmid"),
                                    html.Span(name, className="proxmox-card-name"),
                                ],
                            ),
                            html.Div(
                                className="proxmox-status-wrapper",
                                children=[
                                    html.Span(
                                        status_text,
                                        className="proxmox-card-status",
                                        style={"color": status_colors["text"]},
                                    ),
                                    html.Div(
                                        className="proxmox-status-dot",
                                        style={"backgroundColor": status_colors["dot"]},
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="proxmox-card-body proxmox-card-body-history",
                        children=[
                            html.Div(
                                className="proxmox-history-grid",
                                children=charts,
                            ),
                            html.Div(
                                className="proxmox-extra-section",
                                children=[
                                    html.Div(
                                        className="proxmox-extra-metric",
                                        children=[
                                            html.Span("vCPUs:", className="proxmox-extra-label"),
                                            html.Span(str(cpus), className="proxmox-extra-value"),
                                        ],
                                    ),
                                    html.Div(
                                        className="proxmox-extra-metric",
                                        children=[
                                            html.Span("Uptime:", className="proxmox-extra-label"),
                                            html.Span(uptime, className="proxmox-extra-value"),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    (
                        html.Div(
                            warning,
                            className="proxmox-metric-warning",
                        )
                        if warning
                        else None
                    ),
                ],
            )
        )
    return cards


def _build_classic_cards(vms: List[Dict[str, Any]]) -> List[html.Div]:
    cards: List[html.Div] = []
    for vm in sorted(vms, key=lambda item: item.get("vmid", 0)):
        name = vm.get("name", "N/D")
        vmid = vm.get("vmid", "N/D")
        status_raw = vm.get("status", "desconocido")
        status_text = str(status_raw).upper()
        status_colors = _status_colors(status_raw)
        uptime = vm.get("uptime_human", "0m")
        cpu_pct_value = _clamp_pct(vm.get("cpu_usage_pct"))
        cpu_pct_display = _format_pct(vm.get("cpu_usage_pct"))
        warning = vm.get("status_detail_error")
        cpus = vm.get("cpus", "N/D")
        mem_used = vm.get("mem_used_gb")
        mem_total = vm.get("mem_total_gb")
        disk_used = vm.get("disk_used_gb")
        disk_total = vm.get("disk_total_gb")
        disk_pct = vm.get("disk_usage_pct")

        gauge_value = max(0, min(100, cpu_pct_value))

        cards.append(
            html.Div(
                className="proxmox-card proxmox-card-classic",
                children=[
                    html.Div(
                        className="proxmox-card-header",
                        children=[
                            html.Div(
                                className="proxmox-card-title",
                                children=[
                                    html.Span(f"VM {vmid}", className="proxmox-card-vmid"),
                                    html.Span(name, className="proxmox-card-name"),
                                ],
                            ),
                            html.Div(
                                className="proxmox-status-wrapper",
                                children=[
                                    html.Span(
                                        status_text,
                                        className="proxmox-card-status",
                                        style={"color": status_colors["text"]},
                                    ),
                                    html.Div(
                                        className="proxmox-status-dot",
                                        style={"backgroundColor": status_colors["dot"]},
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="proxmox-card-body proxmox-card-body-classic",
                        children=[
                            html.Div(
                                className="proxmox-gauge-container",
                                children=[
                                    daq.Gauge(
                                        className="proxmox-gauge",
                                        min=0,
                                        max=100,
                                        value=gauge_value,
                                        showCurrentValue=False,
                                        label="CPU uso",
                                        color={
                                            "gradient": True,
                                            "ranges": {
                                                "#27ae60": [0, 60],
                                                "#f1c40f": [60, 85],
                                                "#c0392b": [85, 100],
                                            },
                                        },
                                        size=140,
                                    )
                                ],
                            ),
                            html.Div(
                                className="proxmox-gauge-value",
                                children=[
                                    html.Span(cpu_pct_display, className="proxmox-gauge-number"),
                                ],
                            ),
                            html.Div(
                                className="proxmox-usage-section",
                                children=[
                                    _build_usage_row("Memoria", mem_used, mem_total),
                                    _build_usage_row("Disco", disk_used, disk_total, pct_override=disk_pct),
                                    html.Div(
                                        className="proxmox-extra-metric",
                                        children=[
                                            html.Span("vCPUs:", className="proxmox-extra-label"),
                                            html.Span(str(cpus), className="proxmox-extra-value"),
                                        ],
                                    ),
                                    html.Div(
                                        className="proxmox-extra-metric",
                                        children=[
                                            html.Span("Uptime:", className="proxmox-extra-label"),
                                            html.Span(uptime, className="proxmox-extra-value"),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    (
                        html.Div(
                            warning,
                            className="proxmox-metric-warning",
                        )
                        if warning
                        else None
                    ),
                ],
            )
        )
    return cards


def get_proxmox_layout() -> html.Div:
    poll_seconds = int(getattr(config, "PVE_POLL_INTERVAL_SECONDS", 20))
    refresh_ms = max(5_000, poll_seconds * 1000)

    return html.Div(
        children=[
            html.H1("Proxmox", className="main-title"),
            html.Div(
                id="proxmox-last-update",
                className="info-message",
                style={"textAlign": "center", "marginBottom": "12px"},
            ),
            html.Div(
                id="proxmox-status-message",
                className="info-message",
                style={"textAlign": "center", "marginBottom": "16px"},
            ),
            html.Div(
                className="proxmox-toolbar",
                children=[
                    html.Span("Vista", className="proxmox-toolbar-label"),
                    html.Div(
                        className="proxmox-toggle-wrapper",
                        children=[
                            html.Span("Clásico", className="proxmox-toggle-option"),
                            daq.ToggleSwitch(
                                id="proxmox-view-switch",
                                value=(DEFAULT_VIEW != "classic"),
                                persistence=True,
                                persistence_type="session",
                            ),
                            html.Span("Histórico", className="proxmox-toggle-option"),
                        ],
                    ),
                ],
            ),
            html.Div(
                id="proxmox-cards",
                className="proxmox-grid",
                children=[
                    _build_placeholder_card(
                        "Sin datos disponibles. Esperando la primera actualizacion..."
                    )
                ],
            ),
            dcc.Interval(id="proxmox-interval", interval=refresh_ms, n_intervals=0),
        ]
    )


def register_proxmox_callbacks(app: dash.Dash) -> None:
    @app.callback(
        Output("proxmox-cards", "children"),
        Output("proxmox-last-update", "children"),
        Output("proxmox-status-message", "children"),
        Input("proxmox-interval", "n_intervals"),
        Input("proxmox-view-switch", "value"),
    )
    def update_proxmox_cards(_n: int, view_toggle: Any):
        data = load_observar()
        prox = data.get("proxmox_estado", {}) if isinstance(data, dict) else {}

        try:
            app.logger.info("Proxmox callback payload: %s", prox)
        except Exception:
            pass

        ts = prox.get("ts") if isinstance(prox, dict) else None
        vms = prox.get("vms") if isinstance(prox, dict) else []
        missing = prox.get("missing") if isinstance(prox, dict) else []
        error = prox.get("error") if isinstance(prox, dict) else None

        history_map, history_meta = proxmox_history.load_history_for_dashboard()
        if not isinstance(vms, list):
            vms = []
        for vm in vms:
            if not isinstance(vm, dict):
                continue
            try:
                vmid_int = int(vm.get("vmid"))
            except Exception:
                continue
            history_payload = history_map.get(vmid_int)
            if history_payload:
                vm["history"] = history_payload.get("history", {})
                if not vm.get("name") and history_payload.get("name"):
                    vm["name"] = history_payload.get("name")

        selected_view = DEFAULT_VIEW
        if isinstance(view_toggle, bool):
            selected_view = "history" if view_toggle else "classic"
        elif isinstance(view_toggle, str):
            selected_view = view_toggle.lower()
        if selected_view not in {"history", "classic"}:
            selected_view = "history"

        if vms:
            if selected_view == "classic":
                cards = _build_classic_cards(vms)
            else:
                cards = _build_history_cards(vms, history_meta or {})
        else:
            cards = [
                _build_placeholder_card(
                    "Sin datos disponibles para los VMIDs configurados."
                )
            ]

        last_update = (
            f"Ultima actualizacion: {ts}" if ts else "Sin datos de Proxmox por el momento."
        )

        if error:
            status_element = html.Div(
                "Hipervisor Proxmox no responde.",
                style={"color": "#c0392b", "fontWeight": "600"},
                title=str(error),
            )
        else:
            status_children = [
                html.Div(
                    "Hipervisor Proxmox en línea.",
                    style={"color": "#27ae60", "fontWeight": "600"},
                )
            ]
            if missing:
                missing_str = ", ".join(str(m) for m in missing)
                status_children.append(
                    html.Div(
                        f"VM sin datos en la última consulta: {missing_str}",
                        style={"color": "#e67e22"},
                    )
                )
            status_element = html.Div(status_children)

        return cards, last_update, status_element

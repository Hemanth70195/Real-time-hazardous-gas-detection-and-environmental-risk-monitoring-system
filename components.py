# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard — Industrial UI Components.
Renders the status bar, parameter tiles with integrated SVG sparklines,
horizontal threshold meters, recommended actions, sensor nodes table,
event log table, protocol cards, KPI cards, and alert banners in dark slate theme.
"""

from typing import Any, Dict, List
import streamlit as st

# Clean SVG Icons (Tabler / Material style - 18x18, stroke 1.8)
ICONS = {
    "thermometer": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13.5a4 4 0 1 0 4 0V5a2 2 0 1 0-4 0v8.5m1-4.5h2"/></svg>',
    "droplet": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6.8 11a6 6 0 1 0 10.396 0l-5.196-8-5.2 8z"/></svg>',
    "wind": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 8h8.5a2.5 2.5 0 1 0-2.34-3.24M3 12h15.5a2.5 2.5 0 1 1-2.34 3.24M4 16h5.5a2.5 2.5 0 1 1-2.34 3.24"/></svg>',
    "volume": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>',
    "flask": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.73 3h12.54a2 2 0 0 0 1.73-3l-5-9V3m-7 11h10"/></svg>',
    "shield": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    "link": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
}


def make_svg_sparkline(values: List[float], width: int = 300, height: int = 40) -> str:
    """
    Generates an inline SVG polyline sparkline in calm blue (#2a78d6).
    Renders directly inside the card HTML with zero extra borders, margins, or iframes.
    """
    if not values or len(values) < 2:
        return f'<div style="height: {height}px; color: #64748b; font-size: 0.75rem;">Collecting telemetry...</div>'

    min_v = min(values)
    max_v = max(values)
    span = max_v - min_v if max_v != min_v else 1.0
    n = len(values)

    coords = []
    for i, v in enumerate(values):
        x = (i / (n - 1)) * width
        y = (height - 4) - (((v - min_v) / span) * (height - 8))
        coords.append(f"{x:.1f},{y:.1f}")

    pts = " ".join(coords)
    return (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="none" style="display: block; margin: 8px 0 4px 0; overflow: visible;">'
        f'<polyline points="{pts}" fill="none" stroke="#2a78d6" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )


def render_status_bar(
    site_status: str,
    danger_count: int,
    warning_count: int,
    safe_count: int,
    total_count: int,
    updated_seconds_ago: int = 2,
    data_source: str = "simulation",
    device_id: str = None,
    is_stale: bool = False,
    connection_status: str = "connected",
    uncalibrated_count: int = 0,
):
    """
    Renders top status bar with clear identification of:
    - LIVE SENSOR DATA (ESP32) vs SIMULATED DATA
    - Data freshness (fresh vs STALE / UNAVAILABLE)
    - Uncalibrated raw sensor parameters count
    """
    bar_class = f"status-bar-{site_status.lower()}"
    dot_class = f"dot-{site_status.lower()}"
    status_label = f"Site status: {site_status.lower()}"

    # Build counts summary
    counts_parts = []
    if danger_count > 0:
        counts_parts.append(f"{danger_count} critical")
    if warning_count > 0:
        counts_parts.append(f"{warning_count} warnings")
    counts_parts.append(f"{safe_count} of {total_count} parameters safe")
    if uncalibrated_count > 0:
        counts_parts.append(f"{uncalibrated_count} uncalibrated raw")
    counts_str = ", ".join(counts_parts)

    # Source Tag
    if data_source == "live_esp32":
        if is_stale:
            source_badge = '<span style="background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.72rem; letter-spacing: 0.04em;">SENSOR DATA STALE</span>'
        else:
            source_badge = '<span style="background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.72rem; letter-spacing: 0.04em;">LIVE SENSOR DATA</span>'
        dev_tag = f"ESP32 [{device_id or 'safeedge-01'}]"
        conn_label = f'{ICONS["link"]} USB Serial: {connection_status} ({dev_tag})'
    elif data_source == "cloud_esp32":
        if is_stale:
            source_badge = '<span style="background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.72rem; letter-spacing: 0.04em;">CLOUD DATA STALE</span>'
        else:
            source_badge = '<span style="background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid #a855f7; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.72rem; letter-spacing: 0.04em;">CLOUD IOT STREAM</span>'
        dev_tag = f"ESP32 [{device_id or 'safeedge-01'}]"
        conn_label = f'{ICONS["link"]} Cloud IoT Link: {connection_status} ({dev_tag})'
    else:
        source_badge = '<span style="background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid #3b82f6; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.72rem; letter-spacing: 0.04em;">SIMULATED DATA</span>'
        conn_label = f'{ICONS["link"]} Simulation Hardware Loop'

    time_label = f"Updated {updated_seconds_ago}s ago" if updated_seconds_ago is not None else "Awaiting telemetry"

    html = (
        f'<div class="status-bar-container {bar_class}">'
        f'<div class="status-left">'
        f'<span class="status-dot {dot_class}"></span>'
        f'<span class="status-title">{status_label}</span>'
        f'{source_badge}'
        f'<span class="status-counts">{counts_str}</span>'
        f'</div>'
        f'<div class="status-right">'
        f'<span class="status-hardware-link">{conn_label}</span>'
        f'<span>{time_label}</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_parameter_card(param: Dict[str, Any], history: List[float]):
    """
    Renders a single parameter tile:
    - Icon + Name
    - SAFE / WARNING / DANGER / UNCALIBRATED label
    - Large value with unit
    - Horizontal threshold meter or uncalibrated raw indicator
    - Detailed sub-metrics (e.g. PM1.0, PM2.5, PM10)
    - Integrated inline SVG sparkline
    - Sensor Node footer caption and calibration warnings
    """
    val = param.get("value")
    unit = param.get("unit", "")
    min_v = param.get("min", 0.0)
    max_v = param.get("max", 100.0)
    warn_v = param.get("warn", 50.0)
    danger_v = param.get("danger", 80.0)
    status = str(param.get("status", "SAFE")).upper()
    is_uncal = bool(param.get("is_uncalibrated", False))
    icon_svg = ICONS.get(param.get("icon", "thermometer"), ICONS["thermometer"])
    sub_metrics = param.get("sub_metrics")

    # Styling classes
    if val is None or status == "OFFLINE":
        card_class = "param-card"
        badge_html = '<span style="background: rgba(107, 114, 128, 0.2); color: #9ca3af; border: 1px solid #6b7280; padding: 2px 6px; border-radius: 4px; font-size: 0.72rem; font-weight: 700;">OFFLINE</span>'
        val_display = "--"
        meter_gradient = "linear-gradient(to right, #374151 0%, #374151 100%)"
        val_pct = 0.0
        labels_html = "<span>Sensor offline</span><span>No signal</span>"
        footer_caption = f"{param.get('node', 'NODE')} · SENSOR DISCONNECTED"
    elif is_uncal or status == "UNCALIBRATED":
        card_class = "param-card param-card-warning"
        badge_html = '<span style="background: rgba(245, 158, 11, 0.2); color: #fab219; border: 1px solid #f59e0b; padding: 2px 6px; border-radius: 4px; font-size: 0.72rem; font-weight: 700;">RAW UNCALIBRATED</span>'
        val_display = f"{int(val):,}" if isinstance(val, (int, float)) else str(val)
        meter_gradient = "linear-gradient(to right, #374151 0%, #4b5563 50%, #f59e0b 100%)"
        val_pct = min(100.0, max(0.0, (val / 4095.0) * 100.0)) if max_v > 0 else 50.0
        labels_html = "<span>0 ADC</span><span style='color: #f59e0b;'>No ppm/dB calibration</span><span>4095 ADC</span>"
        footer_caption = f"{param.get('node', 'NODE')} · RAW UNCALIBRATED SENSOR DATA · Not classified as safe"
    else:
        card_class = f"param-card param-card-{status.lower()}"
        badge_class = f"param-badge badge-{status.lower()}"
        badge_html = f'<span class="{badge_class}">{status}</span>'
        val_display = f"{val:.1f}" if isinstance(val, (int, float)) else str(val)

        span = max(0.1, max_v - min_v)
        val_pct = max(0.0, min(100.0, ((val - min_v) / span) * 100.0))
        warn_pct = max(0.0, min(100.0, ((warn_v - min_v) / span) * 100.0))
        danger_pct = max(0.0, min(100.0, ((danger_v - min_v) / span) * 100.0))

        meter_gradient = (
            f"linear-gradient(to right, #0ca30c 0%, #0ca30c {warn_pct:.1f}%, "
            f"#fab219 {warn_pct:.1f}%, #fab219 {danger_pct:.1f}%, "
            f"#d03b3b {danger_pct:.1f}%, #d03b3b 100%)"
        )
        labels_html = f"<span>{min_v:g}</span><span>warn {warn_v:g}</span><span>danger {danger_v:g}</span>"
        footer_caption = f"{param.get('node', 'NODE')} · last {len(history)} readings"

    # Sub-metrics display (e.g., PMS5003 showing PM1.0, PM2.5, PM10)
    sub_metrics_html = ""
    if sub_metrics:
        sub_metrics_html = f'<div style="font-size: 0.75rem; color: #93c5fd; margin-top: -6px; margin-bottom: 8px;">{sub_metrics}</div>'

    sparkline_svg = make_svg_sparkline(history, width=300, height=40)

    tile_html = (
        f'<div class="{card_class}">'
        f'<div>'
        f'<div class="param-header">'
        f'<div class="param-title-wrap">{icon_svg}<span>{param.get("name", "Parameter")}</span></div>'
        f'{badge_html}'
        f'</div>'
        f'<div class="param-value-row">'
        f'<span class="param-value-num">{val_display}</span>'
        f'<span class="param-value-unit">{unit}</span>'
        f'</div>'
        f'{sub_metrics_html}'
        f'<div class="meter-wrapper">'
        f'<div class="meter-track-base" style="background: {meter_gradient};">'
        f'<div class="meter-pin" style="left: {val_pct:.1f}%;"></div>'
        f'</div>'
        f'<div class="meter-labels-row">{labels_html}</div>'
        f'</div>'
        f'</div>'
        f'<div>'
        f'{sparkline_svg}'
        f'<div class="card-subcaption">{footer_caption}</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(tile_html, unsafe_allow_html=True)


def render_recommended_action_card(action_data: Dict[str, str]):
    """Renders Tile 6: Recommended action card."""
    status = action_data.get("status", "normal")
    headline = action_data.get("headline", "No intervention required. Maintain routine site vigilance.")
    guidelines_warn = action_data.get("guidelines_warning", "Warning: respirators and exhaust.")
    guidelines_danger = action_data.get("guidelines_danger", "Danger: evacuate, SCBA.")

    card_class = f"param-card param-card-{status.lower()}"
    headline_class = f"rec-headline rec-headline-{status.lower()}"

    html = (
        f'<div class="{card_class}">'
        f'<div class="rec-card-body">'
        f'<div>'
        f'<div class="param-header">'
        f'<div class="param-title-wrap">{ICONS["shield"]}<span>Recommended action</span></div>'
        f'</div>'
        f'<div class="{headline_class}">{headline}</div>'
        f'</div>'
        f'<div class="rec-guidelines">'
        f'<div>{guidelines_warn}</div>'
        f'<div>{guidelines_danger}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_sensor_nodes_table(nodes: List[Dict[str, Any]]):
    """Renders bottom-left Sensor Nodes card."""
    rows_parts = []
    for n in nodes:
        row = (
            f'<tr>'
            f'<td><strong>{n["node"]}</strong></td>'
            f'<td>{n["sensor"]}</td>'
            f'<td>{n["rssi"]}</td>'
            f'<td>{n["batt"]}</td>'
            f'<td class="state-online">{n["state"]}</td>'
            f'</tr>'
        )
        rows_parts.append(row)

    rows_html = "".join(rows_parts)
    html = (
        f'<div class="bottom-panel-card">'
        f'<div class="bottom-panel-title">Sensor Nodes</div>'
        f'<table class="industrial-table">'
        f'<thead>'
        f'<tr>'
        f'<th>Node</th>'
        f'<th>Sensor</th>'
        f'<th>RSSI</th>'
        f'<th>Batt</th>'
        f'<th>State</th>'
        f'</tr>'
        f'</thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_event_log_table(events: List[Dict[str, Any]]):
    """Renders bottom-right Event Log card."""
    recent_events = events[:4] if events else []
    rows_parts = []

    for ev in recent_events:
        sev = ev.get("severity", "Normal")
        sev_class = f"sev-{sev.lower()}"
        row = (
            f'<tr>'
            f'<td style="color: #9ca3af;">{ev["time"]}</td>'
            f'<td><strong>{ev["node"]}</strong></td>'
            f'<td>{ev["message"]}</td>'
            f'<td class="{sev_class}">{sev}</td>'
            f'</tr>'
        )
        rows_parts.append(row)

    if not rows_parts:
        rows_html = '<tr><td colspan="4" style="color: #9ca3af; text-align: center;">No hazard state transitions recorded.</td></tr>'
    else:
        rows_html = "".join(rows_parts)

    html = (
        f'<div class="bottom-panel-card">'
        f'<div class="bottom-panel-title">Event Log</div>'
        f'<table class="industrial-table">'
        f'<thead>'
        f'<tr>'
        f'<th>Time</th>'
        f'<th>Node</th>'
        f'<th>Message</th>'
        f'<th>Severity</th>'
        f'</tr>'
        f'</thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Additional Reference Mockup Components (Images 1, 2, 3)
# -----------------------------------------------------------------------------

def render_alert_thresholds_table():
    """Renders the ALERT THRESHOLDS table matching Image 1."""
    rows = [
        ("Gas (ppm)", "below 25", "25 to 50", "above 50"),
        ("Temperature (°C)", "below 35", "35 to 45", "above 45"),
        ("Humidity (%)", "below 70", "70 to 85", "above 85"),
        ("Noise (dB)", "below 85", "85 to 100", "above 100"),
    ]

    rows_parts = []
    for param, norm, warn, dang in rows:
        r = (
            f'<tr>'
            f'<td><strong>{param}</strong></td>'
            f'<td style="color: #e5e7eb;">{norm}</td>'
            f'<td style="color: #e5e7eb;">{warn}</td>'
            f'<td style="color: #e5e7eb;">{dang}</td>'
            f'</tr>'
        )
        rows_parts.append(r)

    rows_html = "".join(rows_parts)
    html = (
        f'<div class="bottom-panel-card" style="margin-bottom: 20px;">'
        f'<div class="bottom-panel-title">Alert Thresholds</div>'
        f'<table class="industrial-table">'
        f'<thead>'
        f'<tr>'
        f'<th>Parameter</th>'
        f'<th class="threshold-th-normal">Normal</th>'
        f'<th class="threshold-th-warning">Warning</th>'
        f'<th class="threshold-th-danger">Danger</th>'
        f'</tr>'
        f'</thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_protocol_action_boxes():
    """Renders the 3 color-coded action boxes (Normal, Warning, Danger) matching Image 1."""
    col1, col2, col3 = st.columns(3)

    with col1:
        html = (
            f'<div class="protocol-card protocol-card-normal">'
            f'<div class="protocol-card-title protocol-title-normal">Normal</div>'
            f'<ul class="protocol-list">'
            f'<li>Routine site vigilance</li>'
            f'<li>Daily sensor checks</li>'
            f'<li>Keep exits clear</li>'
            f'</ul>'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)

    with col2:
        html = (
            f'<div class="protocol-card protocol-card-warning">'
            f'<div class="protocol-card-title protocol-title-warning">Warning</div>'
            f'<ul class="protocol-list">'
            f'<li>Deploy respirators</li>'
            f'<li>Start exhaust ventilation</li>'
            f'<li>Restrict non-essential entry</li>'
            f'<li>Alert the supervisor</li>'
            f'</ul>'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)

    with col3:
        html = (
            f'<div class="protocol-card protocol-card-danger">'
            f'<div class="protocol-card-title protocol-title-danger">Danger</div>'
            f'<ul class="protocol-list">'
            f'<li>Mandatory evacuation</li>'
            f'<li>SCBA for responders only</li>'
            f'<li>Isolate the gas source</li>'
            f'<li>Call emergency services</li>'
            f'</ul>'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)


def render_protective_and_emergency_contacts():
    """Renders bottom Protective Equipment & Emergency Contacts cards matching Image 1."""
    col1, col2 = st.columns(2)

    with col1:
        html = (
            f'<div class="info-card">'
            f'<div class="info-card-title">Protective Equipment</div>'
            f'<div class="info-card-content">'
            f'<div>• Half-mask respirator (P100 and organic vapor)</div>'
            f'<div>• Self-contained breathing apparatus (SCBA)</div>'
            f'<div>• Hearing protection above 85 dB</div>'
            f'<div>• Heat-stress hydration kit</div>'
            f'</div>'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)

    with col2:
        html = (
            f'<div class="info-card">'
            f'<div class="info-card-title">Emergency Contacts</div>'
            f'<div class="info-card-content">'
            f'<div>• Safety officer: ext. 101</div>'
            f'<div>• Site control room: ext. 102</div>'
            f'<div>• Fire and rescue: 101</div>'
            f'<div>• Ambulance: 108</div>'
            f'</div>'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)


def render_kpi_cards(min_val: float, avg_val: float, max_val: float, alerts_count: int, unit: str):
    """Renders the 4 KPI stats cards matching Image 2."""
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        html = (
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Minimum</div>'
            f'<div class="kpi-val">{min_val:g} <span style="font-size: 0.95rem; color: #9ca3af;">{unit}</span></div>'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)

    with c2:
        html = (
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Average</div>'
            f'<div class="kpi-val">{avg_val:g} <span style="font-size: 0.95rem; color: #9ca3af;">{unit}</span></div>'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)

    with c3:
        html = (
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Maximum</div>'
            f'<div class="kpi-val">{max_val:g} <span style="font-size: 0.95rem; color: #9ca3af;">{unit}</span></div>'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)

    with c4:
        html = (
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Alerts</div>'
            f'<div class="kpi-val-amber">{alerts_count}</div>'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)


def render_hazard_alert_banner(title: str, description: str):
    """Renders prominent critical hazard alert banner matching Image 3."""
    html = (
        f'<div class="hazard-alert-banner">'
        f'<div class="hazard-alert-title">'
        f'<span style="color: #ef4444; font-size: 1.2rem;">●</span>'
        f'<span>{title}</span>'
        f'</div>'
        f'<div class="hazard-alert-body">{description}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_parameter_summary_table(summary_rows: List[Dict[str, Any]], time_window: str = "24 H"):
    """Renders the Parameter Summary table matching Image 2."""
    rows_parts = []
    for r in summary_rows:
        status_color = "#0ca30c" if r["status"].lower() == "safe" else "#fab219" if r["status"].lower() == "warning" else "#d03b3b"
        row = (
            f'<tr>'
            f'<td><strong>{r["param"]}</strong></td>'
            f'<td>{r["min"]}</td>'
            f'<td>{r["avg"]}</td>'
            f'<td>{r["max"]}</td>'
            f'<td>{r["warnings"]}</td>'
            f'<td style="color: {status_color}; font-weight: 600;">{r["status"]}</td>'
            f'</tr>'
        )
        rows_parts.append(row)

    rows_html = "".join(rows_parts)
    html = (
        f'<div class="bottom-panel-card" style="margin-top: 20px;">'
        f'<div class="bottom-panel-title">Parameter Summary · {time_window}</div>'
        f'<table class="industrial-table">'
        f'<thead>'
        f'<tr>'
        f'<th>Parameter</th>'
        f'<th>Min</th>'
        f'<th>Avg</th>'
        f'<th>Max</th>'
        f'<th>Warnings</th>'
        f'<th>Status</th>'
        f'</tr>'
        f'</thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_hardware_connection_panel(
    status_info: Dict[str, Any],
    available_ports: List[Dict[str, str]],
    current_port: str,
    current_baud: int,
    on_connect_cb=None,
    on_disconnect_cb=None,
):
    """
    Renders connection controls for Live Hardware Mode:
    - Serial Port selection & Refresh
    - Baud Rate configuration
    - Connect / Disconnect button
    - Real-time diagnostic telemetry pill
    """
    is_connected = status_info.get("is_connected", False)
    is_stale = status_info.get("is_stale", False)
    status_str = status_info.get("status", "DISCONNECTED")
    last_msg_time = status_info.get("last_message_time")
    last_age = status_info.get("last_message_age_seconds")
    msgs_rec = status_info.get("messages_received", 0)
    errs_cnt = status_info.get("errors_count", 0)
    device_id = status_info.get("device_id")

    # Connection Status Banner
    if is_connected and not is_stale:
        banner_bg = "rgba(16, 185, 129, 0.12)"
        banner_border = "#10b981"
        banner_icon = "●"
        banner_color = "#10b981"
        status_text = f"ESP32 Connected ({status_info.get('port')}) · Device: {device_id or 'safeedge-esp32'} · Streaming {msgs_rec} pkts"
    elif is_connected and is_stale:
        banner_bg = "rgba(245, 158, 11, 0.12)"
        banner_border = "#f59e0b"
        banner_icon = "▲"
        banner_color = "#fab219"
        status_text = f"ESP32 Connected but DATA STALE (>5s without packet) · Port: {status_info.get('port')} · Age: {last_age}s"
    elif status_str == "ERROR":
        banner_bg = "rgba(239, 68, 68, 0.12)"
        banner_border = "#ef4444"
        banner_icon = "✕"
        banner_color = "#ef4444"
        status_text = f"Serial Port Error: {status_info.get('last_error') or 'Communication failure'}"
    else:
        banner_bg = "rgba(75, 85, 99, 0.15)"
        banner_border = "#4b5563"
        banner_icon = "○"
        banner_color = "#9ca3af"
        status_text = "Serial Link: Disconnected. Select an active ESP32 COM port and click Connect."

    st.markdown(
        f"""
        <div style="background-color: {banner_bg}; border: 1px solid {banner_border}; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="color: {banner_color}; font-size: 1.1rem; line-height: 0;">{banner_icon}</span>
                <span style="font-weight: 600; font-size: 0.92rem; color: #f9fafb;">{status_text}</span>
            </div>
            <div style="font-size: 0.82rem; color: #9ca3af;">
                Last message: <strong style="color: #e5e7eb;">{last_msg_time or 'None'}</strong> | Errors: <strong style="color: {'#ef4444' if errs_cnt > 0 else '#9ca3af'};">{errs_cnt}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_cloud_connection_panel(
    status_info: Dict[str, Any],
    current_backend_url: str,
    current_device_id: str,
):
    """
    Renders connection status and telemetry metrics for Cloud Live Mode (IoT Streaming):
    - Cloud Backend URL and target Device ID
    - Ingestion endpoint health and stale telemetry indicator
    - Real-time diagnostic statistics (packets received, latency, error counter)
    """
    is_connected = status_info.get("is_connected", False)
    is_stale = status_info.get("is_stale", False)
    status_str = status_info.get("status", "DISCONNECTED")
    last_msg_time = status_info.get("last_message_time")
    last_age = status_info.get("last_message_age_seconds")
    msgs_rec = status_info.get("messages_received", 0)
    errs_cnt = status_info.get("errors_count", 0)
    latency_ms = status_info.get("last_poll_duration_ms", 0)
    device_id = status_info.get("device_id") or current_device_id

    # Banner styling
    if is_connected and not is_stale:
        banner_bg = "rgba(168, 85, 247, 0.12)"
        banner_border = "#a855f7"
        banner_icon = "●"
        banner_color = "#c084fc"
        status_text = f"Cloud IoT Streaming Online · Device: {device_id} · Streamed {msgs_rec} pkts ({latency_ms}ms)"
    elif is_connected and is_stale:
        banner_bg = "rgba(245, 158, 11, 0.12)"
        banner_border = "#f59e0b"
        banner_icon = "▲"
        banner_color = "#fab219"
        status_text = f"Cloud Telemetry STALE (>{last_age}s since last packet) · Target: {device_id}"
    elif status_str == "ERROR":
        banner_bg = "rgba(239, 68, 68, 0.12)"
        banner_border = "#ef4444"
        banner_icon = "✕"
        banner_color = "#ef4444"
        status_text = f"Cloud Ingestion Error: {status_info.get('last_error') or 'Cannot reach backend service'}"
    else:
        banner_bg = "rgba(75, 85, 99, 0.15)"
        banner_border = "#4b5563"
        banner_icon = "○"
        banner_color = "#9ca3af"
        status_text = f"Cloud IoT Polling: {current_backend_url} · Awaiting first packet from {device_id}"

    st.markdown(
        f"""
        <div style="background-color: {banner_bg}; border: 1px solid {banner_border}; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="color: {banner_color}; font-size: 1.1rem; line-height: 0;">{banner_icon}</span>
                <span style="font-weight: 600; font-size: 0.92rem; color: #f9fafb;">{status_text}</span>
            </div>
            <div style="font-size: 0.82rem; color: #9ca3af;">
                Backend: <strong style="color: #e5e7eb;">{current_backend_url}</strong> | Last: <strong style="color: #e5e7eb;">{last_msg_time or 'None'}</strong> | Errors: <strong style="color: {'#ef4444' if errs_cnt > 0 else '#9ca3af'};">{errs_cnt}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard — Industrial IoT Monitoring Dashboard.
Real-time environmental safety monitoring, hazard assessment, and IoT node management.
Styled to match the reference mockups for all 4 navigation views.
"""

import io
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from components import (
    render_alert_thresholds_table,
    render_event_log_table,
    render_hazard_alert_banner,
    render_kpi_cards,
    render_parameter_card,
    render_parameter_summary_table,
    render_protective_and_emergency_contacts,
    render_protocol_action_boxes,
    render_recommended_action_card,
    render_sensor_nodes_table,
    render_status_bar,
)
from simulator import SCENARIOS, SENSOR_NODES, get_simulator, read_sensors

st.set_page_config(
    page_title="SafeEdge HazardGuard - Industrial Monitoring",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load and inject dark slate CSS
STYLES_FILE = PROJECT_ROOT / "styles.css"
if STYLES_FILE.exists():
    with open(STYLES_FILE, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def init_session_state():
    """Initializes rolling history and event log in session state."""
    sim = get_simulator()

    if "telemetry_history" not in st.session_state:
        # Pre-seed last 60 readings with realistic baseline values matching mockups
        history = {}
        for key, spec in sim.params_spec.items():
            val = spec["default"]
            drift = spec["drift"]
            vals = []
            for _ in range(60):
                val += random.uniform(-drift, drift)
                val = max(spec["min"], min(spec["max"], val))
                vals.append(round(val, 1))
            history[key] = vals
        st.session_state.telemetry_history = history

    if "event_log" not in st.session_state:
        # Initial event entries matching reference mockup
        st.session_state.event_log = [
            {"time": "14:32:08", "node": "GAS-01", "message": "Reading 8 ppm", "severity": "Normal"},
            {"time": "14:21:03", "node": "PM-03", "message": "Dust back to 30", "severity": "Cleared"},
            {"time": "14:18:41", "node": "PM-03", "message": "Dust 112 µg/m³", "severity": "Warning"},
            {"time": "13:56:27", "node": "MIC-04", "message": "Noise 88 dB", "severity": "Warning"},
        ]

    if "prev_statuses" not in st.session_state:
        st.session_state.prev_statuses = {k: "SAFE" for k in sim.params_spec}

    if "feed_mode" not in st.session_state:
        st.session_state.feed_mode = "Live sensor feed"

    # History page filters
    if "hist_time_range" not in st.session_state:
        st.session_state.hist_time_range = "24 h"
    if "hist_param" not in st.session_state:
        st.session_state.hist_param = "Gas"


init_session_state()


def main():
    # Sidebar matching reference mockups
    st.sidebar.markdown(
        """
        <div style="padding: 10px 0 16px 0;">
            <div style="font-size: 1.3rem; font-weight: 700; color: #f9fafb; letter-spacing: -0.02em;">
                SafeEdge<br/>HazardGuard
            </div>
            <div style="font-size: 0.82rem; color: #9ca3af; margin-top: 4px;">
                Industrial IoT Safety Cockpit
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    page = st.sidebar.radio(
        "Navigation",
        [
            "Complete Monitoring Cockpit",
            "Live Hazard Simulator",
            "History, Trends & Reports",
            "Gas Thresholds & Protocols",
        ],
        index=0,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style="font-size: 0.82rem; color: #9ca3af; line-height: 1.6;">
            <div style="font-weight: 700; text-transform: uppercase; font-size: 0.74rem; letter-spacing: 0.05em; color: #d1d5db; margin-bottom: 8px;">
                IoT hardware
            </div>
            <div style="color: #e5e7eb;">GAS-01 MQ-135</div>
            <div style="color: #e5e7eb;">DHT-02 DHT22</div>
            <div style="color: #e5e7eb;">PM-03 PMS5003</div>
            <div style="color: #e5e7eb;">MIC-04 Sound</div>
            <div style="margin-top: 14px; color: #0ca30c; font-weight: 600; display: flex; align-items: center; gap: 6px;">
                <span style="font-size: 1.1rem; line-height: 0;">●</span> Hardware: online
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if page == "Complete Monitoring Cockpit":
        render_cockpit_page()
    elif page == "Live Hazard Simulator":
        render_simulator_page()
    elif page == "History, Trends & Reports":
        render_history_reports_page()
    elif page == "Gas Thresholds & Protocols":
        render_gas_protocols_page()


# -----------------------------------------------------------------------------
# 1. Complete Monitoring Cockpit (Page 1)
# -----------------------------------------------------------------------------

@st.fragment(run_every="2s")
def render_live_telemetry_grid():
    """
    Auto-refreshing fragment simulating real IoT streaming telemetry.
    Refreshes every 2 seconds without full page reload.
    """
    sim = get_simulator()
    telemetry = sim.read_sensors()
    readings = telemetry["readings"]
    now_str = datetime.now().strftime("%H:%M:%S")

    # Update rolling 60 readings history
    for k, r in readings.items():
        st.session_state.telemetry_history[k].append(r["value"])
        if len(st.session_state.telemetry_history[k]) > 60:
            st.session_state.telemetry_history[k].pop(0)

        # Check for threshold state transitions to log events
        prev_s = st.session_state.prev_statuses.get(k, "SAFE")
        new_s = r["status"]
        if new_s != prev_s:
            st.session_state.prev_statuses[k] = new_s
            node_id = r["node"]
            if new_s == "SAFE" and prev_s in ("WARNING", "DANGER"):
                sev_label = "Cleared"
                msg = f"{r['name']} normalized to {r['value']} {r['unit']}"
            elif new_s == "WARNING":
                sev_label = "Warning"
                msg = f"{r['name']} elevated to {r['value']} {r['unit']}"
            elif new_s == "DANGER":
                sev_label = "Danger"
                msg = f"CRITICAL: {r['name']} at {r['value']} {r['unit']}"
            else:
                sev_label = "Normal"
                msg = f"{r['name']} reading {r['value']} {r['unit']}"

            st.session_state.event_log.insert(
                0,
                {"time": now_str, "node": node_id, "message": msg, "severity": sev_label},
            )
            if len(st.session_state.event_log) > 100:
                st.session_state.event_log.pop()

    # 1. Top Status Bar
    render_status_bar(
        site_status=telemetry["site_status"],
        danger_count=telemetry["danger_count"],
        warning_count=telemetry["warning_count"],
        safe_count=telemetry["safe_count"],
        total_count=telemetry["total_count"],
        updated_seconds_ago=random.randint(1, 2),
    )

    # 2. Grid of 5 Parameter Tiles + 1 Recommended Action (3 per row)
    # Row 1: Temperature, Humidity, Dust
    r1_col1, r1_col2, r1_col3 = st.columns(3)
    with r1_col1:
        render_parameter_card(
            readings["temperature"],
            st.session_state.telemetry_history["temperature"],
        )
    with r1_col2:
        render_parameter_card(
            readings["humidity"],
            st.session_state.telemetry_history["humidity"],
        )
    with r1_col3:
        render_parameter_card(
            readings["dust"],
            st.session_state.telemetry_history["dust"],
        )

    # Row 2: Noise, Gas, Recommended action
    r2_col1, r2_col2, r2_col3 = st.columns(3)
    with r2_col1:
        render_parameter_card(
            readings["noise"],
            st.session_state.telemetry_history["noise"],
        )
    with r2_col2:
        render_parameter_card(
            readings["gas"],
            st.session_state.telemetry_history["gas"],
        )
    with r2_col3:
        render_recommended_action_card(telemetry["recommended_action"])

    # 3. Bottom Row: Sensor Nodes and Event Log
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        render_sensor_nodes_table(telemetry["nodes"])
    with b_col2:
        render_event_log_table(st.session_state.event_log)


def render_cockpit_page():
    """Renders the Complete Monitoring Cockpit page matching reference mockup."""
    render_live_telemetry_grid()

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # Collapsible Demo Controls & Manual Override Panel
    with st.expander("Demo Controls & Manual Override Panel", expanded=False):
        st.markdown(
            """
            <div style="font-size: 0.85rem; color: #9ca3af; margin-bottom: 12px;">
                Simulate critical site events, inject sensor spikes, or manually override IoT parameters to verify system responses.
            </div>
            """,
            unsafe_allow_html=True,
        )

        sim = get_simulator()

        # Preset buttons
        st.markdown("**Scenario Presets:**")
        p_cols = st.columns(6)
        preset_names = ["All Safe", "Dust & Noise", "Gas Leak Danger", "Heat Stress", "Multi-Hazard", "Reset"]

        for idx, p_name in enumerate(preset_names):
            with p_cols[idx]:
                if st.button(p_name, use_container_width=True, key=f"btn_p_{idx}"):
                    if p_name == "Reset":
                        sim.clear_override()
                        st.session_state.feed_mode = "Live sensor feed"
                    else:
                        preset_data = SCENARIOS[p_name]
                        overrides = {
                            k: preset_data[k] for k in ["temperature", "humidity", "dust", "noise", "gas"]
                        }
                        sim.set_override(overrides)
                        st.session_state.feed_mode = "Manual Override"
                    st.rerun()

        st.markdown("---")
        st.markdown("**Manual Parameter Sliders:**")
        s_cols = st.columns(5)
        cur_vals = sim.current_values

        new_overrides = {}
        with s_cols[0]:
            t_val = st.slider("Temp (°C)", 0.0, 50.0, float(cur_vals["temperature"]), 0.5)
            new_overrides["temperature"] = t_val
        with s_cols[1]:
            h_val = st.slider("Humidity (%)", 0.0, 100.0, float(cur_vals["humidity"]), 1.0)
            new_overrides["humidity"] = h_val
        with s_cols[2]:
            d_val = st.slider("Dust (µg/m³)", 0.0, 250.0, float(cur_vals["dust"]), 1.0)
            new_overrides["dust"] = d_val
        with s_cols[3]:
            n_val = st.slider("Noise (dB)", 40.0, 110.0, float(cur_vals["noise"]), 0.5)
            new_overrides["noise"] = n_val
        with s_cols[4]:
            g_val = st.slider("Gas (ppm)", 0.0, 60.0, float(cur_vals["gas"]), 0.5)
            new_overrides["gas"] = g_val

        act_col1, act_col2 = st.columns([1, 4])
        with act_col1:
            if st.button("Apply Sliders", use_container_width=True, type="primary"):
                sim.set_override(new_overrides)
                st.session_state.feed_mode = "Manual Override"
                st.rerun()
        with act_col2:
            if sim.override_active:
                if st.button("Return to Live Sensor Feed", use_container_width=False):
                    sim.clear_override()
                    st.session_state.feed_mode = "Live sensor feed"
                    st.rerun()


# -----------------------------------------------------------------------------
# 2. Live Hazard Simulator (Page 2 - Matching Image 3)
# -----------------------------------------------------------------------------

def render_simulator_page():
    """Renders Page 2: Live Hazard Simulator matching Image 3 reference."""
    st.markdown('<div class="page-header-title">Live Hazard Simulator</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-header-subtitle">Real-time sensor telemetry drift and stress-test simulation laboratory.</div>',
        unsafe_allow_html=True,
    )

    sim = get_simulator()
    telemetry = sim.read_sensors()
    readings = telemetry["readings"]

    # If critical hazard exists, display prominent alert banner matching Image 3
    if telemetry["site_status"] == "critical":
        gas_stat = readings["gas"]["status"]
        if gas_stat == "DANGER":
            banner_title = "Critical hazard: gas concentration above 50 ppm"
            banner_body = "Mandatory evacuation and SCBA. Isolate the source, shut the ventilation intake and notify the safety officer."
        else:
            banner_title = f"Critical hazard: {telemetry['recommended_action']['headline']}"
            banner_body = "Evacuate affected zones immediately and alert site safety commanders."
        render_hazard_alert_banner(banner_title, banner_body)
    elif telemetry["site_status"] == "warning":
        render_hazard_alert_banner(
            "Elevated Warning Threshold Exceeded",
            telemetry["recommended_action"]["headline"],
        )

    # Parameter Selector for Live Stream Inspection
    param_keys = ["gas", "dust", "temperature", "noise", "humidity"]
    param_labels = {
        "gas": "GAS-01 · Gas Concentration (ppm)",
        "dust": "PM-03 · Dust PM10 (µg/m³)",
        "temperature": "DHT-02 · Temperature (°C)",
        "noise": "MIC-04 · Noise Level (dB)",
        "humidity": "DHT-02 · Relative Humidity (%)",
    }

    sel_p = st.selectbox(
        "Select Active Telemetry Channel:",
        param_keys,
        format_func=lambda k: param_labels[k],
        index=0,
    )

    cur_p = readings[sel_p]
    hist_vals = st.session_state.telemetry_history[sel_p]

    # Chart Container matching Image 3
    chart_title = f"{cur_p['node']} · {cur_p['name'].upper()} ({cur_p['unit']}) · LAST 60 READINGS"
    st.markdown(f'<div class="bottom-panel-title" style="margin-top: 10px;">{chart_title}</div>', unsafe_allow_html=True)

    # Plotly Real-Time Trend with Warning & Danger dashed lines
    x_seconds = [f"-{60 - i} s" if i < 59 else "now" for i in range(len(hist_vals))]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_seconds,
            y=hist_vals,
            mode="lines",
            line=dict(color="#2a78d6", width=2.5),
            name=cur_p["name"],
        )
    )

    # Warning threshold dashed line (amber)
    fig.add_hline(
        y=cur_p["warn"],
        line_dash="dash",
        line_color="#fab219",
        line_width=1.5,
        annotation_text=f"Warning {cur_p['warn']:g}",
        annotation_position="top right",
        annotation_font=dict(color="#fab219", size=11),
    )

    # Danger threshold dashed line (red)
    fig.add_hline(
        y=cur_p["danger"],
        line_dash="dash",
        line_color="#d03b3b",
        line_width=1.5,
        annotation_text=f"Danger {cur_p['danger']:g}",
        annotation_position="top right",
        annotation_font=dict(color="#d03b3b", size=11),
    )

    # Mark current live point with dot
    if hist_vals:
        fig.add_trace(
            go.Scatter(
                x=[x_seconds[-1]],
                y=[hist_vals[-1]],
                mode="markers",
                marker=dict(
                    color="#d03b3b" if cur_p["status"] == "DANGER" else "#fab219" if cur_p["status"] == "WARNING" else "#0ca30c",
                    size=8,
                ),
                showlegend=False,
            )
        )

    fig.update_layout(
        paper_bgcolor="#1f2937",
        plot_bgcolor="#111827",
        font=dict(color="#f9fafb", family="Inter"),
        height=320,
        margin=dict(l=30, r=30, t=20, b=30),
        xaxis=dict(showgrid=False, color="#9ca3af"),
        yaxis=dict(gridcolor="#1f2937", color="#9ca3af"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Interactive Scenario Controls
    st.markdown("---")
    st.markdown("**Inject Stress-Test Scenarios:**")
    sc_cols = st.columns(6)
    sc_list = ["All Safe", "Dust & Noise", "Gas Leak Danger", "Heat Stress", "Multi-Hazard", "Reset"]
    for idx, s_name in enumerate(sc_list):
        with sc_cols[idx]:
            if st.button(s_name, key=f"sim_sc_{idx}", use_container_width=True):
                if s_name == "Reset":
                    sim.clear_override()
                else:
                    sim.set_override(SCENARIOS[s_name])
                st.rerun()


# -----------------------------------------------------------------------------
# 3. History, Trends and Reports (Page 3 - Matching Image 2)
# -----------------------------------------------------------------------------

def render_history_reports_page():
    """Renders Page 3: History, trends and reports matching Image 2 reference."""
    st.markdown('<div class="page-header-title">History, trends and reports</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-header-subtitle">Review past readings, spot patterns and export compliance reports.</div>',
        unsafe_allow_html=True,
    )

    # Filter Bar matching Image 2: Time Ranges on Left, Parameters on Right
    bar_col1, bar_col2 = st.columns([1, 1.4])

    with bar_col1:
        st.markdown("**Time Window:**")
        t_cols = st.columns(4)
        time_options = ["1 h", "6 h", "24 h", "7 d"]
        for i, topt in enumerate(time_options):
            with t_cols[i]:
                is_selected = st.session_state.hist_time_range == topt
                btn_type = "primary" if is_selected else "secondary"
                if st.button(topt, key=f"btn_tr_{i}", type=btn_type, use_container_width=True):
                    st.session_state.hist_time_range = topt
                    st.rerun()

    with bar_col2:
        st.markdown("**Select Parameter:**")
        p_cols = st.columns(5)
        param_options = ["Temperature", "Humidity", "Dust", "Noise", "Gas"]
        for j, popt in enumerate(param_options):
            with p_cols[j]:
                is_selected = st.session_state.hist_param == popt
                btn_type = "primary" if is_selected else "secondary"
                if st.button(popt, key=f"btn_hp_{j}", type=btn_type, use_container_width=True):
                    st.session_state.hist_param = popt
                    st.rerun()

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    sim = get_simulator()
    param_key = st.session_state.hist_param.lower()
    spec = sim.params_spec.get(param_key, sim.params_spec["gas"])
    history_vals = st.session_state.telemetry_history.get(param_key, [spec["default"]])

    min_v = min(history_vals) if history_vals else 0.0
    avg_v = round(sum(history_vals) / len(history_vals), 1) if history_vals else 0.0
    max_v = max(history_vals) if history_vals else 0.0

    # Calculate count of threshold warnings
    alerts_count = sum(1 for v in history_vals if v >= spec["warn"])

    # 1. KPI Stats Cards (Minimum, Average, Maximum, Alerts)
    render_kpi_cards(
        min_val=min_v,
        avg_val=avg_v,
        max_val=max_v,
        alerts_count=alerts_count,
        unit=spec["unit"],
    )

    # 2. Main Trend Line Chart matching Image 2
    chart_header = f"{spec['name'].upper()} ({spec['unit'].upper()}) · LAST {st.session_state.hist_time_range.upper()}"
    st.markdown(f'<div class="bottom-panel-title" style="margin-top: 14px;">{chart_header}</div>', unsafe_allow_html=True)

    # Time series points across 24h
    now = datetime.now()
    timestamps = [now - timedelta(minutes=(len(history_vals) - 1 - i) * 24) for i in range(len(history_vals))]
    time_strs = [t.strftime("%H:%M") for t in timestamps]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=time_strs,
            y=history_vals,
            mode="lines",
            line=dict(color="#2a78d6", width=2.5),
            name=spec["name"],
        )
    )

    # Dashed threshold lines
    fig.add_hline(
        y=spec["danger"],
        line_dash="dash",
        line_color="#d03b3b",
        line_width=1.5,
    )
    fig.add_hline(
        y=spec["warn"],
        line_dash="dash",
        line_color="#fab219",
        line_width=1.5,
    )

    # Add peak callout matching Image 2
    if history_vals:
        peak_idx = history_vals.index(max_v)
        fig.add_annotation(
            x=time_strs[peak_idx],
            y=max_v,
            text=f"Peak {max_v:g} {spec['unit']} at {time_strs[peak_idx]}",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1.5,
            arrowcolor="#fab219",
            ax=40,
            ay=-30,
            font=dict(color="#fab219", size=11, family="Inter"),
            bgcolor="#1f2937",
            bordercolor="#fab219",
            borderwidth=1,
            borderpad=4,
        )

    fig.update_layout(
        paper_bgcolor="#1f2937",
        plot_bgcolor="#111827",
        font=dict(color="#f9fafb", family="Inter"),
        height=320,
        margin=dict(l=30, r=30, t=20, b=30),
        xaxis=dict(showgrid=False, color="#9ca3af", nticks=6),
        yaxis=dict(gridcolor="#1f2937", color="#9ca3af"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # 3. Parameter Summary Table matching Image 2
    summary_rows = []
    for k in ["temperature", "humidity", "dust", "noise", "gas"]:
        s = sim.params_spec[k]
        vals = st.session_state.telemetry_history.get(k, [s["default"]])
        mn = min(vals) if vals else s["default"]
        av = round(sum(vals) / len(vals), 1) if vals else s["default"]
        mx = max(vals) if vals else s["default"]
        warn_cnt = sum(1 for v in vals if v >= s["warn"])
        cur_status = sim.evaluate_status(k, vals[-1] if vals else s["default"])
        summary_rows.append({
            "param": f"{s['name']} ({s['unit']})",
            "min": f"{mn:g}",
            "avg": f"{av:g}",
            "max": f"{mx:g}",
            "warnings": warn_cnt,
            "status": "Safe" if cur_status == "SAFE" else "Warning" if cur_status == "WARNING" else "Danger",
        })

    render_parameter_summary_table(summary_rows, time_window=st.session_state.hist_time_range.upper())

    # Action Buttons: Download CSV and Generate PDF Report
    btn_col1, btn_col2, _ = st.columns([1.2, 1.4, 3])
    with btn_col1:
        # Download CSV
        hist_df = pd.DataFrame(st.session_state.telemetry_history)
        csv_data = hist_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name=f"safeedge_telemetry_{st.session_state.hist_time_range}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with btn_col2:
        # Generate PDF / Formatted Text Report
        report_text = f"""SafeEdge HazardGuard — Compliance Inspection Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Time Window: {st.session_state.hist_time_range}
Status: Online

Parameter Summary:
"""
        for r in summary_rows:
            report_text += f"- {r['param']}: Min={r['min']}, Avg={r['avg']}, Max={r['max']}, Warnings={r['warnings']}, Status={r['status']}\n"

        st.download_button(
            label="Generate PDF report",
            data=report_text.encode("utf-8"),
            file_name=f"safeedge_compliance_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            use_container_width=True,
        )


# -----------------------------------------------------------------------------
# 4. Gas Thresholds and Protocols (Page 4 - Matching Image 1)
# -----------------------------------------------------------------------------

def render_gas_protocols_page():
    """Renders Page 4: Gas thresholds and protocols matching Image 1 reference."""
    st.markdown('<div class="page-header-title">Gas thresholds and protocols</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-header-subtitle">Alert limits and the response required at each level.</div>',
        unsafe_allow_html=True,
    )

    # 1. ALERT THRESHOLDS Table (Image 1 top card)
    render_alert_thresholds_table()

    # 2. Three Protocol Action Boxes (Normal, Warning, Danger) (Image 1 middle row)
    render_protocol_action_boxes()

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # 3. Protective Equipment and Emergency Contacts (Image 1 bottom cards)
    render_protective_and_emergency_contacts()


if __name__ == "__main__":
    main()

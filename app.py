"""
Streamlit dashboard for the Greencell voltage-analysis assignment.

Local run:   streamlit run app.py
Deployment:  see README.md (Streamlit Community Cloud / Render / Hugging Face)
"""

import io
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

import analysis

st.set_page_config(page_title="Voltage Analysis | Greencell Assignment",
                   page_icon="⚡", layout="wide")

C_RAW, C_MA1, C_MA2, C_MA3 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
C_PEAK, C_LOW, C_ACCEL = "#4a3aa7", "#e34948", "#e87ba4"


@st.cache_data(show_spinner="Loading and analysing the data…")
def run(threshold: float, prominence: float):
    analysis.PROMINENCE = prominence
    raw = analysis.load_data()
    minute = analysis.build_minute_series(raw)
    minute, raw = analysis.add_moving_averages(minute, raw)
    tp = analysis.find_turning_points(minute)
    cycles = analysis.cycle_table(tp)
    slope = analysis.slope_series(minute)
    accel = analysis.find_slope_acceleration(minute, tp, slope)
    episodes = analysis.threshold_episodes(raw, threshold)
    trend, lin_slope, _ = analysis.linear_trend(minute)
    return raw, minute, tp, cycles, slope, accel, episodes, trend, lin_slope


# ----------------------------- sidebar --------------------------------------
st.sidebar.title("Controls")
threshold = st.sidebar.slider("Low-voltage threshold (V)", 15.0, 60.0, 20.0, 1.0,
                              help="The assignment asks for 20 V. Raise it to see "
                                   "how the detector behaves on this data.")
prominence = st.sidebar.slider("Turning-point sensitivity (V of prominence)",
                               2.0, 30.0, 10.0, 1.0,
                               help="How far a local high/low must stand out from "
                                    "its neighbours to be counted.")
show = st.sidebar.multiselect(
    "Series on the main chart",
    ["Voltage", "60-min MA", "1000-sample MA", "5000-sample MA", "5-day MA",
     "Linear trendline", "Peaks", "Lows", "Acceleration onsets"],
    default=["Voltage", "1000-sample MA", "Linear trendline", "Peaks", "Lows"])

raw, minute, tp, cycles, slope, accel, episodes, trend, lin_slope = run(
    threshold, prominence)

date_min = minute.index.min().to_pydatetime()
date_max = minute.index.max().to_pydatetime()
window = st.sidebar.slider("Time window", date_min, date_max,
                           (date_min, date_max), format="DD MMM HH:mm")
m = minute.loc[window[0]:window[1]]
r = raw[(raw["Timestamp"] >= window[0]) & (raw["Timestamp"] <= window[1])]

# ----------------------------- header ---------------------------------------
st.title("⚡ Voltage data — visualisation and interpretation")
st.caption("Greencell internship assignment · data 26 Jun – 03 Jul 2024 · "
           f"{len(raw):,} readings")

k = st.columns(6)
k[0].metric("Readings", f"{len(r):,}")
k[1].metric("Min voltage", f"{r['Voltage'].min():.0f} V")
k[2].metric("Max voltage", f"{r['Voltage'].max():.0f} V")
k[3].metric("Mean voltage", f"{r['Voltage'].mean():.1f} V")
k[4].metric("Discharge cycles", f"{len(cycles)}")
k[5].metric(f"Instances below {threshold:.0f} V", f"{len(episodes)}")

# ----------------------------- main chart -----------------------------------
fig = go.Figure()
if "Voltage" in show:
    fig.add_trace(go.Scatter(x=m.index, y=m["Voltage"], name="Voltage",
                             line=dict(color=C_RAW, width=1)))
if "60-min MA" in show:
    fig.add_trace(go.Scatter(x=m.index, y=m["MA_60min"], name="60-min MA",
                             line=dict(color="#4a3aa7", width=2)))
if "1000-sample MA" in show:
    fig.add_trace(go.Scatter(x=r["Timestamp"], y=r["MA_1000_samples"],
                             name="1000-sample MA", line=dict(color=C_MA1, width=2)))
if "5000-sample MA" in show:
    fig.add_trace(go.Scatter(x=r["Timestamp"], y=r["MA_5000_samples"],
                             name="5000-sample MA", line=dict(color=C_MA2, width=2)))
if "5-day MA" in show:
    fig.add_trace(go.Scatter(x=m.index, y=m["MA_5day"], name="5-day MA",
                             line=dict(color=C_MA3, width=2.5)))
if "Linear trendline" in show:
    fig.add_trace(go.Scatter(x=m.index, y=trend.loc[m.index], name="Linear trendline",
                             line=dict(color=C_LOW, width=2, dash="dash")))
tpw = tp[(tp["Timestamp"] >= window[0]) & (tp["Timestamp"] <= window[1])]
if "Peaks" in show:
    pk = tpw[tpw["Type"].str.startswith("Peak")]
    fig.add_trace(go.Scatter(x=pk["Timestamp"], y=pk["Voltage"], mode="markers",
                             name=f"Peaks ({len(pk)})",
                             marker=dict(color=C_PEAK, size=10,
                                         line=dict(color="#ffffff", width=1.5))))
if "Lows" in show:
    lo = tpw[tpw["Type"].str.startswith("Low")]
    fig.add_trace(go.Scatter(x=lo["Timestamp"], y=lo["Voltage"], mode="markers",
                             name=f"Lows ({len(lo)})",
                             marker=dict(color=C_LOW, size=10, symbol="triangle-down",
                                         line=dict(color="#ffffff", width=1.5))))
if "Acceleration onsets" in show and not accel.empty:
    aw = accel[(accel["Acceleration starts"] >= window[0]) &
               (accel["Acceleration starts"] <= window[1])]
    fig.add_trace(go.Scatter(x=aw["Acceleration starts"], y=aw["Voltage at onset"],
                             mode="markers", name=f"Discharge accelerates ({len(aw)})",
                             marker=dict(color=C_ACCEL, size=9, symbol="x")))
fig.update_layout(height=560, hovermode="x unified", template="plotly_white",
                  xaxis_title="Timestamp", yaxis_title="Voltage (V)",
                  legend=dict(orientation="h", y=-0.16),
                  margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, width="stretch")

st.info(f"Linear trendline over the full record: **{lin_slope:+.2f} V/day** — "
        f"a net change of {lin_slope * len(minute) / 1440:+.1f} V across the week, "
        "i.e. effectively flat. The trend line is the wrong tool for a cyclic signal; "
        "the moving averages are what carry information here.")

# ----------------------------- tabs -----------------------------------------
t1, t2, t3, t4, t5 = st.tabs(["Peaks & lows", "Discharge cycles",
                              f"Below {threshold:.0f} V", "Slope acceleration",
                              "Interpretation"])

with t1:
    st.subheader(f"{len(tp)} local turning points")
    st.dataframe(tp, width="stretch", hide_index=True)

with t2:
    st.subheader(f"{len(cycles)} discharge cycles")
    st.dataframe(cycles, width="stretch", hide_index=True)
    c1, c2 = st.columns(2)
    h = go.Figure(go.Histogram(x=cycles["Drop (V)"], nbinsx=12,
                               marker_color=C_RAW))
    h.update_layout(title="Depth of discharge per cycle (V)", template="plotly_white",
                    height=320, margin=dict(l=10, r=10, t=40, b=10))
    c1.plotly_chart(h, width="stretch")
    h2 = go.Figure(go.Histogram(x=cycles["Duration (h)"], nbinsx=12,
                                marker_color=C_MA1))
    h2.update_layout(title="Duration of each discharge (hours)",
                     template="plotly_white", height=320,
                     margin=dict(l=10, r=10, t=40, b=10))
    c2.plotly_chart(h2, width="stretch")

with t3:
    st.subheader(f"Instances below {threshold:.0f} V")
    if episodes.empty:
        st.success(f"No instance below {threshold:.0f} V. The lowest reading in the "
                   f"whole record is {raw['Voltage'].min():.0f} V. Drag the threshold "
                   "slider above 25 V to see the detector fire.")
    else:
        st.dataframe(episodes, width="stretch", hide_index=True)

with t4:
    st.subheader(f"{len(accel)} episodes where the downward slope accelerates")
    st.caption("Inside each peak→low cycle: slope < 0 and the slope is becoming more "
               "negative, sustained for at least 15 minutes.")
    st.dataframe(accel, width="stretch", hide_index=True)
    sf = go.Figure()
    sw = slope.loc[window[0]:window[1]]
    sf.add_trace(go.Scatter(x=sw.index, y=sw, name="Slope (V/h)",
                            line=dict(color=C_MA2, width=1)))
    sf.add_hline(y=0, line_color="#52514e")
    sf.update_layout(title="Local slope of the voltage curve",
                     xaxis_title="Timestamp", yaxis_title="V per hour",
                     template="plotly_white", height=340,
                     margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(sf, width="stretch")

with t5:
    st.subheader("How to read this data")
    import build_excel
    for i, s in enumerate(build_excel.interpretation_sentences(
            dict(raw=raw, cycles=cycles, tp=tp, accel=accel, minute=minute)), 1):
        st.markdown(f"**{i}.** {s}")

# ----------------------------- downloads ------------------------------------
st.sidebar.divider()
st.sidebar.subheader("Download results")
for name, frame in [("local_peaks_and_lows.csv", tp),
                    ("discharge_cycles.csv", cycles),
                    (f"below_{int(threshold)}V_instances.csv", episodes),
                    ("slope_acceleration.csv", accel)]:
    st.sidebar.download_button(name, frame.to_csv(index=False).encode(),
                               file_name=name, mime="text/csv",
                               width="stretch")

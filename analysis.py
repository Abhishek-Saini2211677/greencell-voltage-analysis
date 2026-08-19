"""
Greencell Internship Assignment - Data Visualisation & Interpretation
=====================================================================
Voltage time-series analysis.

Pipeline
--------
 1. Load + clean the raw CSV (parse timestamps, sort, collapse intra-minute
    duplicates, build a gap-aware regular 1-minute series).
 2. Plot voltage vs time (matplotlib static + Plotly interactive).
 3. Moving averages: the assignment's 5-day window, plus the 1000/5000-sample
    windows shown in the annexure figure and a readable 60-minute window.
 4. Local peaks and lows -> tabulated to CSV.
 5. Every instance the voltage drops below a threshold -> tabulated to CSV.
 6. BONUS: every point in each downward cycle where the downward slope
    accelerates (voltage falling faster than it was) -> tabulated + printed.

Run:  python analysis.py
Outputs: figures/*.png, figures/*.html, outputs/*.csv
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.signal import find_peaks

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
DATA_FILE = os.path.join("data", "Sample_Data.csv")
FIG_DIR, OUT_DIR = "figures", "outputs"

LOW_VOLTAGE_THRESHOLD = 20.0   # assignment requirement
DIAGNOSTIC_THRESHOLD = 30.0    # used to show the method works on this data

# Palette (validated categorical order: blue, orange, aqua, yellow, magenta, red)
C_RAW, C_MA1, C_MA2, C_MA3 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
C_PEAK, C_LOW, C_ACCEL = "#4a3aa7", "#e34948", "#e87ba4"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#dcdcd8"

GAP_MINUTES = 5          # a jump larger than this is treated as a data gap
SMOOTH_WINDOW = 15       # minutes, median smoothing used for shape detection
PROMINENCE = 10.0        # volts a turning point must stand out by
MIN_SEPARATION = 120     # minutes between two accepted turning points
SLOPE_WINDOW = 31        # minutes, centred window for the local slope estimate

os.makedirs(FIG_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)


# --------------------------------------------------------------------------
# 1. Load and clean
# --------------------------------------------------------------------------
def load_data(path: str = DATA_FILE) -> pd.DataFrame:
    """Read the CSV, parse the day-first timestamps and sort chronologically."""
    df = pd.read_csv(path)
    df = df.rename(columns={"Values": "Voltage"})
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%d-%m-%Y %H:%M")
    df["Voltage"] = pd.to_numeric(df["Voltage"], errors="coerce")
    df = df.dropna(subset=["Timestamp", "Voltage"])
    # The supplied file happens to already be in date order, but parsing the
    # column as a real datetime and sorting on it is what guarantees it - and it
    # is what stops a chart from putting the x-axis in text order (which is how
    # the annexure figure ends up starting at 01-07 and jumping back to 26-06).
    return df.sort_values("Timestamp", kind="mergesort").reset_index(drop=True)


def build_minute_series(df: pd.DataFrame) -> pd.DataFrame:
    """
    Logger writes several readings per minute (timestamps truncated to minutes),
    so collapse each minute to its mean, then reindex onto a strict 1-minute
    grid. Real recording gaps stay as NaN instead of being interpolated across.

    Only holes whose WHOLE length is <= GAP_MINUTES are bridged. Note that
    Series.interpolate(limit=n) would instead fill the first n minutes of every
    outage, however long - which invents data at the edge of each gap.
    """
    per_min = df.groupby("Timestamp", as_index=True)["Voltage"].mean()
    full_idx = pd.date_range(per_min.index.min(), per_min.index.max(), freq="1min")
    s = per_min.reindex(full_idx)

    filled = s.interpolate(limit_area="inside")          # everything, then undo
    isna = s.isna()
    run_id = (isna != isna.shift()).cumsum()
    run_len = isna.groupby(run_id).transform("size")
    bridge = isna & (run_len <= GAP_MINUTES) & filled.notna()
    s = s.where(~bridge, filled)

    out = s.to_frame("Voltage")
    out.index.name = "Timestamp"
    return out


def valid_segments(minute: pd.DataFrame) -> list[pd.Series]:
    """Split the minute series into contiguous runs of recorded data."""
    v = minute["Voltage"]
    isna = v.isna()
    seg_id = (isna != isna.shift()).cumsum()
    return [g for _, g in v.groupby(seg_id) if g.notna().all()]


def data_quality_report(df: pd.DataFrame, minute: pd.DataFrame) -> pd.DataFrame:
    raw_gaps = df["Timestamp"].diff().dt.total_seconds().div(60)
    rows = [
        ("Raw rows in file", len(df)),
        ("Distinct timestamps (minute resolution)", df["Timestamp"].nunique()),
        ("Readings per minute (mean)", round(len(df) / df["Timestamp"].nunique(), 2)),
        ("Readings per minute (median)",
         float(df.groupby("Timestamp").size().median())),
        ("First reading", df["Timestamp"].min()),
        ("Last reading", df["Timestamp"].max()),
        ("Span covered", str(df["Timestamp"].max() - df["Timestamp"].min())),
        ("Minimum voltage", df["Voltage"].min()),
        ("Maximum voltage", df["Voltage"].max()),
        ("Mean voltage", round(df["Voltage"].mean(), 2)),
        ("Std deviation", round(df["Voltage"].std(), 2)),
        (f"Gaps longer than {GAP_MINUTES} min", int((raw_gaps > GAP_MINUTES).sum())),
        ("Longest gap (min)", round(float(raw_gaps.max()), 1)),
        ("Minutes on 1-min grid", len(minute)),
        ("Minutes with no data (kept as NaN)", int(minute["Voltage"].isna().sum())),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value"])


# --------------------------------------------------------------------------
# 3. Moving averages
# --------------------------------------------------------------------------
def add_moving_averages(minute: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    m = minute.copy()
    # Assignment requirement: 5-day moving average (7200 minutes).
    m["MA_5day"] = m["Voltage"].rolling("5D", min_periods=2880).mean()
    # Readable trend line for a ~7-day record.
    m["MA_60min"] = m["Voltage"].rolling(60, min_periods=10).mean()
    m["MA_6hr"] = m["Voltage"].rolling(360, min_periods=30).mean()
    # Sample-count windows used in the annexure figure, on the raw sample order.
    raw = raw.copy()
    raw["MA_1000_samples"] = raw["Voltage"].rolling(1000, min_periods=1).mean()
    raw["MA_5000_samples"] = raw["Voltage"].rolling(5000, min_periods=1).mean()
    return m, raw


# --------------------------------------------------------------------------
# 4. Local peaks and lows
# --------------------------------------------------------------------------
def find_turning_points(minute: pd.DataFrame) -> pd.DataFrame:
    """
    Detect local maxima (end of charge) and local minima (end of discharge).

    Smoothing first stops the 1-volt logger quantisation from producing
    hundreds of meaningless micro-peaks; the reported value/timestamp is then
    snapped back to the true extremum in the raw neighbourhood.
    """
    # Detection runs on the RECORDED minutes only (NaNs dropped, timestamps
    # kept). Filling the gaps with a constant - the obvious shortcut - makes
    # find_peaks measure prominence against a fabricated plateau, and every gap
    # edge then scores as a turning point. Dropping them means prominence is
    # always measured against real neighbouring readings.
    rec = minute["Voltage"].dropna()
    if len(rec) < 3:
        return pd.DataFrame(columns=["No.", "Timestamp", "Voltage", "Type", "Note"])

    smooth = rec.rolling(SMOOTH_WINDOW, center=True, min_periods=3).median()
    v = smooth.to_numpy(dtype=float)
    hi, _ = find_peaks(v, prominence=PROMINENCE, distance=MIN_SEPARATION)
    lo, _ = find_peaks(-v, prominence=PROMINENCE, distance=MIN_SEPARATION)

    # Positions where the recorded series jumps over an outage.
    step = rec.index.to_series().diff().dt.total_seconds().div(60).to_numpy()
    gap_after = np.where(step[1:] > GAP_MINUTES)[0]      # index i -> gap i..i+1
    gap_edges = set(gap_after.tolist()) | set((gap_after + 1).tolist())

    rows = []
    for idx, kind in [(hi, "Peak (local high)"), (lo, "Low (local minimum)")]:
        for i in idx:
            a, b = max(0, i - SMOOTH_WINDOW), min(len(rec), i + SMOOTH_WINDOW + 1)
            window = rec.iloc[a:b]
            j = window.idxmax() if kind.startswith("Peak") else window.idxmin()
            # Flag only if the outage touches the extremum itself, i.e. the
            # reading immediately before or after it is across a gap - that is
            # the case where the true turn may have happened unobserved.
            pos = rec.index.get_loc(j)
            near_gap = pos in gap_edges
            rows.append({"Timestamp": j, "Voltage": float(window.loc[j]),
                         "Type": kind,
                         "Note": "next to a data gap" if near_gap else ""})

    if not rows:
        return pd.DataFrame(columns=["No.", "Timestamp", "Voltage", "Type", "Note"])
    tp = pd.DataFrame(rows).sort_values("Timestamp").reset_index(drop=True)
    tp = tp.drop_duplicates(subset=["Timestamp", "Type"])
    tp.insert(0, "No.", range(1, len(tp) + 1))
    return tp


def cycle_table(tp: pd.DataFrame, verbose: bool = False) -> pd.DataFrame:
    """
    Pair each peak with the low that follows it: one row per discharge cycle.

    A peak with no low after it before the next peak is skipped - that happens
    when the discharge ran into a logger outage - and `verbose` reports how many
    peaks were dropped, so the cycle count is never silently short.
    """
    rows, skipped, seq = [], [], tp.to_dict("records")
    for i, a in enumerate(seq):
        if not a["Type"].startswith("Peak"):
            continue
        nxt = seq[i + 1] if i + 1 < len(seq) else None
        if nxt is None or not nxt["Type"].startswith("Low"):
            skipped.append(a["Timestamp"])
            continue
        dur_h = (nxt["Timestamp"] - a["Timestamp"]).total_seconds() / 3600
        drop = a["Voltage"] - nxt["Voltage"]
        rows.append({
            "Cycle": len(rows) + 1,
            "Peak time": a["Timestamp"], "Peak V": a["Voltage"],
            "Low time": nxt["Timestamp"], "Low V": nxt["Voltage"],
            "Drop (V)": round(drop, 1),
            "Duration (h)": round(dur_h, 2),
            "Avg rate (V/h)": round(-drop / dur_h, 2) if dur_h else np.nan,
        })
    if verbose and skipped:
        print(f"    note: {len(skipped)} peak(s) had no recorded low after them "
              f"(the discharge ran into a logger outage) and form no cycle row: "
              + ", ".join(t.strftime("%d-%m %H:%M") for t in skipped))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 5. Threshold crossings
# --------------------------------------------------------------------------
def threshold_episodes(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """
    Every instance the voltage went below `threshold`, grouped into continuous
    episodes (a single dip of 40 readings is one instance, not 40).
    """
    below = df["Voltage"] < threshold
    if not below.any():
        return pd.DataFrame(columns=["Instance", "Start", "End", "Duration (min)",
                                     "Minutes recorded", "Minimum V",
                                     "Time at minimum", "Readings"])
    grp = (below != below.shift()).cumsum()
    blocks = [blk for _, blk in df[below].groupby(grp[below])]
    # Merge blocks separated by less than a minute: the logger writes several
    # readings per minute and their order inside a minute is arbitrary, so one
    # physical dip can otherwise be split into two "instances".
    merged = []
    for blk in blocks:
        if merged and (blk["Timestamp"].iloc[0] -
                       merged[-1]["Timestamp"].iloc[-1]).total_seconds() <= 60:
            merged[-1] = pd.concat([merged[-1], blk])
        else:
            merged.append(blk)
    # A logger outage in the middle of a dip must not be counted as time spent
    # below the threshold - the voltage during an outage is simply unknown - so
    # split any block that contains a gap longer than GAP_MINUTES.
    split = []
    for blk in merged:
        gap = blk["Timestamp"].diff().dt.total_seconds().div(60) > GAP_MINUTES
        for _, part in blk.groupby(gap.cumsum()):
            split.append(part)
    rows = []
    for blk in split:
        recorded = blk["Timestamp"].nunique()
        rows.append({
            "Instance": len(rows) + 1,
            "Start": blk["Timestamp"].iloc[0],
            "End": blk["Timestamp"].iloc[-1],
            "Duration (min)": round(
                (blk["Timestamp"].iloc[-1] - blk["Timestamp"].iloc[0]).total_seconds() / 60, 1),
            "Minutes recorded": recorded,
            "Minimum V": float(blk["Voltage"].min()),
            "Time at minimum": blk.loc[blk["Voltage"].idxmin(), "Timestamp"],
            "Readings": len(blk),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 6. BONUS: downward-slope acceleration
# --------------------------------------------------------------------------
def slope_series(minute: pd.DataFrame) -> pd.Series:
    """Local slope in V/hour from a centred least-squares fit over SLOPE_WINDOW."""
    y = minute["Voltage"].astype(float)
    half = SLOPE_WINDOW // 2
    x = np.arange(-half, half + 1, dtype=float)          # minutes
    x -= x.mean()
    denom = (x ** 2).sum()
    vals = y.to_numpy()
    out = np.full(len(vals), np.nan)
    for i in range(half, len(vals) - half):
        seg = vals[i - half:i + half + 1]
        if np.isnan(seg).any():
            continue
        out[i] = (x * (seg - seg.mean())).sum() / denom * 60.0   # V per hour
    return pd.Series(out, index=minute.index, name="Slope_V_per_h")


MIN_BURST_MIN = 15        # an acceleration burst must last at least this long
MIN_STEEPENING = 2.0      # V/h the slope must steepen by to count


def find_slope_acceleration(minute: pd.DataFrame, tp: pd.DataFrame,
                            slope: pd.Series) -> pd.DataFrame:
    """
    Inside each downward cycle (peak -> following low), find every episode where
    the downward slope ACCELERATES: the voltage is already falling and the fall
    is getting steeper, i.e. slope < 0 and d(slope)/dt < 0.

    Each contiguous steepening episode is reported once, at its onset, so one
    physical event produces one row. Episodes shorter than MIN_BURST_MIN or that
    steepen by less than MIN_STEEPENING V/h are treated as logger noise.
    """
    curvature = slope.diff()                    # d(slope)/dt
    cycles = cycle_table(tp)
    rows = []
    for _, c in cycles.iterrows():
        seg = slope.loc[c["Peak time"]:c["Low time"]]
        seg_curv = curvature.loc[c["Peak time"]:c["Low time"]]
        falling_and_steepening = (seg < -0.5) & (seg_curv < 0)
        # Smooth the flag so 1-minute flickers do not split one episode in two.
        flag = falling_and_steepening.rolling(11, center=True, min_periods=1).mean() > 0.6
        if not flag.any():
            continue
        # Split the flag into contiguous True runs = distinct episodes.
        blocks = (flag != flag.shift()).cumsum()
        for _, blk in flag[flag].groupby(blocks[flag]):
            t0, t1 = blk.index[0], blk.index[-1]
            dur = (t1 - t0).total_seconds() / 60
            if dur < MIN_BURST_MIN:
                continue
            s0 = float(seg.loc[t0])
            s_min = float(seg.loc[t0:t1].min())
            if (s0 - s_min) < MIN_STEEPENING:
                continue
            rows.append({
                "Cycle": int(c["Cycle"]),
                "Acceleration starts": t0,
                "Acceleration ends": t1,
                "Duration (min)": round(dur, 0),
                "Voltage at onset": round(float(minute["Voltage"].loc[t0]), 1),
                "Slope at onset (V/h)": round(s0, 2),
                "Steepest slope reached (V/h)": round(s_min, 2),
                "Slope change (V/h)": round(s_min - s0, 2),
            })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("Acceleration starts").reset_index(drop=True)
        out.insert(0, "No.", range(1, len(out) + 1))
    return out


# --------------------------------------------------------------------------
# Plots
# --------------------------------------------------------------------------
def _style(ax):
    ax.set_facecolor("#fcfcfb")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.grid(True, color=GRID, linewidth=0.6, alpha=0.9)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))


def linear_trend(minute, raw=None):
    """
    Least-squares straight line - the same line Excel's linear trendline draws.

    Excel fits over the RAW readings, so when `raw` is supplied the fit uses
    those (matching the workbook's =SLOPE/=INTERCEPT exactly). Without it the
    fit falls back to the 1-minute series, which weights each minute equally
    and gives a slightly different slope.
    """
    if raw is not None:
        t0 = minute.index[0]
        x = (raw["Timestamp"] - t0).dt.total_seconds().to_numpy() / 86400.0
        y = raw["Voltage"].to_numpy(dtype=float)
    else:
        s = minute["Voltage"].dropna()
        t0 = minute.index[0]
        x = (s.index - t0).total_seconds().to_numpy() / 86400.0
        y = s.to_numpy()
    slope, intercept = np.polyfit(x, y, 1)
    xf = (minute.index - minute.index[0]).total_seconds().to_numpy() / 86400.0
    return pd.Series(slope * xf + intercept, index=minute.index), slope, intercept


def plot_basic(minute, path, raw=None):
    trend, slope, intercept = linear_trend(minute, raw)
    fig, ax = plt.subplots(figsize=(13, 5.5), dpi=160)
    ax.plot(minute.index, minute["Voltage"], color=C_RAW, lw=1.0, label="Voltage")
    ax.plot(minute.index, minute["MA_60min"], color=C_MA1, lw=2.0,
            label="Trend (60-min moving average)")
    ax.plot(minute.index, trend, color=C_LOW, lw=2.0, ls="--",
            label=f"Linear trendline ({slope:+.2f} V/day)")
    ax.set_title("Voltage over time", fontsize=14, color=INK, loc="left", pad=12)
    ax.set_xlabel("Timestamp", color=INK2)
    ax.set_ylabel("Voltage (V)", color=INK2)
    _style(ax)
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9, ncol=4,
              loc="upper center", bbox_to_anchor=(0.5, -0.14))
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_moving_averages(minute, raw, path):
    fig, ax = plt.subplots(figsize=(13, 5.5), dpi=160)
    ax.plot(minute.index, minute["Voltage"], color=C_RAW, lw=0.8, alpha=0.85,
            label="Voltage (1-min mean)")
    ax.plot(raw["Timestamp"], raw["MA_1000_samples"], color=C_MA1, lw=1.8,
            label="1000-sample moving average")
    ax.plot(raw["Timestamp"], raw["MA_5000_samples"], color=C_MA2, lw=2.0,
            label="5000-sample moving average")
    ax.plot(minute.index, minute["MA_5day"], color=C_MA3, lw=2.4,
            label="5-day moving average")
    ax.set_title("Voltage with moving averages", fontsize=14, color=INK,
                 loc="left", pad=12)
    ax.set_xlabel("Timestamp", color=INK2)
    ax.set_ylabel("Voltage (V)", color=INK2)
    _style(ax)
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9, ncol=4,
              loc="upper center", bbox_to_anchor=(0.5, -0.14))
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_turning_points(minute, tp, path):
    fig, ax = plt.subplots(figsize=(13, 5.5), dpi=160)
    ax.plot(minute.index, minute["Voltage"], color=C_RAW, lw=0.9, label="Voltage")
    pk = tp[tp["Type"].str.startswith("Peak")]
    lw_ = tp[tp["Type"].str.startswith("Low")]
    ax.scatter(pk["Timestamp"], pk["Voltage"], s=46, color=C_PEAK, zorder=5,
               edgecolor="#fcfcfb", linewidth=1.4, label=f"Local peaks ({len(pk)})")
    ax.scatter(lw_["Timestamp"], lw_["Voltage"], s=46, color=C_LOW, zorder=5,
               marker="v", edgecolor="#fcfcfb", linewidth=1.4,
               label=f"Local lows ({len(lw_)})")
    ax.set_title("Local peaks and lows", fontsize=14, color=INK, loc="left", pad=12)
    ax.set_xlabel("Timestamp", color=INK2)
    ax.set_ylabel("Voltage (V)", color=INK2)
    _style(ax)
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9, ncol=3,
              loc="upper center", bbox_to_anchor=(0.5, -0.14))
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_acceleration(minute, slope, accel_tbl, path):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 7.5), dpi=160, sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1]})
    ax1.plot(minute.index, minute["Voltage"], color=C_RAW, lw=0.9, label="Voltage")
    if not accel_tbl.empty:
        ax1.scatter(accel_tbl["Acceleration starts"], accel_tbl["Voltage at onset"],
                    s=34, color=C_ACCEL, zorder=5, edgecolor="#fcfcfb", linewidth=1.2,
                    label=f"Downward slope accelerates ({len(accel_tbl)})")
    ax1.set_title("Where the discharge accelerates", fontsize=14, color=INK,
                  loc="left", pad=12)
    ax1.set_ylabel("Voltage (V)", color=INK2)
    _style(ax1)
    ax1.legend(frameon=False, labelcolor=INK2, fontsize=9, ncol=2,
               loc="upper center", bbox_to_anchor=(0.5, -0.02))

    ax2.axhline(0, color=INK2, lw=1)
    ax2.plot(slope.index, slope, color=C_MA2, lw=1.0)
    ax2.set_ylabel("Slope (V/h)", color=INK2)
    ax2.set_xlabel("Timestamp", color=INK2)
    _style(ax2)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_interactive(minute, raw, tp, accel_tbl, path):
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=minute.index, y=minute["Voltage"], name="Voltage",
                             line=dict(color=C_RAW, width=1)))
    fig.add_trace(go.Scatter(x=raw["Timestamp"], y=raw["MA_1000_samples"],
                             name="1000-sample MA", line=dict(color=C_MA1, width=2)))
    fig.add_trace(go.Scatter(x=minute.index, y=minute["MA_5day"], name="5-day MA",
                             line=dict(color=C_MA3, width=2.5)))
    pk = tp[tp["Type"].str.startswith("Peak")]
    lo = tp[tp["Type"].str.startswith("Low")]
    fig.add_trace(go.Scatter(x=pk["Timestamp"], y=pk["Voltage"], mode="markers",
                             name="Local peaks",
                             marker=dict(color=C_PEAK, size=9,
                                         line=dict(color="#fcfcfb", width=1.5))))
    fig.add_trace(go.Scatter(x=lo["Timestamp"], y=lo["Voltage"], mode="markers",
                             name="Local lows",
                             marker=dict(color=C_LOW, size=9, symbol="triangle-down",
                                         line=dict(color="#fcfcfb", width=1.5))))
    if not accel_tbl.empty:
        fig.add_trace(go.Scatter(x=accel_tbl["Acceleration starts"],
                                 y=accel_tbl["Voltage at onset"], mode="markers",
                                 name="Discharge accelerates",
                                 marker=dict(color=C_ACCEL, size=7, symbol="x")))
    fig.update_layout(
        title="Voltage vs time - moving averages, turning points, acceleration",
        xaxis_title="Timestamp", yaxis_title="Voltage (V)",
        hovermode="x unified", template="plotly_white",
        plot_bgcolor="#fcfcfb", paper_bgcolor="#ffffff",
        legend=dict(orientation="h", y=-0.18), height=620,
    )
    fig.write_html(path, include_plotlyjs="cdn")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    raw = load_data()
    minute = build_minute_series(raw)
    quality = data_quality_report(raw, minute)

    print("\n=== 1. DATA QUALITY / SUMMARY ===")
    print(quality.to_string(index=False))

    minute, raw = add_moving_averages(minute, raw)

    tp = find_turning_points(minute)
    cycles = cycle_table(tp, verbose=True)
    print(f"\n=== 2. LOCAL PEAKS AND LOWS ({len(tp)} turning points) ===")
    print(tp.to_string(index=False))
    print(f"\n--- Discharge cycles ({len(cycles)}) ---")
    print(cycles.to_string(index=False))

    below20 = threshold_episodes(raw, LOW_VOLTAGE_THRESHOLD)
    print(f"\n=== 3. INSTANCES BELOW {LOW_VOLTAGE_THRESHOLD:.0f} V ===")
    if below20.empty:
        print(f"None. The minimum voltage in the whole record is "
              f"{raw['Voltage'].min():.0f} V, so the series never crosses "
              f"{LOW_VOLTAGE_THRESHOLD:.0f} V.")
        below30 = threshold_episodes(raw, DIAGNOSTIC_THRESHOLD)
        print(f"\nSame test at {DIAGNOSTIC_THRESHOLD:.0f} V "
              f"(to demonstrate the detection works): {len(below30)} instances")
        print(below30.to_string(index=False))
        below30.to_csv(os.path.join(OUT_DIR, "below_30V_instances.csv"), index=False)
    else:
        print(below20.to_string(index=False))

    slope = slope_series(minute)
    accel = find_slope_acceleration(minute, tp, slope)
    print(f"\n=== 4. BONUS: DOWNWARD SLOPE ACCELERATION ({len(accel)} instances) ===")
    print(accel.to_string(index=False))
    print("\nTimestamps only:")
    for t in accel["Acceleration starts"]:
        print("  ", t.strftime("%d-%m-%Y %H:%M"))

    # ---- save tables ----
    _, lin_slope, lin_intercept = linear_trend(minute, raw)
    print(f"\n=== 5. LINEAR TRENDLINE (same line Excel draws) ===")
    print(f"    Voltage = {lin_slope:+.4f} V/day x (days since start) + {lin_intercept:.2f} V")
    print(f"    Over the {len(minute)/1440:.1f}-day record that is a net change of "
          f"{lin_slope * len(minute)/1440:+.2f} V - essentially flat.")

    quality.to_csv(os.path.join(OUT_DIR, "data_summary.csv"), index=False)
    tp.to_csv(os.path.join(OUT_DIR, "local_peaks_and_lows.csv"), index=False)
    cycles.to_csv(os.path.join(OUT_DIR, "discharge_cycles.csv"), index=False)
    below20.to_csv(os.path.join(OUT_DIR, "below_20V_instances.csv"), index=False)
    accel.to_csv(os.path.join(OUT_DIR, "slope_acceleration.csv"), index=False)
    minute.to_csv(os.path.join(OUT_DIR, "clean_minute_series.csv"))

    # ---- figures ----
    plot_basic(minute, os.path.join(FIG_DIR, "fig1_voltage_vs_time.png"), raw)
    plot_moving_averages(minute, raw, os.path.join(FIG_DIR, "fig2_moving_averages.png"))
    plot_turning_points(minute, tp, os.path.join(FIG_DIR, "fig3_peaks_and_lows.png"))
    plot_acceleration(minute, slope, accel,
                      os.path.join(FIG_DIR, "fig4_slope_acceleration.png"))
    plot_interactive(minute, raw, tp, accel,
                     os.path.join(FIG_DIR, "interactive_chart.html"))
    print(f"\nSaved figures to {FIG_DIR}/ and tables to {OUT_DIR}/")
    return dict(raw=raw, minute=minute, tp=tp, cycles=cycles,
                below20=below20, accel=accel, slope=slope, quality=quality)


if __name__ == "__main__":
    main()

"""
Exports every number and table the Word report quotes into report_data.json,
so the report is generated from the analysis rather than hand-transcribed.

    python export_report_data.py     # writes report_data.json
    node   build_report.js           # writes Voltage_Analysis_Report.docx
"""

import json
import pandas as pd

import analysis
import build_excel


def frame_to_json(df: pd.DataFrame, dt="%d-%m-%Y %H:%M"):
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = d[c].dt.strftime(dt)
    rows = [[("" if pd.isna(v) else (f"{v:g}" if isinstance(v, float) else str(v)))
             for v in row] for row in d.values]
    return {"cols": [str(c) for c in d.columns], "rows": rows}


def main():
    raw = analysis.load_data()
    minute = analysis.build_minute_series(raw)
    minute, raw = analysis.add_moving_averages(minute, raw)
    tp = analysis.find_turning_points(minute)
    cycles = analysis.cycle_table(tp)
    slope = analysis.slope_series(minute)
    accel = analysis.find_slope_acceleration(minute, tp, slope)
    below20 = analysis.threshold_episodes(raw, analysis.LOW_VOLTAGE_THRESHOLD)
    below30 = analysis.threshold_episodes(raw, analysis.DIAGNOSTIC_THRESHOLD)
    quality = analysis.data_quality_report(raw, minute)
    _, lin_slope, lin_int = analysis.linear_trend(minute, raw)

    peaks = tp[tp["Type"].str.startswith("Peak")]["Voltage"]
    lows = tp[tp["Type"].str.startswith("Low")]["Voltage"]
    gaps = raw["Timestamp"].diff().dt.total_seconds().div(60)

    out = {k: frame_to_json(v) for k, v in
           [("tp", tp), ("cycles", cycles), ("accel", accel),
            ("below30", below30), ("quality", quality)]}

    out["stats"] = dict(
        n=int(len(raw)),
        start=raw["Timestamp"].min().strftime("%d %b %Y %H:%M"),
        end=raw["Timestamp"].max().strftime("%d %b %Y %H:%M"),
        days=round((raw["Timestamp"].max() -
                    raw["Timestamp"].min()).total_seconds() / 86400, 2),
        vmin=float(raw["Voltage"].min()), vmax=float(raw["Voltage"].max()),
        mean=round(float(raw["Voltage"].mean()), 2),
        med=float(raw["Voltage"].median()),
        std=round(float(raw["Voltage"].std()), 2),
        n_tp=int(len(tp)), n_peaks=int(len(peaks)), n_lows=int(len(lows)),
        n_gapflag=int((tp["Note"] != "").sum()),
        n_cycles=int(len(cycles)), n_accel=int(len(accel)),
        n_below20=int(len(below20)), n_below30=int(len(below30)),
        lin_slope=round(float(lin_slope), 4), lin_int=round(float(lin_int), 2),
        net=round(float(lin_slope * len(minute) / 1440), 2),
        mean_drop=round(float(cycles["Drop (V)"].mean()), 1),
        min_drop=float(cycles["Drop (V)"].min()),
        max_drop=float(cycles["Drop (V)"].max()),
        mean_dur=round(float(cycles["Duration (h)"].mean()), 2),
        min_dur=float(cycles["Duration (h)"].min()),
        max_dur=float(cycles["Duration (h)"].max()),
        mean_rate=round(float(cycles["Avg rate (V/h)"].mean()), 2),
        steepest=round(float(accel["Steepest slope reached (V/h)"].min()), 1),
        low_min=float(lows.min()), low_max=float(lows.max()),
        peak_at_100=int((peaks == raw["Voltage"].max()).sum()),
        minutes_grid=int(len(minute)),
        minutes_missing=int(minute["Voltage"].isna().sum()),
        pct_missing=round(100 * float(minute["Voltage"].isna().mean()), 1),
        gaps=int((gaps > analysis.GAP_MINUTES).sum()),
        longest_gap_h=round(float(gaps.max() / 60), 1),
        readings_per_min=round(len(raw) / raw["Timestamp"].nunique(), 2),
        segments=len(analysis.valid_segments(minute)),
    )
    out["sentences"] = build_excel.interpretation_sentences(
        dict(raw=raw, cycles=cycles, tp=tp, accel=accel, minute=minute))

    with open("report_data.json", "w") as f:
        json.dump(out, f, indent=1)
    print("wrote report_data.json")
    print(json.dumps(out["stats"], indent=1))


if __name__ == "__main__":
    main()

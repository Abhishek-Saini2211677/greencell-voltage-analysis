"""Generates and executes Voltage_Analysis.ipynb."""
import nbformat as nbf
from nbclient import NotebookClient

md = lambda t: nbf.v4.new_markdown_cell(t)
code = lambda t: nbf.v4.new_code_cell(t)

cells = [
    md("""# Voltage data — visualisation and interpretation
**Greencell internship assignment (July 2026)**

Dataset: `data/Sample_Data.csv` — two columns, `Values` (voltage, V) and `Timestamp`.

This notebook works through every part of the brief:

| Part | Where |
|---|---|
| 1a — plot voltage vs timestamp | §2 |
| 1b — 5-day moving average | §3 |
| 1c — local peaks and lows, tabulated | §4 |
| 1d — every instance the voltage went below 20 V | §5 |
| Bonus 2 — where the downward slope accelerates | §6 |
| Bonus 3 — hosted version | see `README.md` |

The reusable logic lives in `analysis.py` so the same code backs the notebook,
the Excel builder and the hosted dashboard."""),

    md("""## 1. Import the data into a DataFrame and clean it

Three things in this file need handling before anything is plotted:

1. **The timestamp is a string until you parse it.** The supplied file happens to
   already be in date order (I checked), but a chart drawn against a *text* axis
   sorts lexically, so `01-07-2024` lands before `26-06-2024` — which is exactly
   what happened to the annexure figure. Parse to datetime, then sort on it.
2. **Timestamps are truncated to the minute**, and the logger samples every
   ~15–20 s, so 3–5 rows share each minute.
3. **The logger drops out** — 90 gaps longer than 5 minutes, the longest 5.6 hours,
   splitting the week into 79 stretches of continuous recording. Only holes whose
   whole length is ≤5 min are bridged (`interpolate(limit=5)` would instead fill the
   first 5 minutes of *every* outage), so no figure here contains invented data."""),

    code("""import pandas as pd, numpy as np
import matplotlib.pyplot as plt
import analysis

raw = analysis.load_data()          # parse day-first dates, sort chronologically
minute = analysis.build_minute_series(raw)   # 1-min grid, gaps preserved
minute, raw = analysis.add_moving_averages(minute, raw)

print(raw.dtypes)
raw.head()"""),

    code("""analysis.data_quality_report(raw, minute)"""),

    md("""## 2. Plot the same chart as in Excel

Voltage on the y-axis, timestamp on the x-axis, plus the straight-line trendline
Excel draws and a 60-minute moving average for readability."""),

    code("""%matplotlib inline
analysis.plot_basic(minute, "figures/fig1_voltage_vs_time.png", raw)
from IPython.display import Image, display
display(Image("figures/fig1_voltage_vs_time.png"))

# fit over the raw readings, which is what Excel's trendline does
trend, slope, intercept = analysis.linear_trend(minute, raw)
print(f"Linear trendline: Voltage = {slope:+.4f} V/day x days + {intercept:.2f} V")
print(f"Net change across the {len(minute)/1440:.1f}-day record: "
      f"{slope*len(minute)/1440:+.2f} V  ->  effectively flat.")"""),

    md("""## 3. Moving averages

The brief asks for a **5-day** moving average. On a 7-day record that window only
becomes defined part-way through and flattens the signal almost completely, so the
1000-sample and 5000-sample windows from the annexure figure are plotted alongside
it — those are the ones that actually describe the behaviour."""),

    code("""analysis.plot_moving_averages(minute, raw, "figures/fig2_moving_averages.png")
display(Image("figures/fig2_moving_averages.png"))"""),

    md("""## 4. Local peaks and lows

`scipy.signal.find_peaks` on a 15-minute median-smoothed series, requiring 10 V of
prominence and 2 hours of separation — otherwise the 1 V quantisation of the logger
produces hundreds of meaningless micro-peaks. Each accepted point is snapped back to
the true extremum in the recorded neighbourhood.

Detection runs over the **recorded minutes only**. Filling the gaps first (with the
mean, say) makes `find_peaks` measure prominence against a fabricated plateau, and
every gap edge then scores as a turning point — you get pairs of consecutive
"peaks", which no real signal contains. With the gaps dropped the result alternates
peak–low–peak–low without exception. Points whose neighbouring reading sits across
an outage are flagged, since the true turn may have happened unobserved."""),

    code("""tp = analysis.find_turning_points(minute)
print(f"{(tp.Type == 'Peak (local high)').sum()} peaks, "
      f"{(tp.Type == 'Low (local minimum)').sum()} lows")
tp"""),

    code("""analysis.plot_turning_points(minute, tp, "figures/fig3_peaks_and_lows.png")
display(Image("figures/fig3_peaks_and_lows.png"))"""),

    md("""Pairing each peak with the low that follows it gives one row per discharge cycle
— the shape the whole week is made of."""),

    code("""cycles = analysis.cycle_table(tp)
cycles"""),

    code("""print(f"{len(cycles)} discharge cycles")
print(f"Mean depth   : {cycles['Drop (V)'].mean():.1f} V "
      f"(range {cycles['Drop (V)'].min():.0f}-{cycles['Drop (V)'].max():.0f} V)")
print(f"Mean duration: {cycles['Duration (h)'].mean():.2f} h "
      f"(range {cycles['Duration (h)'].min():.1f}-{cycles['Duration (h)'].max():.1f} h)")
print(f"Mean rate    : {cycles['Avg rate (V/h)'].mean():.2f} V/h")"""),

    md("""## 5. Every instance the voltage went below 20 V

Consecutive readings under the threshold are grouped into **episodes**, so one
physical dip is one instance rather than one instance per reading."""),

    code("""below20 = analysis.threshold_episodes(raw, 20.0)   # episodes, split at outages
print(f"Instances below 20 V: {len(below20)}")
print(f"Lowest reading anywhere in the file: {raw['Voltage'].min():.0f} V")
below20"""),

    md("""**The answer is zero** — the series never goes below 20 V, because its minimum is
25 V. To show the detector is doing real work rather than silently returning an
empty frame, here is the identical test at 30 V:"""),

    code("""analysis.threshold_episodes(raw, 30.0)"""),

    md("""## 6. Bonus — where does the downward slope accelerate?

Two derivatives:

* **slope** — a centred 31-minute least-squares fit at every minute, in V/hour.
* **curvature** — the change in that slope from one minute to the next.

Inside each peak→low cycle, an *acceleration* is a stretch where the voltage is
already falling (`slope < 0`) **and** the fall is getting steeper
(`d(slope)/dt < 0`). Each contiguous stretch is reported once, at its onset;
stretches shorter than 15 minutes or steepening by less than 2 V/h are treated as
logger noise."""),

    code("""slope_s = analysis.slope_series(minute)
accel = analysis.find_slope_acceleration(minute, tp, slope_s)
print(f"{len(accel)} acceleration episodes across {len(cycles)} cycles")
accel"""),

    code("""print("Timestamps where the downward slope accelerates:")
for t in accel["Acceleration starts"]:
    print("  ", t.strftime("%d-%m-%Y %H:%M"))"""),

    code("""analysis.plot_acceleration(minute, slope_s, accel,
                           "figures/fig4_slope_acceleration.png")
display(Image("figures/fig4_slope_acceleration.png"))"""),

    md("""## 7. Interactive version

The same chart as a Plotly figure — hover for values, drag to zoom. This is also
what the hosted Streamlit dashboard serves (`app.py`, deployment steps in
`README.md`)."""),

    code("""analysis.plot_interactive(minute, raw, tp, accel,
                          "figures/interactive_chart.html")
print("Written to figures/interactive_chart.html")"""),

    md("""## 8. Interpretation"""),

    code("""import build_excel
res = dict(raw=raw, minute=minute, tp=tp, cycles=cycles, accel=accel)
for i, s in enumerate(build_excel.interpretation_sentences(res), 1):
    print(f"{i}. {s}\\n")"""),
]

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata = {"kernelspec": {"display_name": "Python 3", "language": "python",
                              "name": "python3"},
               "language_info": {"name": "python", "version": "3.11"}}
NotebookClient(nb, timeout=900, kernel_name="python3",
               resources={"metadata": {"path": "."}}).execute()
nbf.write(nb, "Voltage_Analysis.ipynb")
print("wrote Voltage_Analysis.ipynb")

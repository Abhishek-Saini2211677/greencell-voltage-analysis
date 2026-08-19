# Voltage Data — Visualisation & Interpretation

Greencell internship assignment (July 2026). Analysis of a week of voltage
telemetry: 21,919 readings taken between **26 Jun 2024 06:17** and
**03 Jul 2024 10:30**.

**Live dashboard:** _paste your URL here after deploying (see below)_

---

## What is in this repo

| File | What it does |
|---|---|
| `analysis.py` | The whole analysis pipeline. Run it to regenerate every figure and table. |
| `app.py` | Interactive Streamlit + Plotly dashboard (the hosted version). |
| `build_excel.py` | Builds `Voltage_Analysis.xlsx` — native Excel chart with a trendline. |
| `make_notebook.py` | Generates and executes `Voltage_Analysis.ipynb`. |
| `export_report_data.py` + `build_report.js` | Export every number to `report_data.json`, then build the Word report from it. |
| `data/Sample_Data.csv` | The supplied dataset. |
| `figures/` | PNG figures + a standalone interactive `interactive_chart.html`. |
| `outputs/` | Every result table as CSV, plus the full console log. |
| `Voltage_Analysis.xlsx` | The Excel deliverable — 9 sheets. |
| `Voltage_Analysis.ipynb` | The analysis as an executed notebook. |
| `Voltage_Analysis_Report.docx` | The written report. |
| `requirements.txt` / `requirements-dev.txt` | Runtime deps (app + analysis) / extras needed only to rebuild the notebook and report. |

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python analysis.py        # prints all tables, writes figures/ and outputs/
python build_excel.py     # additionally writes Voltage_Analysis.xlsx
streamlit run app.py      # opens the dashboard at http://localhost:8501

# rebuilding the notebook and the Word report (needs requirements-dev.txt + Node)
pip install -r requirements-dev.txt
python make_notebook.py         # -> Voltage_Analysis.ipynb
python export_report_data.py    # -> report_data.json
npm install docx && node build_report.js   # -> Voltage_Analysis_Report.docx
```

## What the analysis does

1. **Clean** — parses the day-first timestamps and sorts on the parsed date (the
   supplied file is already in order; sorting makes that true by construction rather
   than by luck), averages the 3–5 readings that share each minute, and reindexes
   onto a strict 1-minute grid. Only holes whose *entire* length is ≤5 minutes are
   bridged — note that `interpolate(limit=5)` does **not** mean that, it fills the
   first 5 minutes of every outage however long. Real outages stay as gaps.
2. **Plot** — voltage on Y, timestamp on X, with a linear trendline and moving
   averages (60-minute, 1000-sample, 5000-sample, and the 5-day window the brief
   asks for).
3. **Turning points** — median-smooths the series, then `scipy.signal.find_peaks`
   with a 10 V prominence and a 2-hour minimum separation, running over the
   **recorded minutes only**. Filling the gaps first would make prominence measure
   against a fabricated plateau and turn every gap edge into a fake peak; with them
   dropped, the detected points alternate peak–low–peak–low with no exceptions.
   → 21 peaks, 22 lows, 21 complete discharge cycles. Points whose neighbouring
   reading is across an outage are flagged `next to a data gap`, because the true
   turn may have happened unobserved (24 of 43 are).
4. **Threshold crossings** — every continuous episode below a threshold, so one
   physical dip is one row rather than one row per reading. At the assignment's
   20 V the answer is **zero instances**: the lowest reading in the file is 25 V.
   The same test at 30 V returns 4 episodes, which demonstrates the detector works.
   Episodes are also split at outages longer than 5 minutes — counting logger
   downtime as time-below-threshold would overstate the event — and the table
   reports `Minutes recorded` next to `Duration` so the two can be compared.
5. **Bonus — slope acceleration** — fits a centred 31-minute least-squares slope
   (V/hour) at every minute, then inside each peak→low cycle finds every contiguous
   run where the slope is negative *and* getting more negative (`d²V/dt² < 0`),
   sustained ≥15 minutes and steepening by ≥2 V/h. → 38 episodes.

## Hosting the dashboard (bonus part 3)

Three free options. **Streamlit Community Cloud is the easiest** — no card, no CLI.

### Option A — Streamlit Community Cloud (recommended)

1. Push this folder to a **public** GitHub repo:

   ```bash
   git init
   git add .
   git commit -m "Greencell assignment: voltage analysis"
   git branch -M main
   git remote add origin https://github.com/<your-username>/greencell-voltage-analysis.git
   git push -u origin main
   ```

2. Go to <https://share.streamlit.io> and sign in with GitHub.
3. **Create app** → pick the repo, branch `main`, main file `app.py` → **Deploy**.
4. Wait ~2 minutes. You get a URL like
   `https://<your-username>-greencell-voltage-analysis.streamlit.app`.
5. Paste that URL at the top of this README and in your submission.

### Option B — Render

1. Push to GitHub as above.
2. <https://render.com> → **New → Web Service** → connect the repo.
3. Settings:
   - Build command: `pip install -r requirements.txt`
   - Start command:
     `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
   - Instance type: Free
4. Deploy. (`render.yaml` in this repo already contains these settings, so Render
   will pick them up automatically via **New → Blueprint**.)

### Option C — Hugging Face Spaces

1. <https://huggingface.co/new-space> → SDK **Streamlit** → Space name of your choice.
2. Upload `app.py`, `analysis.py`, `build_excel.py`, `requirements.txt` and the
   `data/` folder (or `git push` to the Space remote).
3. It builds and serves automatically at
   `https://huggingface.co/spaces/<user>/<space>`.

> On every host, keep `data/Sample_Data.csv` in the repo — the app reads it from a
> relative path, so nothing else needs configuring.

## Notes and caveats

- **The 5-day moving average is barely meaningful on a 7-day record** — it only
  becomes defined once 2 days of data have accumulated, and it flattens the signal
  almost completely. It is included because the brief asks for it; the 60-minute
  and 1000-sample averages are the ones that actually describe the behaviour.
- **The annexure figure has its x-axis out of order** (01-07 plotted before 26-06).
  That is a text-axis artifact, not a problem with the file: the data is in order,
  but a string axis sorts lexically. Parsing the column to a datetime fixes it.
- **38% of the minutes in the window have no reading.** The logger drops out for
  stretches of up to 5.6 hours — 90 gaps, splitting the week into 79 stretches of
  continuous recording — and several recharge ramps fall inside those gaps, which is
  why a few peaks appear as vertical jumps rather than rising edges.
- **The dataset is probably state of charge (%), not volts.** A quantity capped at
  exactly 100, recharged to full and drained over 4–9 hours, 21 times in a week,
  behaves like SoC; a real pack voltage would not sit at a round 100 for tens of
  minutes. The analysis is identical either way — only the unit label changes.

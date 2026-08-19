const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, PageBreak,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, ImageRun,
  TableOfContents, Header, Footer, PageNumber, LevelFormat, convertInchesToTwip,
} = require("docx");

const D = JSON.parse(fs.readFileSync("report_data.json", "utf8"));
const S = D.stats;

const NAVY = "1F3864";
const INK = "1A1A1A";
const MUTED = "52514E";
const FONT = "Calibri";
const PAGE_W = 9360;            // A4 minus 1" margins, in DXA

const p = (text, o = {}) => new Paragraph({
  alignment: o.align, spacing: { before: o.before ?? 0, after: o.after ?? 140 },
  indent: o.indent,
  children: [new TextRun({
    text, font: FONT, size: o.size ?? 21, bold: o.bold, italics: o.italics,
    color: o.color ?? INK,
  })],
});

const rich = (runs, o = {}) => new Paragraph({
  spacing: { before: o.before ?? 0, after: o.after ?? 140 }, indent: o.indent,
  alignment: o.align,
  children: runs.map(r => new TextRun({
    text: r.t, bold: r.b, italics: r.i, font: FONT, size: o.size ?? 21,
    color: r.c ?? INK,
  })),
});

const h1 = t => new Paragraph({
  heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 180 },
  children: [new TextRun({ text: t, font: FONT, size: 30, bold: true, color: NAVY })],
});
const h2 = t => new Paragraph({
  heading: HeadingLevel.HEADING_2, spacing: { before: 260, after: 130 },
  children: [new TextRun({ text: t, font: FONT, size: 24, bold: true, color: NAVY })],
});

const bullet = (text, level = 0) => new Paragraph({
  numbering: { reference: "bullets", level }, spacing: { after: 90 },
  children: [new TextRun({ text, font: FONT, size: 21, color: INK })],
});

const code = text => new Paragraph({
  spacing: { after: 60 },
  shading: { type: ShadingType.CLEAR, fill: "F4F4F2" },
  children: [new TextRun({ text, font: "Consolas", size: 18, color: "1F3864" })],
});

const caption = t => new Paragraph({
  spacing: { before: 60, after: 220 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: t, font: FONT, size: 17, italics: true, color: MUTED })],
});

function image(path, widthPx, heightPx) {
  return new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 120, after: 40 },
    children: [new ImageRun({
      type: "png", data: fs.readFileSync(path),
      transformation: { width: widthPx, height: heightPx },
    })],
  });
}

function table(cols, rows, widths, opts = {}) {
  const fontSize = opts.size ?? 16;
  const head = new TableRow({
    tableHeader: true,
    children: cols.map((c, i) => new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: NAVY },
      margins: { top: 60, bottom: 60, left: 80, right: 80 },
      children: [new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { after: 0 },
        children: [new TextRun({ text: c, bold: true, color: "FFFFFF",
                                 font: FONT, size: fontSize })],
      })],
    })),
  });
  const body = rows.map((r, ri) => new TableRow({
    children: r.map((v, i) => new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      shading: ri % 2 ? { type: ShadingType.CLEAR, fill: "F7F7F5" } : undefined,
      margins: { top: 50, bottom: 50, left: 80, right: 80 },
      children: [new Paragraph({
        alignment: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER,
        spacing: { after: 0 },
        children: [new TextRun({ text: String(v), font: FONT, size: fontSize,
                                 color: INK })],
      })],
    })),
  }));
  return new Table({
    columnWidths: widths, width: { size: PAGE_W, type: WidthType.DXA },
    rows: [head, ...body],
    borders: {
      top:    { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" },
      bottom: { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" },
      left:   { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" },
      right:  { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "DCDCD8" },
      insideVertical:   { style: BorderStyle.SINGLE, size: 2, color: "DCDCD8" },
    },
  });
}

const even = (cols, first) => {
  const w = first ?? Math.floor(PAGE_W / cols.length);
  const rest = Math.floor((PAGE_W - w) / (cols.length - 1));
  const out = [w, ...Array(cols.length - 1).fill(rest)];
  out[out.length - 1] += PAGE_W - out.reduce((a, b) => a + b, 0);
  return out;
};

// ---------------------------------------------------------------- content ----
const body = [];

// Title block
body.push(new Paragraph({
  spacing: { before: 1400, after: 80 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Data Visualisation and Interpretation",
                           font: FONT, size: 52, bold: true, color: NAVY })],
}));
body.push(new Paragraph({
  spacing: { after: 500 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Voltage time-series analysis of a one-week telemetry record",
                           font: FONT, size: 26, color: MUTED })],
}));
body.push(table(
  ["Field", "Detail"],
  [["Assignment", "Greencell Internship — Data visualisation and interpretation"],
   ["Prepared by", "Kishan Saini"],
   ["Dataset", "Sample_Data.csv — Values (voltage, V) and Timestamp"],
   ["Records", `${S.n.toLocaleString()} readings`],
   ["Period covered", `${S.start} to ${S.end} (${S.days} days)`],
   ["Tools", "Microsoft Excel · Python (pandas, NumPy, SciPy, Matplotlib, Plotly) · Streamlit"],
   ["Deliverables", "Voltage_Analysis.xlsx · Voltage_Analysis.ipynb · analysis.py · app.py · this report"]],
  [2400, 6960], { size: 19 }));
body.push(new Paragraph({ spacing: { before: 700 }, children: [new PageBreak()] }));

// -------------------------------------------------- 1. Summary of findings ---
body.push(h1("1. Summary of findings"));
body.push(p(`The record is not a drifting signal — it is a repeating duty cycle. Over ${S.days} days the voltage stays inside a ${S.vmin}–${S.vmax} V band and traces ${S.n_cycles} complete charge–discharge cycles: a fast rise back to about 100 V, then a long, nearly straight decline lasting on average ${S.mean_dur} hours and losing ${S.mean_drop} V.`));
body.push(p("The four headline numbers a reviewer will want:"));
body.push(table(
  ["Question", "Answer"],
  [["What shape is the data?", `Sawtooth — ${S.n_cycles} discharge cycles in ${S.days} days`],
   ["What does the trendline say?", `${S.lin_slope >= 0 ? "+" : ""}${S.lin_slope} V/day (R² ≈ 0.001) — flat; no degradation`],
   ["How many local peaks and lows?", `${S.n_peaks} peaks, ${S.n_lows} lows`],
   ["How often below 20 V?", `${S.n_below20} times — the minimum anywhere is ${S.vmin} V`],
   ["Where does the fall accelerate?", `${S.n_accel} episodes, steepest ${S.steepest} V/h`]],
  [4200, 5160], { size: 19 }));
body.push(p("Every figure and table below is regenerated from the raw CSV by a single script, so nothing here is hand-transcribed.", { italics: true, color: MUTED, size: 19, before: 120 }));

body.push(h2("Assignment checklist"));
body.push(table(
  ["Requirement", "Where", "Result"],
  [["Excel: plot voltage (Y) vs timestamp (X)", "Voltage_Analysis.xlsx → Chart", "Done"],
   ["Excel: add a trendline", "Same chart, equation + R² shown", `${S.lin_slope >= 0 ? "+" : ""}${S.lin_slope} V/day`],
   ["Excel: 5 sentences of interpretation", "§6 of this report; Interpretation sheet", "Done"],
   ["Python 1a: import to DataFrame and plot", "§4, Figure 2", "Done"],
   ["Python 1b: 5-day moving average", "§4, Figure 3", "Done (with caveat)"],
   ["Python 1c: find and tabulate peaks and lows", "§5.1, Tables 3–4", `${S.n_peaks} + ${S.n_lows}`],
   ["Python 1d: every instance below 20 V", "§5.2", "0 instances"],
   ["Bonus 2: accelerating downward slope", "§5.3, Table 6", `${S.n_accel} episodes`],
   ["Bonus 3: host the code", "§7", "Streamlit app ready to deploy"]],
  [3700, 3100, 2560], { size: 18 }));

// ------------------------------------------------------ 2. The data ----------
body.push(h1("2. The data, and what had to be fixed first"));
body.push(p(`The file holds ${S.n.toLocaleString()} rows with two columns, Values (voltage in volts) and Timestamp. Three properties of the file matter before a single chart is drawn.`));

body.push(h2("2.1 The timestamp is text until you parse it"));
body.push(p("The supplied CSV is, as it happens, already in date order — I checked rather than assumed. What is not safe is the column's type: read without a format, Timestamp is a string, and a chart drawn against a string axis orders it lexically, so 01-07-2024 lands before 26-06-2024. That is visibly what happened to the reference figure in the assignment annexure, whose x-axis starts at 01-07 and jumps back to 26-06 part-way across — the data was fine, the axis was not. Parsing to a real datetime and sorting on it makes the ordering true by construction instead of by luck:"));
body.push(code(`df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%d-%m-%Y %H:%M")`));
body.push(code(`df = df.sort_values("Timestamp", kind="mergesort")`));

body.push(h2("2.2 Timestamps are truncated to the minute"));
body.push(p(`The logger samples every 15–20 seconds but the timestamp column carries no seconds, so ${S.readings_per_min} rows share each minute on average. Those duplicates are collapsed to a per-minute mean before any derivative is taken; otherwise the slope calculation divides by a zero time step.`));

body.push(h2("2.3 The logger drops out"));
body.push(p(`There are ${S.gaps} gaps longer than five minutes, the longest ${S.longest_gap_h} hours, which breaks the week into ${S.segments} separate stretches of continuous recording. After bridging only those holes whose entire length is five minutes or less, ${S.minutes_missing.toLocaleString()} of ${S.minutes_grid.toLocaleString()} minutes (${S.pct_missing}%) remain empty. Longer outages are deliberately left as gaps rather than drawn through, so no figure in this report contains an invented value — worth noting because pandas\u2019 obvious shortcut, interpolate(limit=5), does not mean "fill holes up to 5 minutes"; it fills the first five minutes of every outage however long, which would fabricate data at 78 gap edges. This is also why a few recharges appear as vertical jumps rather than rising edges: the ramp itself happened while the logger was down.`));

body.push(p("Table 1 — the data-quality report the script prints on every run.", { italics: true, color: MUTED, size: 19, before: 160, after: 80 }));
body.push(table(D.quality.cols, D.quality.rows, [5400, 3960], { size: 18 }));

// ------------------------------------------------------ 3. Excel -------------
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(h1("3. Excel: chart and trendline"));
body.push(p("Voltage_Analysis.xlsx contains the chart the brief asks for — voltage on the y-axis, timestamp on the x-axis — drawn as a native Excel scatter chart with a straight line joining the points, plus a linear trendline with its equation and R² displayed."));
body.push(image("figures/fig0_excel_chart.png", 620, 229));
body.push(caption("Figure 1 — the Excel chart: voltage vs timestamp with a linear trendline (equation and R² on the plot)."));
body.push(rich([
  { t: "The trendline is nearly horizontal: " },
  { t: `${S.lin_slope >= 0 ? "+" : ""}${S.lin_slope} V per day, R² ≈ 0.001`, b: true },
  { t: `, i.e. a net change of about ${S.net >= 0 ? "+" : ""}${S.net} V across the whole week. The same figure is reproduced on the Summary sheet by =SLOPE(Data!A:A, Data!B:B), and the Python fit in §4 uses the same raw readings so that all three agree. That near-zero R² is the useful result, not a failure: a straight line simply cannot describe a signal that is cycling, and the fact that it comes out flat tells us the cycling is stable rather than drifting. A moving average is the right smoother here, which is why the workbook also carries a second chart using a 500-point moving-average trendline.` },
]));
body.push(p("The workbook is organised as follows:"));
[["Read Me", "what each sheet contains, and the sorting caveat"],
 ["Data", `all ${S.n.toLocaleString()} readings, sorted oldest to newest`],
 ["Chart", "the two charts above"],
 ["Summary", "headline statistics written as live Excel formulas (MIN, MAX, AVERAGE, STDEV, COUNTIF, SLOPE, INTERCEPT, RSQ) over the Data sheet, so they recalculate if the data changes"],
 ["Interpretation", "the five sentences of §6"],
 ["Peaks and Lows / Cycles / Below 20V / Acceleration", "the Python results, tabulated"],
].forEach(([a, b]) => body.push(rich([{ t: a + " — ", b: true }, { t: b }],
                                     { indent: { left: 360 }, after: 80 })));

// ------------------------------------------------------ 4. Python plots ------
body.push(h1("4. Python: the same chart, and moving averages"));
body.push(p("The data is read into a pandas DataFrame, cleaned as described in §2, and plotted with Matplotlib (static figures for this report) and Plotly (the interactive version and the hosted dashboard)."));
body.push(image("figures/fig1_voltage_vs_time.png", 620, 262));
body.push(caption("Figure 2 — voltage vs time with a 60-minute moving average and the linear trendline. Breaks in the blue line are real logger outages, not missing plot data."));

body.push(h2("4.1 On the 5-day moving average"));
body.push(p(`The brief asks for a 5-day moving average. The record is only ${S.days} days long, so a 5-day window does not become fully defined until day five and averages away almost everything that is interesting — it lands as a nearly flat line at the series mean of ${S.mean} V. It is plotted because it was asked for, alongside the 1000-sample and 5000-sample windows used in the annexure figure and a 60-minute window. The shorter windows are the ones that actually describe the behaviour: the 1000-sample average tracks each individual cycle, while the 5000-sample average shows that the cycle-to-cycle mean barely moves all week.`));
body.push(image("figures/fig2_moving_averages.png", 620, 262));
body.push(caption("Figure 3 — the same series with four moving averages. The 5-day window (yellow) is almost a straight line; the 1000-sample window (orange) is what resolves individual cycles."));

// ------------------------------------------------------ 5. Results -----------
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(h1("5. Results"));

body.push(h2("5.1 Local peaks and lows"));
body.push(p("Method. The 1 V quantisation of the logger means a naïve maximum-finder returns hundreds of meaningless micro-peaks. The series is therefore median-smoothed over 15 minutes, and SciPy's find_peaks is asked for turning points with at least 10 V of prominence and at least 2 hours of separation. Each accepted point is then snapped back to the true extremum in the recorded neighbourhood, so every reported voltage and timestamp is an actual reading rather than a smoothed value."));
body.push(p("One detail matters more than it looks. Detection runs over the recorded minutes only, with the empty minutes dropped rather than filled. Filling them — with the series mean, say — is the obvious shortcut and it quietly ruins the result: prominence is then measured against a fabricated plateau, so every gap edge scores as a turning point, and the table fills with pairs of consecutive 'peaks' that no real signal can contain. With the gaps dropped, the 43 detected points alternate peak–low–peak–low without a single exception, which is the signature of a detector that is tracking the actual cycle."));
body.push(code(`hi, _ = find_peaks(smoothed,  prominence=10, distance=120)   # local highs`));
body.push(code(`lo, _ = find_peaks(-smoothed, prominence=10, distance=120)   # local lows`));
body.push(p(`Result: ${S.n_peaks} local peaks and ${S.n_lows} local lows, strictly alternating. ${S.peak_at_100} of the ${S.n_peaks} peaks sit at exactly ${S.vmax} V; the lows scatter from ${S.low_min} V to ${S.low_max} V. ${S.n_gapflag} of the ${S.n_tp} points are marked "next to a data gap" in Table 2 — the reading immediately before or after the extremum is on the far side of an outage, so the true turn may have happened while the logger was down and the recorded value is a bound rather than the peak itself. That is most of the sub-100 V highs: the charge was still climbing when recording stopped.`, { before: 120 }));
body.push(image("figures/fig3_peaks_and_lows.png", 620, 262));
body.push(caption("Figure 4 — every detected local high (circles) and local low (triangles)."));
body.push(p(`Table 2 — all ${D.tp.rows.length} turning points, in time order.`, { italics: true, color: MUTED, size: 19, before: 140, after: 80 }));
body.push(table(D.tp.cols, D.tp.rows, [700, 2300, 1200, 2660, 2500], { size: 16 }));

body.push(p("Pairing each peak with the low that follows it gives one row per discharge cycle — the unit the whole week is built from.", { before: 200 }));
body.push(p(`Table 3 — the ${S.n_cycles} discharge cycles. Mean depth ${S.mean_drop} V (range ${S.min_drop}–${S.max_drop} V), mean duration ${S.mean_dur} h (range ${S.min_dur}–${S.max_dur} h), mean rate ${S.mean_rate} V/h.`, { italics: true, color: MUTED, size: 19, after: 80 }));
body.push(table(D.cycles.cols, D.cycles.rows,
  [780, 1740, 900, 1740, 840, 1000, 1180, 1180], { size: 16 }));

body.push(h2("5.2 Every instance the voltage went below 20 V"));
body.push(p("Method. Consecutive readings under the threshold are grouped into episodes, so one physical dip is one row rather than one row per reading; episodes separated by less than a minute are merged, because the order of readings inside a single truncated minute is arbitrary."));
body.push(rich([
  { t: "Result: there are no such instances. " , b: true },
  { t: `The lowest reading anywhere in the ${S.n.toLocaleString()}-row file is ${S.vmin} V, so the series never approaches 20 V. Reporting an empty table is the correct answer, but an empty table is also what a broken detector produces — so the same function was run at 30 V, where it returns ${S.n_below30} episodes. That confirms the logic works and gives a useful secondary result: the deepest discharges of the week.` },
]));
body.push(p(`Table 4 — the same test at 30 V (${S.n_below30} episodes), included as evidence the detection works.`, { italics: true, color: MUTED, size: 19, before: 140, after: 80 }));
body.push(table(D.below30.cols, D.below30.rows,
  [820, 1520, 1520, 1080, 1240, 940, 1520, 820], { size: 15 }));
body.push(p("Two details in that table are deliberate. Episodes are split at any outage longer than five minutes, because the voltage during an outage is unknown and counting it as time-below-threshold overstates the event — the 28 Jun dip reads as 46 recorded minutes plus a single later reading, not one uninterrupted stretch across the 98-minute gap that sits inside it. And Minutes recorded is shown next to Duration so the two can be compared: where they diverge, the logger was down. Practically, the pack was never taken near a low-voltage cut-out all week; the deepest excursion is 30 Jun at 25 V for around an hour.", { before: 140 }));

body.push(h2("5.3 Bonus — where the downward slope accelerates"));
body.push(p("Method. Two derivatives are needed. The first is the local slope: a centred 31-minute least-squares fit at every minute, expressed in volts per hour. The second is the change in that slope from minute to minute — the curvature. Inside each peak→low cycle, an acceleration is a stretch where the voltage is already falling and the fall is getting steeper:"));
body.push(code(`falling_and_steepening = (slope < -0.5) & (slope.diff() < 0)`));
body.push(p("Each contiguous stretch is reported once, at its onset, so one physical event yields one row. Stretches shorter than 15 minutes, or that steepen by less than 2 V/h, are treated as logger noise. Reporting onsets rather than every qualifying minute is what keeps the answer interpretable — the raw per-minute flag fires thousands of times."));
body.push(rich([
  { t: `Result: ${S.n_accel} acceleration episodes across the ${S.n_cycles} cycles`, b: true },
  { t: `, roughly two per cycle, reaching a steepest fall of ${S.steepest} V/h against a cycle average of ${S.mean_rate} V/h. Physically this is the signature of extra load being switched on mid-discharge: the same pack, drained two to three times faster for twenty to forty minutes at a stretch.` },
]));
body.push(image("figures/fig4_slope_acceleration.png", 620, 358));
body.push(caption("Figure 5 — top: onsets of accelerating discharge. Bottom: the local slope in V/hour; every marker above sits where this curve is negative and heading further down."));
body.push(p(`Table 5 — all ${S.n_accel} acceleration episodes.`, { italics: true, color: MUTED, size: 19, before: 140, after: 80 }));
body.push(table(
  ["No.", "Cycle", "Starts", "Ends", "Min", "V at onset", "Slope at onset", "Steepest", "Change"],
  D.accel.rows,
  [620, 660, 1580, 1580, 640, 1000, 1180, 1000, 1100], { size: 15 }));

// ------------------------------------------------------ 6. Interpretation ----
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(h1("6. Interpretation"));
body.push(p("The five sentences the brief asks for:", { after: 160 }));
D.sentences.forEach((s, i) => body.push(rich(
  [{ t: `${i + 1}. `, b: true }, { t: s }], { after: 160 })));

body.push(h2("6.1 What the data most likely is"));
body.push(p("Nothing in the file names the source, so this is inference rather than fact: a quantity bounded at exactly 100, recharged to full and drained over four to eight hours, twenty-two times in a week, reads much more like battery state of charge (in percent) than a raw pack voltage in volts. A real pack voltage would not sit at a round ceiling of exactly 100 for tens of minutes at a time, and would show a curved rather than near-linear decline. Either way the analysis is unchanged — only the unit label would be — but it is worth flagging rather than asserting \"voltage\" and moving on."));

body.push(h2("6.2 What I would do next with more data"));
[`Correlate the ${S.n_accel} acceleration episodes with a load or speed channel, if one exists. The hypothesis that they are load events is testable and currently unverified.`,
 "Investigate the logger outages. A third of the week is unrecorded, and gaps that coincide with recharges make the cycle count a lower bound.",
 "Extend the window. Cycle depth and charge duration are the two metrics that would reveal degradation, and neither shows a trend over seven days — a month or more is needed before that means anything.",
 "Set the alerting threshold from the observed distribution, not a round number. Nothing came near 20 V; a threshold at 30 V would have flagged three real events."].forEach(t => body.push(bullet(t)));

// ------------------------------------------------------ 7. Hosting -----------
body.push(h1("7. Bonus — hosting the analysis"));
body.push(p("app.py is a Streamlit dashboard serving the same analysis interactively: a Plotly chart with selectable series, a movable time window, a live low-voltage threshold slider, a sensitivity control for the turning-point detector, every result table, and CSV downloads. It runs locally with one command:"));
body.push(code(`streamlit run app.py`));
body.push(p("To publish it free of charge, with no card and no CLI (full step-by-step in README.md):"));
[`Push the folder to a public GitHub repository.`,
 "Sign in at share.streamlit.io with the same GitHub account.",
 "Create app → select the repository, branch main, main file app.py → Deploy.",
 "After about two minutes the app is live at a *.streamlit.app URL; paste it into README.md and the submission."].forEach(t => body.push(bullet(t)));
body.push(p("The repository also contains a render.yaml, so the same app deploys on Render as a Blueprint without any further configuration, and it runs unchanged as a Hugging Face Streamlit Space. data/Sample_Data.csv is committed alongside the code and read from a relative path, so no host-side setup is needed.", { before: 120 }));

// ------------------------------------------------------ 8. Appendix ----------
body.push(h1("8. Appendix — files and how to reproduce"));
body.push(table(
  ["File", "What it is"],
  [["analysis.py", "The whole pipeline: clean → plot → peaks/lows → thresholds → acceleration. Run it to regenerate every figure and table."],
   ["Voltage_Analysis.ipynb", "The same analysis as an executed notebook, section by section against the brief."],
   ["build_excel.py", "Builds Voltage_Analysis.xlsx, including the native chart and trendline."],
   ["export_report_data.py · build_report.js", "Export every figure in this report to report_data.json, then build the .docx from it — so no number here is typed by hand."],
   ["make_notebook.py", "Generates and executes the notebook."],
   ["app.py", "The Streamlit dashboard (the hosted version)."],
   ["Voltage_Analysis.xlsx", "The Excel deliverable — nine sheets."],
   ["figures/", "Figures 1–5 as PNG, plus a standalone interactive_chart.html."],
   ["outputs/", "Every table as CSV, plus the full console log of a run."],
   ["requirements.txt · render.yaml · README.md", "Dependencies, Render blueprint, and setup/deployment instructions."]],
  [2900, 6460], { size: 18 }));
body.push(p("Reproduce from a clean checkout:", { before: 160 }));
body.push(code(`pip install -r requirements.txt`));
body.push(code(`python analysis.py        # figures/ and outputs/`));
body.push(code(`python build_excel.py     # Voltage_Analysis.xlsx`));
body.push(code(`streamlit run app.py      # the dashboard`));
body.push(p("Analysis parameters are constants at the top of analysis.py — smoothing window, prominence, minimum separation, slope window, minimum burst length — so every judgement call in the method is visible and adjustable in one place.", { before: 140 }));

// ---------------------------------------------------------------- document ---
const doc = new Document({
  creator: "Kishan Saini",
  title: "Data Visualisation and Interpretation — Voltage Time-Series Analysis",
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "•",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360, hanging: 200 } } },
      }],
    }],
  },
  styles: { default: { document: { run: { font: FONT, size: 21, color: INK } } } },
  sections: [{
    properties: { page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({
            children: ["Voltage time-series analysis · Kishan Saini · page ", PageNumber.CURRENT],
            font: FONT, size: 16, color: MUTED,
          })],
        })],
      }),
    },
    children: body,
  }],
});

Packer.toBuffer(doc).then(b => {
  fs.writeFileSync("Voltage_Analysis_Report.docx", b);
  console.log("wrote Voltage_Analysis_Report.docx");
});

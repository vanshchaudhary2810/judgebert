// Frontend for the Legal Meaning Checker. Talks to the FastAPI backend in app/server.py.
const $ = (s) => document.querySelector(s);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const LANG = { en: "English", hi: "Hindi", fr: "French" };
let lastBatch = null;

// ---------------------------------------------------------------- tabs
document.querySelectorAll(".tab").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === b));
    document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + b.dataset.tab));
    if (b.dataset.tab === "results") loadResults();
  })
);

async function api(path, opts) {
  const r = await fetch(path, opts);
  let body = null;
  try { body = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error((body && body.detail) || `Request failed (${r.status})`);
  return body;
}

// ---------------------------------------------------------------- status + examples
async function init() {
  try {
    const s = await api("/api/status");
    const el = $("#status");
    if (s.model_loaded) {
      el.className = "status status-ok";
      el.textContent = `Model ready · ${s.device.toUpperCase()}`;
    } else {
      el.className = "status status-bad";
      el.textContent = "Model not loaded";
      el.title = s.error || "";
    }
  } catch (e) {
    $("#status").className = "status status-bad";
    $("#status").textContent = "Backend offline";
  }
  try {
    const ex = await api("/api/examples");
    $("#example-list").innerHTML = ex
      .map((e, i) => `<button class="chip" data-i="${i}"><span class="dot" style="background:${e.kind === "good" ? "var(--good)" : "var(--bad)"}"></span>${esc(e.title)}</button>`)
      .join("");
    $("#example-list").querySelectorAll(".chip").forEach((c) =>
      c.addEventListener("click", () => {
        const e = ex[+c.dataset.i];
        $("#original").value = e.original;
        $("#simplified").value = e.simplified;
        $("#lang").value = e.lang;
        analyze();
      })
    );
  } catch (_) {}
}

// ---------------------------------------------------------------- analyze
function decisionClass(d) {
  return d === "Preserved" ? "b-good" : d === "Not Preserved" ? "b-bad" : "b-warn";
}

function wordsHtml(pairs) {
  if (!pairs || !pairs.length) return '<span class="muted">-</span>';
  const m = Math.max(...pairs.map(([, s]) => Math.abs(s)), 1e-9);
  return pairs
    .map(([w, s]) => {
      const a = Math.min(Math.abs(s) / m, 1);
      const bg = s < 0 ? `rgba(179,38,30,${(0.55 * a).toFixed(3)})` : `rgba(29,115,71,${(0.45 * a).toFixed(3)})`;
      return `<span class="w" style="background:${a > 0.08 ? bg : "transparent"}" title="${s.toFixed(4)}">${esc(w)}</span>`;
    })
    .join(" ");
}

function barRow(label, value, max, cls, flag, valText) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return `<div class="bar-row ${flag ? "flag" : ""}"><div>${esc(label)}</div>
    <div class="bar-track"><div class="bar-fill ${cls}" style="width:${pct}%"></div>${max === 1 ? '<div class="threshold"></div>' : ""}</div>
    <div class="bar-val">${valText ?? value}</div></div>`;
}

async function analyze() {
  const original = $("#original").value.trim();
  const simplified = $("#simplified").value.trim();
  const out = $("#result");
  if (!original || !simplified) {
    out.innerHTML = '<div class="error-box">Please fill in both the original text and the simplified version.</div>';
    return;
  }
  const btn = $("#analyze");
  btn.disabled = true;
  out.innerHTML = '<div class="spinner"></div><p class="muted" style="text-align:center">Reading both texts with the model…</p>';
  try {
    const r = await api("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ original, simplified, lang: $("#lang").value, explain_words: $("#words").checked }),
    });
    renderResult(r);
  } catch (e) {
    out.innerHTML = `<div class="error-box">${esc(e.message)}</div>`;
  } finally {
    btn.disabled = false;
  }
}

function renderResult(r) {
  const pos = ((r.lmp_score - 1) / 9) * 100;
  const flagged = new Set(r.error_types);
  const findings = r.rule_findings.length
    ? `<ul class="findings">${r.rule_findings.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>`
    : `<p class="muted">${r.rules_available ? "No legal change detected by the rules (modality, negation, exceptions, conditions, numbers, scope, parties)." : "Rule checks cover English and Hindi."}</p>`;
  const gm = r.generic_metrics;
  $("#result").innerHTML = `
    <div class="score-row">
      <div class="score-big">${r.lmp_score.toFixed(1)}<small> / 10</small></div>
      <div>
        <div class="badge ${decisionClass(r.decision)}">${esc(r.decision)}</div>
        <div class="muted" style="font-size:13px;margin-top:6px">Legal meaning preservation score</div>
      </div>
    </div>
    <div class="scale"><div class="scale-marker" style="left:${pos}%"></div></div>
    <div class="scale-labels"><span style="left:0">1</span><span style="left:11.1%">2</span><span style="left:61.1%">6.5</span><span style="right:0">10</span></div>
    <div class="scale-key"><span class="k-bad">not preserved</span><span class="k-warn">partially preserved</span><span class="k-good">preserved</span></div>

    <div class="section-title">Compared with generic similarity metrics</div>
    <div class="bars">
      ${barRow("Our model", r.lmp_score, 10, "ours", true, r.lmp_score.toFixed(1))}
      ${barRow("chrF (characters)", gm.chrF, 10, "", false, gm.chrF.toFixed(1))}
      ${barRow("BLEU (word n-grams)", gm.BLEU, 10, "", false, gm.BLEU.toFixed(1))}
    </div>

    <div class="section-title">Legal error types (model probability; line = 0.5 threshold)</div>
    <div class="bars">${r.error_probs.map((e) => barRow(e.label, e.p, 1, flagged.has(e.type) ? "hot" : "", flagged.has(e.type), e.p.toFixed(2))).join("")}</div>

    <div class="section-title">What changed legally (rule check)</div>
    ${findings}

    ${r.attributions.simplified.length ? `
    <div class="section-title">Which words drove the score</div>
    <div class="field-label" style="text-transform:none;letter-spacing:0">Simplified</div>
    <div class="words">${wordsHtml(r.attributions.simplified)}</div>
    <div class="field-label" style="text-transform:none;letter-spacing:0;margin-top:8px">Original</div>
    <div class="words">${wordsHtml(r.attributions.original)}</div>
    <div class="legend"><span class="neg">lowered the score</span><span class="pos">raised the score</span></div>` : ""}

    <div class="explanation">${esc(r.explanation)}</div>
    <div class="meta">
      <span>Language: ${LANG[r.lang] || r.lang}${r.lang !== r.lang_detected ? ` (detected ${LANG[r.lang_detected]})` : ""}</span>
      <span>${r.tokens} sub-word tokens${r.truncated ? " (truncated)" : ""}</span>
      <span>${r.time_ms} ms on ${String(r.device).toUpperCase()}</span>
    </div>`;
}

$("#analyze").addEventListener("click", analyze);

// ---------------------------------------------------------------- batch
function toCsv(rows) {
  if (!rows.length) return "";
  const cols = Object.keys(rows[0]);
  const q = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  return "﻿" + [cols.join(","), ...rows.map((r) => cols.map((c) => q(r[c])).join(","))].join("\n");
}
function download(name, text) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  a.download = name;
  a.click();
}
$("#batch-template").addEventListener("click", async () => {
  const ex = await api("/api/examples");
  download("pairs_template.csv", toCsv(ex.map((e) => ({ original: e.original, simplified: e.simplified, lang: e.lang }))));
});
$("#batch-download").addEventListener("click", () => lastBatch && download("lmp_results.csv", toCsv(lastBatch)));
$("#batch-run").addEventListener("click", async () => {
  const f = $("#batch-file").files[0];
  const out = $("#batch-out");
  if (!f) { out.innerHTML = '<div class="error-box" style="margin-top:14px">Choose a CSV file first.</div>'; return; }
  const fd = new FormData();
  fd.append("file", f);
  out.innerHTML = '<div class="spinner"></div>';
  try {
    const r = await api("/api/batch", { method: "POST", body: fd });
    lastBatch = r.rows;
    $("#batch-download").disabled = false;
    const avg = r.rows.reduce((s, x) => s + x.lmp_score, 0) / r.rows.length;
    const count = (d) => r.rows.filter((x) => x.decision === d).length;
    out.innerHTML = `<p class="note" style="margin:14px 0">${r.n} pairs scored in ${(r.time_ms / 1000).toFixed(1)} s · mean score ${avg.toFixed(2)} ·
        ${count("Preserved")} preserved, ${count("Partially Preserved")} partially, ${count("Not Preserved")} not preserved</p>
      <div class="table-wrap"><table class="batch-table"><thead><tr><th>#</th><th>Original</th><th>Simplified</th><th>Lang</th>
      <th class="num">Score</th><th>Decision</th><th>Error types</th><th class="num">chrF</th></tr></thead><tbody>
      ${r.rows.map((x, i) => `<tr><td>${i + 1}</td><td class="text">${esc(x.original)}</td><td class="text">${esc(x.simplified)}</td><td>${esc(x.lang)}</td>
        <td class="num"><b>${x.lmp_score.toFixed(1)}</b></td><td><span class="badge ${decisionClass(x.decision)}">${esc(x.decision)}</span></td>
        <td>${esc(x.error_types) || '<span class="muted">-</span>'}</td><td class="num">${x.chrF.toFixed(1)}</td></tr>`).join("")}
      </tbody></table></div>`;
  } catch (e) {
    out.innerHTML = `<div class="error-box" style="margin-top:14px">${esc(e.message)}</div>`;
  }
});

// ---------------------------------------------------------------- results
let resultsLoaded = false;
async function loadResults() {
  if (resultsLoaded) return;
  const out = $("#results-out");
  try {
    const s = await api("/api/results");
    resultsLoaded = true;
    out.innerHTML = renderResults(s);
  } catch (e) {
    out.innerHTML = `<div class="card error-box">${esc(e.message)}</div>`;
  }
}

function table(headers, rows, numericFrom = 1) {
  return `<div class="table-wrap"><table><thead><tr>${headers.map((h, i) => `<th class="${i >= numericFrom ? "num" : ""}">${h}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr class="${r.cls || ""}">${r.cells.map((c, i) => `<td class="${i >= numericFrom ? "num" : ""}">${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function renderResults(s) {
  const m = s.meta;
  const f3 = (x) => (typeof x === "number" ? x.toFixed(3) : esc(x));
  const head = `<div class="card">
      <h2>Final results</h2>
      <p class="muted">Model ${esc(m.model)}, ${m.seeds.length} seeds, ${m.n_test} test pairs (90 each in French, English and Hindi). ${esc(m.labels_note)}</p>
      <div class="table-wrap"><table class="headline"><thead><tr><th>Measure</th><th>Our model</th><th>Best baseline</th></tr></thead><tbody>
      ${s.headline.map((h) => `<tr><td>${esc(h.measure)}</td><td><span class="big">${esc(h.ours)}</span>${h.ours_note ? ` <span class="muted">(${esc(h.ours_note)})</span>` : ""}</td>
        <td>${esc(h.baseline)}${h.baseline_name ? ` <span class="muted">(${esc(h.baseline_name)})</span>` : ""}</td></tr>`).join("")}
      </tbody></table></div></div>`;

  const exp1 = `<div class="card"><h2>1 · Generic similarity metrics vs. our model</h2>
      ${table(["System", "Pearson", "95% CI", "Spearman", "RMSE", "MAE", "% over-estimated", "Decision F1"],
        s.exp1.map((r) => ({ cls: r.ours ? "ours" : "", cells: [r.ours ? `<b>${esc(r.system)}</b>` : esc(r.system), r.ours ? `<b>${esc(r.pearson)}</b>` : esc(r.pearson), esc(r.ci), esc(r.spearman), esc(r.rmse), esc(r.mae), esc(r.over), esc(r.f1)] })))}
      <p class="note">Ours = mean ± std over seeds. "% over-estimated" = predictions more than 0.5 points above the human score.</p>
      <figure class="figure"><img src="/results/fig_scatter.png" alt="Predicted vs human scores"><figcaption>BERTScore (left) gives almost every simplification 9-10; our model (right) follows the human scores.</figcaption></figure></div>`;

  const langs = `<div class="card"><h2>2 · Languages and zero-shot transfer</h2>
      ${table(["Test language", "Setting", "Ours: Pearson", "Best baseline"],
        s.languages.map((r) => ({ cells: [esc(r.language), esc(r.setting), `<b>${f3(r.ours)}</b>`, r.baseline == null ? "-" : `${f3(r.baseline)} <span class="muted">(${esc(r.baseline_name)})</span>`] })), 2)}
      <p class="note">The paper's French-only JUDGEBERT reaches 0.74 on French.</p></div>`;

  const sanity = `<div class="card"><h2>3 · Sanity checks</h2>
      ${table(["System", "Identical pairs scored ~10", "Unrelated legal pairs scored ~1", "Mean score, unrelated (expect 1)"],
        s.sanity.map((r) => ({ cls: r.ours ? "ours" : "", cells: [r.ours ? `<b>${esc(r.system)}</b>` : esc(r.system), `${r.identical.toFixed(1)}%`, `${r.unrelated.toFixed(1)}%`, r.unrelated_mean.toFixed(2)] })))}</div>`;

  const domain = `<div class="card"><h2>4 · New legal domain</h2>
      ${table(["Setting", "System", "Pearson", "% over-estimated", "Pairs"],
        s.domain.map((r) => ({ cells: [esc(r.setting), esc(r.system), r.pearson.toFixed(3), r.over.toFixed(1), r.n] })), 2)}
      <p class="note">The tenancy probe uses rule-labelled pairs.</p></div>`;

  const maxDrop = Math.max(...s.edits.map((e) => Math.max(e.ours, e.baseline)));
  const edits = `<div class="card"><h2>5 · Sensitivity to one legal edit</h2>
      <p class="muted">Score drop when one legal detail of a correct simplification is changed. Higher = the metric notices the change.</p>
      <div class="bars" style="margin:12px 0 6px">${s.edits.map((e) => `
        <div style="margin-bottom:6px"><div style="font-size:14px;font-weight:600;margin-bottom:3px">${esc(e.edit)}</div>
        ${barRow("Our model", Math.max(e.ours, 0), maxDrop, "ours", false, e.ours.toFixed(2))}
        ${barRow(`Best baseline (${e.baseline_name})`, Math.max(e.baseline, 0), maxDrop, "", false, e.baseline.toFixed(2))}</div>`).join("")}</div>
      <figure class="figure"><img src="/results/fig_robustness.png" alt="Score drop per legal edit and metric"><figcaption>All seven metrics, per edit type.</figcaption></figure></div>`;

  const abl = s.ablation ? `<div class="card"><h2>6 · Improvement attempt: legal-edit augmentation (negative result)</h2>
      ${table(["System (seed 42)", "Pearson", "RMSE", "% over-estimated", "Avg. edit drop", "Number edit drop", "Negation drop"],
        s.ablation.map((r) => ({ cells: [esc(r.system), r.pearson.toFixed(3), r.rmse.toFixed(2), r.over.toFixed(1), r.avg_drop.toFixed(2), r.number_drop.toFixed(2), r.negation_drop.toFixed(2)] })))}
      <p class="note">Training on rule-made edits of real pairs lowered agreement with humans, so the final model does not use it.</p></div>` : "";

  return head + exp1 + langs + sanity + domain + edits + abl;
}

init();

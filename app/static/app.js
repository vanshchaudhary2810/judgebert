const $ = (s) => document.querySelector(s);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const LANG = { en: "English", hi: "Hindi", fr: "French" };
let examples = [];
let lastBatch = null;
let resultsLoaded = false;

document.querySelectorAll(".tab").forEach((a) =>
  a.addEventListener("click", (ev) => {
    ev.preventDefault();
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === a));
    document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + a.dataset.tab));
    if (a.dataset.tab === "results") loadResults();
  })
);

async function api(path, opts) {
  const r = await fetch(path, opts);
  let body = null;
  try { body = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error((body && body.detail) || `Request failed (${r.status})`);
  return body;
}

async function init() {
  const st = $("#status");
  try {
    const s = await api("/api/status");
    if (s.model_loaded) {
      st.className = "status ok";
      st.textContent = `model loaded (${s.device})`;
    } else {
      st.className = "status err";
      st.textContent = "model not loaded";
      st.title = s.error || "";
    }
  } catch (e) {
    st.className = "status err";
    st.textContent = "server not reachable";
  }
  try {
    examples = await api("/api/examples");
    $("#example-list").innerHTML += examples.map((e, i) => `<option value="${i}">${esc(e.title)}</option>`).join("");
  } catch (_) {}
}

$("#example-list").addEventListener("change", (ev) => {
  const e = examples[+ev.target.value];
  if (!e) return;
  $("#original").value = e.original;
  $("#simplified").value = e.simplified;
  $("#lang").value = e.lang;
  analyze();
});

function decisionClass(d) {
  return d === "Preserved" ? "d-good" : d === "Not Preserved" ? "d-bad" : "d-warn";
}

function wordsHtml(pairs) {
  if (!pairs || !pairs.length) return "-";
  const m = Math.max(...pairs.map(([, s]) => Math.abs(s)), 1e-9);
  return pairs
    .map(([w, s]) => {
      const a = Math.min(Math.abs(s) / m, 1);
      const bg = s < 0 ? `rgba(200,60,50,${(0.5 * a).toFixed(3)})` : `rgba(60,140,80,${(0.4 * a).toFixed(3)})`;
      return `<span class="w" style="background:${a > 0.08 ? bg : "transparent"}" title="${s.toFixed(4)}">${esc(w)}</span>`;
    })
    .join(" ");
}

async function analyze() {
  const original = $("#original").value.trim();
  const simplified = $("#simplified").value.trim();
  const out = $("#result");
  if (!original || !simplified) {
    out.innerHTML = '<p class="error">Both the original and the simplified text are required.</p>';
    return;
  }
  const btn = $("#analyze");
  btn.disabled = true;
  out.innerHTML = '<p class="hint">Analyzing&hellip;</p>';
  try {
    const r = await api("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ original, simplified, lang: $("#lang").value, explain_words: $("#words").checked }),
    });
    renderResult(r);
  } catch (e) {
    out.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  } finally {
    btn.disabled = false;
  }
}

function renderResult(r) {
  const pos = ((r.lmp_score - 1) / 9) * 100;
  const flagged = new Set(r.error_types);
  const gm = r.generic_metrics;
  const findings = r.rule_findings.length
    ? `<ul>${r.rule_findings.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>`
    : `<p class="hint">${r.rules_available ? "No change found by the rules." : "Rule checks are available for English and Hindi only."}</p>`;
  const errRows = r.error_probs
    .map((e) => `<tr class="${flagged.has(e.type) ? "flag" : ""}"><td>${esc(e.label)}</td>
      <td><span class="mini" style="width:${Math.round(e.p * 120)}px"></span></td><td class="n">${e.p.toFixed(2)}</td></tr>`)
    .join("");
  $("#result").innerHTML = `
    <p class="score-line"><span class="score-num">${r.lmp_score.toFixed(1)}</span> / 10 &nbsp;
      <span class="${decisionClass(r.decision)}">${esc(r.decision)}</span></p>
    <div class="scale"><div class="s1"></div><div class="s2"></div><div class="s3"></div><div class="mark" style="left:calc(${pos}% - 1px)"></div></div>
    <div class="ticks"><span style="left:0">1</span><span style="left:calc(11.1% - 3px)">2</span><span style="left:calc(61.1% - 8px)">6.5</span><span style="right:0">10</span></div>

    <h3>Comparison with generic metrics</h3>
    <table><tr><th>Metric</th><th class="n">Score (1-10)</th></tr>
      <tr class="hl"><td>This model</td><td class="n">${r.lmp_score.toFixed(1)}</td></tr>
      <tr><td>chrF</td><td class="n">${gm.chrF.toFixed(1)}</td></tr>
      <tr><td>BLEU</td><td class="n">${gm.BLEU.toFixed(1)}</td></tr></table>

    <h3>Legal error types</h3>
    <table><tr><th>Type</th><th>Probability</th><th class="n"></th></tr>${errRows}</table>
    <p class="note">Types with probability 0.5 or more are marked in red.</p>

    <h3>Rule-based check</h3>
    ${findings}

    ${r.attributions.simplified.length ? `
    <h3>Word attributions</h3>
    <p class="note">Red: lowered the score. Green: raised it.</p>
    <p><b>Simplified:</b></p><div class="words">${wordsHtml(r.attributions.simplified)}</div>
    <p><b>Original:</b></p><div class="words">${wordsHtml(r.attributions.original)}</div>` : ""}

    <div class="explain">${esc(r.explanation)}</div>
    <p class="meta">${LANG[r.lang] || r.lang}${r.lang !== r.lang_detected ? ` (detected: ${LANG[r.lang_detected]})` : ""} &middot;
      ${r.tokens} tokens${r.truncated ? " (truncated)" : ""} &middot; ${r.time_ms} ms on ${esc(r.device)}</p>`;
}

$("#analyze").addEventListener("click", analyze);

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
  const ex = examples.length ? examples : await api("/api/examples");
  download("pairs_template.csv", toCsv(ex.map((e) => ({ original: e.original, simplified: e.simplified, lang: e.lang }))));
});

$("#batch-download").addEventListener("click", () => lastBatch && download("lmp_results.csv", toCsv(lastBatch)));

$("#batch-run").addEventListener("click", async () => {
  const f = $("#batch-file").files[0];
  const out = $("#batch-out");
  if (!f) { out.innerHTML = '<p class="error">Choose a CSV file first.</p>'; return; }
  const fd = new FormData();
  fd.append("file", f);
  out.innerHTML = '<p class="hint">Scoring&hellip;</p>';
  try {
    const r = await api("/api/batch", { method: "POST", body: fd });
    lastBatch = r.rows;
    $("#batch-download").disabled = false;
    const avg = r.rows.reduce((s, x) => s + x.lmp_score, 0) / r.rows.length;
    const count = (d) => r.rows.filter((x) => x.decision === d).length;
    out.innerHTML = `<p>${r.n} pairs scored in ${(r.time_ms / 1000).toFixed(1)} s. Mean score ${avg.toFixed(2)};
        ${count("Preserved")} preserved, ${count("Partially Preserved")} partially preserved, ${count("Not Preserved")} not preserved.</p>
      <div class="wrap-table"><table><tr><th>#</th><th>Original</th><th>Simplified</th><th>Lang</th><th class="n">Score</th><th>Decision</th><th>Error types</th><th class="n">chrF</th></tr>
      ${r.rows.map((x, i) => `<tr><td>${i + 1}</td><td>${esc(x.original)}</td><td>${esc(x.simplified)}</td><td>${esc(x.lang)}</td>
        <td class="n"><b>${x.lmp_score.toFixed(1)}</b></td><td class="${decisionClass(x.decision)}">${esc(x.decision)}</td>
        <td>${esc(x.error_types) || "-"}</td><td class="n">${x.chrF.toFixed(1)}</td></tr>`).join("")}
      </table></div>`;
  } catch (e) {
    out.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
});

async function loadResults() {
  if (resultsLoaded) return;
  const out = $("#results-out");
  try {
    const s = await api("/api/results");
    resultsLoaded = true;
    out.innerHTML = renderResults(s);
  } catch (e) {
    out.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

function table(headers, rows, numFrom = 1) {
  return `<div class="wrap-table"><table><tr>${headers.map((h, i) => `<th class="${i >= numFrom ? "n" : ""}">${h}</th>`).join("")}</tr>
    ${rows.map((r) => `<tr class="${r.cls || ""}">${r.cells.map((c, i) => `<td class="${i >= numFrom ? "n" : ""}">${c}</td>`).join("")}</tr>`).join("")}</table></div>`;
}

function renderResults(s) {
  const m = s.meta;
  const f3 = (x) => (typeof x === "number" ? x.toFixed(3) : esc(x));
  const head = `<h2>Final results</h2>
    <p>Model ${esc(m.model)}, ${m.seeds.length} seeds, ${m.n_test} test pairs (90 each in French, English and Hindi). ${esc(m.labels_note)}</p>
    ${table(["Measure", "Our model", "Best baseline"],
      s.headline.map((h) => ({ cells: [esc(h.measure), `<b>${esc(h.ours)}</b>${h.ours_note ? ` (${esc(h.ours_note)})` : ""}`,
        `${esc(h.baseline)}${h.baseline_name ? ` (${esc(h.baseline_name)})` : ""}`] })), 9)}`;

  const exp1 = `<h2>1. Generic similarity metrics vs. our model</h2>
    ${table(["System", "Pearson", "95% CI", "Spearman", "RMSE", "MAE", "% over-estimated", "Decision F1"],
      s.exp1.map((r) => ({ cls: r.ours ? "hl" : "", cells: [esc(r.system), esc(r.pearson), esc(r.ci), esc(r.spearman), esc(r.rmse), esc(r.mae), esc(r.over), esc(r.f1)] })))}
    <p class="note">Our model: mean &plusmn; std over seeds. % over-estimated: predictions more than 0.5 above the human score.</p>
    <div class="figure"><img src="/results/fig_scatter.png" alt="Predicted vs human scores"></div>`;

  const langs = `<h2>2. Languages and zero-shot transfer</h2>
    ${table(["Test language", "Setting", "Our model (Pearson)", "Best baseline"],
      s.languages.map((r) => ({ cells: [esc(r.language), esc(r.setting), f3(r.ours), r.baseline == null ? "-" : `${f3(r.baseline)} (${esc(r.baseline_name)})`] })), 2)}
    <p class="note">JUDGEBERT (French only) reports 0.74 on French.</p>`;

  const sanity = `<h2>3. Sanity checks</h2>
    ${table(["System", "Identical pairs scored ~10", "Unrelated pairs scored ~1", "Mean score on unrelated pairs"],
      s.sanity.map((r) => ({ cls: r.ours ? "hl" : "", cells: [esc(r.system), `${r.identical.toFixed(1)}%`, `${r.unrelated.toFixed(1)}%`, r.unrelated_mean.toFixed(2)] })))}`;

  const domain = `<h2>4. New legal domain</h2>
    ${table(["Setting", "System", "Pearson", "% over-estimated", "Pairs"],
      s.domain.map((r) => ({ cells: [esc(r.setting), esc(r.system), r.pearson.toFixed(3), r.over.toFixed(1), r.n] })), 2)}
    <p class="note">The tenancy probe uses rule-labelled pairs.</p>`;

  const edits = `<h2>5. Sensitivity to one legal edit</h2>
    <p>Average drop in score when one legal detail of a correct simplification is changed (higher is better).</p>
    ${table(["Edit", "Our model", "Best baseline"],
      s.edits.map((e) => ({ cells: [esc(e.edit), `<b>${e.ours.toFixed(2)}</b>`, `${e.baseline.toFixed(2)} (${esc(e.baseline_name)})`] })))}
    <div class="figure"><img src="/results/fig_robustness.png" alt="Score drop per edit type"></div>`;

  const abl = s.ablation ? `<h2>6. Improvement attempt: legal-edit augmentation</h2>
    ${table(["System (seed 42)", "Pearson", "RMSE", "% over-estimated", "Avg. edit drop", "Number drop", "Negation drop"],
      s.ablation.map((r) => ({ cells: [esc(r.system), r.pearson.toFixed(3), r.rmse.toFixed(2), r.over.toFixed(1), r.avg_drop.toFixed(2), r.number_drop.toFixed(2), r.negation_drop.toFixed(2)] })))}
    <p class="note">The augmentation lowered agreement with human scores, so the final model does not use it.</p>` : "";

  return head + exp1 + langs + sanity + domain + edits + abl;
}

init();

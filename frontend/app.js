// AI Teacher frontend logic — full journey:
// upload -> plan -> teach -> question -> answer -> adapt -> video -> quiz -> report
const $ = (id) => document.getElementById(id);
const api = (p, body) =>
  fetch(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
    .then(async (r) => { if (!r.ok) throw new Error((await r.json()).detail || r.statusText); return r.json(); });

let state = { sessionId: null, plan: null, materialId: null, current: null, quiz: [] };

// ---------- health ----------
fetch("/api/health").then(r => r.json()).then(h => {
  const el = $("health");
  el.textContent = `LLM: ${h.llm_provider}${h.llm_ready ? " ✓" : " ⚠ set key"} · TTS: ${h.tts} · Avatar: ${h.avatar}`;
  el.className = "ml-auto text-xs px-3 py-1 rounded-full " + (h.llm_ready ? "bg-emerald-900/50 text-emerald-300" : "bg-amber-900/50 text-amber-300");
}).catch(() => {});

// ---------- upload ----------
$("file").addEventListener("change", async (e) => {
  const f = e.target.files[0]; if (!f) return;
  $("fileLabel").textContent = "Uploading & indexing…";
  const fd = new FormData(); fd.append("file", f);
  try {
    const r = await fetch("/api/upload", { method: "POST", body: fd }).then(x => x.json());
    if (r.detail) throw new Error(r.detail);
    state.materialId = r.material_id;
    $("fileLabel").textContent = f.name;
    $("matInfo").textContent = `✓ Indexed ${r.chunks} chunks (${r.chars.toLocaleString()} chars) for grounded (RAG) teaching.`;
  } catch (err) { $("matInfo").className = "text-xs text-rose-400 mt-2"; $("matInfo").textContent = "✗ " + err.message; }
});

// ---------- plan ----------
$("startBtn").addEventListener("click", async () => {
  const btn = $("startBtn"); btn.disabled = true; btn.innerHTML = '<span class="spin"></span> Planning…';
  try {
    const body = {
      instruction: $("instruction").value.trim(),
      topic: $("topic").value.trim(),
      material_id: state.materialId,
      level: $("level").value, language: $("language").value,
      time_minutes: parseInt($("time").value) || 20, goal: $("goal").value.trim(),
    };
    const r = await api("/api/plan", body);
    state.sessionId = r.session_id; state.plan = r.plan;
    renderPlan(r.plan, r.profile);
  } catch (e) { alert("Planning failed: " + e.message); }
  finally { btn.disabled = false; btn.textContent = "Plan my lesson →"; }
});

function renderPlan(plan, profile) {
  $("planCard").classList.remove("hidden");
  $("quizCard").classList.remove("hidden");
  $("planTopic").textContent = "📚 " + plan.topic;
  $("planMeta").textContent = `${plan.subject} · ${plan.total_minutes} min · ${profile.level} · ${plan.language} · ${plan.segments.length} segments`;
  const box = $("segs"); box.innerHTML = "";
  plan.segments.forEach((s) => {
    const d = document.createElement("div");
    d.className = "seg cursor-pointer border border-slate-700 rounded-lg p-2.5 text-sm flex items-center gap-2";
    d.innerHTML = `<span class="w-6 h-6 grid place-items-center rounded bg-slate-700 text-xs">${s.id}</span>
      <span class="flex-1">${s.title}</span><span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-700">${s.visual_type}</span>`;
    d.onclick = () => teach(s.id, d);
    box.appendChild(d);
  });
  // auto-start first segment
  if (plan.segments[0]) teach(plan.segments[0].id, box.firstChild);
}

// ---------- teach a segment ----------
async function teach(segId, el, adapt) {
  document.querySelectorAll(".seg").forEach(x => x.classList.remove("active"));
  if (el) el.classList.add("active");
  const stage = $("stage");
  stage.className = "glass rounded-2xl p-6 min-h-[320px]";
  stage.innerHTML = `<div class="grid place-items-center h-64 text-slate-400"><span class="spin"></span></div>`;
  try {
    const c = await api("/api/teach", { session_id: state.sessionId, segment_id: segId, adapt: adapt || null });
    state.current = { segId, concept: c.title };
    renderSegment(c, segId);
  } catch (e) { stage.innerHTML = `<p class="text-rose-400">${e.message}</p>`; }
}

function renderSegment(c, segId) {
  const v = c.visual;
  const stage = $("stage");
  stage.className = "glass rounded-2xl p-6 fade";
  stage.innerHTML = `
    <div class="flex items-start gap-4">
      <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-sky-400 to-indigo-500 grid place-items-center text-3xl shrink-0">🧑‍🏫</div>
      <div class="flex-1">
        <h3 class="font-semibold text-lg">${c.title}</h3>
        <p class="text-slate-300 mt-1 leading-relaxed">${c.narration}</p>
      </div>
    </div>
    <div class="mt-4 grid md:grid-cols-2 gap-4">
      <div class="bg-slate-900/60 rounded-xl p-4">
        <p class="text-xs text-sky-400 mb-2">ON SCREEN · ${v.type.toUpperCase()}</p>
        <ul class="space-y-1 text-sm">${(c.on_screen||[]).map(b=>`<li>• ${b}</li>`).join("")}</ul>
        ${v.equation?`<p class="mt-3 text-amber-300 font-mono text-lg">${v.equation}</p>`:""}
        ${v.code?`<pre class="mt-3 bg-black/50 rounded p-2 text-xs overflow-auto">${escapeHtml(v.code)}</pre>`:""}
      </div>
      <div class="bg-slate-900/60 rounded-xl p-4">
        <p class="text-xs text-emerald-400 mb-2">EXAMPLE</p>
        <p class="text-sm text-slate-300">${c.example||"—"}</p>
      </div>
    </div>
    <div class="flex flex-wrap gap-2 mt-4">
      <button class="btn text-sm px-3 py-1.5 rounded-lg bg-sky-600" onclick="askQuestion(${segId})">❓ Ask me a question</button>
      <button class="btn text-sm px-3 py-1.5 rounded-lg bg-slate-700" onclick="teach(${segId},null,'simplify')">🐢 Simplify</button>
      <button class="btn text-sm px-3 py-1.5 rounded-lg bg-slate-700" onclick="teach(${segId},null,'harder')">🚀 Go deeper</button>
      <button class="btn text-sm px-3 py-1.5 rounded-lg bg-slate-700" onclick="teach(${segId},null,'example')">➕ Another example</button>
      <button class="btn text-sm px-3 py-1.5 rounded-lg bg-emerald-700 ml-auto" onclick="nextSeg(${segId})">Next →</button>
    </div>
    <div id="qa" class="mt-4"></div>`;
}

function nextSeg(segId) {
  const segs = state.plan.segments; const i = segs.findIndex(s => s.id === segId);
  if (i < segs.length - 1) {
    const nxt = segs[i + 1];
    teach(nxt.id, document.querySelectorAll(".seg")[i + 1]);
  } else { alert("Lesson complete! Scroll to the Final Assessment 📝"); }
}

// ---------- interactive question ----------
async function askQuestion(segId) {
  const qa = $("qa"); qa.innerHTML = `<span class="spin"></span>`;
  const q = await api("/api/question", { session_id: state.sessionId, segment_id: segId });
  renderQuestion(q, qa);
}

function renderQuestion(q, mount) {
  let opts = "";
  if (q.type === "mcq" && q.options.length) {
    opts = q.options.map(o => `<label class="block bg-slate-900/60 rounded-lg p-2 cursor-pointer hover:bg-slate-800 text-sm">
      <input type="radio" name="opt_${q.id}" value="${escapeAttr(o)}" class="mr-2">${o}</label>`).join("");
  } else {
    opts = `<input id="ans_${q.id}" class="w-full bg-slate-900/60 rounded-lg p-2 text-sm" placeholder="Type your answer…">`;
  }
  mount.innerHTML = `<div class="bg-indigo-950/40 border border-indigo-500/30 rounded-xl p-4 fade">
    <p class="font-medium mb-2">🤔 ${q.text}</p>
    <div class="space-y-2">${opts}</div>
    <button class="btn mt-3 text-sm px-3 py-1.5 rounded-lg bg-indigo-600" onclick="submitAns('${q.id}')">Submit answer</button>
    <div id="res_${q.id}" class="mt-3"></div>
  </div>`;
}

async function submitAns(qid) {
  let val = "";
  const radio = document.querySelector(`input[name="opt_${qid}"]:checked`);
  val = radio ? radio.value : ($(`ans_${qid}`)?.value || "");
  const res = $(`res_${qid}`); res.innerHTML = `<span class="spin"></span>`;
  const r = await api("/api/answer", { session_id: state.sessionId, question_id: qid, answer: val });
  const ev = r.evaluation;
  const color = ev.correct ? "emerald" : "rose";
  let html = `<div class="bg-${color}-950/40 border border-${color}-500/30 rounded-lg p-3 text-sm fade">
    <p><b>${ev.correct ? "✅ Correct" : "❌ Not quite"}</b> · understanding ${(ev.understanding*100).toFixed(0)}%</p>
    <p class="text-slate-300 mt-1">${ev.feedback}</p>
    ${ev.misconception?`<p class="text-amber-300 mt-1 text-xs">Misconception spotted: ${ev.misconception}</p>`:""}</div>`;
  if (r.remediation) {
    html += `<div class="bg-slate-900/60 rounded-lg p-3 mt-2 text-sm fade">
      <p class="text-sky-400 text-xs mb-1">🔄 LET ME RE-EXPLAIN</p>
      <p class="text-slate-200">${r.remediation.narration}</p>
      <p class="text-slate-400 text-xs mt-2">New example: ${r.remediation.example}</p>
      <div id="qa2"></div></div>`;
  }
  res.innerHTML = html;
  if (r.remediation) renderQuestion(r.remediation.recheck, document.getElementById("qa2"));
}

// ---------- video ----------
$("videoBtn").addEventListener("click", async () => {
  const b = $("videoBtn"); b.disabled = true; b.innerHTML = '<span class="spin"></span> Rendering video (voice + visuals + avatar)… this can take a few minutes';
  try {
    const r = await api("/api/video", { session_id: state.sessionId });
    $("videoCard").classList.remove("hidden");
    $("player").src = r.video_url + "?t=" + Date.now();
    $("videoCard").scrollIntoView({ behavior: "smooth" });
  } catch (e) { alert("Video failed: " + e.message); }
  finally { b.disabled = false; b.textContent = "🎬 Generate full teaching video"; }
});

// ---------- quiz ----------
$("quizBtn").addEventListener("click", async () => {
  const box = $("quiz"); box.innerHTML = `<span class="spin"></span>`;
  const r = await api("/api/quiz", { session_id: state.sessionId, n: 5 });
  state.quiz = r.questions;
  box.innerHTML = r.questions.map((q, i) => {
    const opts = (q.type === "mcq" && q.options.length)
      ? q.options.map(o => `<label class="block text-sm"><input type="radio" name="q_${q.id}" value="${escapeAttr(o)}" class="mr-2">${o}</label>`).join("")
      : `<input id="qz_${q.id}" class="w-full bg-slate-900/60 rounded p-2 text-sm mt-1" placeholder="Answer">`;
    return `<div class="bg-slate-900/50 rounded-lg p-3"><p class="text-sm font-medium">${i+1}. ${q.text}</p><div class="mt-2 space-y-1">${opts}</div></div>`;
  }).join("") + `<button class="btn mt-2 px-4 py-2 rounded-lg bg-emerald-600 font-semibold" onclick="gradeQuiz()">Submit & get report</button>`;
});

async function gradeQuiz() {
  const answers = {};
  state.quiz.forEach(q => {
    const radio = document.querySelector(`input[name="q_${q.id}"]:checked`);
    answers[q.id] = radio ? radio.value : (document.getElementById(`qz_${q.id}`)?.value || "");
  });
  const rep = $("report"); rep.classList.remove("hidden"); rep.innerHTML = `<span class="spin"></span>`;
  const r = await api("/api/grade", { session_id: state.sessionId, answers });
  const R = r.report;
  rep.innerHTML = `<div class="fade">
    <div class="flex items-center gap-3"><div class="text-4xl font-bold text-sky-400">${R.score}%</div>
      <div class="text-sm text-slate-300">Learning report for <b>${R.topic}</b></div></div>
    <div class="grid md:grid-cols-2 gap-3 mt-3 text-sm">
      <div class="bg-emerald-950/30 rounded-lg p-3"><p class="text-emerald-400 text-xs mb-1">STRONG</p>${(R.strong_areas||[]).map(x=>`<div>• ${x}</div>`).join("")||"—"}</div>
      <div class="bg-rose-950/30 rounded-lg p-3"><p class="text-rose-400 text-xs mb-1">NEEDS WORK</p>${(R.weak_areas||[]).map(x=>`<div>• ${x}</div>`).join("")||"—"}</div>
    </div>
    <p class="mt-3 text-sm"><b class="text-sky-400">Recommendation:</b> ${R.recommendation}</p>
    <p class="mt-1 text-sm"><b class="text-indigo-400">Learn next:</b> ${R.next_topic}</p>
  </div>`;
}

function escapeHtml(s){return (s||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));}
function escapeAttr(s){return (s||"").replace(/"/g,"&quot;");}
window.teach = teach; window.askQuestion = askQuestion; window.submitAns = submitAns;
window.gradeQuiz = gradeQuiz; window.nextSeg = nextSeg;
"""The web page served at http://127.0.0.1:<http_port>/ (one self-contained document, no external requests)."""

PANEL_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIBody remote</title>
<style>
body{font:15px system-ui,sans-serif;margin:0;background:#15181d;color:#e6e6e6}
main{max-width:46rem;margin:0 auto;padding:1rem}
h1{font-size:1.2rem;margin:.2rem 0 .8rem}
section{background:#1e232a;border-radius:8px;padding:.8rem;margin:.7rem 0}
h2{font-size:.9rem;margin:0 0 .5rem;color:#9fb3c8;text-transform:uppercase;letter-spacing:.04em}
input,select,button,textarea{font:inherit;color:inherit;background:#2a313a;border:1px solid #3b4551;border-radius:6px;padding:.4rem .6rem}
textarea{width:100%;box-sizing:border-box;min-height:3.2rem}
button{cursor:pointer}button:hover{background:#34404c}
.row{display:flex;flex-wrap:wrap;gap:.4rem;margin:.3rem 0;align-items:center}
.chips button{padding:.25rem .55rem}
#state{font-size:.85rem;color:#9fb3c8;white-space:pre-wrap}
#msg{min-height:1.2rem;font-size:.85rem}.err{color:#ff8a80}.ok{color:#8fd694}
</style></head><body><main>
<h1>AIBody remote</h1>
<section id="login"><h2>Token</h2>
<div class="row"><input id="token" type="password" size="34" placeholder="remote.token from config.json" autocomplete="off">
<button id="save">Connect</button></div>
<div style="font-size:.8rem;color:#9fb3c8">The token stays in this tab's session storage. Opening the page as
http://127.0.0.1:PORT/#token=... fills it in (a fragment is never sent to the server).</div></section>
<section><h2>Status</h2><div id="state">not connected</div><div id="msg"></div></section>
<section><h2>Speak</h2><textarea id="text" placeholder="Text"></textarea>
<div class="row"><button data-act="say">Say exactly this</button><button data-act="ask">Ask the AI</button>
<button data-act="event">Scene event</button><button data-act="stop">Stop</button>
<label><input type="checkbox" id="interrupt"> interrupt</label></div></section>
<section><h2>Expression</h2><div class="row chips" id="expressions"></div></section>
<section><h2>Gesture</h2><div class="row chips" id="gestures"></div></section>
<section><h2>Pose</h2><div class="row chips" id="poses"></div></section>
<section><h2>Eyes</h2><div class="row chips" id="look"></div></section>
<section><h2>Push-to-talk</h2><div class="row"><button data-ptt="start">Start</button>
<button data-ptt="stop">Stop</button></div></section>
<script>
"use strict";
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem("aibody_token") || "";
if (location.hash.startsWith("#token=")) {
  token = decodeURIComponent(location.hash.slice(7));
  sessionStorage.setItem("aibody_token", token);
  history.replaceState(null, "", location.pathname);
}
$("token").value = token;
function show(text, ok) { const m = $("msg"); m.textContent = text; m.className = ok ? "ok" : "err"; }
async function call(path, body) {
  const options = {headers: {"Authorization": "Bearer " + token}};
  if (body !== undefined) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const r = await fetch(path, options);
  const data = await r.json().catch(() => ({ok: false, error: "bad answer"}));
  if (!r.ok || !data.ok) throw new Error(data.error || ("HTTP " + r.status));
  return data;
}
async function act(name, params) {
  try { await call("/api/" + name, params || {}); show(name + ": sent", true); }
  catch (e) { show(name + ": " + e.message, false); }
}
function chips(id, names, make) {
  const box = $(id);
  const key = names.join("\\n");
  if (box.dataset.key === key) return;
  box.dataset.key = key;
  box.replaceChildren(...names.map(n => {
    const b = document.createElement("button");
    b.textContent = n; b.onclick = () => make(n); return b;
  }));
}
async function refresh() {
  if (!token) return;
  try {
    const s = await call("/api/status");
    const lines = [
      "Plugin: " + (s.plugin_connected ? "connected (" + s.link + ")" : "not connected"),
      "Mode: " + (s.mode ? s.mode.active + " (requested " + s.mode.requested + ")" : "?"),
      "Persona: " + (s.persona || "-"),
      "Microphone: " + (s.mic ? (s.mic.mode + (s.mic.ptt_active ? ", talking" : "")) : "?"),
      "Last: " + (s.turn || "-")];
    if (s.last_action && s.last_action.action) {
      lines.push("Remote: " + s.last_action.action + (s.last_action.ok ? "" : " FAILED - " + s.last_action.note));
    }
    $("state").textContent = lines.join("\\n");
    chips("expressions", s.expressions || [], n => act("expression", {name: n}));
    chips("gestures", s.gestures || [], n => act("gesture", {name: n}));
    chips("poses", s.poses || [], n => act("pose", {name: n}));
    const targets = ["client", "camera", "forward", "away", "off"];
    chips("look", targets.concat((s.gaze_atoms || []).map(a => "atom:" + a)), n =>
      n.startsWith("atom:") ? act("look", {target: "atom", atom: n.slice(5)}) : act("look", {target: n}));
  } catch (e) { $("state").textContent = "not connected: " + e.message; }
}
$("save").onclick = () => { token = $("token").value.trim(); sessionStorage.setItem("aibody_token", token); refresh(); };
document.querySelectorAll("button[data-act]").forEach(b => b.onclick = () => {
  const name = b.dataset.act, text = $("text").value;
  if (name === "stop") return act("stop");
  const params = {text};
  if (name === "say") params.interrupt = $("interrupt").checked;
  act(name, params);
});
document.querySelectorAll("button[data-ptt]").forEach(b => b.onclick = () => act("ptt", {action: b.dataset.ptt}));
refresh(); setInterval(refresh, 1500);
</script></main></body></html>
"""

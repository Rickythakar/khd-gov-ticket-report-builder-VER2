with open("templates/dashboard.html", "w") as f:
    f.write(r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ app_name }}</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
/* ============================================================
   ASCII-BRUTALIST DESIGN SYSTEM v2
   Bloomberg terminal x Luxury tech brand
   Dense. Sharp. Tasteful.
   ============================================================ */
:root {
  --bg: #030303;
  --surface: #0a0a0a;
  --surface-hover: #111111;
  --raised: #161616;
  --border: #1f1f1f;
  --border-hi: #333333;
  
  --amber: #ffb800;
  --amber-dim: rgba(255, 184, 0, 0.15);
  --cyan: #00e5ff;
  --cyan-dim: rgba(0, 229, 255, 0.15);
  --blue: #0066ff;
  --green: #00fa9a;
  --red: #ff3366;
  
  --text: #a0aab2;
  --bright: #ffffff;
  --dim: #55626d;
  --faint: #2a3238;
  
  --font: 'JetBrains Mono', monospace;
  --ease: cubic-bezier(0.16, 1, 0.3, 1);
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background-color: var(--bg);
  /* Luxury dot matrix grid */
  background-image: radial-gradient(var(--border) 1px, transparent 1px);
  background-size: 24px 24px;
  background-position: -12px -12px;
  color: var(--text);
  font-family: var(--font);
  font-size: 11px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

::selection { background: var(--cyan-dim); color: var(--cyan); }
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 0; }
::-webkit-scrollbar-thumb:hover { background: var(--cyan); }

/* ---- LAYOUT ---- */
.app { display: flex; min-height: 100vh; }

/* ---- SIDEBAR ---- */
.side {
  width: 240px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 10;
  box-shadow: 10px 0 30px rgba(0,0,0,0.8);
}
.side-inner {
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100vh;
  position: sticky;
  top: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
  position: relative;
}
.brand-mark {
  font-size: 28px;
  font-weight: 800;
  color: var(--cyan);
  background: #041021;
  border: 1px solid rgba(0, 229, 255, 0.2);
  padding: 0 6px;
  line-height: 1.1;
  letter-spacing: -2px;
  box-shadow: 0 0 20px rgba(0, 229, 255, 0.1);
  position: relative;
  display: inline-block;
}
.brand-mark::before, .brand-mark::after {
  content: "HD";
  position: absolute;
  top: -1px; left: 0; width: 100%; height: 100%;
  background: transparent;
  padding: 0 6px;
  color: var(--cyan);
  border: 1px solid transparent;
  pointer-events: none;
}
.brand-mark::before {
  left: 2px;
  text-shadow: -2px 0 var(--red);
  clip-path: inset(0 0 0 0);
  animation: glitch-anim-1 3s infinite linear alternate-reverse;
}
.brand-mark::after {
  left: -2px;
  text-shadow: 2px 0 var(--amber);
  clip-path: inset(0 0 0 0);
  animation: glitch-anim-2 2.5s infinite linear alternate-reverse;
}
@keyframes glitch-anim-1 {
  0% { clip-path: inset(20% 0 80% 0); transform: translate(0); }
  2% { clip-path: inset(10% 0 60% 0); transform: translate(-2px, 1px); }
  4% { clip-path: inset(80% 0 10% 0); transform: translate(2px, -1px); }
  6% { clip-path: inset(40% 0 30% 0); transform: translate(-2px, 2px); }
  8% { clip-path: inset(0 0 100% 0); transform: translate(0); }
  100% { clip-path: inset(0 0 100% 0); transform: translate(0); }
}
@keyframes glitch-anim-2 {
  0% { clip-path: inset(10% 0 50% 0); transform: translate(0); }
  2% { clip-path: inset(80% 0 5% 0); transform: translate(2px, -2px); }
  4% { clip-path: inset(30% 0 40% 0); transform: translate(-2px, 1px); }
  6% { clip-path: inset(60% 0 20% 0); transform: translate(2px, 2px); }
  8% { clip-path: inset(0 0 100% 0); transform: translate(0); }
  100% { clip-path: inset(0 0 100% 0); transform: translate(0); }
}
.brand-name { font-size: 9px; color: var(--dim); letter-spacing: 0.2em; text-transform: uppercase; line-height: 1.4; }
.brand-name b { color: var(--bright); font-weight: 700; display: block; font-size: 11px; letter-spacing: 0.1em; }

/* Upload */
.drop {
  border: 1px dashed var(--border-hi);
  background: rgba(255,255,255,0.01);
  padding: 16px 10px;
  text-align: center;
  cursor: pointer;
  position: relative;
  transition: all 0.2s var(--ease);
}
.drop:hover { border-color: var(--amber); background: var(--amber-dim); }
.drop.loaded { border-color: var(--green); border-style: solid; background: rgba(0,250,154,0.05); }
.drop input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.drop-icon { color: var(--dim); font-size: 16px; margin-bottom: 4px; transition: color 0.2s; }
.drop:hover .drop-icon { color: var(--amber); }
.drop-text { color: var(--text); font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; }
.drop-file { color: var(--green); font-size: 10px; word-break: break-all; font-weight: 600; }

/* Mode */
.mode-label { font-size: 9px; color: var(--dim); letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: -8px; }
.mode-row { display: flex; border: 1px solid var(--border); }
.mode-btn {
  flex: 1;
  padding: 8px 4px;
  font-family: var(--font);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  background: transparent;
  border: none;
  border-right: 1px solid var(--border);
  color: var(--dim);
  cursor: pointer;
  transition: all 0.2s;
}
.mode-btn:last-child { border-right: none; }
.mode-btn:hover { color: var(--bright); background: var(--raised); }
.mode-btn.on { color: var(--bg); background: var(--amber); }

.spacer { flex: 1; }

/* Sidebar buttons */
.side-actions { display: flex; flex-direction: column; gap: 8px; }
.s-btn {
  font-family: var(--font);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  padding: 10px;
  border: 1px solid var(--border-hi);
  background: transparent;
  color: var(--text);
  cursor: pointer;
  transition: all 0.2s var(--ease);
  text-align: center;
  position: relative;
  overflow: hidden;
}
.s-btn::before {
  content: '';
  position: absolute;
  top: 0; left: -100%; width: 100%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
  transition: left 0.4s var(--ease);
}
.s-btn:hover::before { left: 100%; }
.s-btn:hover { border-color: var(--bright); color: var(--bright); background: var(--raised); }
.s-btn.pri { background: var(--cyan-dim); border-color: var(--cyan); color: var(--cyan); }
.s-btn.pri:hover { background: var(--cyan); color: var(--bg); box-shadow: 0 0 15px var(--cyan-dim); }
.s-btn:disabled { opacity: 0.3; pointer-events: none; }

/* ---- MAIN ---- */
.main { flex: 1; padding: 24px 32px; height: 100vh; overflow-y: auto; overflow-x: hidden; }

/* Header */
.head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-hi);
  margin-bottom: 24px;
}
.head-title { font-size: 14px; font-weight: 300; letter-spacing: 0.3em; text-transform: uppercase; color: var(--bright); display: flex; align-items: center; gap: 12px; }
.head-title::before { content: ""; display: block; width: 12px; height: 12px; background: var(--amber); animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
.head-meta { display: flex; gap: 16px; font-size: 11px; }
.tag { color: var(--dim); display: flex; align-items: center; gap: 6px; }
.tag::before { content: "///"; color: var(--border-hi); letter-spacing: -1px; }
.tag.hi { color: var(--cyan); font-weight: 700; }
.tag.hi::before { color: var(--cyan); }

/* ---- METRIC GRID (Top Row) ---- */
.grid-top {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.m-card {
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 16px;
  position: relative;
  transition: all 0.2s var(--ease);
}
.m-card::before {
  content: ""; position: absolute; top: 0; left: 0; width: 3px; height: 100%;
  background: var(--border-hi); transition: background 0.2s;
}
.m-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.6); border-color: var(--border-hi); }
.m-card:hover::before { background: var(--cyan); }
.m-card:nth-child(3n+1):hover::before { background: var(--amber); }
.m-card:nth-child(3n+2):hover::before { background: var(--cyan); }
.m-card:nth-child(3n+3):hover::before { background: var(--green); }

.m-label { font-size: 9px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.15em; font-weight: 600; margin-bottom: 4px; }
.m-val { font-size: 28px; font-weight: 300; color: var(--bright); line-height: 1; letter-spacing: -1px; }
.m-val .unit { font-size: 12px; font-weight: 400; color: var(--dim); margin-left: 2px; }
.m-spark-svg { position: absolute; bottom: 12px; right: 12px; opacity: 0.4; transition: opacity 0.2s; }
.m-card:hover .m-spark-svg { opacity: 1; }

.m-tooltip {
  display: none;
  position: absolute;
  top: -28px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg);
  border: 1px solid var(--border-hi);
  padding: 4px 8px;
  font-size: 9px;
  color: var(--amber);
  white-space: nowrap;
  pointer-events: none;
  z-index: 10;
  box-shadow: 0 4px 10px rgba(0,0,0,0.8);
}
.m-card:hover .m-tooltip { display: block; }

/* ---- COMMAND CENTER GRID ---- */
.cmd-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  align-items: start;
}
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
  height: auto;
  position: relative;
  overflow: hidden;
}
.panel::before {
  content: "";
  position: absolute; top: 0; left: 0; height: 100%; width: 2px;
  background: var(--cyan);
  opacity: 0; transition: opacity 0.2s;
}
.panel:hover::before { opacity: 1; }
.panel.span-2 { grid-column: 1 / -1; }
.panel:hover { border-color: var(--cyan); box-shadow: 0 4px 20px rgba(0,229,255,0.05); }

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid transparent;
  background: var(--bg);
  cursor: crosshair;
  user-select: none;
  transition: background 0.2s;
}
.panel:hover .panel-head { background: var(--surface-hover); }
.panel.open .panel-head { border-bottom-color: var(--border); background: var(--surface-hover); }

.p-title { font-size: 11px; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: var(--bright); display: flex; align-items: center; gap: 8px; }
.p-title .dot { display: inline-block; width: 6px; height: 6px; background: var(--cyan); transition: transform 0.2s, background 0.2s; }
.panel.open .p-title .dot { transform: scale(1.5); background: var(--green); }
.p-title .dot.warn { background: var(--amber); }
.panel.open .p-title .dot.warn { background: var(--amber); }
.p-title .dot.bad { background: var(--red); }
.panel.open .p-title .dot.bad { background: var(--red); }

.p-meta { font-size: 9px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.1em; display: flex; align-items: center; gap: 8px; }
.p-arrow { color: var(--dim); transition: transform 0.2s, color 0.2s; font-size: 10px; }
.panel:hover .p-arrow { color: var(--cyan); }
.panel.open .p-arrow { transform: rotate(90deg); color: var(--green); }

.panel-body-wrap {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.4s var(--ease);
}
.panel.open .panel-body-wrap { grid-template-rows: 1fr; }
.panel-body {
  padding: 0 16px;
  overflow: hidden;
  transition: padding 0.4s var(--ease);
}
.panel.open .panel-body { padding: 16px; }

/* ASCII Loader */
.ascii-loader {
  font-family: var(--font);
  font-size: 10px;
  color: var(--cyan);
  white-space: pre-wrap;
  display: none;
  padding: 24px 0;
  text-align: left;
  letter-spacing: 0.05em;
  opacity: 0.8;
}
.panel.loading .ascii-loader { display: block; }
.panel.loading .panel-content { display: none; }
.panel.open .panel-content {
  display: block;
  animation: data-reveal 0.6s var(--ease) forwards;
}
@keyframes data-reveal {
  0% { opacity: 0; transform: translateY(4px); filter: blur(2px); }
  100% { opacity: 1; transform: translateY(0); filter: blur(0); }
}

/* ---- TABLES ---- */
.tbl { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
.tbl th {
  text-align: left;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  color: var(--dim);
  padding: 8px;
  border-bottom: 1px solid var(--border-hi);
  white-space: nowrap;
}
.tbl td { padding: 8px; border-bottom: 1px solid var(--border); font-size: 11px; cursor: crosshair; transition: all 0.15s; }
.tbl tr { transition: background 0.15s, transform 0.15s; }
.tbl tr:hover { background: var(--cyan-dim); transform: scale(1.002); }
.tbl tr:hover td { color: var(--bright); text-shadow: 0 0 10px rgba(0,229,255,0.4); border-bottom-color: var(--cyan); }
.tbl tr:hover td:first-child { box-shadow: inset 4px 0 0 var(--cyan); }
.tbl .r { text-align: right; }
.tbl .accent { color: var(--cyan); font-weight: 600; }
.tbl .warn-text { color: var(--amber); }
.tbl .bad-text { color: var(--red); }

/* ---- BAR CHART ---- */
.bars { display: flex; flex-direction: column; gap: 8px; padding-right: 4px; }
.bar-r { display: flex; align-items: center; gap: 12px; cursor: crosshair; }
.bar-l { font-size: 11px; color: var(--text); min-width: 110px; text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; transition: color 0.2s; }
.bar-t { flex: 1; height: 10px; background: var(--faint); position: relative; border: 1px solid var(--border); box-shadow: inset 0 1px 3px rgba(0,0,0,0.5); overflow: hidden; }
.bar-f { 
  height: 100%; 
  background: repeating-linear-gradient(45deg, var(--cyan), var(--cyan) 2px, transparent 2px, transparent 6px);
  position: absolute; left: 0; top: 0; 
  transition: width 0.8s cubic-bezier(0.16, 1, 0.3, 1), filter 0.2s; 
  box-shadow: 0 0 10px rgba(0, 229, 255, 0.2);
}
.panel:nth-child(even) .bar-f { background: repeating-linear-gradient(45deg, var(--amber), var(--amber) 2px, transparent 2px, transparent 6px); box-shadow: 0 0 10px rgba(255, 184, 0, 0.2); }
.bar-v { font-size: 10px; color: var(--bright); min-width: 32px; font-weight: 600; text-align: right; transition: text-shadow 0.2s; }

.bar-r:hover .bar-l { color: var(--bright); }
.bar-r:hover .bar-f { filter: brightness(1.5); }
.bar-r:hover .bar-v { text-shadow: 0 0 10px rgba(255,255,255,0.8); }

/* ---- LISTS ---- */
.lst { list-style: none; display: flex; flex-direction: column; gap: 8px; }
.lst li { font-size: 12px; line-height: 1.5; color: var(--text); padding-left: 12px; position: relative; }
.lst li::before { content: ""; position: absolute; left: 0; top: 6px; width: 4px; height: 4px; background: var(--amber); }

/* ---- TABS ---- */
.tab-bar { display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin-bottom: 16px; padding-bottom: 4px; overflow-x: auto; scrollbar-width: none; }
.tab-bar::-webkit-scrollbar { display: none; }
.tab-btn {
  font-family: var(--font);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  padding: 4px 8px;
  background: transparent;
  border: 1px solid transparent;
  color: var(--dim);
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.tab-btn:hover { color: var(--bright); background: var(--surface-hover); }
.tab-btn.on { color: var(--cyan); border-color: var(--border-hi); background: var(--surface-hover); }
.tab-panel { display: none; animation: quickFadeIn 0.2s var(--ease); }
.tab-panel.on { display: block; }

/* ---- 2-COL & 3-COL ---- */
.c2 { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.c3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
.stat-box { text-align: center; padding: 16px; background: var(--bg); border: 1px solid var(--border); }
.stat-lbl { font-size: 9px; font-weight: 700; color: var(--dim); text-transform: uppercase; letter-spacing: 0.15em; margin-bottom: 8px; }
.stat-val { font-size: 24px; font-weight: 300; color: var(--bright); letter-spacing: -1px; line-height: 1; }

/* ---- EMPTY STATE ---- */
.empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 60vh; border: 1px dashed var(--border-hi); margin-top: 24px; }
.empty-t { font-size: 14px; font-weight: 300; letter-spacing: 0.3em; text-transform: uppercase; color: var(--dim); display: flex; align-items: center; }
.empty-cursor { display: inline-block; width: 10px; height: 16px; background: var(--cyan); margin-left: 8px; animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }

/* ---- MODAL ---- */
.overlay {
  display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.8); backdrop-filter: blur(4px);
  z-index: 100; align-items: center; justify-content: center;
}
.overlay.open { display: flex; }
.modal {
  background: var(--bg); border: 1px solid var(--border-hi); padding: 24px; min-width: 480px;
  box-shadow: 0 20px 50px rgba(0,0,0,0.8), inset 0 0 0 1px rgba(255,255,255,0.05);
  animation: slideUp 0.3s var(--ease);
}
@keyframes slideUp { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
.modal-t { font-size: 14px; font-weight: 700; letter-spacing: 0.2em; text-transform: uppercase; color: var(--bright); margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 12px; }
.modal-s { font-size: 9px; font-weight: 700; color: var(--dim); text-transform: uppercase; letter-spacing: 0.15em; margin: 16px 0 8px; }
.modal-row { display: flex; gap: 12px; }
.m-input {
  flex: 1; width: 100%; background: var(--surface); border: 1px solid var(--border-hi); color: var(--bright);
  font-family: var(--font); font-size: 11px; padding: 8px 10px; outline: none; transition: border-color 0.2s;
}
.m-input:focus { border-color: var(--cyan); box-shadow: inset 0 0 0 1px var(--cyan); }
.m-input-lbl { font-size: 9px; color: var(--dim); margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.1em; }
.modal-check { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--text); cursor: pointer; margin: 6px 0; }
.modal-check input { accent-color: var(--cyan); width: 14px; height: 14px; }

.export-opts { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 12px 0; }
.ex-card {
  border: 1px solid var(--border-hi); background: var(--surface); padding: 16px 12px; text-align: center;
  cursor: pointer; transition: all 0.2s;
}
.ex-card:hover { border-color: var(--cyan); background: var(--cyan-dim); transform: translateY(-2px); }
.ex-icon { font-size: 24px; margin-bottom: 8px; color: var(--bright); }
.ex-title { font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--cyan); }
.ex-desc { font-size: 10px; color: var(--text); margin-top: 4px; }

.modal-btns { display: flex; gap: 8px; margin-top: 24px; }
.modal-btns .s-btn { flex: 1; }

/* ---- ANIMATIONS ---- */
@keyframes quickFadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
.fade { animation: fadeSlideIn 0.5s var(--ease) forwards; opacity: 0; }
@keyframes fadeSlideIn { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
.fd1 { animation-delay: 0.1s; }
.fd2 { animation-delay: 0.2s; }
.fd3 { animation-delay: 0.3s; }

/* Stagger panels */
.panel { opacity: 0; animation: fadeSlideIn 0.5s var(--ease) forwards; }
.panel:nth-child(1) { animation-delay: 0.3s; }
.panel:nth-child(2) { animation-delay: 0.4s; }
.panel:nth-child(3) { animation-delay: 0.5s; }
.panel:nth-child(4) { animation-delay: 0.6s; }
.panel:nth-child(5) { animation-delay: 0.7s; }
.panel:nth-child(6) { animation-delay: 0.8s; }
.panel:nth-child(7) { animation-delay: 0.9s; }

</style>
</head>
<body>
<div class="app">

  <!-- ======== SIDEBAR ======== -->
  <div class="side">
    <div class="side-inner">
      <div class="brand">
        <span class="brand-mark">HD</span>
        <span class="brand-name">KASEYA<br><b>HELP DESK</b>SERVICES</span>
      </div>

      <div class="drop {{ 'loaded' if csv_name else '' }}" id="dropZone">
        <input type="file" accept=".csv" id="csvIn">
        {% if csv_name %}
          <div class="drop-icon">✓</div>
          <div class="drop-file">{{ csv_name }}</div>
          <div class="drop-text" style="margin-top:4px; font-size:8px;">READY</div>
        {% else %}
          <div class="drop-icon">⇡</div>
          <div class="drop-text">MOUNT DATA.CSV</div>
        {% endif %}
      </div>

      <div class="mode-label">ENVIRONMENT</div>
      <div class="mode-row">
        <button class="mode-btn {{ 'on' if mode == MODE_CUSTOMER else '' }}" onclick="setMode('{{ MODE_CUSTOMER }}')">PARTNER</button>
        <button class="mode-btn {{ 'on' if mode == MODE_INTERNAL else '' }}" onclick="setMode('{{ MODE_INTERNAL }}')">INTERNAL</button>
      </div>

      <div class="spacer"></div>

      <div class="side-actions">
        <button class="s-btn pri" onclick="openExport()" {{ 'disabled' if not has_data else '' }}>COMPILE REPORT</button>
        <button class="s-btn" onclick="openSettings()">SYS CONFIG</button>
      </div>
    </div>
  </div>

  <!-- ======== MAIN ======== -->
  <div class="main">

    <div class="head fade">
      <div class="head-title">SYSTEM STATUS</div>
      <div class="head-meta">
        {% if mode == MODE_INTERNAL %}<span class="tag hi">INTERNAL_OP</span>{% else %}<span class="tag hi">PARTNER_VIEW</span>{% endif %}
        {% if partner_name %}<span class="tag">{{ partner_name }}</span>{% endif %}
        {% if date_range %}<span class="tag">{{ date_range }}</span>{% endif %}
      </div>
    </div>

    {% if error %}
    <div style="border: 1px solid var(--red); background: rgba(255,51,102,0.1); padding: 12px 16px; color: var(--red); margin-bottom: 24px; font-weight: 600; letter-spacing: 0.05em;">
      [ERR] {{ error }}
    </div>
    {% endif %}

    {% if not has_data %}
    <div class="empty fade fd1">
      <div class="empty-t">AWAITING DATA STREAM<span class="empty-cursor"></span></div>
      <div style="font-size:11px; color:var(--dim); margin-top:12px; letter-spacing:0.1em;">INITIATE UPLOAD SEQUENCE VIA SIDEBAR</div>
    </div>

    {% else %}
    <!-- METRICS GRID -->
    <div class="grid-top fade fd1">
      {% for label, value in a.headline_metrics[:8] %}
      <div class="m-card">
        <div class="m-label">{{ label }}</div>
        <div class="m-val" data-val="{{ value }}">{{ value }}</div>
        <svg class="m-spark-svg" data-label="{{ label }}" width="70" height="20"></svg>
        <div class="m-tooltip"></div>
      </div>
      {% endfor %}
    </div>

    <!-- COMMAND CENTER WIDGETS -->
    <div class="cmd-grid fade fd2">

      <!-- Executive Brief -->
      <div class="panel span-2" onclick="togglePanel(this, event)">
        <div class="panel-head">
          <div class="p-title"><span class="dot"></span>Executive Summary</div>
          <div class="p-meta">GENERATED INTEL <span class="p-arrow">►</span></div>
        </div>
        <div class="panel-body-wrap"><div class="panel-body">
          <div class="ascii-loader"></div>
          <div class="panel-content">
            <div class="c2">
              <div>
                <div class="stat-lbl" style="text-align:left;">KEY INSIGHTS</div>
                <ul class="lst">{% for p in a.executive_brief_points %}<li>{{ p }}</li>{% endfor %}</ul>
              </div>
              <div>
                <div class="stat-lbl" style="text-align:left;">PRIORITY ACTIONS</div>
                <ul class="lst">{% for p in a.priority_actions[:5] %}<li>{{ p }}</li>{% endfor %}</ul>
              </div>
            </div>
          </div>
        </div></div>
      </div>

      <!-- Resolution Time -->
      <div class="panel" onclick="togglePanel(this, event)">
        <div class="panel-head">
          <div class="p-title"><span class="dot"></span>Resolution Vectors</div>
          <div class="p-meta">MEDIAN {{ a.resolution.median_fmt }} | P90 {{ a.resolution.p90_fmt }} <span class="p-arrow">►</span></div>
        </div>
        <div class="panel-body-wrap"><div class="panel-body">
          <div class="ascii-loader"></div>
          <div class="panel-content">
            <div class="c3" style="margin-bottom:20px;">
              <div class="stat-box"><div class="stat-lbl">Median</div><div class="stat-val">{{ a.resolution.median_fmt }}</div></div>
              <div class="stat-box"><div class="stat-lbl">P90</div><div class="stat-val">{{ a.resolution.p90_fmt }}</div></div>
              <div class="stat-box"><div class="stat-lbl">P95</div><div class="stat-val">{{ a.resolution.p95_fmt }}</div></div>
            </div>
            <div class="tab-bar">
              <button class="tab-btn on" onclick="switchTab(this,'res')">By Queue</button>
              <button class="tab-btn" onclick="switchTab(this,'res')">By Priority</button>
              <button class="tab-btn" onclick="switchTab(this,'res')">By Issue</button>
            </div>
            <div class="tab-panel on" data-tabs="res">
              {% if a.resolution.by_queue %}
              <table class="tbl"><tr><th>Queue</th><th class="r">Vol</th><th class="r">Median</th><th class="r">P90</th></tr>
              {% for r in a.resolution.by_queue[:6] %}<tr><td>{{ r.Queue }}</td><td class="r">{{ r.Tickets }}</td><td class="r accent">{{ r['Median (min)'] }}m</td><td class="r">{{ r['P90 (min)'] }}m</td></tr>{% endfor %}
              </table>{% else %}<div style="color:var(--dim); padding:10px;">NO DATA</div>{% endif %}
            </div>
            <div class="tab-panel" data-tabs="res">
              {% if a.resolution.by_priority %}
              <table class="tbl"><tr><th>Priority</th><th class="r">Vol</th><th class="r">Median</th><th class="r">P90</th></tr>
              {% for r in a.resolution.by_priority[:6] %}<tr><td>{{ r.Priority }}</td><td class="r">{{ r.Tickets }}</td><td class="r accent">{{ r['Median (min)'] }}m</td><td class="r">{{ r['P90 (min)'] }}m</td></tr>{% endfor %}
              </table>{% else %}<div style="color:var(--dim); padding:10px;">NO DATA</div>{% endif %}
            </div>
            <div class="tab-panel" data-tabs="res">
              {% if a.resolution.by_issue_type %}
              <table class="tbl"><tr><th>Issue Type</th><th class="r">Vol</th><th class="r">Median</th><th class="r">P90</th></tr>
              {% for r in a.resolution.by_issue_type[:6] %}<tr><td>{{ r['Issue Type'][:20] }}</td><td class="r">{{ r.Tickets }}</td><td class="r accent">{{ r['Median (min)'] }}m</td><td class="r">{{ r['P90 (min)'] }}m</td></tr>{% endfor %}
              </table>{% else %}<div style="color:var(--dim); padding:10px;">NO DATA</div>{% endif %}
            </div>
          </div>
        </div></div>
      </div>

      <!-- SLA Compliance -->
      <div class="panel" onclick="togglePanel(this, event)">
        <div class="panel-head">
          <div class="p-title"><span class="dot"></span>SLA Integrity</div>
          <div class="p-meta" style="color:{% if a.sla.overall >= 90 %}var(--green){% elif a.sla.overall >= 75 %}var(--amber){% else %}var(--red){% endif %}; font-weight:700;">{{ a.sla.overall }}% COMPLIANT <span class="p-arrow">►</span></div>
        </div>
        <div class="panel-body-wrap"><div class="panel-body">
          <div class="ascii-loader"></div>
          <div class="panel-content">
            <div class="tab-bar">
              <button class="tab-btn on" onclick="switchTab(this,'sla')">Priority Metrics</button>
              <button class="tab-btn" onclick="switchTab(this,'sla')">Breach Log ({{ a.sla.breach_count }})</button>
            </div>
            <div class="tab-panel on" data-tabs="sla">
              {% if a.sla.by_priority %}
              <table class="tbl">
                <tr><th>Priority</th><th class="r">Vol</th><th class="r">Target</th><th class="r">Compliance</th></tr>
                {% for r in a.sla.by_priority %}
                <tr>
                  <td>{{ r.Priority }}</td><td class="r">{{ r.Tickets }}</td><td class="r">{{ r['Target (min)'] }}m</td>
                  <td class="r {% if r.Compliance >= 95 %}accent{% elif r.Compliance < 80 %}bad-text{% endif %}">{{ r.Compliance }}%</td>
                </tr>
                {% endfor %}
              </table>
              {% else %}<div style="color:var(--dim); padding:10px;">NO SLA DATA</div>{% endif %}
            </div>
            <div class="tab-panel" data-tabs="sla">
              {% if a.sla.breach_count > 0 %}
              <table class="tbl"><tr><th>Ticket ID</th><th>Priority</th><th class="r">Res Time</th><th class="r">Target</th></tr>
              {% for r in a.sla.breaching[:6] %}
              <tr><td>{{ r.get('Ticket Number','—') }}</td><td>{{ r.Priority }}</td><td class="r bad-text">{{ r['Resolution Minutes']|round|int }}m</td><td class="r">{{ r['SLA Target (min)']|round|int }}m</td></tr>
              {% endfor %}
              </table>
              {% else %}<div style="color:var(--green); font-weight:700; padding:10px; border:1px solid rgba(0,250,154,0.2); background:rgba(0,250,154,0.05); text-align:center;">ZERO BREACHES DETECTED</div>{% endif %}
            </div>
          </div>
        </div></div>
      </div>

      <!-- Queue & Escalation -->
      <div class="panel" onclick="togglePanel(this, event)">
        <div class="panel-head">
          <div class="p-title"><span class="dot"></span>Distribution & Esc.</div>
          <div class="p-meta">ROUTING METRICS <span class="p-arrow">►</span></div>
        </div>
        <div class="panel-body-wrap"><div class="panel-body">
          <div class="ascii-loader"></div>
          <div class="panel-content">
            <div class="tab-bar">
              <button class="tab-btn on" onclick="switchTab(this,'qe')">Queues</button>
              <button class="tab-btn" onclick="switchTab(this,'qe')">Esc. Reasons</button>
              <button class="tab-btn" onclick="switchTab(this,'qe')">Sources</button>
            </div>
            <div class="tab-panel on" data-tabs="qe">
              <div class="bars">
                {% for r in a.queue_table[:6] %}
                <div class="bar-r"><div class="bar-l">{{ r.Queue[:22] }}</div><div class="bar-t"><div class="bar-f" style="width:{{ r.Share }}%;"></div></div><div class="bar-v">{{ r.Tickets }}</div></div>
                {% endfor %}
              </div>
            </div>
            <div class="tab-panel" data-tabs="qe">
              <div class="bars">
                {% for r in a.escalation_table[:6] %}
                <div class="bar-r"><div class="bar-l">{{ r['Escalation Reason'][:22] }}</div><div class="bar-t"><div class="bar-f" style="width:{{ r.Share }}%;"></div></div><div class="bar-v">{{ r.Tickets }}</div></div>
                {% endfor %}
              </div>
            </div>
            <div class="tab-panel" data-tabs="qe">
              {% if a.source_table %}
              <div class="bars">
                {% for r in a.source_table[:6] %}
                <div class="bar-r"><div class="bar-l">{{ r.Source[:18] }}</div><div class="bar-t"><div class="bar-f" style="width:{{ r.Share }}%;"></div></div><div class="bar-v">{{ r.Tickets }}</div></div>
                {% endfor %}
              </div>{% else %}<div style="color:var(--dim); padding:10px;">NO DATA</div>{% endif %}
            </div>
          </div>
        </div></div>
      </div>

      <!-- Danger Zone -->
      <div class="panel" onclick="togglePanel(this, event)">
        <div class="panel-head">
          <div class="p-title"><span class="dot warn"></span>Anomaly Detection</div>
          <div class="p-meta" style="color:var(--amber);">RISK FACTORS <span class="p-arrow">►</span></div>
        </div>
        <div class="panel-body-wrap"><div class="panel-body">
          <div class="ascii-loader"></div>
          <div class="panel-content">
            <div class="tab-bar">
              <button class="tab-btn on" onclick="switchTab(this,'dz')">Hot Accounts</button>
              <button class="tab-btn" onclick="switchTab(this,'dz')">Repeat Contacts</button>
              <button class="tab-btn" onclick="switchTab(this,'dz')">After Hours</button>
            </div>
            <div class="tab-panel on" data-tabs="dz">
              {% if a.danger_zone_companies %}
              <table class="tbl"><tr><th>Company</th><th class="r">Vol</th><th class="r">Esc</th><th class="r">Esc%</th></tr>
              {% for r in a.danger_zone_companies[:6] %}
              <tr><td>{{ r.Company[:26] }}</td><td class="r">{{ r.Tickets }}</td><td class="r">{{ r.Escalated }}</td>
              <td class="r {% if r['Escalation Rate'] >= 80 %}bad-text{% elif r['Escalation Rate'] >= 50 %}warn-text{% endif %}">{{ r['Escalation Rate'] }}%</td></tr>
              {% endfor %}
              </table>
              {% else %}<div style="color:var(--dim); padding:10px;">NO ANOMALIES DETECTED</div>{% endif %}
            </div>
            <div class="tab-panel" data-tabs="dz">
              {% if a.repeat_contacts %}
              <table class="tbl"><tr><th>Contact</th><th class="r">Vol</th><th>Companies</th></tr>
              {% for r in a.repeat_contacts[:6] %}<tr><td>{{ r.Contact[:22] }}</td><td class="r warn-text">{{ r.Tickets }}</td><td style="font-size:9px;color:var(--dim);">{{ r.Companies[:20] }}</td></tr>{% endfor %}
              </table>
              {% else %}<div style="color:var(--dim); padding:10px;">NO REPEAT OFFENDERS</div>{% endif %}
            </div>
            <div class="tab-panel" data-tabs="dz">
              <div class="c2" style="margin-bottom:16px;">
                <div class="stat-box" style="border-color:var(--amber-dim);"><div class="stat-lbl">After-Hrs Vol</div><div class="stat-val" style="color:var(--amber);">{{ a.after_hours.total }}</div></div>
                <div class="stat-box"><div class="stat-lbl">Overall Rate</div><div class="stat-val">{{ a.after_hours.rate }}%</div></div>
              </div>
              {% if a.after_hours.by_day %}
              <div class="bars">
                {% set max_day = namespace(v=1) %}{% for d in a.after_hours.by_day %}{% if d.Tickets > max_day.v %}{% set max_day.v = d.Tickets %}{% endif %}{% endfor %}
                {% for d in a.after_hours.by_day %}
                <div class="bar-r"><div class="bar-l">{{ d.Day[:3] }}</div><div class="bar-t"><div class="bar-f" style="width:{{ (d.Tickets / max_day.v * 100)|round }}%;"></div></div><div class="bar-v">{{ d.Tickets }}</div></div>
                {% endfor %}
              </div>{% endif %}
            </div>
          </div>
        </div></div>
      </div>

      <!-- Coverage -->
      <div class="panel span-2" onclick="togglePanel(this, event)">
        <div class="panel-head">
          <div class="p-title"><span class="dot"></span>Coverage Profile</div>
          <div class="p-meta">SYSTEM SCOPE <span class="p-arrow">►</span></div>
        </div>
        <div class="panel-body-wrap"><div class="panel-body">
          <div class="ascii-loader"></div>
          <div class="panel-content">
            <div class="tab-bar">
              <button class="tab-btn on" onclick="switchTab(this,'cov')">Accounts</button>
              <button class="tab-btn" onclick="switchTab(this,'cov')">Issue Types</button>
              <button class="tab-btn" onclick="switchTab(this,'cov')">Sub-Issue Types</button>
            </div>
            <div class="tab-panel on" data-tabs="cov">
              <table class="tbl"><tr><th>Company</th><th class="r">Vol</th><th class="r">Share</th></tr>
              {% for r in a.company_table[:10] %}<tr><td>{{ r.Company[:32] }}</td><td class="r">{{ r.Tickets }}</td><td class="r accent">{{ r.Share }}%</td></tr>{% endfor %}
              </table>
            </div>
            <div class="tab-panel" data-tabs="cov">
              <table class="tbl"><tr><th>Type</th><th class="r">Vol</th><th class="r">Share</th></tr>
              {% for r in a.issue_type_table[:10] %}<tr><td>{{ r['Issue Type'][:28] }}</td><td class="r">{{ r.Tickets }}</td><td class="r accent">{{ r.Share }}%</td></tr>{% endfor %}
              </table>
            </div>
            <div class="tab-panel" data-tabs="cov">
              {% if a.sub_issue_type_table %}
              <table class="tbl"><tr><th>Sub-Type</th><th class="r">Vol</th><th class="r">Share</th></tr>
              {% for r in a.sub_issue_type_table[:10] %}<tr><td>{{ r['Sub-Issue Type'][:28] }}</td><td class="r">{{ r.Tickets }}</td><td class="r accent">{{ r.Share }}%</td></tr>{% endfor %}
              </table>{% else %}<div style="color:var(--dim); padding:10px;">NO SUB-ISSUE DATA</div>{% endif %}
            </div>
          </div>
        </div></div>
      </div>

      <!-- Technicians (Internal) -->
      {% if mode == MODE_INTERNAL %}
      <div class="panel span-2" onclick="togglePanel(this, event)">
        <div class="panel-head">
          <div class="p-title"><span class="dot bad"></span>Technician Telemetry</div>
          <div class="p-meta" style="color:var(--red);">INTERNAL ONLY <span class="p-arrow">►</span></div>
        </div>
        <div class="panel-body-wrap"><div class="panel-body">
          <div class="ascii-loader"></div>
          <div class="panel-content">
            <div class="c2">
              <div>
                {% if a.technician_scorecards %}
                <table class="tbl">
                  <tr><th>Operator</th><th class="r">Vol</th><th class="r">Avg Res</th><th class="r">Esc%</th><th class="r">FCR%</th></tr>
                  {% for r in a.technician_scorecards[:8] %}
                  <tr>
                    <td>{{ r.Technician[:20] }}</td><td class="r">{{ r.Tickets }}</td><td class="r">{{ r['Avg Resolution (min)'] }}m</td>
                    <td class="r {% if r['Escalation Rate'] > 60 %}bad-text{% elif r['Escalation Rate'] > 40 %}warn-text{% endif %}">{{ r['Escalation Rate'] }}%</td>
                    <td class="r accent">{{ r.get('FCR Rate', '—') }}%</td>
                  </tr>
                  {% endfor %}
                </table>
                {% endif %}
              </div>
              <div>
                 <div class="stat-box" style="margin-bottom:16px;">
                   <div class="stat-lbl">Global FCR Rate</div>
                   <div class="stat-val" style="color:var(--cyan); font-size: 32px;">{{ a.fcr_rate }}%</div>
                 </div>
                 {% if a.noise.total > 0 %}
                 <div style="border: 1px dashed var(--border-hi); padding: 16px; background: rgba(255,255,255,0.02);">
                   <div class="stat-lbl">System Noise Detected</div>
                   <div style="font-size:18px; font-weight:300; color:var(--text); margin-bottom:8px;">{{ a.noise.total }} events ({{ a.noise.rate }}%)</div>
                   <div style="display:flex; gap:16px; font-size:10px; color:var(--dim);">
                      <div>SPAM: <span style="color:var(--bright)">{{ a.noise.spam }}</span></div>
                      <div>SYNC: <span style="color:var(--bright)">{{ a.noise.sync }}</span></div>
                   </div>
                 </div>
                 {% endif %}
              </div>
            </div>
          </div>
        </div></div>
      </div>
      {% endif %}

    </div><!-- end cmd-grid -->
    {% endif %}

  </div>
</div>

<!-- EXPORT MODAL -->
<div class="overlay" id="exportModal">
  <div class="modal">
    <div class="modal-t">COMPILE REPORT ARTIFACTS</div>
    <div class="modal-s">METADATA</div>
    <div class="modal-row">
      <div style="flex:1"><div class="m-input-lbl">TITLE</div><input class="m-input" id="exTitle" value="{{ report_title }}"></div>
      <div style="flex:1"><div class="m-input-lbl">FILENAME</div><input class="m-input" id="exFile" value="{{ output_filename }}"></div>
    </div>
    <div class="modal-s" style="margin-top:24px;">FORMAT SELECTION</div>
    <div class="export-opts">
      <div class="ex-card" onclick="doExport('wb')">
        <div class="ex-icon">▤</div>
        <div class="ex-title">XLSX DATABANK</div>
        <div class="ex-desc">Raw tickets & pivots</div>
      </div>
      <div class="ex-card" onclick="doExport('both')">
        <div class="ex-icon">▤ + 📄</div>
        <div class="ex-title">FULL PACKAGE</div>
        <div class="ex-desc">XLSX + Executive PDF</div>
      </div>
    </div>
    <div class="modal-btns">
      <button class="s-btn" onclick="closeModal('exportModal')">ABORT</button>
    </div>
  </div>
</div>

<!-- SETTINGS MODAL -->
<div class="overlay" id="settingsModal">
  <div class="modal">
    <div class="modal-t">SYSTEM CONFIGURATION</div>
    <div class="modal-s">SLA TARGETS (MINUTES)</div>
    <div class="modal-row" style="flex-wrap:wrap;">
      {% for p in ['Critical','High','Medium','Low','None'] %}
      <div style="flex: 1 0 30%;"><div class="m-input-lbl">{{ p|upper }}</div><input class="m-input sla-in" data-p="{{ p }}" type="number" value="{{ settings.sla_targets.get(p, 1440) }}"></div>
      {% endfor %}
    </div>
    <div class="modal-s" style="margin-top:24px;">FILTER PROTOCOLS</div>
    <label class="modal-check"><input type="checkbox" id="chkSpam" {{ 'checked' if settings.noise_filter.get('hide_spam', True) }}> Mute Spam Tokens</label>
    <label class="modal-check"><input type="checkbox" id="chkSync" {{ 'checked' if settings.noise_filter.get('hide_sync_errors', True) }}> Mute Sync Anomalies</label>
    
    <div class="modal-s" style="margin-top:24px;">SYSTEM INFO</div>
    <div style="font-size:10px;color:var(--dim); font-family:var(--font);">{{ app_name }} v{{ app_version }} // LOCAL INSTANCE ONLY // SECURE</div>
    <div class="modal-btns">
      <button class="s-btn pri" onclick="saveSettings()">COMMIT</button>
      <button class="s-btn" style="border-color:var(--red); color:var(--red);" onclick="resetSettings()">FACTORY RESET</button>
      <button class="s-btn" onclick="closeModal('settingsModal')">DISMISS</button>
    </div>
  </div>
</div>

<script>
const ASCII_FRAMES = [
  "[INITIALIZING MODULE]\\n> VERIFYING DATA INTEGRITY... [OK]\\n> DECRYPTING PAYLOAD...",
  "[INITIALIZING MODULE]\\n> VERIFYING DATA INTEGRITY... [OK]\\n> DECRYPTING PAYLOAD... 0x4F2A",
  "[INITIALIZING MODULE]\\n> VERIFYING DATA INTEGRITY... [OK]\\n> DECRYPTING PAYLOAD... 0x8B1C\\n> ALLOCATING MEMORY...",
  "[INITIALIZING MODULE]\\n> VERIFYING DATA INTEGRITY... [OK]\\n> DECRYPTING PAYLOAD... 0xFFFF\\n> ALLOCATING MEMORY... [OK]\\n> RENDER DATA STREAM..."
];

function togglePanel(panel, event) {
  if (event && (event.target.tagName === 'BUTTON' || event.target.closest('.tab-bar'))) {
    return;
  }
  
  if (panel.classList.contains('open')) {
    panel.classList.remove('open');
    return;
  }
  
  panel.classList.add('loading');
  panel.classList.add('open');
  
  const loader = panel.querySelector('.ascii-loader');
  if (loader) {
    let frame = 0;
    loader.textContent = ASCII_FRAMES[0];
    const interval = setInterval(() => {
      frame++;
      if (frame >= ASCII_FRAMES.length) {
        clearInterval(interval);
        setTimeout(() => {
          panel.classList.remove('loading');
          panel.querySelectorAll('.bar-f').forEach(b => {
            const w = b.style.width;
            b.style.width = '0';
            requestAnimationFrame(() => requestAnimationFrame(() => { b.style.width = w; }));
          });
        }, 150);
      } else {
        loader.textContent = ASCII_FRAMES[frame];
      }
    }, 80);
  } else {
    panel.classList.remove('loading');
  }
}

function switchTab(btn, group) {
  const bar = btn.parentElement;
  bar.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  const idx = Array.from(bar.children).indexOf(btn);
  const panels = btn.closest('.panel-body').querySelectorAll('.tab-panel[data-tabs="'+group+'"]');
  panels.forEach((p, i) => { p.classList.toggle('on', i === idx); });
}

function openExport(){document.getElementById('exportModal').classList.add('open')}
function openSettings(){document.getElementById('settingsModal').classList.add('open')}
function closeModal(id){document.getElementById(id).classList.remove('open')}
document.querySelectorAll('.overlay').forEach(o=>o.addEventListener('click',e=>{if(e.target===o)o.classList.remove('open')}));

document.getElementById('csvIn').addEventListener('change',async e=>{
  const f=e.target.files[0];if(!f)return;
  const fd=new FormData();fd.append('file',f);
  const r=await fetch('/upload',{method:'POST',body:fd});
  if(r.ok)location.reload();else alert('UPLOAD REJECTED');
});

async function setMode(m){await fetch('/mode/'+m,{method:'POST'});location.reload()}

function doExport(t){
  window.open('/export/workbook','_blank');
  if(t==='both')setTimeout(()=>window.open('/export/pdf','_blank'),500);
  closeModal('exportModal');
}

async function saveSettings(){
  const sla={};document.querySelectorAll('.sla-in').forEach(i=>sla[i.dataset.p]=parseInt(i.value)||1440);
  await fetch('/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    sla_targets:sla,noise_filter:{hide_spam:document.getElementById('chkSpam').checked,hide_sync_errors:document.getElementById('chkSync').checked}
  })});location.reload();
}
async function resetSettings(){await fetch('/settings/reset',{method:'POST'});location.reload()}

// ---- SPARKLINE GENERATOR ----
const SPARKS = {{ a.get('sparks', {}) | tojson if a else '{}' }};
document.querySelectorAll('.m-spark-svg').forEach(svg => {
  const label = svg.dataset.label;
  const data = SPARKS[label];
  if (!data || !data.length) { svg.style.display = 'none'; return; }

  const w = 70, h = 20, gap = 2;
  const mx = Math.max(...data, 1);
  const barW = Math.max(2, (w - gap * (data.length - 1)) / data.length);

  data.forEach((v, i) => {
    const barH = Math.max(1, (v / mx) * (h - 2));
    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('x', i * (barW + gap));
    rect.setAttribute('y', h - barH);
    rect.setAttribute('width', barW);
    rect.setAttribute('height', barH);
    rect.setAttribute('fill', 'var(--cyan)');
    rect.style.transform = `scaleY(0)`;
    rect.style.transformOrigin = 'bottom';
    rect.style.transition = `transform 0.4s cubic-bezier(0.16, 1, 0.3, 1) ${i * 0.05 + 0.3}s`;
    svg.appendChild(rect);
    requestAnimationFrame(() => requestAnimationFrame(() => { rect.style.transform = 'scaleY(1)'; }));
  });
  
  // Tooltips
  const card = svg.closest('.m-card');
  const tip = card.querySelector('.m-tooltip');
  if (tip) {
    tip.textContent = data.map(v => typeof v === 'number' ? (v % 1 ? v.toFixed(1) : v) : v).join(' · ');
  }
});

// Bar animation setup
document.querySelectorAll('.bar-f').forEach(b => {
  b.style.width = '0';
});

// Counter animation
document.querySelectorAll('.m-val').forEach(el => {
  const raw = el.textContent.trim();
  const num = parseFloat(raw.replace(/[^0-9.]/g, ''));
  if (isNaN(num) || num === 0) return;
  const suffix = raw.replace(/[0-9.,]+/, '');
  const isInt = !raw.includes('.') || raw.endsWith('%');
  const duration = 1000;
  const start = performance.now();
  el.textContent = isInt ? '0' + suffix : '0.0' + suffix;
  
  function step(now) {
    const p = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - p, 4); // exponential out
    const val = num * ease;
    el.textContent = (isInt ? Math.round(val) : val.toFixed(1)) + suffix;
    if (p < 1) requestAnimationFrame(step);
  }
  
  const card = el.closest('.m-card');
  const idx = card ? Array.from(card.parentNode.children).indexOf(card) : 0;
  setTimeout(() => requestAnimationFrame(step), idx * 50 + 200);
});

// Open Executive Summary by default after load
setTimeout(() => {
  const execPanel = document.querySelector('.panel');
  if (execPanel) togglePanel(execPanel, null);
}, 500);
</script>
</body>
</html>
""")
print("Patched completely via string replacement.")

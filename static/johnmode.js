/* ============================================================
   JOSHBOT — _johnmode_ Easter Egg
   A stick-figure tutorial guide for the KHD dashboard.
   Canvas-based character with pose interpolation & guided tour.
   ============================================================ */
(function () {
  "use strict";

  // ---- CSS injected into page ----
  const JOHN_CSS = `
    #john-overlay{position:fixed;inset:0;z-index:100010;pointer-events:none;font-family:'JetBrains Mono',monospace;}
    #john-highlight{position:absolute;border:2px solid #00e676;border-radius:4px;box-shadow:0 0 18px rgba(0,230,118,.35);transition:all .45s cubic-bezier(.16,1,.3,1);pointer-events:none;z-index:100011;}
    #john-char{position:fixed;bottom:32px;left:32px;z-index:100015;transition:all .6s cubic-bezier(.16,1,.3,1);pointer-events:none;}
    #john-bubble{position:fixed;bottom:180px;left:32px;z-index:100014;background:#0a0a0a;border:1px solid #00e676;color:#a0aab2;font-size:11px;line-height:1.5;padding:14px 18px;max-width:340px;min-width:200px;border-radius:2px;pointer-events:auto;transition:all .45s cubic-bezier(.16,1,.3,1);box-shadow:0 8px 30px rgba(0,0,0,.7);}
    #john-bubble::after{content:'';position:absolute;bottom:-8px;left:24px;border:8px solid transparent;border-top-color:#00e676;border-bottom:none;}
    #john-bubble .jb-name{color:#00e676;font-weight:700;font-size:10px;letter-spacing:.15em;margin-bottom:6px;}
    #john-controls{position:fixed;bottom:0;left:0;right:0;z-index:100016;background:#0a0a0a;border-top:1px solid #1f1f1f;display:flex;align-items:center;gap:8px;padding:8px 16px;pointer-events:auto;}
    #john-controls button{background:#161616;border:1px solid #333;color:#a0aab2;font-family:'JetBrains Mono',monospace;font-size:10px;padding:6px 14px;cursor:pointer;letter-spacing:.1em;transition:all .2s;}
    #john-controls button:hover{border-color:#00e676;color:#00e676;background:#0a0a0a;}
    #john-controls .jc-step{color:#55626d;font-size:9px;margin-left:auto;letter-spacing:.15em;}
    #john-feedback-panel{position:fixed;bottom:44px;right:16px;z-index:100017;background:#0a0a0a;border:1px solid #ffb800;padding:14px;width:300px;display:none;pointer-events:auto;}
    #john-feedback-panel textarea{width:100%;height:60px;background:#030303;border:1px solid #333;color:#a0aab2;font-family:'JetBrains Mono',monospace;font-size:10px;padding:6px;resize:none;}
    #john-feedback-panel button{margin-top:6px;background:#161616;border:1px solid #ffb800;color:#ffb800;font-family:'JetBrains Mono',monospace;font-size:10px;padding:4px 12px;cursor:pointer;}
    .john-explain-cursor,.john-explain-cursor *{cursor:crosshair !important;}
  `;

  // ---- Canvas HTML ----
  const JOHN_SVG = '<canvas id="john-canvas" width="100" height="140"></canvas>';

  // ---- Poses (joint angles in degrees) ----
  // Keys: headY, bodyTilt, lArmA, lArmB, rArmA, rArmB, lLeg, rLeg, crouch
  const POSES = {
    idle0:    { headY:0, bodyTilt:0,   lArmA:-15, lArmB:-30, rArmA:15,   rArmB:30,  lLeg:5,   rLeg:-5,  crouch:0 },
    idle1:    { headY:2, bodyTilt:2,   lArmA:-20, lArmB:-25, rArmA:20,   rArmB:25,  lLeg:3,   rLeg:-3,  crouch:0 },
    idle2:    { headY:-1,bodyTilt:-2,  lArmA:-12, lArmB:-35, rArmA:12,   rArmB:35,  lLeg:6,   rLeg:-6,  crouch:0 },
    pointR:   { headY:3, bodyTilt:8,   lArmA:-20, lArmB:-30, rArmA:85,   rArmB:10,  lLeg:8,   rLeg:-3,  crouch:0 },
    peek:     { headY:-8,bodyTilt:-5,  lArmA:-40, lArmB:-60, rArmA:40,   rArmB:60,  lLeg:15,  rLeg:-15, crouch:16 },
    pullup:   { headY:4, bodyTilt:0,   lArmA:-150,lArmB:-20, rArmA:150,  rArmB:20,  lLeg:2,   rLeg:-2,  crouch:-8 },
    wave1:    { headY:2, bodyTilt:3,   lArmA:-15, lArmB:-30, rArmA:140,  rArmB:40,  lLeg:4,   rLeg:-4,  crouch:0 },
    wave2:    { headY:2, bodyTilt:3,   lArmA:-15, lArmB:-30, rArmA:140,  rArmB:-30, lLeg:4,   rLeg:-4,  crouch:0 },
    stumble:  { headY:-6,bodyTilt:22,  lArmA:-70, lArmB:-50, rArmA:100,  rArmB:60,  lLeg:25,  rLeg:-20, crouch:4 },
    flipCrouch:{ headY:-6,bodyTilt:0,  lArmA:-40, lArmB:-50, rArmA:40,   rArmB:50,  lLeg:20,  rLeg:-20, crouch:22 },
    flipAir:  { headY:8, bodyTilt:0,   lArmA:-160,lArmB:-15, rArmA:160,  rArmB:15,  lLeg:-10, rLeg:10,  crouch:-20 },
    flipLand: { headY:0, bodyTilt:0,   lArmA:-30, lArmB:-40, rArmA:30,   rArmB:40,  lLeg:12,  rLeg:-12, crouch:8 },
  };

  // ---- Named animation sequences ----
  const SEQUENCES = {
    idle:    [{ pose:'idle0',d:900 },{ pose:'idle1',d:900 },{ pose:'idle2',d:900 }],
    pointR:  [{ pose:'pointR',d:1200 },{ pose:'idle0',d:600 }],
    peek:    [{ pose:'peek',d:1000 },{ pose:'idle1',d:400 },{ pose:'peek',d:800 },{ pose:'idle0',d:500 }],
    pullup:  [{ pose:'pullup',d:1000 },{ pose:'idle0',d:600 }],
    wave:    [{ pose:'wave1',d:350 },{ pose:'wave2',d:350 },{ pose:'wave1',d:350 },{ pose:'wave2',d:350 },{ pose:'idle0',d:400 }],
    stumble: [{ pose:'stumble',d:1100 },{ pose:'idle2',d:500 },{ pose:'stumble',d:700 },{ pose:'idle0',d:500 }],
    flip:    [{ pose:'flipCrouch',d:350 },{ pose:'flipAir',d:450 },{ pose:'flipLand',d:300 },{ pose:'idle0',d:500 }],
  };

  // ---- Tour steps ----
  const STEPS = [
    { sel:null,               anim:'stumble', text:"What's up, John. It's JOSHBOT. I built this thing so let me walk you through it real quick before I bounce." },
    { sel:'#dropZone',        anim:'wave',    text:"This is the drop zone. Drag a CSV here or click to upload. Multi-file works -- it merges months automatically." },
    { sel:'.mode-btn',        anim:'flip',    text:"Mode toggle. PARTNER view hides the internal ops panels. INTERNAL shows everything. Opens in SYS CONFIG.",openModal:'settingsModal' },
    { sel:'.m-card',          anim:'peek',    text:"Metric cards. Total tickets, SLA, escalation rate, resolution time. Deltas show month-over-month change." },
    { sel:'.side-filters',    anim:'pointR',  text:"Time horizon controls. 1M, QTR, HALF, YR. If you uploaded multiple months, pick one or view aggregated." },
    { sel:'.panel',           anim:'pullup',  text:"Analysis panels. Click to expand. Each one has tabs -- resolution breakdown, categories, SLA, trends." },
    { sel:'#settingsModal .modal-s', anim:'flip', text:"SYS CONFIG. AI provider, API keys, noise filters, mode switch. All settings persist in settings.json.",openModal:'settingsModal',centerModal:true },
    { sel:'.s-btn.pri',       anim:'wave',    text:"The COMPILE REPORT button. Exports to Excel workbook and/or PDF. Title and filename are configurable." },
    { sel:'#aiToggleBtn',     anim:'peek',    text:"AI orb. Long-press opens the chat. Regular click opens the AI analysis view. Needs API key in settings." },
    { sel:'.pv-lbl',          anim:'pullup',  text:"Danger Zone -- hot accounts, repeat contacts, after-hours volume. The red ones need attention ASAP.",match:'HOT ACCOUNTS' },
    { sel:null,               anim:'flip',    text:"Alright that's the tour. My Uber's been waiting 20 minutes so I gotta go. Click EXPLAIN on anything if you get stuck. Peace." },
  ];

  // ---- State ----
  let step = 0, feedbackNotes = {}, animFrame = 0, currentSeq = 'idle';
  let seqIdx = 0, seqT = 0, seqStart = 0, looping = true, rafId = null;
  let explainActive = false, styleEl, overlayEl, charEl, bubbleEl, ctrlEl, hlEl, fbEl;

  // ---- Utilities ----
  function smoothstep(t) { return t * t * (3 - 2 * t); }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function lerpPose(a, b, t) {
    const out = {};
    for (const k in a) out[k] = lerp(a[k], b[k] || 0, t);
    return out;
  }
  function deg(d) { return d * Math.PI / 180; }

  // ---- Canvas Renderer ----
  function drawJohn(canvas, pose) {
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const cx = W / 2, baseY = H - 16 + pose.crouch;
    const green = '#00e676', dark = '#0a4a2a', drink = '#00d4ff';

    // Shadow
    ctx.fillStyle = 'rgba(0,230,118,0.12)';
    ctx.beginPath();
    ctx.ellipse(cx, H - 8, 22, 5, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.lineCap = 'round'; ctx.lineJoin = 'round';

    // Body tilt
    ctx.save();
    ctx.translate(cx, baseY - 40);
    ctx.rotate(deg(pose.bodyTilt));

    // Torso
    ctx.strokeStyle = green; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -35);
    ctx.stroke();

    // Left arm (holds drink)
    ctx.save();
    ctx.translate(0, -33);
    ctx.rotate(deg(pose.lArmA));
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, 18);
    ctx.strokeStyle = green; ctx.lineWidth = 2.5; ctx.stroke();
    ctx.save();
    ctx.translate(0, 18);
    ctx.rotate(deg(pose.lArmB));
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, 14);
    ctx.stroke();
    // Drink (cup)
    ctx.fillStyle = drink;
    ctx.fillRect(-4, 12, 8, 10);
    ctx.fillStyle = '#006680';
    ctx.fillRect(-4, 12, 8, 3);
    ctx.restore();
    ctx.restore();

    // Right arm (with fingers)
    ctx.save();
    ctx.translate(0, -33);
    ctx.rotate(deg(pose.rArmA));
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, 18);
    ctx.strokeStyle = green; ctx.lineWidth = 2.5; ctx.stroke();
    ctx.save();
    ctx.translate(0, 18);
    ctx.rotate(deg(pose.rArmB));
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, 14);
    ctx.stroke();
    // Fingers
    ctx.strokeStyle = green; ctx.lineWidth = 1.5;
    for (let i = -1; i <= 1; i++) {
      ctx.beginPath(); ctx.moveTo(0, 14); ctx.lineTo(i * 3, 19);
      ctx.stroke();
    }
    ctx.restore();
    ctx.restore();

    // Head
    ctx.save();
    ctx.translate(0, -35 + pose.headY);
    ctx.strokeStyle = green; ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.arc(0, -14, 11, 0, Math.PI * 2);
    ctx.stroke();
    // Glasses (signature look)
    ctx.strokeStyle = green; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(-5, -14, 4.5, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(5, -14, 4.5, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-0.5, -14); ctx.lineTo(0.5, -14);
    ctx.stroke();
    // Ear stems
    ctx.beginPath(); ctx.moveTo(-9.5, -14); ctx.lineTo(-11, -14); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(9.5, -14); ctx.lineTo(11, -14); ctx.stroke();
    // Eyes (dots inside glasses)
    ctx.fillStyle = green;
    ctx.beginPath(); ctx.arc(-5, -14, 1.5, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(5, -14, 1.5, 0, Math.PI * 2); ctx.fill();
    // Mouth
    ctx.beginPath(); ctx.arc(0, -8, 3, 0.1, Math.PI - 0.1); ctx.strokeStyle = green; ctx.lineWidth = 1; ctx.stroke();
    ctx.restore();

    // Legs
    ctx.save();
    ctx.translate(0, 0);
    // Left leg
    ctx.save(); ctx.rotate(deg(pose.lLeg));
    ctx.strokeStyle = green; ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, 28 - pose.crouch * 0.4);
    ctx.stroke();
    // Shoe
    ctx.fillStyle = dark;
    ctx.fillRect(-4, 26 - pose.crouch * 0.4, 9, 5);
    ctx.strokeStyle = green; ctx.lineWidth = 1;
    ctx.strokeRect(-4, 26 - pose.crouch * 0.4, 9, 5);
    ctx.restore();
    // Right leg
    ctx.save(); ctx.rotate(deg(pose.rLeg));
    ctx.strokeStyle = green; ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, 28 - pose.crouch * 0.4);
    ctx.stroke();
    ctx.fillStyle = dark;
    ctx.fillRect(-5, 26 - pose.crouch * 0.4, 9, 5);
    ctx.strokeStyle = green; ctx.lineWidth = 1;
    ctx.strokeRect(-5, 26 - pose.crouch * 0.4, 9, 5);
    ctx.restore();
    ctx.restore();

    ctx.restore(); // body tilt
  }

  // ---- Animation loop ----
  function playSeq(name, loop) {
    currentSeq = name; looping = loop !== false;
    seqIdx = 0; seqT = 0; seqStart = performance.now();
    if (!rafId) tick();
  }

  function tick() {
    const seq = SEQUENCES[currentSeq];
    if (!seq) return;
    const now = performance.now();
    const elapsed = now - seqStart;
    const frame = seq[seqIdx];
    const nextIdx = (seqIdx + 1) % seq.length;
    const nextFrame = seq[nextIdx];
    const t = Math.min(elapsed / frame.d, 1);
    const st = smoothstep(t);
    const poseA = POSES[frame.pose];
    const poseB = POSES[nextFrame.pose];
    const current = lerpPose(poseA, poseB, st);
    const canvas = document.getElementById('john-canvas');
    if (canvas) drawJohn(canvas, current);
    if (t >= 1) {
      seqIdx = nextIdx;
      seqStart = now;
      if (seqIdx === 0 && !looping) { currentSeq = 'idle'; looping = true; }
    }
    rafId = requestAnimationFrame(tick);
  }

  // ---- DOM Setup ----
  function setup() {
    styleEl = document.createElement('style');
    styleEl.textContent = JOHN_CSS;
    document.head.appendChild(styleEl);

    overlayEl = document.createElement('div');
    overlayEl.id = 'john-overlay';
    overlayEl.innerHTML = '<div id="john-highlight"></div>';
    document.body.appendChild(overlayEl);

    hlEl = document.getElementById('john-highlight');

    charEl = document.createElement('div');
    charEl.id = 'john-char';
    charEl.innerHTML = JOHN_SVG;
    document.body.appendChild(charEl);

    bubbleEl = document.createElement('div');
    bubbleEl.id = 'john-bubble';
    document.body.appendChild(bubbleEl);

    ctrlEl = document.createElement('div');
    ctrlEl.id = 'john-controls';
    document.body.appendChild(ctrlEl);

    fbEl = document.createElement('div');
    fbEl.id = 'john-feedback-panel';
    fbEl.innerHTML = '<div style="color:#ffb800;font-size:9px;letter-spacing:.15em;margin-bottom:6px;">FEEDBACK FOR STEP <span id="jfb-step"></span></div><textarea id="jfb-text" placeholder="Notes for Josh..."></textarea><button onclick="window.johnMode.saveFeedback()">SAVE</button>';
    document.body.appendChild(fbEl);

    playSeq('idle', true);
  }

  // ---- Close any open modals ----
  function closeModals() {
    document.querySelectorAll('.overlay.open').forEach(function (o) { o.classList.remove('open'); });
  }

  // ---- Highlight element ----
  function highlight(el) {
    if (!el) { hlEl.style.display = 'none'; return; }
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(function () {
      const r = el.getBoundingClientRect();
      hlEl.style.display = 'block';
      hlEl.style.left = (r.left - 6) + 'px';
      hlEl.style.top = (r.top - 6) + 'px';
      hlEl.style.width = (r.width + 12) + 'px';
      hlEl.style.height = (r.height + 12) + 'px';
    }, 350);
  }

  // ---- Render step ----
  function renderStep() {
    const s = STEPS[step];
    closeModals();

    if (s.openModal) {
      setTimeout(function () {
        var modal = document.getElementById(s.openModal);
        if (modal) modal.classList.add('open');
      }, 100);
    }

    // Find target
    var target = null;
    if (s.sel) {
      if (s.match) {
        var all = document.querySelectorAll(s.sel);
        for (var i = 0; i < all.length; i++) {
          if (all[i].textContent.indexOf(s.match) !== -1) { target = all[i]; break; }
        }
      } else {
        target = document.querySelector(s.sel);
      }
    }

    setTimeout(function () { highlight(target); }, s.openModal ? 300 : 50);

    // Position character near target if available
    if (target && !s.centerModal) {
      var tr = target.getBoundingClientRect();
      var left = Math.max(16, Math.min(tr.left - 120, window.innerWidth - 140));
      var bottom = Math.max(32, window.innerHeight - tr.bottom - 10);
      charEl.style.left = left + 'px';
      charEl.style.bottom = bottom + 'px';
      bubbleEl.style.left = left + 'px';
      bubbleEl.style.bottom = (bottom + 148) + 'px';
    } else {
      charEl.style.left = '32px';
      charEl.style.bottom = '48px';
      bubbleEl.style.left = '32px';
      bubbleEl.style.bottom = '196px';
    }

    // Bubble
    bubbleEl.innerHTML = '<div class="jb-name">JOSHBOT</div>' + s.text;

    // Controls
    ctrlEl.innerHTML =
      '<button onclick="window.johnMode.prev()"' + (step === 0 ? ' disabled style="opacity:.3"' : '') + '>BACK</button>' +
      '<button onclick="window.johnMode.next()">' + (step === STEPS.length - 1 ? 'FINISH' : 'NEXT') + '</button>' +
      '<button onclick="window.johnMode.explainMode()">CLICK TO EXPLAIN</button>' +
      '<button onclick="window.johnMode.feedback()">FEEDBACK</button>' +
      '<button onclick="window.johnMode.exit()">EXIT</button>' +
      '<span class="jc-step">' + (step + 1) + ' / ' + STEPS.length + '</span>';

    // Animation
    if (s.anim && SEQUENCES[s.anim]) playSeq(s.anim, false);
  }

  // ---- Public API ----
  function start() {
    step = 0;
    feedbackNotes = {};
    explainActive = false;
    setup();
    renderStep();
  }

  function next() {
    if (step >= STEPS.length - 1) { exit(); return; }
    step++;
    renderStep();
  }

  function prev() {
    if (step <= 0) return;
    step--;
    renderStep();
  }

  function feedback() {
    var panel = document.getElementById('john-feedback-panel');
    var showing = panel.style.display === 'block';
    panel.style.display = showing ? 'none' : 'block';
    if (!showing) {
      document.getElementById('jfb-step').textContent = step + 1;
      document.getElementById('jfb-text').value = feedbackNotes[step] || '';
    }
  }

  function saveFeedback() {
    var text = document.getElementById('jfb-text').value.trim();
    if (text) feedbackNotes[step] = text;
    document.getElementById('john-feedback-panel').style.display = 'none';
  }

  function closeFeedback() {
    document.getElementById('john-feedback-panel').style.display = 'none';
  }

  function explainMode() {
    if (explainActive) { disableExplain(); return; }
    explainActive = true;
    document.body.classList.add('john-explain-cursor');
    bubbleEl.innerHTML = '<div class="jb-name">JOSHBOT</div>Click on any element and I\'ll explain it. Click EXPLAIN again to cancel.';
    document.addEventListener('click', explainClick, true);
  }

  function disableExplain() {
    explainActive = false;
    document.body.classList.remove('john-explain-cursor');
    document.removeEventListener('click', explainClick, true);
    renderStep();
  }

  function explainClick(e) {
    // Ignore clicks on our own UI
    if (e.target.closest('#john-controls') || e.target.closest('#john-bubble') ||
        e.target.closest('#john-feedback-panel') || e.target.closest('#john-char')) return;

    e.preventDefault();
    e.stopPropagation();

    var el = e.target;
    var tag = el.tagName.toLowerCase();
    var cls = el.className || '';
    var id = el.id || '';
    var txt = (el.textContent || '').slice(0, 80).trim();
    var context = 'Element: <' + tag + '>' + (id ? ' id="' + id + '"' : '') + (cls ? ' class="' + cls + '"' : '') + ' | Text: "' + txt + '"';

    // Move character to element
    var r = el.getBoundingClientRect();
    var left = Math.max(16, Math.min(r.left - 120, window.innerWidth - 140));
    var bottom = Math.max(32, window.innerHeight - r.bottom - 10);
    charEl.style.left = left + 'px';
    charEl.style.bottom = bottom + 'px';
    bubbleEl.style.left = left + 'px';
    bubbleEl.style.bottom = (bottom + 148) + 'px';

    highlight(el);
    playSeq('flip', false);
    bubbleEl.innerHTML = '<div class="jb-name">JOSHBOT</div>Asking the AI about this...';

    fetch('/ai/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: 'Explain this dashboard element to a new user: ' + context, context: context, fast_mode: true })
    }).then(function (r) { return r.json(); })
      .then(function (data) {
        bubbleEl.innerHTML = '<div class="jb-name">JOSHBOT</div>' + (data.answer || data.error || 'No response from AI.');
      })
      .catch(function (err) {
        bubbleEl.innerHTML = '<div class="jb-name">JOSHBOT</div>AI is offline. ' + err.message;
      });
  }

  function exit() {
    if (explainActive) disableExplain();
    closeModals();

    // Slide JOSHBOT off screen
    charEl.style.left = '-100px';
    charEl.style.opacity = '0';
    bubbleEl.style.left = '-400px';
    bubbleEl.style.opacity = '0';

    setTimeout(function () {
      // Full cleanup
      if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
      [overlayEl, charEl, bubbleEl, ctrlEl, fbEl, styleEl].forEach(function (el) {
        if (el && el.parentNode) el.parentNode.removeChild(el);
      });

      // Alert if feedback was collected
      var notes = Object.keys(feedbackNotes);
      if (notes.length > 0) {
        var msg = 'JOSHBOT Feedback (' + notes.length + ' notes):\n\n';
        notes.forEach(function (k) { msg += 'Step ' + (parseInt(k) + 1) + ': ' + feedbackNotes[k] + '\n'; });
        alert(msg);
      }
    }, 1800);
  }

  // ---- Exports ----
  window.johnMode = { start: start, next: next, prev: prev, feedback: feedback, saveFeedback: saveFeedback, closeFeedback: closeFeedback, explainMode: explainMode, exit: exit };
})();

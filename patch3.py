import re

with open("templates/dashboard.html", "r") as f:
    content = f.read()

# 1. Update logo glitch in CSS
brand_css = r"""
.brand {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border);
}
.brand-mark {
  font-size: 32px;
  font-weight: 800;
  color: #89CFF0; /* baby blue */
  background: #020a1c;
  border: 1px solid rgba(137, 207, 240, 0.3);
  padding: 4px 10px;
  line-height: 1;
  letter-spacing: -1px;
  box-shadow: 0 0 15px rgba(137, 207, 240, 0.1);
  animation: tasteful-glitch 4s infinite;
  display: inline-block;
}
@keyframes tasteful-glitch {
  0%, 96%, 98%, 100% { transform: translate(0, 0) skewX(0); opacity: 1; filter: hue-rotate(0deg); }
  97% { transform: translate(-2px, 1px) skewX(10deg); opacity: 0.8; filter: hue-rotate(45deg); }
  99% { transform: translate(2px, -1px) skewX(-10deg); opacity: 0.9; filter: hue-rotate(-45deg); }
}
.brand-name { font-size: 10px; color: var(--dim); letter-spacing: 0.25em; text-transform: uppercase; line-height: 1.5; }
.brand-name b { color: var(--bright); font-weight: 700; display: block; font-size: 12px; letter-spacing: 0.15em; text-shadow: 0 0 10px rgba(255,255,255,0.2); }
"""

content = re.sub(r'\.brand \{.*\.brand-name b \{.*?\}', brand_css, content, flags=re.DOTALL)

# 2. Top Metric Cards CSS (4 columns)
grid_css = r"""
/* ---- METRIC GRID (Top Row) ---- */
.grid-top {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.m-card {
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 16px 16px 20px 16px;
  position: relative;
  transition: all 0.2s var(--ease);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 90px;
}
.m-card::before {
  content: ""; position: absolute; top: 0; left: 0; width: 3px; height: 100%;
  background: var(--border-hi); transition: background 0.2s;
}
.m-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.6); border-color: var(--border-hi); }
.m-card:hover::before { background: var(--cyan); }
.m-card:nth-child(4n+1):hover::before { background: var(--cyan); }
.m-card:nth-child(4n+2):hover::before { background: var(--blue); }
.m-card:nth-child(4n+3):hover::before { background: var(--amber); }
.m-card:nth-child(4n+4):hover::before { background: var(--green); }

.m-label { font-size: 9px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.15em; font-weight: 600; margin-bottom: 8px; z-index: 2; position: relative; }
.m-val { font-size: 32px; font-weight: 300; color: var(--bright); line-height: 1; letter-spacing: -1px; z-index: 2; position: relative; }
.m-val .unit { font-size: 12px; font-weight: 400; color: var(--dim); margin-left: 2px; }
.m-spark-svg { position: absolute; bottom: 12px; right: 12px; opacity: 0.4; transition: opacity 0.2s; z-index: 1; pointer-events: none; }
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
"""

content = re.sub(r'/\* ---- METRIC GRID \(Top Row\) ---- \*/.*?/\* ---- COMMAND CENTER GRID ---- \*/', grid_css + "\n/* ---- COMMAND CENTER GRID ---- */", content, flags=re.DOTALL)

# 3. Move Mode toggle from sidebar to Settings Modal
sidebar_mode_regex = r'<div class="mode-label">ENVIRONMENT</div>\s*<div class="mode-row">.*?</div>\s*<div class="spacer"></div>'
content = re.sub(sidebar_mode_regex, '<div class="spacer"></div>', content, flags=re.DOTALL)

settings_modal_addition = r"""    <div class="modal-s">ENVIRONMENT MODE</div>
    <div class="mode-row" style="margin-bottom: 24px;">
      <button class="mode-btn {{ 'on' if mode == MODE_CUSTOMER else '' }}" onclick="setMode('{{ MODE_CUSTOMER }}')">PARTNER / CUSTOMER VIEW</button>
      <button class="mode-btn {{ 'on' if mode == MODE_INTERNAL else '' }}" onclick="setMode('{{ MODE_INTERNAL }}')">INTERNAL OPERATOR</button>
    </div>
    
    <div class="modal-s">SLA TARGETS (MINUTES)</div>"""

content = content.replace('<div class="modal-s">SLA TARGETS (MINUTES)</div>', settings_modal_addition)

# 4. Update the Sparkline JS to draw abstract patterns if no data
js_spark = r"""// ---- SPARKLINE GENERATOR ----
const SPARKS = {{ a.get('sparks', {}) | tojson if a else '{}' }};
document.querySelectorAll('.m-spark-svg').forEach((svg, cardIndex) => {
  const label = svg.dataset.label;
  const data = SPARKS[label];
  const w = 70, h = 24, gap = 2;
  
  if (!data || !data.length) { 
    // Draw abstract data grid (binary pattern) for empty sparklines
    const patternColors = ['#00e5ff', '#0066ff', '#ffb800', '#00fa9a'];
    const c = patternColors[cardIndex % 4];
    for (let i=0; i<8; i++) {
      for (let j=0; j<3; j++) {
        if (Math.random() > 0.5) {
          const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
          rect.setAttribute('x', i * 8 + (w - 60));
          rect.setAttribute('y', j * 8);
          rect.setAttribute('width', 6);
          rect.setAttribute('height', 6);
          rect.setAttribute('fill', c);
          rect.setAttribute('opacity', Math.random() * 0.5 + 0.1);
          svg.appendChild(rect);
        }
      }
    }
    return; 
  }

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
"""

content = re.sub(r'// ---- SPARKLINE GENERATOR ----.*?// Bar animation setup', js_spark + "\n// Bar animation setup", content, flags=re.DOTALL)

with open("templates/dashboard.html", "w") as f:
    f.write(content)

print("Patch 3 successful.")

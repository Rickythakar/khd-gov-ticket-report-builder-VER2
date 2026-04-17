import re

with open("templates/dashboard.html", "r") as f:
    content = f.read()

# 1. CSS for the sidebar filters
css_filters = r"""
.side-filters {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
  transition: opacity 0.2s;
}
.side.collapsed .side-filters { display: none; }

.f-lbl { font-size: 9px; color: var(--dim); letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: -6px; }
.f-row { display: flex; border: 1px solid var(--border); }
.f-btn {
  flex: 1; padding: 6px 2px; background: transparent; border: none; border-right: 1px solid var(--border);
  color: var(--dim); font-family: var(--font); font-size: 9px; cursor: crosshair; transition: all 0.2s;
  text-align: center;
}
.f-btn:last-child { border-right: none; }
.f-btn:hover { background: var(--raised); color: var(--bright); }
.f-btn.on { background: var(--cyan); color: var(--bg); font-weight: 700; box-shadow: 0 0 10px rgba(0, 229, 255, 0.2); }

.f-meta { display: flex; flex-direction: column; gap: 8px; font-size: 9px; color: var(--dim); margin-top: 8px; }
.f-meta-row { display: flex; gap: 8px; align-items: center; justify-content: space-between; }
.f-clear {
  background: rgba(255,51,102,0.05); color: var(--red); border: 1px solid var(--red);
  padding: 6px; font-size: 9px; font-family: var(--font); cursor: crosshair; transition: all 0.2s;
  text-align: center; letter-spacing: 0.15em; font-weight: 700; width: 100%;
}
.f-clear:hover { background: var(--red); color: var(--bright); box-shadow: 0 0 15px rgba(255,51,102,0.3); }

/* ---- TREND LINE CHARTS (Redesign) ---- */
.trend-chart { overflow: visible; filter: drop-shadow(0 0 8px rgba(0,229,255,0.1)); }
.trend-line { fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; transition: stroke-dashoffset 1.5s cubic-bezier(0.16, 1, 0.3, 1); }
.trend-area { transition: opacity 1.5s cubic-bezier(0.16, 1, 0.3, 1) 0.2s; }
.trend-dot { transition: r 0.2s, opacity 0.4s ease, fill 0.2s; cursor: crosshair; }
.trend-dot:hover { r: 5; fill: var(--bright); }
.trend-label { font-family: var(--font); font-size: 9px; fill: var(--dim); }
.trend-val { font-family: var(--font); font-size: 10px; fill: var(--bright); font-weight: 600; text-shadow: 0 0 4px rgba(0,0,0,0.8); }
.trend-grid { stroke: rgba(255,255,255,0.05); stroke-dasharray: 2 4; }
"""

# Replace the old trend CSS with the new filters + trend CSS
content = re.sub(r'/\* ---- TREND LINE CHARTS ---- \*/.*?/\* ---- LISTS ---- \*/', css_filters + "\n/* ---- LISTS ---- */", content, flags=re.DOTALL)

# 2. Move PERIOD SELECTOR to sidebar
# Find the spacer in the sidebar
sidebar_html = r"""      <div class="spacer"></div>"""

sidebar_filters = r"""
      {% if has_data %}
      <div class="side-filters fade fd1">
        <div class="f-lbl">TIME HORIZON</div>
        <div class="f-row">
          {% for p in ['1M','QTR','HALF','YR'] %}
          <button class="f-btn {{ 'on' if period == p else '' }}" onclick="setPeriod('{{ p }}')">{{ p }}</button>
          {% endfor %}
        </div>
        
        {% if period == '1M' and available_months|length > 1 %}
        <div class="f-lbl" style="margin-top:8px;">MONTH RANGE</div>
        <div class="f-row" style="flex-wrap:wrap; border-bottom:none;">
          {% for m in available_months %}
          <button class="f-btn {{ 'on' if (selected_month == m or (not selected_month and loop.last)) else '' }}" onclick="setMonth('{{ m }}')" style="flex: 1 0 25%; border-bottom: 1px solid var(--border);">{{ m }}</button>
          {% endfor %}
        </div>
        {% endif %}

        <div class="f-meta">
          <div class="f-meta-row">
            {% if file_count > 1 %}<span style="color:var(--cyan);">{{ file_count }} ARCHIVES</span>{% else %}<span>1 ARCHIVE</span>{% endif %}
            {% if comp.has_comparison %}<span>{{ comp.month_count }} MONTHS</span>{% endif %}
          </div>
          <button class="f-clear" onclick="clearData()">[ PURGE CACHE ]</button>
        </div>
      </div>
      {% endif %}
      
      <div class="spacer"></div>"""

content = content.replace(sidebar_html, sidebar_filters)

# 3. Remove the old PERIOD SELECTOR from main
old_selector_regex = r'<!-- PERIOD SELECTOR \+ FILE INFO -->.*?</div>\s*</div>'
content = re.sub(old_selector_regex, '', content, flags=re.DOTALL)

# 4. Redesign renderTrendChart in JS
js_trend_chart = r"""// ---- HIGH END SVG LINE CHART RENDERER ----
function renderTrendChart(svg) {
  if (svg.dataset.rendered) return;
  let values = [];
  let labels = [];
  try {
    values = JSON.parse(svg.dataset.values || '[]');
    labels = JSON.parse(svg.dataset.labels || '[]');
  } catch (error) { return; }
  
  const color = svg.dataset.color || 'var(--cyan)';
  const unit = svg.dataset.unit || '';
  if (values.length < 2) return;
  svg.dataset.rendered = '1';

  const w = 800; 
  const h = 160;
  const pad = {top: 20, right: 40, bottom: 24, left: 16};
  const cw = w - pad.left - pad.right;
  const ch = h - pad.top - pad.bottom;

  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  
  const minVal = Math.min(...values) * 0.8;
  const maxVal = Math.max(...values) * 1.1;
  const range = (maxVal - minVal) || 1;
  
  const pts = values.map((v, i) => {
    const x = pad.left + (i / (values.length - 1)) * cw;
    const y = pad.top + ch - ((v - minVal) / range) * ch;
    return { x, y, v, label: labels[i] };
  });

  const pathD = `M ${pts.map(p => `${p.x},${p.y}`).join(' L ')}`;
  const areaD = `${pathD} L ${pts[pts.length-1].x},${pad.top+ch} L ${pts[0].x},${pad.top+ch} Z`;

  // Draw Grid
  for (let i=0; i<=3; i++) {
    const gy = pad.top + (i/3)*ch;
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', pad.left); line.setAttribute('x2', pad.left+cw);
    line.setAttribute('y1', gy); line.setAttribute('y2', gy);
    line.classList.add('trend-grid');
    svg.appendChild(line);
  }

  // Defs for Glow and Gradient
  const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
  const uid = Math.random().toString(36).substr(2, 9);
  defs.innerHTML = `
    <linearGradient id="grad-${uid}" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="${color}" stop-opacity="0.3" />
      <stop offset="100%" stop-color="${color}" stop-opacity="0.0" />
    </linearGradient>
    <filter id="glow-${uid}" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  `;
  svg.appendChild(defs);

  // Draw Area
  const area = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  area.setAttribute('d', areaD);
  area.setAttribute('fill', `url(#grad-${uid})`);
  area.classList.add('trend-area');
  area.style.opacity = '0';
  svg.appendChild(area);

  // Draw Line
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', pathD);
  path.classList.add('trend-line');
  path.setAttribute('stroke', color);
  path.setAttribute('filter', `url(#glow-${uid})`);
  
  const pathLen = 3000; 
  path.setAttribute('stroke-dasharray', pathLen);
  path.setAttribute('stroke-dashoffset', pathLen);
  svg.appendChild(path);

  // Draw Points & Labels
  pts.forEach((p, i) => {
    // Label x-axis
    const txtX = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    txtX.setAttribute('x', p.x); txtX.setAttribute('y', pad.top + ch + 16);
    txtX.setAttribute('text-anchor', i === 0 ? 'start' : (i === pts.length-1 ? 'end' : 'middle'));
    txtX.classList.add('trend-label');
    txtX.textContent = p.label;
    svg.appendChild(txtX);

    // Value label above dot
    const txtY = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    txtY.setAttribute('x', p.x); txtY.setAttribute('y', p.y - 12);
    txtY.setAttribute('text-anchor', 'middle');
    txtY.classList.add('trend-val');
    txtY.textContent = Number.isInteger(p.v) ? p.v + unit : p.v.toFixed(1) + unit;
    txtY.style.opacity = '0';
    txtY.style.transition = `opacity 0.3s ease ${i * 0.1 + 0.6}s`;
    svg.appendChild(txtY);

    // Dot
    const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    dot.setAttribute('cx', p.x); dot.setAttribute('cy', p.y);
    dot.setAttribute('r', '3');
    dot.setAttribute('fill', '#020a1c');
    dot.setAttribute('stroke', color);
    dot.setAttribute('stroke-width', '2');
    dot.classList.add('trend-dot');
    dot.style.opacity = '0';
    
    // Hover interactivity
    dot.addEventListener('mouseenter', () => {
      txtY.style.fill = 'var(--bright)';
      txtY.style.fontSize = '12px';
    });
    dot.addEventListener('mouseleave', () => {
      txtY.style.fill = '';
      txtY.style.fontSize = '';
    });
    
    svg.appendChild(dot);
    
    requestAnimationFrame(() => {
      setTimeout(() => { dot.style.opacity = '1'; }, i * 100 + 400);
    });
  });

  requestAnimationFrame(() => {
    setTimeout(() => {
      path.setAttribute('stroke-dashoffset', '0');
      area.style.opacity = '1';
    }, 100);
    setTimeout(() => {
      svg.querySelectorAll('.trend-val').forEach(t => t.style.opacity = '1');
    }, 500);
  });
}
"""

content = re.sub(r'// ---- SVG LINE CHART RENDERER ----.*?function renderTrendChart.*?}', js_trend_chart, content, flags=re.DOTALL)

with open("templates/dashboard.html", "w") as f:
    f.write(content)

print("Patch 7 selectors applied.")

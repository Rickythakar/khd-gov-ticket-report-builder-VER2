import re

with open("templates/dashboard.html", "r") as f:
    content = f.read()

# 1. Update logo glitch in CSS
brand_css = """
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
"""

content = re.sub(r'\.brand \{.*\.brand-name \{.*?\}', brand_css, content, flags=re.DOTALL)

# 2. Add panel collapsible CSS
panel_css = """
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

/* ASCII Loader inside panel-body */
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
"""

content = re.sub(r'/\* ---- COMMAND CENTER GRID ---- \*/.*?/\* ---- TABLES ---- \*/', panel_css, content, flags=re.DOTALL)

# 3. Update Table and Bar charts for more interactive and hacker vibe
table_css = """
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
"""

content = re.sub(r'/\* ---- TABLES ---- \*/.*?/\* ---- LISTS ---- \*/', table_css, content, flags=re.DOTALL)

# 4. Update the HTML structure of the panels to include the panel-body-wrap, ascii-loader, and panel-content
# and update the p-meta to include the arrow

def panel_replacer(match):
    head = match.group(1)
    body_content = match.group(2)
    
    # Add arrow to p-meta
    head = re.sub(r'<div class="p-meta">(.*?)</div>', r'<div class="p-meta">\1 <span class="p-arrow">►</span></div>', head)
    
    new_html = f"""<div class="panel" onclick="togglePanel(this, event)">
        <div class="panel-head">
{head}        </div>
        <div class="panel-body-wrap"><div class="panel-body">
          <div class="ascii-loader"></div>
          <div class="panel-content">
{body_content}          </div>
        </div></div>
      </div>"""
    return new_html

content = re.sub(r'<div class="panel(?: span-2)?">\s*<div class="panel-head">(.*?)</div>\s*<div class="panel-body">(.*?)</div>\s*</div>', panel_replacer, content, flags=re.DOTALL)

# Also fix the panel span-2 that got lost in the regex (since I didn't capture the class name)
# Actually, I should refine my regex
def panel_replacer2(match):
    classes = match.group(1)
    head = match.group(2)
    body_content = match.group(3)
    
    # Add arrow to p-meta if not there
    if '<span class="p-arrow">' not in head:
        head = re.sub(r'<div class="p-meta"(.*?)>(.*?)</div>', r'<div class="p-meta"\1>\2 <span class="p-arrow">►</span></div>', head)
        
    # Replace onclick if there is one on panel-head, we move it to panel and use togglePanel
    # Actually, let's just make the whole panel head clickable
    head = re.sub(r'<div class="panel-head".*?>', '<div class="panel-head" onclick="togglePanel(this.parentElement, event)">', head)
    
    new_html = f"""<div class="{classes}">
{head}        <div class="panel-body-wrap"><div class="panel-body">
          <div class="ascii-loader"></div>
          <div class="panel-content">
{body_content}          </div>
        </div></div>
      </div>"""
    return new_html

# Let's read from disk, do the replacement again because the first one failed if the regex wasn't right
with open("templates/dashboard.html", "r") as f:
    content = f.read()

content = re.sub(r'\.brand \{.*\.brand-name \{.*?\}', brand_css, content, flags=re.DOTALL)
content = re.sub(r'/\* ---- COMMAND CENTER GRID ---- \*/.*?/\* ---- TABLES ---- \*/', panel_css, content, flags=re.DOTALL)
content = re.sub(r'/\* ---- TABLES ---- \*/.*?/\* ---- LISTS ---- \*/', table_css, content, flags=re.DOTALL)

# Now do HTML
content = re.sub(r'<div class="(panel[^"]*)">\s*(<div class="panel-head">.*?</div>)\s*<div class="panel-body">\s*(.*?)\s*</div>\s*</div>', panel_replacer2, content, flags=re.DOTALL)

# 5. Add togglePanel JS
js_toggle = """
const ASCII_FRAMES = [
  "[INITIALIZING MODULE]\\n> VERIFYING DATA INTEGRITY... [OK]\\n> DECRYPTING PAYLOAD...",
  "[INITIALIZING MODULE]\\n> VERIFYING DATA INTEGRITY... [OK]\\n> DECRYPTING PAYLOAD... 0x4F2A",
  "[INITIALIZING MODULE]\\n> VERIFYING DATA INTEGRITY... [OK]\\n> DECRYPTING PAYLOAD... 0x8B1C\\n> ALLOCATING MEMORY...",
  "[INITIALIZING MODULE]\\n> VERIFYING DATA INTEGRITY... [OK]\\n> DECRYPTING PAYLOAD... 0xFFFF\\n> ALLOCATING MEMORY... [OK]\\n> RENDER DATA STREAM..."
];

function togglePanel(panel, event) {
  // Prevent toggle if clicking on a tab button or inner interactive element
  if (event && (event.target.tagName === 'BUTTON' || event.target.closest('.tab-bar'))) {
    return;
  }
  
  if (panel.classList.contains('open')) {
    panel.classList.remove('open');
    return;
  }
  
  // Open and animate
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
          // re-trigger bar animation
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
"""

content = content.replace("function switchTab", js_toggle + "\nfunction switchTab")

with open("templates/dashboard.html", "w") as f:
    f.write(content)

print("Patched.")

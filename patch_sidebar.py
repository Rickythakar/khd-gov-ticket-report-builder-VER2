import re

with open("templates/dashboard.html", "r") as f:
    content = f.read()

# 1. Update .side CSS to include transition and .collapsed rules
side_css_old = r"""/* ---- SIDEBAR ---- */
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
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100vh;
  position: sticky;
  top: 0;
}"""

side_css_new = r"""/* ---- SIDEBAR ---- */
.side {
  width: 240px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 10;
  box-shadow: 10px 0 30px rgba(0,0,0,0.8);
  transition: width 0.3s var(--ease);
}
.side.collapsed {
  width: 72px;
}
.side-inner {
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100vh;
  position: sticky;
  top: 0;
  overflow: hidden;
  transition: padding 0.3s var(--ease);
}
.side.collapsed .side-inner {
  padding: 24px 14px;
}

/* Collapsed Brand */
.side.collapsed .brand { justify-content: center; padding-bottom: 24px; gap: 0; }
.side.collapsed .brand-name { opacity: 0; position: absolute; pointer-events: none; width: 0; }
.brand-mark { transition: transform 0.3s var(--ease); }
.side.collapsed .brand-mark { transform: scale(0.9); margin-left: -2px; }

/* Collapsed Dropzone */
.side.collapsed .drop-text, .side.collapsed .drop-file { display: none; }
.side.collapsed .drop { padding: 16px 0; }
.side.collapsed .drop-icon { margin-bottom: 0; font-size: 20px; line-height: 1; }

/* Collapsed Buttons */
.side.collapsed .s-btn-txt { display: none; }
.s-btn-icn { display: none; font-size: 16px; line-height: 1; }
.side.collapsed .s-btn-icn { display: inline-block; }
.side.collapsed .s-btn { padding: 12px 0; display: flex; justify-content: center; align-items: center; }

.col-btn {
  background: transparent;
  border: 1px solid var(--border-hi);
  color: var(--dim);
  font-family: var(--font);
  font-size: 14px;
  cursor: pointer;
  padding: 6px;
  margin-top: 12px;
  transition: all 0.2s var(--ease);
  text-align: center;
  display: flex;
  justify-content: center;
  align-items: center;
}
.col-btn:hover { background: var(--raised); color: var(--cyan); border-color: var(--cyan); }
.col-btn .ico { transition: transform 0.3s var(--ease); }
.side.collapsed .col-btn .ico { transform: rotate(180deg); }
"""

content = content.replace(side_css_old, side_css_new)

# 2. Update Sidebar HTML
sidebar_old = r"""      <div class="side-actions">
        <button class="s-btn pri" onclick="openExport()" {{ 'disabled' if not has_data else '' }}>COMPILE REPORT</button>
        <button class="s-btn" onclick="openSettings()">SYS CONFIG</button>
      </div>"""

sidebar_new = r"""      <div class="side-actions">
        <button class="s-btn pri" onclick="openExport()" {{ 'disabled' if not has_data else '' }} title="COMPILE REPORT">
          <span class="s-btn-icn">▤</span><span class="s-btn-txt">COMPILE REPORT</span>
        </button>
        <button class="s-btn" onclick="openSettings()" title="SYS CONFIG">
          <span class="s-btn-icn">⚙</span><span class="s-btn-txt">SYS CONFIG</span>
        </button>
        <button class="col-btn" onclick="toggleSidebar()" title="TOGGLE SIDEBAR">
          <span class="ico">«</span>
        </button>
      </div>"""

content = content.replace(sidebar_old, sidebar_new)

# 3. Add JS toggle function
js_old = "function togglePanel(panelTrigger, event) {"
js_new = """function toggleSidebar() {
  document.querySelector('.side').classList.toggle('collapsed');
  // Optional: save state to localStorage to persist across reloads
  localStorage.setItem('sidebar_collapsed', document.querySelector('.side').classList.contains('collapsed'));
}

// Restore sidebar state on load
if(localStorage.getItem('sidebar_collapsed') === 'true') {
  document.querySelector('.side').classList.add('collapsed');
}

function togglePanel(panelTrigger, event) {"""

content = content.replace(js_old, js_new)

with open("templates/dashboard.html", "w") as f:
    f.write(content)

print("Sidebar patch applied.")

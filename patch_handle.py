import re

with open("templates/dashboard.html", "r") as f:
    content = f.read()

# Replace col-btn with sidebar-handle
content = content.replace('<button class="col-btn" onclick="toggleSidebar()" title="TOGGLE SIDEBAR">', '')
content = content.replace('<span class="ico">«</span>\n        </button>', '')

# We will just inject the handle right after <div class="side">
handle_html = """<div class="side">
    <button class="sidebar-handle" onclick="toggleSidebar()" title="TOGGLE SIDEBAR">
      <span class="ico">«</span>
    </button>"""

content = content.replace('<div class="side">', handle_html, 1)

# CSS for the handle
handle_css = """
/* Sidebar Toggle Handle */
.sidebar-handle {
  position: absolute;
  top: 50%;
  right: -14px;
  transform: translateY(-50%);
  width: 14px;
  height: 64px;
  background: var(--surface);
  border: 1px solid var(--border-hi);
  border-left: none;
  cursor: crosshair;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dim);
  font-size: 10px;
  z-index: 100;
  transition: all 0.2s var(--ease);
}
.sidebar-handle:hover {
  background: var(--raised);
  color: var(--cyan);
  border-color: var(--cyan);
  width: 18px;
  right: -18px;
}
.sidebar-handle .ico { transition: transform 0.3s var(--ease); }
.side.collapsed .sidebar-handle .ico { transform: rotate(180deg); }
"""

# add css handle right before /* Brand */
content = content.replace('/* Collapsed Brand */', handle_css + '\n/* Collapsed Brand */')

# remove old col-btn css
content = re.sub(r'\.col-btn \{.*?\n\}', '', content, flags=re.DOTALL)
content = re.sub(r'\.col-btn:hover \{.*?\}', '', content, flags=re.DOTALL)
content = re.sub(r'\.col-btn \.ico \{.*?\}', '', content, flags=re.DOTALL)
content = re.sub(r'\.side\.collapsed \.col-btn \.ico \{.*?\}', '', content, flags=re.DOTALL)

with open("templates/dashboard.html", "w") as f:
    f.write(content)

print("Toggle handle applied.")

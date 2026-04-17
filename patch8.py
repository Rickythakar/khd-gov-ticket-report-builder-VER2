import re

with open("templates/dashboard.html", "r") as f:
    content = f.read()

# 1. CSS for .drop
css_drop_old = r"""/* Upload */
.drop {
  border: 1px dashed var(--border-hi);
  background: rgba(255,255,255,0.01);
  padding: 16px 10px;
  text-align: center;
  cursor: pointer;
  position: relative;
  transition: all 0.2s var(--ease);
}
.side.collapsed .drop { padding: 16px 0; display: flex; align-items: center; justify-content: center; }
.drop:hover { border-color: var(--amber); background: rgba(255, 184, 0, 0.05); }
.drop.loaded { border-color: var(--green); border-style: solid; background: rgba(0,250,154,0.05); }
.drop input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.drop-icon { color: var(--dim); font-size: 16px; margin-bottom: 4px; transition: color 0.2s; }
.side.collapsed .drop-icon { margin-bottom: 0; font-size: 20px; line-height: 1; }
.drop:hover .drop-icon { color: var(--amber); }
.drop-text { color: var(--text); font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; transition: opacity 0.2s; }
.drop-file { color: var(--green); font-size: 10px; word-break: break-all; font-weight: 600; transition: opacity 0.2s; }
.side.collapsed .drop-text, .side.collapsed .drop-file { display: none; }"""

css_drop_new = r"""/* Upload */
.drop {
  border: 1px dashed var(--border-hi);
  background: rgba(255,255,255,0.01);
  padding: 16px 10px;
  text-align: center;
  cursor: pointer;
  position: relative;
  transition: all 0.2s var(--ease);
}
.side.collapsed .drop { padding: 16px 0; display: flex; align-items: center; justify-content: center; }
.drop:hover { border-color: var(--cyan); background: var(--cyan-dim); }
.drop.loaded { 
  border-color: var(--cyan); 
  border-style: solid; 
  background: rgba(0, 229, 255, 0.02); 
  animation: drop-pulse 4s infinite ease-in-out;
}
@keyframes drop-pulse {
  0%, 100% { box-shadow: inset 0 0 0px rgba(0,229,255,0); border-color: var(--border-hi); }
  50% { box-shadow: inset 0 0 15px rgba(0,229,255,0.1); border-color: var(--cyan); }
}
.drop input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.drop-icon { color: var(--dim); font-size: 16px; margin-bottom: 6px; transition: color 0.2s; line-height: 1; }
.side.collapsed .drop-icon { margin-bottom: 0; font-size: 20px; }
.drop:hover .drop-icon { color: var(--cyan); }
.drop-text { color: var(--cyan); font-size: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.15em; margin-top: 8px; transition: opacity 0.2s; }
.drop-file { color: var(--bright); font-size: 9px; word-break: break-all; font-weight: 400; letter-spacing: 0.05em; transition: opacity 0.2s; }
.side.collapsed .drop-text, .side.collapsed .drop-file { display: none; }"""

content = content.replace(css_drop_old, css_drop_new)

# 2. HTML for dropZone
html_drop_old = r"""      <div class="drop {{ 'loaded' if csv_name else '' }}" id="dropZone">
        <input type="file" accept=".csv" id="csvIn" multiple>
        {% if csv_name %}
          {% if file_count > 1 %}
            <div class="drop-icon" style="color:var(--cyan); display:flex; justify-content:center; align-items:center; gap:2px; font-weight:800; font-size:16px;">
              {{ file_count }}<span style="font-size:12px; font-weight:400; animation: blink 2s infinite;">❖</span>
            </div>
            <div class="drop-file" style="color:var(--cyan); margin-top:2px;">ARCHIVES MOUNTED</div>
            <div class="drop-text" style="margin-top:4px; font-size:8px;">SYSTEM READY</div>
          {% else %}
            <div class="drop-icon" style="color:var(--green); animation: blink 2s infinite;">◆</div>
            <div class="drop-file">{{ csv_name }}</div>
            <div class="drop-text" style="margin-top:4px; font-size:8px;">READY</div>
          {% endif %}
        {% else %}
          <div class="drop-icon">⇡</div>
          <div class="drop-text">MOUNT DATA.CSV</div>
        {% endif %}
      </div>"""

html_drop_new = r"""      <div class="drop {{ 'loaded' if csv_name else '' }}" id="dropZone">
        <input type="file" accept=".csv" id="csvIn" multiple>
        {% if csv_name %}
          <div class="drop-icon" style="color:var(--cyan); font-size:18px;">
            {% if file_count > 1 %}▤{% else %}■{% endif %}
          </div>
          <div class="drop-file">{{ csv_name }}</div>
          <div class="drop-text">DATA LINK SECURE</div>
        {% else %}
          <div class="drop-icon">⇡</div>
          <div class="drop-text" style="color:var(--dim); font-weight:400;">MOUNT DATA.CSV</div>
        {% endif %}
      </div>"""

content = content.replace(html_drop_old, html_drop_new)

with open("templates/dashboard.html", "w") as f:
    f.write(content)

print("Dropzone patch applied.")

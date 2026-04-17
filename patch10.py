import re

with open("templates/dashboard.html", "r") as f:
    content = f.read()

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
  animation: drop-pulse 6s infinite ease-in-out;
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
.side.collapsed .drop-text, .side.collapsed .drop-file { display: none; }

/* Mode */"""

content = re.sub(r'/\* Upload \*/.*?/\* Mode \*/', css_drop_new, content, flags=re.DOTALL)

with open("templates/dashboard.html", "w") as f:
    f.write(content)

print("Dropzone CSS patch 10 applied.")

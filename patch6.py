import re

with open("templates/dashboard.html", "r") as f:
    content = f.read()

new_hover = r"""
.brand-mark {
  font-size: 26px;
  font-weight: 800;
  color: #020a1c; /* Deep navy text */
  background: #89CFF0; /* Baby blue fill */
  border: 1px solid #89CFF0;
  padding: 4px 10px;
  line-height: 1.1;
  letter-spacing: -2px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: crosshair;
  /* Brutalist cut corner */
  clip-path: polygon(0 0, 100% 0, 100% calc(100% - 12px), calc(100% - 12px) 100%, 0 100%);
  transition: background 0s, color 0s, box-shadow 0s, border-color 0s;
  width: 44px;
  height: 38px;
}

/* Hover state: Switch to matrix green on dark background */
.brand-mark:hover {
  background: #020a1c;
  color: #00fa9a; /* Matrix green */
  border-color: #00fa9a;
  box-shadow: inset 0 0 10px rgba(0, 250, 154, 0.1), 0 0 15px rgba(0, 250, 154, 0.2);
}
"""

content = re.sub(r'\.brand-mark \{.*?\.brand-mark:hover \{.*?\}', new_hover, content, flags=re.DOTALL)

with open("templates/dashboard.html", "w") as f:
    f.write(content)

print("Patch 6 applied.")

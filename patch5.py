import re

with open("templates/dashboard.html", "r") as f:
    content = f.read()

brand_css = r"""
.brand {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border);
}
.brand-mark {
  font-size: 26px;
  font-weight: 800;
  color: #020a1c; /* Deep navy text */
  background: #89CFF0; /* Baby blue fill */
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
  transition: background 0s, color 0s, box-shadow 0s;
  width: 44px;
  height: 38px;
}

/* Hover state: Switch to matrix green on dark background */
.brand-mark:hover {
  background: #020a1c;
  color: #00fa9a; /* Matrix green */
  box-shadow: 0 0 15px rgba(0, 250, 154, 0.2);
}

/* Typographic character-scramble Matrix Glitch */
.brand-mark::after {
  content: "01";
  position: absolute;
  top: 0; left: 0; width: 100%; height: 100%;
  background: #020a1c;
  color: #00fa9a;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  letter-spacing: -1px;
  pointer-events: none;
  opacity: 0;
}

.brand-mark:hover::after {
  animation: hacker-scramble 0.25s steps(1) forwards;
}

@keyframes hacker-scramble {
  0%   { content: "01"; opacity: 1; }
  20%  { content: "10"; opacity: 1; }
  40%  { content: "0x"; opacity: 1; }
  60%  { content: "F#"; opacity: 1; }
  80%  { content: "11"; opacity: 1; text-shadow: 0 0 8px rgba(0,250,154,0.5); }
  100% { opacity: 0; }
}

/* Remove old pseudo elements and slice animations */
"""

content = re.sub(r'\.brand-mark \{.*\.brand-name \{', brand_css + "\n.brand-name {", content, flags=re.DOTALL)

with open("templates/dashboard.html", "w") as f:
    f.write(content)

print("Patch 5 applied.")

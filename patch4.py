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
  display: inline-block;
  cursor: crosshair;
  /* Brutalist cut corner */
  clip-path: polygon(0 0, 100% 0, 100% calc(100% - 12px), calc(100% - 12px) 100%, 0 100%);
  transition: background 0.2s, color 0.2s;
}

/* Base states for the pseudo-elements (hidden by default) */
.brand-mark::before,
.brand-mark::after {
  content: "HD";
  position: absolute;
  top: 0; left: 0; width: 100%; height: 100%;
  color: #89CFF0;
  background: #020a1c;
  padding: 4px 10px;
  clip-path: polygon(0 0, 100% 0, 100% calc(100% - 12px), calc(100% - 12px) 100%, 0 100%);
  display: none;
  pointer-events: none;
}

/* Only animate ON HOVER - Matrix Style Glitch */
.brand-mark:hover {
  background: transparent;
  color: transparent; /* hide real text, show pseudos */
}
.brand-mark:hover::before,
.brand-mark:hover::after {
  display: block;
}
.brand-mark:hover::before {
  left: 2px;
  text-shadow: -2px 0 var(--cyan);
  animation: matrix-glitch-1 0.3s infinite linear alternate-reverse;
}
.brand-mark:hover::after {
  left: -2px;
  text-shadow: 2px 0 var(--blue);
  animation: matrix-glitch-2 0.25s infinite linear alternate-reverse;
}

@keyframes matrix-glitch-1 {
  0% { clip-path: inset(20% 0 80% 0); transform: translate(0); }
  20% { clip-path: inset(60% 0 10% 0); transform: translate(-2px, 1px); }
  40% { clip-path: inset(40% 0 50% 0); transform: translate(2px, -1px); }
  60% { clip-path: inset(80% 0 5% 0); transform: translate(-2px, 2px); }
  80% { clip-path: inset(10% 0 70% 0); transform: translate(0); }
  100% { clip-path: inset(30% 0 20% 0); transform: translate(0); }
}
@keyframes matrix-glitch-2 {
  0% { clip-path: inset(10% 0 50% 0); transform: translate(0); }
  20% { clip-path: inset(80% 0 5% 0); transform: translate(2px, -2px); }
  40% { clip-path: inset(30% 0 40% 0); transform: translate(-2px, 1px); }
  60% { clip-path: inset(60% 0 20% 0); transform: translate(2px, 2px); }
  80% { clip-path: inset(0 0 100% 0); transform: translate(0); }
  100% { clip-path: inset(0 0 100% 0); transform: translate(0); }
}

.brand-name { font-size: 10px; color: var(--dim); letter-spacing: 0.25em; text-transform: uppercase; line-height: 1.5; }
.brand-name b { color: var(--bright); font-weight: 700; display: block; font-size: 12px; letter-spacing: 0.15em; text-shadow: 0 0 10px rgba(255,255,255,0.2); }
"""

# We replace from .brand { down to .brand-name b { ... }
content = re.sub(r'\.brand \{.*\.brand-name b \{.*?\}', brand_css, content, flags=re.DOTALL)

with open("templates/dashboard.html", "w") as f:
    f.write(content)

print("Patch 4 applied.")

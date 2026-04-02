from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    project_dir = Path(__file__).resolve().parent
    streamlit_file = project_dir / "streamlit_app.py"
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(streamlit_file),
        "--server.address",
        "127.0.0.1",
    ]
    return subprocess.call(command, cwd=str(project_dir))


if __name__ == "__main__":
    raise SystemExit(main())

Frontend rollback snapshot created on `2026-04-02 11:28:13`.

Purpose:
- Preserve the current FastAPI dashboard frontend before Gemini-driven UI work.
- Keep the frontend-coupled logic nearby for comparison if Gemini changes the data contract.

Captured files:
- `templates/dashboard.html`
- `static/`
- `assets/`
- `server.py`
- `comparison.py`
- `analytics.py`
- `metrics.py`
- `utils.py`
- `config.py`

Suggested restore path if Gemini breaks the UI:
1. Diff the live file against this snapshot.
2. Restore only the affected frontend file first, usually `templates/dashboard.html`.
3. If the break is contract-related, compare `server.py`, `comparison.py`, `analytics.py`, `metrics.py`, and `utils.py` against this snapshot.

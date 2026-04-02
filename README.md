# KHD Governance Report Builder

KHD Governance Report Builder is a local Streamlit app that turns a KHD ticket CSV into a governance workbook and optional executive PDF snapshot.

The folder rename to `khd-gov-ticket-report-builder` does not break the app logic. The code uses same-folder imports, so the main cleanup needed after the rename was the documentation and launch flow.

## Easiest Way To Run

From Command Prompt:

```cmd
cd C:\Users\ricky.thakar\Downloads\CODE\khd-gov-ticket-report-builder
setup.cmd
run.cmd
```

Then open:

```text
http://localhost:8501
```

No PowerShell activation is required.

If you use VS Code on a corporate Windows laptop, this repo includes workspace settings that:

- disable Python terminal auto-activation
- prefer Command Prompt over PowerShell
- point VS Code at `.venv\Scripts\python.exe`

That avoids the common `Activate.ps1` execution-policy problem on managed machines.

## Direct Interpreter Launch

If the virtual environment already exists:

```cmd
cd C:\Users\ricky.thakar\Downloads\CODE\khd-gov-ticket-report-builder
.venv\Scripts\python.exe app.py
```

The app now defaults to `127.0.0.1`, so it stays local to your machine by default.

## What The Tool Does

- uploads a completed-ticket CSV export
- detects partner and reporting-period context
- validates required columns and reports missing fields clearly
- builds a review-ready governance workbook
- optionally produces a PDF snapshot for leadership review
- keeps workbook generation local on the machine

## Current Structure

```text
khd-gov-ticket-report-builder/
|-- app.py
|-- run.cmd
|-- setup.cmd
|-- config.py
|-- streamlit_app.py
|-- validators.py
|-- utils.py
|-- excel_builder.py
|-- pdf_builder.py
|-- requirements.txt
|-- README.md
|-- assets/
|   `-- hd_services_logo.png
`-- .streamlit/
    `-- config.toml
```

## Key Notes

- `app.py` is a thin launcher that starts Streamlit from the current interpreter.
- `streamlit_app.py` contains the Streamlit UI.
- `validators.py` handles CSV validation and field preparation.
- `utils.py` contains report-building and summarization helpers.
- `excel_builder.py` and `pdf_builder.py` generate the output files.

## Local-Only Behavior

This project is set up to run locally:

- `app.py` launches Streamlit with `--server.address 127.0.0.1`
- `.streamlit/config.toml` also sets `address = "127.0.0.1"`
- `run.cmd` uses the local virtual environment interpreter if present

That means the intended URL is:

```text
http://localhost:8501
```

or:

```text
http://127.0.0.1:8501
```

## Security / Data Handling

Current behavior:

- reads a user-provided CSV and optional PNG logo
- processes data locally with `pandas`
- creates Excel and optional PDF outputs locally
- does not call external APIs or cloud services
- does not require credentials or a database

## Setup Details

`setup.cmd` will:

- create `.venv` if needed
- install dependencies from `requirements.txt`
- print the exact next steps

Manual setup is also supported:

```cmd
cd C:\Users\ricky.thakar\Downloads\CODE\khd-gov-ticket-report-builder
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

## Requirements

Dependencies remain in `requirements.txt`:

```text
pandas>=2.2.0
Pillow>=10.0.0
streamlit>=1.43.0
xlsxwriter>=3.2.0
```

## Required CSV Fields

- `Ticket Number`
- `Nexus Ticket Number`
- `Title`
- `Company`
- `Created`
- `Complete Date`
- `Issue Type`
- `Queue`
- `Escalation Reason`
- `Source`

Aliases can be adjusted in [`config.py`](C:/Users/ricky.thakar/Downloads/CODE/khd-gov-ticket-report-builder/config.py).

## Troubleshooting

### PowerShell activation is blocked

Skip activation and use:

```cmd
run.cmd
```

or:

```cmd
.venv\Scripts\python.exe app.py
```

### The app does not start

Run:

```cmd
setup.cmd
```

### The browser opens but the app is not reachable

Use:

```text
http://localhost:8501
```

If another app is already using port `8501`, stop that app first or run Streamlit manually on another port.

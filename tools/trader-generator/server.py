"""
Minimal FastAPI file server for browsing and downloading generated CSVs.
Started after generate.py completes. No connection to behavioral-mirror.

Endpoints:
  GET /          - Lists all generated CSVs with download links
  GET /csv/{fn}  - Downloads a specific trader CSV
  GET /summary   - Returns summary.txt contents
  GET /status    - Generation status: running, complete, failed
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

DATA_DIR = os.environ.get("OUTPUT_DIR", "/data")

app = FastAPI(title="Trader Generator File Server")


@app.get("/status")
def status():
    """Return generation status."""
    status_file = os.path.join(DATA_DIR, ".status")
    if os.path.exists(status_file):
        with open(status_file) as f:
            return {"status": f.read().strip()}
    return {"status": "unknown"}


@app.get("/summary", response_class=PlainTextResponse)
def summary():
    """Return summary.txt contents."""
    path = os.path.join(DATA_DIR, "summary.txt")
    if not os.path.exists(path):
        raise HTTPException(404, "summary.txt not found")
    with open(path) as f:
        return f.read()


@app.get("/csv/{filename}")
def download_csv(filename: str):
    """Download a specific trader CSV."""
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = os.path.join(DATA_DIR, "csvs", filename)
    if not os.path.exists(path):
        raise HTTPException(404, f"{filename} not found")
    return FileResponse(path, media_type="text/csv", filename=filename)


@app.get("/", response_class=HTMLResponse)
def index():
    """List all generated CSVs with download links."""
    csv_dir = os.path.join(DATA_DIR, "csvs")
    files = []
    if os.path.isdir(csv_dir):
        files = sorted(f for f in os.listdir(csv_dir) if f.endswith(".csv"))

    status_text = "unknown"
    status_file = os.path.join(DATA_DIR, ".status")
    if os.path.exists(status_file):
        with open(status_file) as f:
            status_text = f.read().strip()

    rows = ""
    for fn in files:
        path = os.path.join(csv_dir, fn)
        size_kb = os.path.getsize(path) / 1024
        rows += (
            f'<tr><td><a href="/csv/{fn}">{fn}</a></td>'
            f"<td>{size_kb:.1f} KB</td></tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Trader Generator</title>
  <style>
    body {{ font-family: monospace; margin: 2rem; background: #1a1a2e; color: #e0e0e0; }}
    h1 {{ color: #0f0; }}
    a {{ color: #4fc3f7; }}
    table {{ border-collapse: collapse; margin-top: 1rem; }}
    th, td {{ padding: 0.4rem 1.2rem; text-align: left; border-bottom: 1px solid #333; }}
    th {{ color: #aaa; }}
    .status {{ padding: 0.5rem 1rem; border-radius: 4px; display: inline-block; margin-bottom: 1rem; }}
    .status.complete {{ background: #1b5e20; }}
    .status.running {{ background: #e65100; }}
    .status.failed {{ background: #b71c1c; }}
  </style>
</head>
<body>
  <h1>Trader Generator Output</h1>
  <div class="status {status_text.split(':')[0]}">{status_text}</div>
  <p><a href="/summary">View summary.txt</a></p>
  <table>
    <tr><th>File</th><th>Size</th></tr>
    {rows}
  </table>
  <p>{len(files)} CSV files</p>
</body>
</html>"""
    return html

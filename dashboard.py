"""Live dashboard for batch.py — reads progress.json / errors.json.

    python dashboard.py --output batch_outputs     # then open http://127.0.0.1:5001
"""
import argparse
import json
import os
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

OUTPUT_DIR = os.getenv("BATCH_OUTPUT_DIR", "batch_outputs")

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DSF Batch Dashboard</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600;700&display=swap');
        :root { --bg:#0a0f1a; --s1:#111827; --s2:#1e293b; --brd:#2d3a4f; --t1:#e2e8f0; --t2:#94a3b8; --g:#10b981; --r:#ef4444; --y:#f59e0b; --b:#3b82f6; }
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:'IBM Plex Sans',sans-serif; background:var(--bg); color:var(--t1); min-height:100vh; }
        .container { max-width:900px; margin:0 auto; padding:30px 20px; }
        h1 { color:var(--g); font-size:1.5rem; margin-bottom:24px; }
        .cards { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:24px; }
        .card { background:var(--s1); border:1px solid var(--brd); border-radius:12px; padding:20px; text-align:center; }
        .card .val { font-size:2rem; font-weight:700; font-family:'IBM Plex Mono',monospace; }
        .card .lbl { font-size:.75rem; color:var(--t2); margin-top:4px; }
        .card.success .val { color:var(--g); }
        .card.error .val { color:var(--r); }
        .card.warn .val { color:var(--y); }
        .card.info .val { color:var(--b); }
        .bar-bg { background:var(--s2); border-radius:8px; height:12px; overflow:hidden; margin-bottom:24px; }
        .bar-fill { height:100%; background:linear-gradient(90deg,var(--g),#059669); transition:width .5s; border-radius:8px; }
        .section { background:var(--s1); border:1px solid var(--brd); border-radius:12px; padding:20px; margin-bottom:16px; }
        .section h3 { font-size:.9rem; color:var(--t2); margin-bottom:12px; }
        table { width:100%; border-collapse:collapse; font-size:.8rem; }
        th { text-align:left; color:var(--t2); padding:8px 12px; border-bottom:1px solid var(--brd); }
        td { padding:8px 12px; border-bottom:1px solid var(--brd); font-family:'IBM Plex Mono',monospace; }
        .status-ok { color:var(--g); }
        .status-fail { color:var(--r); }
        .status-skip { color:var(--y); }
        .refresh { color:var(--t2); font-size:.75rem; text-align:right; margin-bottom:8px; }
        @media(max-width:600px) { .cards { grid-template-columns:repeat(2,1fr); } }
    </style>
</head>
<body>
    <div class="container">
        <h1>&#9670; DSF Document AI — Batch</h1>
        <div class="refresh">Auto-refreshes every 5s | <span id="time"></span></div>

        <div class="cards">
            <div class="card info"><div class="val" id="total">-</div><div class="lbl">Total PDFs</div></div>
            <div class="card success"><div class="val" id="done">-</div><div class="lbl">Completed</div></div>
            <div class="card warn"><div class="val" id="skip">-</div><div class="lbl">Skipped</div></div>
            <div class="card error"><div class="val" id="fail">-</div><div class="lbl">Failed</div></div>
        </div>

        <div class="bar-bg"><div class="bar-fill" id="bar" style="width:0%"></div></div>

        <div class="section" id="errorsSection" style="display:none">
            <h3>Recent Errors</h3>
            <table>
                <thead><tr><th>File</th><th>Status</th><th>Error</th></tr></thead>
                <tbody id="errorRows"></tbody>
            </table>
        </div>

        <div class="section">
            <h3>Recent Completions</h3>
            <table>
                <thead><tr><th>File</th><th>Status</th></tr></thead>
                <tbody id="recentRows"></tbody>
            </table>
        </div>
    </div>

    <script>
        const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
        async function refresh() {
            try {
                const r = await fetch('/api/progress');
                const d = await r.json();

                document.getElementById('total').textContent = d.total_found || 0;
                document.getElementById('done').textContent = d.total_completed || 0;
                document.getElementById('skip').textContent = (d.skipped_files || []).length;
                document.getElementById('fail').textContent = d.total_failed || 0;

                const pct = d.total_found > 0 ? Math.round(((d.total_completed + (d.skipped_files||[]).length) / d.total_found) * 100) : 0;
                document.getElementById('bar').style.width = pct + '%';
                document.getElementById('time').textContent = new Date().toLocaleTimeString();

                // Recent completions (last 15)
                const recent = (d.completed_files || []).slice(-15).reverse();
                document.getElementById('recentRows').innerHTML = recent.map(f =>
                    `<tr><td>${esc(f)}</td><td class="status-ok">✓ done</td></tr>`
                ).join('');

                // Errors
                const errs = d.failed_files || [];
                if (errs.length > 0) {
                    document.getElementById('errorsSection').style.display = 'block';
                    const errResp = await fetch('/api/errors');
                    const errData = await errResp.json();
                    document.getElementById('errorRows').innerHTML = errData.slice(-10).reverse().map(e =>
                        `<tr><td>${esc(e.filename||'?')}</td><td class="status-fail">${esc(e.status||'?')}</td><td>${esc((e.error||'').substring(0,80))}</td></tr>`
                    ).join('');
                }
            } catch (e) { console.error(e); }
        }
        refresh();
        setInterval(refresh, 5000);
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(TEMPLATE)

def _read(name, default):
    path = os.path.join(app.config["OUTPUT_DIR"], name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


@app.route("/api/progress")
def api_progress():
    return jsonify(_read("progress.json", {}))


@app.route("/api/errors")
def api_errors():
    return jsonify(_read("errors.json", []))


app.config["OUTPUT_DIR"] = OUTPUT_DIR

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=OUTPUT_DIR)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5001)
    args = ap.parse_args()
    app.config["OUTPUT_DIR"] = args.output
    app.run(host=args.host, port=args.port)

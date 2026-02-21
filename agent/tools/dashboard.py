"""Real-time monitoring dashboard — SSE-streaming HTML UI.

Serves a single-page HTML dashboard showing:
- Current tick and mode
- State hash
- Telemetry counters
- Ledger height and chain status
- Evolution bounds status
- Recent actions

Uses Server-Sent Events (SSE) for live updates.
"""

import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dev-bot Dashboard</title>
<style>
  :root {
    --bg: #0a0a0f;
    --card: #12121a;
    --border: #1e1e2e;
    --accent: #6366f1;
    --green: #22c55e;
    --red: #ef4444;
    --yellow: #eab308;
    --text: #e2e8f0;
    --muted: #64748b;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 24px;
  }
  h1 {
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  h1 .dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    background: var(--green);
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
  }
  .card h3 {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
    margin-bottom: 12px;
  }
  .metric {
    font-size: 2rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .metric.green { color: var(--green); }
  .metric.red { color: var(--red); }
  .metric.yellow { color: var(--yellow); }
  .sub { font-size: 0.85rem; color: var(--muted); margin-top: 4px; }
  .log {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    max-height: 300px;
    overflow-y: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    line-height: 1.6;
  }
  .log-line { color: var(--muted); }
  .log-line.action { color: var(--accent); }
  .log-line.error { color: var(--red); }
</style>
</head>
<body>
<h1><span class="dot"></span> Dev-bot Control Kernel</h1>
<div class="grid">
  <div class="card">
    <h3>Tick</h3>
    <div class="metric" id="tick">0</div>
    <div class="sub" id="mode">mode: initializing</div>
  </div>
  <div class="card">
    <h3>State Hash</h3>
    <div class="metric" id="hash" style="font-size:0.9rem;word-break:break-all">—</div>
  </div>
  <div class="card">
    <h3>Ledger</h3>
    <div class="metric green" id="ledger">0</div>
    <div class="sub" id="chain">chain: —</div>
  </div>
  <div class="card">
    <h3>Executions</h3>
    <div class="metric" id="execs">0 / 0</div>
    <div class="sub">success / fail</div>
  </div>
  <div class="card">
    <h3>Gate Rejects</h3>
    <div class="metric yellow" id="rejects">0</div>
  </div>
  <div class="card">
    <h3>Rollbacks</h3>
    <div class="metric red" id="rollbacks">0</div>
  </div>
</div>
<h3 style="color:var(--muted);margin-bottom:12px;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.1em">Event Log</h3>
<div class="log" id="log"></div>

<script>
const es = new EventSource('/events');
const log = document.getElementById('log');

es.onmessage = function(e) {
  try {
    const d = JSON.parse(e.data);
    if (d.tick !== undefined) document.getElementById('tick').textContent = d.tick;
    if (d.mode) document.getElementById('mode').textContent = 'mode: ' + d.mode;
    if (d.state_hash) document.getElementById('hash').textContent = d.state_hash;
    if (d.ledger_height !== undefined) document.getElementById('ledger').textContent = d.ledger_height;
    if (d.chain_valid !== undefined) document.getElementById('chain').textContent = 'chain: ' + (d.chain_valid ? 'VALID' : 'BROKEN');
    if (d.exec_success !== undefined) document.getElementById('execs').textContent = d.exec_success + ' / ' + d.exec_fail;
    if (d.gate_rejects !== undefined) document.getElementById('rejects').textContent = d.gate_rejects;
    if (d.rollbacks !== undefined) document.getElementById('rollbacks').textContent = d.rollbacks;
    if (d.event) {
      const cls = d.event.includes('error') || d.event.includes('fail') ? 'error' :
                  d.event.includes('exec') || d.event.includes('action') ? 'action' : '';
      const el = document.createElement('div');
      el.className = 'log-line ' + cls;
      el.textContent = '[tick ' + (d.tick || '?') + '] ' + d.event + (d.detail ? ': ' + d.detail : '');
      log.prepend(el);
      while (log.children.length > 100) log.removeChild(log.lastChild);
    }
  } catch(err) {}
};
</script>
</body>
</html>"""


class DashboardState:
    """Shared dashboard state updated by the agent loop."""

    def __init__(self):
        self.data = {
            "tick": 0,
            "mode": "initializing",
            "state_hash": "",
            "ledger_height": 0,
            "chain_valid": True,
            "exec_success": 0,
            "exec_fail": 0,
            "gate_rejects": 0,
            "rollbacks": 0,
        }
        self._events = []
        self._lock = threading.Lock()

    def update(self, **kwargs):
        with self._lock:
            self.data.update(kwargs)

    def add_event(self, event, detail="", tick=0):
        with self._lock:
            self._events.append(
                {
                    "event": event,
                    "detail": detail,
                    "tick": tick,
                }
            )
            if len(self._events) > 200:
                self._events.pop(0)

    def snapshot(self):
        with self._lock:
            d = dict(self.data)
            if self._events:
                d.update(self._events[-1])
            return d


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for dashboard and SSE events."""

    dashboard_state = None

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())

        elif self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            try:
                while True:
                    data = self.__class__.dashboard_state.snapshot()
                    self.wfile.write(f"data: {json.dumps(data)}\n\n".encode())
                    self.wfile.flush()
                    time.sleep(1)
            except (BrokenPipeError, ConnectionResetError):
                pass

        else:
            self.send_response(404)
            self.end_headers()


def start_dashboard(state, port=8081):
    """Start the dashboard server in a background daemon thread.

    Args:
        state: DashboardState instance
        port: HTTP port

    Returns:
        (server, thread)
    """
    DashboardHandler.dashboard_state = state
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread

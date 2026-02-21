# Dev-botDeterministic Autonomous DevOps Agent

A bounded, auditable, self-improving autonomous agent for continuous system
maintenance.
Core properties
Non-bypassable policy gate — every action passes through before execution
kernel/gate.py
Append-only cryptographic ledger — SHA-256 hash-chained, tamper-evident
action log
Deterministic replay — any ledger can be replayed and verified offline
Online learning within envelopes — habit table updates success rates; auto-
rollback on failure
Multi-timescale scheduler — fast (0.5s) metric ingest, medium (5s) anomaly
scoring, slow (30s) LLM planning
Quick start

# Install dependencies

pip install pyyaml requests

# Run with stub LLM (no API key needed)

cd agent
python run.py

# Run with real Claude API

ANTHROPIC_API_KEY=sk-... python run.py --llm anthropic

# Run with local Ollama

python run.py --llm ollama

# Run all tests (in a separate shell while agent is running, or standalone)

python tests/replay_tests.py

# Verify ledger integrity

python -c "from kernel.ledger import Ledger; ok,n = Ledger.verify('ledger.jsonl'); print(f'{"
Architecture
kernel/
event_loop.py gate.py Main tick loop, exception isolation
Policy enforcement — NEVER bypassed
ledger.py Append-only SHA-256 chained log
watchdog.py Stall detection + rollback trigger
rollback.py Deep-copy snapshot stack
sparse/
anomaly.py EWMA anomaly detection (no ML deps)
habits.py Bayesian success-rate table
dense/
llm_iface.py Swappable LLM backend (stub / Anthropic / Ollama)
planner.py Token-budgeted proposal generator
patcher.py Plan text → structured action dict
memory/
hot_cache.py Bounded FIFO recent-context buffer
vector_store.py Cosine similarity retrieval (bag-of-words)
episodic_ledger.py Queryable (ctx, action, outcome) history
archive.py gzip-compressed cold snapshots
tools/
shell.py Gated subprocess execution
git.py ci.py metrics.py Git read/write operations (writes need approval)
Test runner (stub; swap for pytest/cargo/etc.)
Metric reader (stub; swap for Prometheus/Datadog)
scheduler/
clocks.py Three-tier due-time tracker
budgets.py Token + call rate limiter (refills per minute)
config/
policy.yaml budgets.yaml Tool allowlist + risk thresholds
Rate limits + timescale config
Timescales
Tier Interval Work
Fast 0.5 s
Metric ingest, hot cache update
Medium 5 s Anomaly scoring, candidate selection
Slow 30 s LLM planning, gated execution, archiving
Extending
Real LLM — set --llm anthropic and export ANTHROPIC_API_KEY.
Real metrics — replace Datadog query.
tools/metrics.py::read() with a Prometheus scrape or
Real CI — replace tools/ci.py::run_tests() with pytest , cargo test , etc.
Real tool execution — replace the _execute() stub in run.py with actual systemctl ,
kubectl , or docker calls.
Vector DB — swap memory/vector_store.py compatible .add() / .search() API.
for Chroma, Qdrant, or Weaviate with a
Adding a new tool

1. Add an entry to config/policy.yaml with max_risk and requires_approval.
2. Add the tool keyword to ACTION_REGISTRY in dense/patcher.py.
3. Implement the tool function in tools/.
4. Dispatch it in the _execute() function in run.py.
The gate automatically enforces the new policy rule — no other changes required.
Ledger format
Each line is a JSON object:
{
}
"hash": "<sha256>",
"prev": "<prev_hash>",
"rec": { "event": "...", "ts": 1234567890.0, ... }
Verify with:
from kernel.ledger import Ledger
ok, n = Ledger.verify("ledger.jsonl")

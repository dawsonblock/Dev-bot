import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from kernel.ledger import Ledger

if __name__ == "__main__":
    ledger_path = sys.argv[1] if len(sys.argv) > 1 else "ledger.jsonl"
    if not os.path.exists(ledger_path):
        print("No ledger found. Run the agent first.")
    else:
        ok, n = Ledger.verify(ledger_path)
        if ok:
            print(f"REPLAY OK: {n} actions cryptographically verified.")
        else:
            print(f"REPLAY FAILED at record {n}.")

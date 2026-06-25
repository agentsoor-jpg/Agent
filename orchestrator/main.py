"""Legacy entry point wrapper. Delegates execution directly to orchestrator.app."""
import sys
import os

# Append project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if __name__ == "__main__":
    from orchestrator.app import app
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

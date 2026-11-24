"""Lance le backend FastAPI + le frontend React et ouvre l'interface dans le navigateur."""
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"


def wait_for(url: str, timeout: float = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def main():
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=ROOT,
    )
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=ROOT / "interface",
        shell=True,
    )

    print("Backend FastAPI starting on", BACKEND_URL)
    print("Frontend Vite starting on", FRONTEND_URL)

    if not wait_for(f"{BACKEND_URL}/health"):
        print("ERROR: backend did not start in time")
    if not wait_for(FRONTEND_URL):
        print("ERROR: frontend did not start in time")

    webbrowser.open(FRONTEND_URL)
    print("Interface opened in your browser. Press Ctrl+C to stop everything.")

    try:
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for proc in (backend, frontend):
            try:
                proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()

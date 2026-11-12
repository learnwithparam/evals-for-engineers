"""uv run review <step-name>: a keyboard-fast review app for the traces in that step's problem folder.

Keys: 1 pass, 2 fail, d defer, left and right arrows to move. It saves marks.csv on every key, and
notes.csv when the folder has one (the note-the-failures step).
"""

import csv
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import leases, paths

PAGE = Path(__file__).with_name("page.html")


def step_dir(name: str) -> Path:
    for d in sorted((paths.ROOT / "parts").glob(f"*/*-{name}/problem")):
        return d
    raise SystemExit(f"There is no step called {name}. Try: uv run review mark-the-traces")


def read_csv(p: Path) -> dict:
    if not p.exists():
        return {}
    return {r["trace_id"]: r for r in csv.DictReader(open(p))}


def write_csv(p: Path, field: str, values: dict) -> None:
    with open(p, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["trace_id", field])
        for k, v in values.items():
            if v:
                w.writerow([k, v])


class App:
    def __init__(self, folder: Path):
        self.folder = folder
        self.traces = paths.read_jsonl(folder / "sample.jsonl")
        self.notes_mode = (folder / "notes.csv").exists()
        self.marks = {k: v["mark"] for k, v in read_csv(folder / "marks.csv").items()}
        self.notes = {k: v["note"] for k, v in read_csv(folder / "notes.csv").items()}
        if self.notes_mode:  # in the notes step, review only the failed traces
            self.traces = [t for t in self.traces if self.marks.get(t["trace_id"]) == "fail"]

    def state(self) -> dict:
        items = []
        for t in self.traces:
            items.append(
                {
                    "trace": t,
                    "lease": leases.text(t["lease_id"]),
                    "mark": self.marks.get(t["trace_id"], ""),
                    "note": self.notes.get(t["trace_id"], ""),
                }
            )
        return {
            "folder": str(self.folder.relative_to(paths.ROOT)),
            "notes_mode": self.notes_mode,
            "items": items,
        }

    def save(self, body: dict) -> dict:
        tid = body["trace_id"]
        if "mark" in body and not self.notes_mode:
            self.marks[tid] = body["mark"]
            ordered = {t["trace_id"]: self.marks.get(t["trace_id"], "") for t in self.traces}
            write_csv(self.folder / "marks.csv", "mark", ordered)
        if "note" in body and self.notes_mode:
            self.notes[tid] = body["note"].strip()
            write_csv(
                self.folder / "notes.csv",
                "note",
                {t["trace_id"]: self.notes.get(t["trace_id"], "") for t in self.traces},
            )
        return {"ok": True}


def main() -> int:
    if len(sys.argv) < 2:
        print("Use: uv run review mark-the-traces   (or note-the-failures)")
        return 1
    app = App(step_dir(sys.argv[1]))
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, kind="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/api/state":
                return self._send(200, app.state())
            return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            return self._send(200, app.save(json.loads(self.rfile.read(n) or b"{}")))

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(
        f"Review app for {app.folder.relative_to(paths.ROOT)}: http://127.0.0.1:{port}  (Ctrl+C to stop)"
    )
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

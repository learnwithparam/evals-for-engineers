"""uv run review <step-name>: a keyboard-fast review app for the traces in a step's problem folder.

Keys: 1 pass, 2 fail, d defer, left and right arrows to move. It saves marks.csv on every key, and
notes.csv when the folder has one (the note-the-failures step).
"""

import contextlib
import csv
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import leases, paths

PAGE = Path(__file__).with_name("page.html")


def step_dir(name: str) -> Path:
    for folder in sorted((paths.ROOT / "parts").glob(f"*/*-{name}/problem")):
        return folder
    raise SystemExit(f"There is no step called {name}. Try: uv run review mark-the-traces")


def read_csv(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as file:
        return {row["trace_id"]: row for row in csv.DictReader(file)}


def write_csv(path: Path, field: str, values: dict) -> None:
    with open(path, "w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["trace_id", field])
        for trace_id, value in values.items():
            if value:
                writer.writerow([trace_id, value])


class App:
    def __init__(self, folder: Path):
        self.folder = folder
        self.traces = paths.read_jsonl(folder / "sample.jsonl")
        self.notes_mode = (folder / "notes.csv").exists()
        marks = read_csv(folder / "marks.csv")
        notes = read_csv(folder / "notes.csv")
        self.marks = {trace_id: row["mark"] for trace_id, row in marks.items()}
        self.notes = {trace_id: row["note"] for trace_id, row in notes.items()}
        if self.notes_mode:  # in the notes step, review only the failed traces
            self.traces = [
                trace for trace in self.traces if self.marks.get(trace["trace_id"]) == "fail"
            ]

    def state(self) -> dict:
        items = []
        for trace in self.traces:
            items.append(
                {
                    "trace": trace,
                    "lease": leases.text(trace["lease_id"]),
                    "mark": self.marks.get(trace["trace_id"], ""),
                    "note": self.notes.get(trace["trace_id"], ""),
                }
            )
        return {
            "folder": str(self.folder.relative_to(paths.ROOT)),
            "notes_mode": self.notes_mode,
            "items": items,
        }

    def _in_trace_order(self, saved: dict) -> dict:
        return {trace["trace_id"]: saved.get(trace["trace_id"], "") for trace in self.traces}

    def save(self, body: dict) -> dict:
        trace_id = body["trace_id"]
        if "mark" in body and not self.notes_mode:
            self.marks[trace_id] = body["mark"]
            write_csv(self.folder / "marks.csv", "mark", self._in_trace_order(self.marks))
        if "note" in body and self.notes_mode:
            self.notes[trace_id] = body["note"].strip()
            write_csv(self.folder / "notes.csv", "note", self._in_trace_order(self.notes))
        return {"ok": True}


class ReviewHandler(BaseHTTPRequestHandler):
    """Serves the page, the review state as JSON, and saves each mark or note posted to it."""

    app: App

    def log_message(self, *_details):
        """Stay quiet: the terminal shows only the address of the app."""

    def _send(self, status: int, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/state":
            return self._send(200, self.app.state())
        return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) or b"{}"
        return self._send(200, self.app.save(json.loads(body)))


def main() -> int:
    if len(sys.argv) < 2:
        print("Use: uv run review mark-the-traces   (or note-the-failures)")
        return 1
    app = App(step_dir(sys.argv[1]))
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
    ReviewHandler.app = app
    server = ThreadingHTTPServer(("127.0.0.1", port), ReviewHandler)
    print(
        f"Review app for {app.folder.relative_to(paths.ROOT)}: "
        f"http://127.0.0.1:{port}  (Ctrl+C to stop)"
    )
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())

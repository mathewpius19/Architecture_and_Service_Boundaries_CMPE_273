"""Inventory service for the online-store assignment."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from urllib.parse import parse_qs, urlparse


INVENTORY = {
    "keyboard": 10,
    "mouse": 0,
    "monitor": 3,
}


class InventoryHandler(BaseHTTPRequestHandler):
    def _send_json(self, status, body):
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["inventory", "items"] and parts[2]:
            item_id = parts[2]
            try:
                quantity = int(parse_qs(parsed.query).get("quantity", ["1"])[0])
            except ValueError:
                self._send_json(400, {"error": "quantity must be an integer"})
                return
            if quantity < 1:
                self._send_json(400, {"error": "quantity must be at least 1"})
                return
            available_units = INVENTORY.get(item_id, 0)
            self._send_json(200, {
                "item_id": item_id,
                "requested_quantity": quantity,
                "available": available_units >= quantity,
            })
            return
        if parsed.path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        self._send_json(404, {"error": "not found"})

    def log_message(self, format, *args):
        print(f"[inventory] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    port = int(os.getenv("INVENTORY_PORT", "8001"))
    server = ThreadingHTTPServer(("127.0.0.1", port), InventoryHandler)
    print(f"Inventory service listening on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()

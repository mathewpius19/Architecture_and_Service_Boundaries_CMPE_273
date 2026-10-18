"""Order service that queries the independent inventory service."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import urllib.error
import urllib.request
import uuid


INVENTORY_URL = os.getenv("INVENTORY_URL", "http://127.0.0.1:8001")
ORDERS = []


class OrderHandler(BaseHTTPRequestHandler):
    def _send_json(self, status, body):
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _inventory_available(self, item_id, quantity):
        url = f"{INVENTORY_URL}/inventory/items/{item_id}?quantity={quantity}"
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            print(f"[order] inventory dependency failed: {error}", flush=True)
            return None

    def do_POST(self):
        if self.path != "/orders":
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            item_id = payload["item_id"]
            quantity = int(payload["quantity"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            self._send_json(400, {"error": "body must contain item_id and integer quantity"})
            return
        if not isinstance(item_id, str) or not item_id or quantity < 1:
            self._send_json(400, {"error": "item_id is required and quantity must be at least 1"})
            return

        inventory_result = self._inventory_available(item_id, quantity)
        if inventory_result is None:
            self._send_json(503, {"error": "inventory service unavailable", "retryable": True})
            return
        if not inventory_result.get("available", False):
            self._send_json(409, {
                "error": "item unavailable",
                "item_id": item_id,
                "requested_quantity": quantity,
            })
            return

        order = {"order_id": str(uuid.uuid4()), "item_id": item_id, "quantity": quantity, "status": "created"}
        ORDERS.append(order)
        # In a fuller system this state change would publish OrderCreated.
        self._send_json(201, order)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        self._send_json(404, {"error": "not found"})

    def log_message(self, format, *args):
        print(f"[order] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    port = int(os.getenv("ORDER_PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), OrderHandler)
    print(f"Order service listening on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()

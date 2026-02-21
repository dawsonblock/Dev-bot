"""Network RPC transport for Dev-bot consensus cluster.

Provides HTTP server and client for Raft consensus RPCs:
- /heartbeat
- /request_vote
- /append_entries
"""

import json
import threading
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer


class RPCHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data)

        path = self.path
        response = {}

        # Access the node and consensus engines attached to the server
        node = self.server.node
        consensus = self.server.consensus

        try:
            if path == "/heartbeat":
                node.heartbeat_received(payload["node_id"])
                response = {"status": "ok"}

            elif path == "/request_vote":
                term, granted = consensus.request_vote(
                    payload["candidate_id"],
                    payload["term"],
                    payload["last_log_index"],
                    payload["last_log_term"],
                )
                response = {"term": term, "vote_granted": granted}

            elif path == "/append_entries":
                term, success = consensus.append_entries(
                    payload["leader_id"],
                    payload["term"],
                    payload["prev_log_index"],
                    payload["prev_log_term"],
                    payload["entries"],
                    payload["leader_commit"],
                )
                response = {"term": term, "success": success}
            else:
                self.send_error(404, "Unknown RPC route")
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            self.send_error(500, str(e))

    def log_message(self, format, *args):
        # Suppress default HTTP logging
        pass


class RPCServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, node, consensus):
        super().__init__(server_address, RequestHandlerClass)
        self.node = node
        self.consensus = consensus


def start_rpc_server(port, node, consensus):
    """Start the RPC server in a background thread.

    Returns the server instance so it can be shut down if needed.
    """
    server = RPCServer(("", port), RPCHandler, node, consensus)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def rpc_call(addr, endpoint, payload, timeout=0.5):
    """Send an RPC call to a peer.

    Returns:
        dict if successful, None if timeout or connection error.
    """
    url = f"http://{addr}{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_data = response.read()
            if not res_data:
                return {}
            return json.loads(res_data)
    except Exception:
        return None

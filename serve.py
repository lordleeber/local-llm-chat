#!/usr/bin/env python3
"""Serve the chat page locally, optionally proxying /v1 to the LLM server.

Only needs the Python standard library.

    python serve.py                 # page at http://localhost:8000
    python serve.py --proxy         # also forward /v1/* to the Mac (avoids browser CORS issues)
    python serve.py --proxy --target http://100.103.191.79:8080 --port 8000
"""
import argparse
import http.client
import http.server
import os
import urllib.parse
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TARGET = "http://100.103.191.79:8080"
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


def make_handler(target, proxy):
    t = urllib.parse.urlsplit(target)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=HERE, **kwargs)

        def _is_api(self):
            return proxy and (self.path.startswith("/v1/") or self.path == "/health")

        def do_GET(self):
            if self._is_api():
                return self._forward()
            return super().do_GET()

        def do_POST(self):
            if self._is_api():
                return self._forward()
            self.send_error(404)

        def _forward(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
            conn_cls = http.client.HTTPSConnection if t.scheme == "https" else http.client.HTTPConnection
            # Long timeout: the first request after a server restart loads the model (~30s).
            conn = conn_cls(t.hostname, t.port, timeout=600)
            try:
                conn.request(self.command, t.path.rstrip("/") + self.path, body=body, headers=headers)
                resp = conn.getresponse()
            except (OSError, http.client.HTTPException) as e:
                # Detail goes in the body: the status line must be Latin-1, and Windows socket errors are localized.
                self.send_error(502, "Bad Gateway", f"Cannot reach {target}: {e}")
                return
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() not in HOP_BY_HOP:
                    self.send_header(k, v)
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                # Relay as it arrives so streaming (SSE) stays live.
                while True:
                    chunk = resp.read1(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (OSError, http.client.HTTPException):
                pass  # browser pressed stop (ConnectionAbortedError on Windows), or upstream stalled/broke
            finally:
                conn.close()
                self.close_connection = True

        def log_message(self, fmt, *args):
            pass

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--proxy", action="store_true", help="forward /v1/* to --target")
    ap.add_argument("--target", default=DEFAULT_TARGET, help=f"LLM server (default {DEFAULT_TARGET})")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.target, args.proxy))
    url = f"http://localhost:{args.port}/" + ("?proxy=1" if args.proxy else "")
    print(f"Chat page: {url}")
    if args.proxy:
        print(f"Proxying /v1 -> {args.target}")
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

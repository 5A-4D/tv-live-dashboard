#!/usr/bin/env python3
"""Serve only dashboard demo/static assets on loopback, never build or private state."""
import argparse
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class DemoHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_head(self):
        target = (ROOT / unquote(urlsplit(self.path).path).lstrip('/')).resolve()
        allowed = any(target.is_relative_to(ROOT / name) for name in ['demo', 'web'])
        if not allowed:
            self.send_error(403, 'Only demo and web assets are served')
            return None
        if target.is_file() and target.suffix not in {'.html', '.js', '.css', '.png', '.jpg', '.svg', '.txt'}:
            self.send_error(403, 'This file type is not served')
            return None
        if target.is_dir() and not (target / 'index.html').is_file():
            self.send_error(403, 'Directory listing is disabled')
            return None
        return super().send_head()


@contextmanager
def demo_server(port=0):
    server = ThreadingHTTPServer(('127.0.0.1', port), partial(DemoHandler, directory=str(ROOT)))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    try:
        with demo_server(args.port) as origin:
            print(origin + '/demo/', flush=True)
            threading.Event().wait()
    except KeyboardInterrupt:
        pass

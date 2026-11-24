"""Serve the local FPL research app. Uses the Python standard library."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import threading
from urllib.parse import urlparse

from snapshot import ROOT, VERSION
from search_tools import ResearchTools


def evidence_for(filename):
    if not re.fullmatch(r'\d{8}-\d{6}-[0-9a-f]{32}\.json', filename):
        raise ValueError('Invalid trace filename')
    trace = json.loads((ROOT / f'results/search_agent/{VERSION}/traces' / filename).read_text(encoding='utf-8'))
    steps = []
    for step in trace.get('steps', []):
        models = []
        for line in step.get('stdout', '').splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get('type') == 'session.auto_mode_resolved':
                models.append(event['data']['chosenModel'])
        steps.append({key: value for key, value in {
            'models': models, 'action': step.get('action'),
            'observation': step.get('observation'),
            'validation_error': step.get('validation_error')}.items() if value})
    return {'prototype_version':VERSION,'trace':filename,'snapshot':trace.get('snapshot'),'periods':trace.get('periods_used',[]),'steps':steps}


def make_handler(snapshot, port, search=None):
    if search is None:
        from run_search_agent import run_search
        search = run_search
    web = Path(__file__).with_name('web')
    routes = {'/': ('index.html', 'text/html'), '/styles.css': ('styles.css', 'text/css'),
              '/app.js': ('app.js', 'text/javascript')}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, value, kind='application/json'):
            body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', kind + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/api/snapshot':
                self.send(200, snapshot)
            elif path in routes:
                filename, kind = routes[path]
                self.send(200, (web / filename).read_bytes(), kind)
            elif path == '/favicon.ico':
                self.send_response(204)
                self.end_headers()
            else:
                self.send(404, {'error': 'Page not found'})

        def do_POST(self):
            if self.path != '/api/search':
                self.send(404, {'error': 'Page not found'})
                return
            if (self.headers.get('Origin') != f'http://127.0.0.1:{port}' or
                    self.headers.get('Host') != f'127.0.0.1:{port}'):
                self.send(403, {'error': 'Open the app using its local address'})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 10000:
                    raise ValueError('Request too large or empty')
                question = json.loads(self.rfile.read(size)).get('question')
                if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
                    raise ValueError('Enter a question between 1 and 2000 characters')
            except (ValueError, AttributeError, UnicodeError) as exc:
                self.send(400, {'error': str(exc)})
                return
            if not lock.acquire(blocking=False):
                self.send(429, {'error': 'A search is already running. Please wait for it to finish.'})
                return
            try:
                result = search(question)
                if not snapshot.get('recorded_demo'):
                    result['evidence'] = evidence_for(result['trace'])
                self.send(200, result)
            except Exception as exc:
                self.send(502, {'error': str(exc)})
            finally:
                lock.release()
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='replay the recorded example without a CSV or Copilot')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--check', action='store_true', help='check data and assets without serving')
    args = parser.parse_args()
    search = None
    if args.demo:
        from recorded_demo import load_demo
        snapshot, search = load_demo()
    else:
        tools = ResearchTools()
        snapshot = tools.describe_snapshot()
    for filename in ('index.html', 'styles.css', 'app.js'):
        if not Path(__file__).with_name('web').joinpath(filename).is_file():
            raise ValueError(f'Missing frontend asset: {filename}')
    if args.check:
        print('[PASS] Recorded example and frontend assets verified' if args.demo else '[PASS] Research snapshot, source fingerprints and frontend assets verified')
        return
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(snapshot, args.port, search))
    print(f'Open http://127.0.0.1:{args.port} — Ctrl+C stops the app', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

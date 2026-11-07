"""提供招聘资料接口和工作台静态资源。"""
import json
import logging
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from src.repository import load_candidates
from src.service import analyze_batch

ROOT = Path(__file__).resolve().parents[1]
MAX_REQUEST_BYTES = 29 * 1024 * 1024
MIME = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
        '.js': 'text/javascript; charset=utf-8',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type='application/json; charset=utf-8'):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == '/api/health':
            try:
                count = len(load_candidates())
                self.respond(200, {'status': 'connected', 'message': '数据服务已连接',
                                   'detail': f'Python 服务正常，已加载 {count} 份候选人画像'})
            except (OSError, ValueError, KeyError, TypeError):
                logging.exception('候选人数据读取失败')
                self.respond(503, {'detail': '候选人数据读取失败，请检查 data/candidates.json'})
            return
        if path == '/':
            self.send_response(302)
            self.send_header('Location', '/ui/')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if path in ('/ui', '/ui/'):
            path = '/ui/index.html'
        if path.startswith('/ui/'):
            base, relative = ROOT / 'frontend', path[len('/ui/'):]
        else:
            self.respond(404, {'detail': '页面或接口不存在'})
            return
        target = (base / relative).resolve()
        if not target.is_relative_to(base.resolve()) or not target.is_file() or target.suffix not in MIME:
            self.respond(404, {'detail': '文件不存在'})
            return
        self.respond(200, target.read_bytes(), MIME[target.suffix])

    def do_POST(self):
        if urlsplit(self.path).path != '/api/analyze/batch':
            self.respond(404, {'detail': '接口不存在'})
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.respond(415, {'detail': '请求必须使用 application/json'})
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_REQUEST_BYTES:
                self.respond(413, {'detail': '请求为空或超过 29 MB 限制'})
                return
            self.connection.settimeout(20)
            payload = json.loads(self.rfile.read(size))
        except (ValueError, OSError):
            self.respond(400, {'detail': '请求内容无法读取，请检查 JSON 格式'})
            return
        try:
            self.respond(200, analyze_batch(payload))
        except ValueError as exc:
            self.respond(400, {'detail': str(exc)})
        except Exception:
            logging.exception('简历处理失败')
            self.respond(500, {'detail': '数据处理失败，请检查后台日志和候选人 JSON 文件'})

    def log_message(self, format, *args):
        logging.info('%s - %s', self.client_address[0], format % args)


def run(host, port, open_browser=False):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    server = ThreadingHTTPServer((host, port), Handler)
    browser_host = '127.0.0.1' if host == '0.0.0.0' else host
    url = f'http://{browser_host}:{server.server_port}/ui/'
    logging.info('TalentScope: %s', url)
    if open_browser:
        try:
            webbrowser.open(url)
        except webbrowser.Error:
            logging.warning('浏览器未能自动打开，请访问 %s', url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

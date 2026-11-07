"""运行方式：uv run --locked python app.py。"""
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv
from src.server import run


def port_number(value):
    try:
        port = int(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError('端口应为 1 到 65535 的整数') from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError('端口应为 1 到 65535 的整数')
    return port


if __name__ == '__main__':
    load_dotenv(Path(__file__).resolve().parent / '.env', override=False)
    parser = argparse.ArgumentParser(description='TalentScope 招聘工作台')
    parser.add_argument('--host', default=os.getenv('HR_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=port_number, default=os.getenv('HR_PORT', '8808'))
    parser.add_argument('--open', action=argparse.BooleanOptionalAction, default=False,
                        help='启动后打开浏览器，--no-open 可关闭自动打开')
    args = parser.parse_args()
    try:
        run(args.host, args.port, open_browser=args.open)
    except OSError as exc:
        parser.exit(1, f'启动失败：{exc}\n可使用 --port 8809 更换端口。\n')

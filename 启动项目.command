#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
if ! command -v uv >/dev/null 2>&1; then
    if [ -x "$HOME/.local/bin/uv" ]; then
        export PATH="$HOME/.local/bin:$PATH"
    else
        printf '%s\n' '未找到 uv，请安装后重新打开：' 'https://docs.astral.sh/uv/getting-started/installation/'
        if [ -t 0 ]; then read -r -p '按回车关闭窗口。'; fi
        exit 1
    fi
fi
uv run --locked python app.py --open "$@"
launch_result=$?
if [ "$launch_result" -ne 0 ] && [ -t 0 ]; then
    read -r -p '启动未完成，请查看上方提示。按回车关闭窗口。'
fi
exit "$launch_result"

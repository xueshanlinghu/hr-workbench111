# TalentScope 招聘工作台

集中上传简历，整理候选人资料，查看六项能力画像。HR 与用人部门可以在同一页面搜索、比较和复核候选人信息。

## 运行环境

- Windows 或 macOS。
- Python 3.13，由 uv 按项目中的 `.python-version` 选择。
- uv 安装说明：<https://docs.astral.sh/uv/getting-started/installation/>。

## 启动

打开项目文件夹。首次运行时，uv 会联网准备 Python 和项目依赖。在项目目录打开终端，执行：

```text
uv sync --locked
uv run --locked python app.py
```

`uv sync --locked` 按锁文件创建本机环境并安装依赖；`uv run` 使用项目环境启动服务。

浏览器打开 <http://127.0.0.1:8808/ui/>。停止服务时，在运行终端按 `Ctrl+C`。

也可以使用项目根目录的快捷入口：

- Windows：双击 `启动项目.cmd`。
- macOS：双击 `启动项目.command`，也可在终端运行 `bash 启动项目.command`。需要设置执行权限时，运行 `chmod +x 启动项目.command`。

快捷入口同样调用 uv，并在服务启动后打开浏览器。Windows 和 macOS 使用相同的终端启动命令，由 uv 在各自电脑上建立项目环境。

## 使用

1. 选择 `candidate_records` 中的 Word 简历，也可以直接把文件拖入上传区。
2. 点击“开始批量审核”，查看候选人列表与筛选状态。
3. 点击候选人，查看右侧能力画像、技能和摘要。
4. 使用姓名、技能或学历搜索，按筛选状态查看对应记录。
5. 点击“清空结果”重置已识别的候选人、画像和统计，开始下一轮处理。上传队列及项目中的原始简历和档案继续保留。

同一份内容重复上传会合并到已有记录。文件在内存中处理，本批结果保存在当前页面会话中，候选人档案保存在项目目录中。

## 配置

默认监听本机 `127.0.0.1:8808`。

需要调整时，把 `.env.example` 复制为 `.env`，修改其中的 `HR_HOST` 或 `HR_PORT`，然后重启服务。程序会读取项目根目录的 `.env`。显式命令行参数优先，其次是系统环境变量，再次是 `.env` 和默认值。

指定其他运行端口，例如：

```text
uv run --locked python app.py --port 8809
```

随后打开 <http://127.0.0.1:8809/ui/>。共享配置结构时提交 `.env.example`；真实 `.env` 留在本机。

## 文件与数据

支持 Word（`.docx`）和文本 PDF。每批支持 1—20 份简历，单份文件大小上限为 10 MiB，单批合计上限为 20 MiB；PDF 页数上限为 50 页。

候选人画像与筛选结论读取自 `data/candidates.json`，按简历内容关联已有档案。新简历提取明确标注的基础信息，并进入人工复核流程。更新候选人经历时，同步维护对应的档案与评价记录。

## 项目结构

```text
app.py                  启动入口与运行配置
src/server.py           HTTP 接口与静态资源
src/resume_reader.py    简历文件读取
src/service.py          基础字段、画像关联与批次处理
src/repository.py       候选人档案读取与校验
frontend/               工作台页面与交互
candidate_records/      Word 简历
data/candidates.json    候选人资料与画像
tests/                  功能与接口检查
```

## 检查

在项目根目录执行：

```text
uv run --locked python -m unittest discover -s tests -v
```

该命令验证文件读取、画像关联、批次处理和接口行为。随后在浏览器上传文件，核对候选人切换、搜索筛选和雷达图显示。

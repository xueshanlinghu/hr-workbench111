"""把 Word 和 PDF 统一转换为文本；后续业务层不关心文件格式。"""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.table import Table
from pypdf import PdfReader

SUPPORTED_SUFFIXES = {'.docx', '.pdf'}
MAX_FILE_BYTES = 10 * 1024 * 1024


def normalize_text(text):
    return text.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n').strip()


def read_word(raw):
    # 先限制解压大小；docx 本身是 ZIP 包，不必解压到磁盘。
    with ZipFile(BytesIO(raw)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 50 * 1024 * 1024:
            raise ValueError('Word 文档内容过大，请精简附件或图片后上传')
    document = Document(BytesIO(raw))
    lines = []
    for block in document.iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                cells = []
                seen = set()
                for cell in row.cells:
                    # 合并单元格可能在同一行重复出现。
                    if cell._tc not in seen:
                        seen.add(cell._tc)
                        cells.append(cell.text.strip())
                # 两列“字段/值”保持同行，便于后续字段解析。
                if len(cells) == 2 and cells[0].rstrip('：:') in ('姓名', 'Name', '邮箱', '手机号', '学历', '教育背景', '工作经验', '核心技能', '技能'):
                    lines.append(cells[0].rstrip('：:') + '：' + cells[1])
                else:
                    lines.append('\n'.join(cells))
        else:
            lines.append(block.text)
    return '\n'.join(lines)


def read_pdf(raw):
    reader = PdfReader(BytesIO(raw))
    if reader.is_encrypted:
        raise ValueError('PDF 已加密，请解除密码保护后上传')
    if len(reader.pages) > 50:
        raise ValueError('PDF 超过 50 页，请上传简历正文')
    lines = []
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ''
        if not text.strip():
            raise ValueError(f'PDF 第 {number} 页未读取到文字，可能是扫描件或图片页；请先进行 OCR 文字识别，或上传 Word 版本')
        lines.append(text)
    return '\n'.join(lines)


def read_resume(filename, raw):
    suffix = Path(filename).suffix.lower() if isinstance(filename, str) else ''
    if suffix == '.doc':
        raise ValueError('旧版 .doc 请先用 Word 或 WPS 另存为 .docx 或 PDF 后上传')
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError('请上传 Word（.docx）或 PDF 简历')
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError('单份简历不能超过 10 MB')
    if not raw:
        raise ValueError('简历文件为空')
    try:
        if suffix == '.docx':
            text = read_word(raw)
        elif suffix == '.pdf':
            if not raw.startswith(b'%PDF-'):
                raise ValueError('文件不是有效 PDF，请勿仅修改扩展名')
            text = read_pdf(raw)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('文件无法解析，可能已损坏或格式不正确；请重新另存后上传') from exc
    text = normalize_text(text)
    if not text:
        raise ValueError('未读取到简历文字；图片简历请先进行 OCR 文字识别')
    if any(ord(c) < 32 and c not in '\n\t' for c in text):
        raise ValueError('文件包含无法识别的文本，请重新另存后上传')
    return text

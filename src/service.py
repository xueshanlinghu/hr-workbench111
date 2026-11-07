"""解析简历基础信息，关联候选人档案并处理上传批次。"""
import base64
import copy
import hashlib
import re

from src.repository import find_by_digest, load_candidates
from src.resume_reader import read_resume, MAX_FILE_BYTES

MAX_FILES = 20
MAX_BATCH_BYTES = 20 * 1024 * 1024


def extract_basic_fields(text):
    """只提取有明确标签或格式的字段，不推断能力、不生成评价。"""
    def field(label):
        match = re.search(r'^[^\S\r\n]*' + label + r'[^\S\r\n]*[:：][^\S\r\n]*([^\r\n]*)', text, re.M | re.I)
        return match.group(1).strip() if match else ''

    email = re.search(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', text)
    phone = re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', text)
    years = re.search(r'工作经验\s*[:：]\s*(\d+)\s*年', text)
    skills = field('(?:核心技能|技能)')
    return {
        'candidate_name': field('(?:姓名|Name)') or '待核实姓名',
        'candidate_email': email.group() if email else '',
        'parsed_features': {
            'candidate_phone': phone.group() if phone else '',
            'education': field('(?:教育背景|学历)'),
            'years_experience': int(years.group(1)) if years else None,
            'skills': [s.strip().rstrip('。') for s in re.split(r'[、,，;；]', skills) if s.strip()],
        },
    }


def analyze_resume(filename, raw, records):
    text = read_resume(filename, raw)
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    # Word/PDF 排版会引入空白和换行；仅忽略空白，不能按姓名借用画像。
    compact_digest = hashlib.sha256(re.sub(r'\s+', '', text).encode('utf-8')).hexdigest()
    record = find_by_digest(records, digest) or next(
        (r for r in records if r.get('text_sha256') == compact_digest), None)
    if record:
        result = copy.deepcopy(record)
        scores = result['profile_score']['radar'].values()
        result['profile_score']['fit'] = round(sum(scores) / 600, 4)
        result['data_source'] = 'json_profile'
    else:
        result = extract_basic_fields(text)
        result.update({
            'profile_score': {'fit': None, 'radar': None},
            'is_qualified': None,
            'evaluation_report': '已提取基本资料，尚未建立六项能力画像。请核实经历并补充评估记录。',
            'data_source': 'basic_fields',
        })
    result['thread_id'] = 'resume-' + compact_digest[:24]
    result['filename'] = filename
    result['needs_review'] = result['is_qualified'] is None
    return result


def analyze_batch(payload):
    files = payload.get('files') if isinstance(payload, dict) else None
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise ValueError(f'请选择 1 到 {MAX_FILES} 份简历')
    records = load_candidates()
    candidates, failures, seen = [], [], set()
    duplicates = 0
    total_bytes = 0
    for index, item in enumerate(files):
        filename = item.get('filename', '') if isinstance(item, dict) else ''
        try:
            if not isinstance(filename, str) or not filename.strip():
                filename = ''
                raise ValueError('请提供有效的文件名')
            if not isinstance(item, dict) or not isinstance(item.get('content_base64'), str):
                raise ValueError('文件数据格式不正确')
            raw = base64.b64decode(item['content_base64'], validate=True)
            total_bytes += len(raw)
            if total_bytes > MAX_BATCH_BYTES:
                raise ValueError('单批文件总大小不能超过 20 MB，请分批上传')
            candidate = analyze_resume(filename, raw, records)
            if candidate['thread_id'] in seen:
                duplicates += 1
                continue
            seen.add(candidate['thread_id'])
            candidates.append(candidate)
        except (ValueError, TypeError) as exc:
            failures.append({'index': index, 'filename': filename, 'error': str(exc)})
    return {'candidates': candidates, 'failures': failures, 'duplicates': duplicates}

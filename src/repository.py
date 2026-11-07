"""读取并校验候选人档案。"""
import json
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[1] / 'data' / 'candidates.json'
RADAR_KEYS = (
    'business_understanding', 'solution_judgment', 'engineering_integration',
    'evaluation_troubleshooting', 'communication_collaboration', 'delivery_reuse',
)


def load_candidates(path=DATA_FILE):
    """每次请求重新读取文件，修改数据后无需重启服务。"""
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError('候选人数据必须是 JSON 对象')
    records = data.get('candidates')
    if not isinstance(records, list):
        raise ValueError('candidates 必须是数组')
    for record in records:
        if not isinstance(record, dict):
            raise ValueError('候选人档案必须是对象')
        for key in ('candidate_name', 'candidate_email', 'evaluation_report', 'content_sha256'):
            if not isinstance(record.get(key), str):
                raise ValueError(f'档案字段 {key} 缺失或不是文本')
        if not record['candidate_name'].strip():
            raise ValueError('候选人姓名不能为空')
        profile = record.get('profile_score')
        radar = profile.get('radar') if isinstance(profile, dict) else None
        if not isinstance(radar, dict) or set(radar) != set(RADAR_KEYS):
            raise ValueError('画像需要完整的六个能力字段')
        if any(type(v) not in (int, float) or not 0 <= v <= 100 for v in radar.values()):
            raise ValueError('能力分数必须是 0 到 100 的数字')
        if 'is_qualified' not in record or not any(record['is_qualified'] is value for value in (True, False, None)):
            raise ValueError('筛选结论只能是 true、false 或 null')
        features = record.get('parsed_features')
        if not isinstance(features, dict):
            raise ValueError('parsed_features 必须是对象')
        for key in ('candidate_phone', 'education'):
            if not isinstance(features.get(key), str):
                raise ValueError(f'档案字段 {key} 缺失或不是文本')
        skills = features.get('skills')
        if not isinstance(skills, list) or any(not isinstance(s, str) for s in skills):
            raise ValueError('skills 必须是文本数组')
        years = features.get('years_experience')
        if years is not None and (type(years) is not int or years < 0):
            raise ValueError('工作年限必须是非负整数或 null')
    return records


def find_by_digest(records, digest):
    return next((record for record in records if record['content_sha256'] == digest), None)

import base64
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_formats import word_bytes
from src.resume_reader import read_resume
from src.repository import load_candidates
from src.service import analyze_batch, analyze_resume, MAX_FILE_BYTES
from src.server import Handler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]


class RecruitmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_candidates()
        cls.raw = (ROOT / 'candidate_records/陈思远简历-FDE工程师.docx').read_bytes()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_all_original_records_have_six_scores(self):
        for path in (ROOT / 'candidate_records').glob('*.docx'):
            result = analyze_resume(path.name, path.read_bytes(), self.records)
            self.assertEqual(result['data_source'], 'json_profile')
            self.assertEqual(len(result['profile_score']['radar']), 6)

    def test_renamed_file_keeps_profile(self):
        result = analyze_resume('改名.docx', self.raw, self.records)
        self.assertEqual(result['candidate_name'], '陈思远')

    def test_changed_content_does_not_borrow_old_score(self):
        result = analyze_resume('修改简历.docx', word_bytes(read_resume('简历.docx', self.raw) + '\n补充经历'), self.records)
        self.assertIsNone(result['profile_score']['radar'])

    def test_unknown_resume_extracts_fields_without_inventing_scores(self):
        raw = word_bytes('姓名：王同学\n邮箱：wang@example.com\n工作经验：0年\n技能：Python、SQL')
        result = analyze_resume('新简历.docx', raw, self.records)
        self.assertEqual(result['candidate_name'], '王同学')
        self.assertEqual(result['parsed_features']['years_experience'], 0)
        self.assertIsNone(result['profile_score']['fit'])
        self.assertIsNone(result['is_qualified'])

    def test_txt_is_not_supported(self):
        with self.assertRaisesRegex(ValueError, 'Word'):
            analyze_resume('简历.txt', '姓名：陈思远'.encode(), self.records)

    def test_invalid_files(self):
        for filename, raw in [('resume.pdf', self.raw), ('empty.docx', b''),
                              ('large.docx', b'x' * (MAX_FILE_BYTES + 1)), ('binary.docx', b'\x00a')]:
            with self.assertRaises(ValueError):
                analyze_resume(filename, raw, self.records)

    def test_partial_batch_and_deduplication(self):
        good = {'filename': 'ok.docx', 'content_base64': base64.b64encode(self.raw).decode()}
        result = analyze_batch({'files': [good, good, {'filename': 'bad.docx', 'content_base64': '!!!'}]})
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(result['duplicates'], 1)
        self.assertEqual(len(result['failures']), 1)

    def test_limit(self):
        for files in ([], [{}] * 21):
            with self.assertRaises(ValueError):
                analyze_batch({'files': files})

    def test_bad_radar_is_rejected(self):
        data = json.loads((ROOT / 'data/candidates.json').read_text(encoding='utf-8'))
        data['candidates'][0]['profile_score']['radar']['business_understanding'] = 150
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_candidates(path)

    def test_http_upload(self):
        payload = {'files': [{'filename': 'ok.docx', 'content_base64': base64.b64encode(self.raw).decode()}]}
        request = Request(self.url + '/api/analyze/batch', data=json.dumps(payload).encode(),
                          headers={'Content-Type': 'application/json'})
        with urlopen(request) as response:
            self.assertEqual(json.load(response)['candidates'][0]['candidate_name'], '陈思远')

    def test_health_and_static(self):
        with urlopen(self.url + '/') as response:
            self.assertTrue(response.url.endswith('/ui/'))
        with urlopen(self.url + '/api/health') as response:
            self.assertEqual(json.load(response)['status'], 'connected')
        with urlopen(self.url + '/ui/') as response:
            self.assertIn(b'TalentScope', response.read())

    def test_private_files_not_served(self):
        for path in ('/data/candidates.json', '/ui/%2e%2e/data/candidates.json', '/.env'):
            with self.assertRaises(HTTPError) as error:
                urlopen(self.url + path)
            self.assertEqual(error.exception.code, 404)

    def test_invalid_json(self):
        request = Request(self.url + '/api/analyze/batch', data=b'{broken',
                          headers={'Content-Type': 'application/json'})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 400)


if __name__ == '__main__':
    unittest.main()

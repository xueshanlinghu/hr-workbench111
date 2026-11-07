import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from io import BytesIO

from pypdf import PdfWriter
from test_formats import word_bytes
from src.repository import load_candidates
from src.resume_reader import read_resume
from src.service import analyze_batch, extract_basic_fields

ROOT = Path(__file__).resolve().parents[1]


class RegressionTests(unittest.TestCase):
    def test_empty_label_does_not_consume_next_field(self):
        result = extract_basic_fields('姓名：\n邮箱：alex@example.com\n技能：\n工作经验：0年')
        self.assertEqual(result['candidate_name'], '待核实姓名')
        self.assertEqual(result['candidate_email'], 'alex@example.com')
        self.assertEqual(result['parsed_features']['skills'], [])

    def test_profile_fields_are_validated_before_display(self):
        source = json.loads((ROOT / 'data/candidates.json').read_text())
        for value in (None, {}, {'skills': None}, {'candidate_phone':'', 'education':'', 'skills':[], 'years_experience':'<img>'}):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                data = json.loads(json.dumps(source))
                data['candidates'][0]['parsed_features'] = value
                p = Path(tmp) / 'data.json'; p.write_text(json.dumps(data))
                with self.assertRaises(ValueError): load_candidates(p)

    def test_same_filename_failure_has_its_own_index(self):
        good = base64.b64encode(word_bytes('姓名：李同学')).decode()
        result = analyze_batch({'files':[{'filename':'简历.docx','content_base64':good},
                                         {'filename':'简历.docx','content_base64':'!!!'}]})
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(result['failures'][0]['index'], 1)

    def test_invalid_filename_does_not_abort_batch(self):
        result = analyze_batch({'files':[{'filename':None,'content_base64':'YQ=='}]})
        self.assertEqual(result['candidates'], [])
        self.assertEqual(result['failures'][0]['filename'], '')

    def test_invalid_port_has_actionable_error(self):
        for value in ('abc', '-1', '65536'):
            with self.subTest(value=value):
                result = subprocess.run([sys.executable, str(ROOT/'app.py')],
                    env={**os.environ,'HR_PORT':value}, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('65535', result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_pdf_page_limit(self):
        writer = PdfWriter()
        for _ in range(51): writer.add_blank_page(595, 842)
        output = BytesIO(); writer.write(output)
        with self.assertRaisesRegex(ValueError, '50'):
            read_resume('超长.pdf', output.getvalue())

    def test_downloadable_word_archives_match_data(self):
        records = load_candidates()
        for record in records:
            with self.subTest(name=record['candidate_name']):
                p = ROOT / 'candidate_records' / record['filename']
                text = read_resume(p.name, p.read_bytes())
                self.assertIn(record['candidate_name'], text)
                for heading in ('教育背景','工作经历','相关项目','资格证书和技能'):
                    self.assertIn(heading, text)


if __name__ == '__main__':
    unittest.main()

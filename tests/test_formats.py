from io import BytesIO
from pathlib import Path
import base64
import unittest

from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from src.repository import load_candidates
from src.resume_reader import read_resume
from src.service import analyze_resume, analyze_batch

ROOT = Path(__file__).resolve().parents[1]


def word_bytes(text):
    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def pdf_bytes(text='', encrypted=False):
    writer = PdfWriter()
    page = writer.add_blank_page(595, 842)
    if text:
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        stream = DecodedStreamObject()
        lines = ['BT /F1 12 Tf 50 780 Td']
        for line in text.splitlines():
            line = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            lines.append(f'({line}) Tj 0 -18 Td')
        stream.set_data(('\n'.join(lines) + '\nET').encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted:
        writer.encrypt('password')
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


class FormatTests(unittest.TestCase):
    def test_docx_matches_original_profile(self):
        text = read_resume('陈思远.docx', (ROOT / 'candidate_records/陈思远简历-FDE工程师.docx').read_bytes())
        result = analyze_resume('陈思远.docx', word_bytes(text), load_candidates())
        self.assertEqual(result['candidate_name'], '陈思远')
        self.assertEqual(result['data_source'], 'json_profile')

    def test_docx_table(self):
        document = Document()
        table = document.add_table(rows=2, cols=2)
        table.cell(0,0).text, table.cell(0,1).text = '姓名', '王同学'
        table.cell(1,0).text, table.cell(1,1).text = '核心技能', 'Python、SQL'
        output = BytesIO(); document.save(output)
        result = analyze_resume('表格简历.docx', output.getvalue(), load_candidates())
        self.assertEqual(result['candidate_name'], '王同学')
        self.assertEqual(result['parsed_features']['skills'], ['Python', 'SQL'])

    def test_pdf_text(self):
        result = analyze_resume('resume.pdf', pdf_bytes('Name: Alex\nEmail: alex@example.com'), load_candidates())
        self.assertEqual(result['candidate_name'], 'Alex')
        self.assertEqual(result['candidate_email'], 'alex@example.com')
        self.assertIsNone(result['profile_score']['radar'])

    def test_scan_and_encryption(self):
        for raw, message in [(pdf_bytes(), 'OCR'), (pdf_bytes('Hello', True), '加密')]:
            with self.assertRaisesRegex(ValueError, message):
                read_resume('resume.pdf', raw)

    def test_legacy_doc_and_corruption(self):
        for name, raw in [('old.doc', b'old'), ('broken.docx', b'bad'), ('broken.pdf', b'%PDF-bad')]:
            with self.assertRaises(ValueError):
                read_resume(name, raw)

    def test_cross_format_dedup(self):
        text = 'Name: Alex\nEmail: alex@example.com'
        files = [{'filename':name, 'content_base64':base64.b64encode(raw).decode()} for name,raw in
                 [('resume.pdf',pdf_bytes(text)),('resume.docx',word_bytes(text)),('bad.pdf',b'bad')]]
        result = analyze_batch({'files':files})
        self.assertEqual(len(result['candidates']),1)
        self.assertEqual(result['duplicates'],1)
        self.assertEqual(len(result['failures']),1)


if __name__ == '__main__':
    unittest.main()

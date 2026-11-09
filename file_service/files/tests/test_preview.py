import io
import re
import zipfile
from unittest import TestCase

from file_service.files import preview

SHEET = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheetData><row r="1">'
    '<c r="A1" s="3"/>'                                  # self-closing cell right before a linked one
    '<c r="B1" s="7" t="s"><v>0</v></c>'                 # shared string, styled
    '<c r="C1"><v>5</v></c>'                             # untouched neighbour
    '<c r="D1" t="inlineStr"><is><t>inline &amp; text</t></is></c>'
    '<c r="E1" s="2"/>'                                  # empty linked cell -> shows the URL
    '<c r="F1" t="s"><v>1</v></c>'                       # link with a forbidden scheme
    '</row></sheetData>'
    '<hyperlinks>'
    '<hyperlink ref="B1" r:id="rId1"/>'
    '<hyperlink ref="D1" r:id="rId2"/>'
    '<hyperlink ref="E1" r:id="rId3"/>'
    '<hyperlink ref="F1" r:id="rId4"/>'
    '</hyperlinks></worksheet>'
)
RELS = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
    'Target="https://example.com/a?x=1&amp;y=2" TargetMode="External"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
    'Target="mailto:a@b.c" TargetMode="External"/>'
    '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
    'Target="https://example.com/empty" TargetMode="External"/>'
    '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
    'Target="file:///etc/passwd" TargetMode="External"/>'
    '</Relationships>'
)
SST = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<si><r><t>Rich </t></r><r><t>"text"</t></r><rPh><t>ignored</t></rPh></si>'
    '<si><t>bad</t></si></sst>'
)


def make_xlsx(with_links=True):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('xl/worksheets/sheet1.xml', SHEET)
        z.writestr('xl/sharedStrings.xml', SST)
        if with_links:
            z.writestr('xl/worksheets/_rels/sheet1.xml.rels', RELS)
    return buf.getvalue()


def sheet_of(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read('xl/worksheets/sheet1.xml').decode('utf-8')


class PrepareSpreadsheetTests(TestCase):
    def setUp(self):
        self.out = sheet_of(preview.prepare_spreadsheet_for_preview(make_xlsx(), '.xlsx'))

    def test_neighbouring_cells_survive(self):
        self.assertIn('<c r="A1" s="3"/>', self.out)
        self.assertIn('<c r="C1"><v>5</v></c>', self.out)
        self.assertIn('<c r="F1" t="s"><v>1</v></c>', self.out)

    def test_linked_cell_keeps_style_and_gets_formula(self):
        self.assertRegex(self.out, r'<c r="B1" s="7" t="str"><f>HYPERLINK\(')
        # rich-text shared string joined, quotes doubled, & escaped for XML
        self.assertIn('https://example.com/a?x=1&amp;y=2', self.out)
        self.assertIn('Rich ""text""', self.out)

    def test_inline_string_and_empty_cell(self):
        self.assertIn('inline &amp; text', self.out)
        self.assertRegex(self.out, r'<c r="E1" s="2" t="str"><f>HYPERLINK\("https://example.com/empty","https://example.com/empty"\)</f>')

    def test_unsafe_scheme_is_left_alone(self):
        self.assertNotIn('file:///', self.out)

    def test_xml_stays_well_formed(self):
        import xml.etree.ElementTree as ET
        ET.fromstring(self.out)

    def test_no_links_or_other_extension_returns_same_bytes(self):
        data = make_xlsx(with_links=False)
        self.assertIs(preview.prepare_spreadsheet_for_preview(data, '.xlsx'), data)
        self.assertIs(preview.prepare_spreadsheet_for_preview(b'x', '.xls'), b'x')

    def test_garbage_returns_original(self):
        self.assertEqual(preview.prepare_spreadsheet_for_preview(b'not a zip', '.xlsx'), b'not a zip')


class GuessExtensionTests(TestCase):
    def test_by_name_then_mimetype(self):
        self.assertEqual(preview.guess_extension('Report.XLSX'), '.xlsx')
        self.assertEqual(preview.guess_extension(None, 'x.bin', mimetype='application/msword'), '.doc')
        self.assertIsNone(preview.guess_extension('a.zip', mimetype='application/zip'))

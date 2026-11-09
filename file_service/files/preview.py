"""
Helpers for the document preview endpoint (Office -> PDF through Gotenberg).

Kept free of Django imports so it can be unit-tested on its own.
"""
import io
import logging
import os
import posixpath
import re
import threading
import xml.etree.ElementTree as ET
import zipfile
from xml.sax.saxutils import escape, unescape

import requests

logger = logging.getLogger('file_service')

GOTENBERG_URL = os.environ.get('GOTENBERG_URL', 'http://gotenberg:3000').rstrip('/')
GOTENBERG_TIMEOUT = int(os.environ.get('PREVIEW_CONVERT_TIMEOUT', '60'))
PREVIEW_MAX_BYTES = int(os.environ.get('PREVIEW_MAX_BYTES', str(30 * 1024 * 1024)))
PREVIEW_MAX_PARALLEL = int(os.environ.get('PREVIEW_MAX_PARALLEL', '2'))
PREVIEW_QUEUE_WAIT = 5  # seconds a request waits for a free conversion slot

SPREADSHEET_EXTENSIONS = frozenset(('.xlsx', '.xls', '.ods', '.csv', '.tsv'))
PREVIEW_EXTENSIONS = SPREADSHEET_EXTENSIONS | frozenset((
    '.doc', '.docx', '.odt', '.rtf', '.txt',
    '.ppt', '.pptx', '.odp',
))

# Fallback when the stored name has no usable extension.
MIME_EXTENSIONS = {
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/vnd.oasis.opendocument.text': '.odt',
    'application/rtf': '.rtf',
    'text/rtf': '.rtf',
    'text/plain': '.txt',
    'application/vnd.ms-excel': '.xls',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
    'application/vnd.oasis.opendocument.spreadsheet': '.ods',
    'text/csv': '.csv',
    'application/vnd.ms-powerpoint': '.ppt',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
    'application/vnd.oasis.opendocument.presentation': '.odp',
}

# Limits for the xlsx pre-processing (zip-bomb guard).
_XLSX_MAX_UNPACKED = 200 * 1024 * 1024
_XLSX_MAX_AUX_XML = 50 * 1024 * 1024
_SAFE_LINK_SCHEMES = ('http://', 'https://', 'mailto:', 'ftp://')

_MAIN_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
_CELL_RE = re.compile(r'<c\b([^>]*?)(?:/>|>(.*?)</c>)', re.DOTALL)
_HYPERLINK_RE = re.compile(r'<(?:\w+:)?hyperlink\b([^>]*?)/?>')
_REF_ATTR_RE = re.compile(r'\bref="([^"]+)"')
_RID_ATTR_RE = re.compile(r'\b(?:\w+:)?id="([^"]+)"')
_R_ATTR_RE = re.compile(r'(?<![\w:])r="([A-Z]+[0-9]+)"')
_S_ATTR_RE = re.compile(r'(?<![\w:])s="([0-9]+)"')
_T_ATTR_RE = re.compile(r'(?<![\w:])t="(\w+)"')
_V_RE = re.compile(r'<v>(.*?)</v>', re.DOTALL)
_INLINE_T_RE = re.compile(r'<t\b[^>]*>(.*?)</t>', re.DOTALL)


class PreviewError(Exception):
    """Conversion failed; `args[0]` is for logs only, never for the client."""


class PreviewBusy(PreviewError):
    """No free conversion slot."""


_slots = threading.BoundedSemaphore(PREVIEW_MAX_PARALLEL)


def guess_extension(*names, mimetype=None):
    """First supported extension among the given file names, else by mimetype."""
    for name in names:
        ext = os.path.splitext(name or '')[1].lower()
        if ext in PREVIEW_EXTENSIONS:
            return ext
    return MIME_EXTENSIONS.get((mimetype or '').split(';')[0].strip().lower())


def convert_to_pdf(name, data, ext):
    """Convert one document through Gotenberg. Returns PDF bytes."""
    if not _slots.acquire(timeout=PREVIEW_QUEUE_WAIT):
        raise PreviewBusy('all conversion slots are busy')
    try:
        form = {}
        if ext in SPREADSHEET_EXTENSIONS:
            form['singlePageSheets'] = 'true'
            data = prepare_spreadsheet_for_preview(data, ext)
        try:
            resp = requests.post(
                GOTENBERG_URL + '/forms/libreoffice/convert',
                files={'files': (name, data)},
                data=form,
                timeout=GOTENBERG_TIMEOUT,
            )
        except requests.RequestException as e:
            raise PreviewError('gotenberg request failed: %s' % e)
        if resp.status_code != 200:
            raise PreviewError('gotenberg answered %s: %s' % (resp.status_code, resp.text[:500]))
        if not resp.content.startswith(b'%PDF'):
            raise PreviewError('gotenberg answered 200 but not with a PDF')
        return resp.content
    finally:
        _slots.release()


def _shared_strings(zin):
    """Plain text of every <si> (rich-text runs joined, phonetic hints skipped)."""
    try:
        info = zin.getinfo('xl/sharedStrings.xml')
    except KeyError:
        return []
    if info.file_size > _XLSX_MAX_AUX_XML:
        return []
    root = ET.fromstring(zin.read(info))
    strings = []
    for si in root.findall(_MAIN_NS + 'si'):
        parts = []
        for child in si:
            if child.tag == _MAIN_NS + 't':
                parts.append(child.text or '')
            elif child.tag == _MAIN_NS + 'r':
                parts.extend(t.text or '' for t in child.findall(_MAIN_NS + 't'))
        strings.append(''.join(parts))
    return strings


def _sheet_links(zin):
    """{sheet xml path: {rel id: external target}} for sheets that have hyperlinks."""
    result = {}
    for item in zin.infolist():
        name = item.filename
        if not (name.startswith('xl/worksheets/_rels/') and name.endswith('.rels')):
            continue
        if item.file_size > _XLSX_MAX_AUX_XML:
            continue
        sheet = posixpath.join('xl/worksheets', posixpath.basename(name)[:-len('.rels')])
        rels = {}
        for rel in ET.fromstring(zin.read(item)):
            if rel.attrib.get('Type', '').lower().endswith('/hyperlink') and rel.attrib.get('Target'):
                target = rel.attrib['Target']
                if target.lower().startswith(_SAFE_LINK_SCHEMES):
                    rels[rel.attrib.get('Id')] = target
        if rels:
            result[sheet] = rels
    return result


def _cell_display(attrs, inner, strings):
    """Visible text of a cell, or '' when it has none."""
    if not inner:
        return ''
    kind = _T_ATTR_RE.search(attrs)
    kind = kind.group(1) if kind else 'n'
    if kind == 'inlineStr':
        return unescape(''.join(_INLINE_T_RE.findall(inner)))
    v = _V_RE.search(inner)
    if not v:
        return ''
    if kind == 's':
        text = v.group(1).strip()
        return strings[int(text)] if text.isdigit() and int(text) < len(strings) else ''
    return unescape(v.group(1))


def _patch_sheet(xml_text, rels, strings):
    """Replace hyperlinked cells with =HYPERLINK() cells in one pass over the sheet."""
    targets = {}
    for m in _HYPERLINK_RE.finditer(xml_text):
        attrs = m.group(1)
        ref, rid = _REF_ATTR_RE.search(attrs), _RID_ATTR_RE.search(attrs)
        if ref and rid and rid.group(1) in rels:
            targets.setdefault(ref.group(1).split(':')[0], rels[rid.group(1)])
    if not targets:
        return xml_text

    def repl(m):
        attrs, inner = m.group(1), m.group(2)
        r = _R_ATTR_RE.search(attrs)
        if not r or r.group(1) not in targets:
            return m.group(0)
        target = targets[r.group(1)]
        display = _cell_display(attrs, inner, strings) or target
        s = _S_ATTR_RE.search(attrs)
        style = ' s="%s"' % s.group(1) if s else ''
        formula = 'HYPERLINK("%s","%s")' % (target.replace('"', '""'), display.replace('"', '""'))
        return '<c r="%s"%s t="str"><f>%s</f><v>%s</v></c>' % (
            r.group(1), style, escape(formula), escape(display))

    return _CELL_RE.sub(repl, xml_text)


def prepare_spreadsheet_for_preview(file_bytes, ext):
    """
    LibreOffice's headless PDF export drops native xlsx cell hyperlinks (tdf#169919).
    Turn them into HYPERLINK() formulas in memory; the stored file is not touched.
    Any problem -> the original bytes are returned and the preview just has no links.
    """
    if ext != '.xlsx':
        return file_bytes
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zin:
            if sum(i.file_size for i in zin.infolist()) > _XLSX_MAX_UNPACKED:
                return file_bytes
            links = _sheet_links(zin)
            if not links:
                return file_bytes
            strings = _shared_strings(zin)
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w') as zout:
                for item in zin.infolist():
                    content = zin.read(item)
                    if item.filename in links:
                        content = _patch_sheet(content.decode('utf-8'), links[item.filename], strings).encode('utf-8')
                    zout.writestr(item, content)
            return out.getvalue()
    except Exception as e:
        logger.warning('Failed to preprocess xlsx hyperlinks: %s', e)
        return file_bytes

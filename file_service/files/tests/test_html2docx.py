from file_service.utils.html2docx import (BaseStyleHandler,
                                          TableCreator, TableDrawer,
                                          PageStyleProcesser)
from docx import Document
from bs4 import BeautifulSoup

import pytest


@pytest.fixture
def page_styles():
    page_styles = """<style>
    @page { }
    * { }
    </style>"""
    bs_style = BeautifulSoup(page_styles, 'html.parser').find_all('style')[0].contents[0].strip()
    return bs_style


@pytest.fixture
def page_size_a4():
    page_styles = """<style>
    @page { size: A4; }
    * { }
    </style>"""
    bs_style = BeautifulSoup(page_styles, 'html.parser').find_all('style')[0].contents[0].strip()
    return bs_style


@pytest.fixture
def page_size_letter():
    page_styles = """<style>
    @page { size: Letter; }
    * { }
    </style>"""
    bs_style = BeautifulSoup(page_styles, 'html.parser').find_all('style')[0].contents[0].strip()
    return bs_style


@pytest.fixture
def single_selector_tag_styles():
    tag_styles = """<style>
        .tar { }
    </style>"""
    bs_style = BeautifulSoup(tag_styles, 'html.parser').find_all('style')[0].contents[0].strip()
    return bs_style

@pytest.fixture
def tag_styles():
    tag_styles = """<style>
        table { }
    </style>"""
    bs_style = BeautifulSoup(tag_styles, 'html.parser').find_all('style')[0].contents[0].strip()
    return bs_style

@pytest.fixture
def complex_styles_1():
    tag_styles = """<style>
        .title td { }
    </style>"""
    bs_style = BeautifulSoup(tag_styles, 'html.parser').find_all('style')[0].contents[0].strip()
    return bs_style

@pytest.fixture
def complex_styles_2():
    tag_styles = """<style>
        .title .tdTitle { }
    </style>"""
    bs_style = BeautifulSoup(tag_styles, 'html.parser').find_all('style')[0].contents[0].strip()
    return bs_style

@pytest.fixture
def complex_styles_3():
    tag_styles = """<style>
        .title tfoot td { }
    </style>"""
    bs_style = BeautifulSoup(tag_styles, 'html.parser').find_all('style')[0].contents[0].strip()
    return bs_style

@pytest.fixture
def single_selector():
    single_selector = "<div class=tar></div>"
    bs_single_selector = BeautifulSoup(single_selector, 'html.parser').find_all('div')[0]
    return bs_single_selector

@pytest.fixture
def tag_name_selector():
    tag_name_selector = "<table></table>"
    bs_tag_name_selector = BeautifulSoup(tag_name_selector, 'html.parser').find_all('table')[0]
    return bs_tag_name_selector

@pytest.fixture
def complex_selector_1():
    """
    Selector: .title td
    """
    complex_selector_1 = "<html><table class='title'><tr><td></td></tr></table></html>"
    bs_complex_selector_1 = BeautifulSoup(complex_selector_1, 'html.parser').find_all('td')[0]
    return bs_complex_selector_1

@pytest.fixture
def complex_selector_2():
    """
    Selector: .title tdTitle
    """
    complex_selector_2 = "<table class='title'><tr><td class='tdTitle'></tr></td></table>"
    bs_complex_selector_2 = BeautifulSoup(complex_selector_2, 'html.parser').find_all('td')[0]
    return bs_complex_selector_2

@pytest.fixture
def complex_selector_3():
    """
    Selector: .title tfoot td
    """
    complex_selector_3 = "<table class='title'><tfoot><tr><td class='tdTitle'></td></tr></tfoot></table>"
    bs_complex_selector_3 = BeautifulSoup(complex_selector_3, 'html.parser').find_all('td')[0]
    return bs_complex_selector_3

@pytest.fixture
def document():
    return Document()

@pytest.fixture
def complex_table():
    """
    docx structure              table view and labled cells.
    before processing
    _____________________       _______________________
    |0   |1   |2   |3   |        |r2       |    |r2  |
    |____|____|____|____|        |c2       |____|    |
    |4   |5   |6   |7   |        |         |    |    |
    |____|____|____|____|   =>   |_________|____|____|
    |8   |9   |10  |11  |        |    |    |r2  |r2  |
    |____|____|____|____|        |____|____|    |    |
    |12  |13  |14  |15  |        |c2       |    |    |
    |____|____|____|____|        |_________|____|____|

    r2 -> rowspan = 2
    c2 -> colspan = 2

    HTML2DOCX makr up this table on 9 ThTdCells.
    ThTdCell corresponds to td or th cell in html structure.
    Example:
    ThTdCell with index 0.
    Contains [0, 1, 4, 5] cells. (labled_cells)
    cell with index 0 should have cell.rowspan=2, cell.colsapn=2, cell.index=0.
    cells [1, 4, 5] should have cell.rowspan=None, cell.colspan=None, and corresponding cell.index (1,4,5).
    ___________        ___________
    |0   |1   |        |r2       |
    |____|____|        |c2       |
    |4   |5   |   =>   |         |
    |____|____|        |_________| 

    ThTdCell with index 1.
    Contains [2] cell.
    cell.rowspan=None, cell.colspan=None, cell.index=2

    ThTdCell with index 2.
    Contains [3, 7] cells.
    ______       ______
    |3   |       |r2  |
    |____|  =>   |    |
    |7   |       |    |
    |____|       |____|

    cell with index 3 cell.rowspan=2, cell.colspan=None, cell.index=3.
    cell with index 7 cell.rowspan=None, cell.colspan = None, cell.index=7.
    """

    table = """<table>
        <tr>
            <td rowspan='2' colspan='2'></td>
            <td></td>
            <td rowspan='2'></td>
        </tr>
        <tr>
            <td></td>
        </tr>
        <tr>
            <td></td>
            <td></td>
            <td rowspan='2'></td>
            <td rowspan='2'></td>
        </tr>
        <tr>
            <td colspan='2'></td>
        </tr>
    </table>"""
    bs_table = BeautifulSoup(table, 'html.parser').find_all('table')[0]
    return bs_table


def test_can_parse_page_styles(page_styles):
    page_style_handler = BaseStyleHandler()
    page_style_handler.setup_styles(page_styles)
    assert len(page_style_handler.page_rules) == 2


def test_can_parse_base_tag_styles(tag_styles, tag_name_selector):
    tag_style_handler = BaseStyleHandler(tag_name_selector)
    tag_style_handler.setup_styles(tag_styles)
    assert len(tag_style_handler.tag_rules) == 1
    for rule in tag_style_handler.tag_rules:
        assert rule.selectorText == "table"


def test_can_parse_single_tag_styles(single_selector_tag_styles, single_selector):
    tag_style_handler = BaseStyleHandler(single_selector)
    tag_style_handler.setup_styles(single_selector_tag_styles)
    assert len(tag_style_handler.tag_rules) == 1
    for rule in tag_style_handler.tag_rules:
        assert rule.selectorText == ".tar"


def test_can_parse_complex_selector_1(complex_styles_1, complex_selector_1):
    tag_style_handler = BaseStyleHandler(complex_selector_1)
    tag_style_handler.setup_styles(complex_styles_1)
    assert len(tag_style_handler.tag_rules) == 1
    for rule in tag_style_handler.tag_rules:
        assert rule.selectorText == ".title td"


def test_can_parse_complex_selector_2(complex_styles_2, complex_selector_2):
    tag_style_handler = BaseStyleHandler(complex_selector_2)
    tag_style_handler.setup_styles(complex_styles_2)
    assert len(tag_style_handler.tag_rules) == 1
    for rule in tag_style_handler.tag_rules:
        assert rule.selectorText == ".title .tdTitle"


def test_can_parse_complex_selector_3(complex_styles_3, complex_selector_3):
    tag_style_handler = BaseStyleHandler(complex_selector_3)
    tag_style_handler.setup_styles(complex_styles_3)
    assert len(tag_style_handler.tag_rules) == 1
    for rule in tag_style_handler.tag_rules:
        assert rule.selectorText == ".title tfoot td"


def test_can_create_docx_table(complex_table, document):
    table_creator = TableCreator(complex_table, document)
    table = table_creator.create()
    assert len(table.rows) == 4
    assert len(table.columns) == 4


def test_can_mark_up_cells_in_tables(complex_table, document, page_styles):
    drawer = TableDrawer(complex_table, document, page_styles)
    assert len(drawer.td_th_cells) == 9

    # ThTdCell with index 0.
    # Contains [0, 1, 4, 5] cells. (labled_cells)
    # cell with index 0 should have cell.rowspan=2, cell.colsapn=2, cell.index=0.
    
    # ___________        ___________
    # |0   |1   |        |r2       |
    # |____|____|        |c2       |
    # |4   |5   |   =>   |         |
    # |____|____|        |_________| 

    first_labled_cell = drawer.td_th_cells[0].labled_cells[0]  
    assert first_labled_cell.colspan == 2
    assert first_labled_cell.rowspan == 2
    assert first_labled_cell.index == 0

    # cells [1, 4, 5] should have cell.rowspan=None, cell.colspan=None, and corresponding cell.index (1,4,5).
    for cell in drawer.td_th_cells[0].labled_cells[1:]:
        assert cell.colspan is None
        assert cell.rowspan is None

    idxs = [cell.index for cell in drawer.td_th_cells[0].labled_cells[1:]]
    assert len(idxs) == 3
    assert [1, 4, 5] == idxs 

    second_labled_cell = drawer.td_th_cells[1].labled_cells[0]
    assert second_labled_cell.rowspan is None
    assert second_labled_cell.colspan is None
    assert second_labled_cell.index == 2

    # ThTdCell with index 2.
    # Contains [3, 7] cells.
    # ______       ______
    # |3   |       |r2  |
    # |____|  =>   |    |
    # |7   |       |    |
    # |____|       |____|

    # cell with index 3 cell.rowspan=2, cell.colspan=None, cell.index=3.
    # cell with index 7 cell.rowspan=None, cell.colspan = None, cell.index=7.

    third_labled_cell = second_labled_cell = drawer.td_th_cells[2].labled_cells[0]
    assert third_labled_cell.colspan is None
    assert third_labled_cell.rowspan == 2
    assert third_labled_cell.index == 3

    seventh_labled_cell = drawer.td_th_cells[2].labled_cells[1]
    assert seventh_labled_cell.rowspan is None
    assert seventh_labled_cell.colspan is None
    assert seventh_labled_cell.index == 7

    ## ThTdCell with index 9.
    # Contains [12, 13] cells.
    # ___________          ___________
    # |12  |13  |   =>     |c2       |
    # |____|____|          |_________|

    twelfth_labled_cell = drawer.td_th_cells[8].labled_cells[0]
    assert twelfth_labled_cell.colspan == 2
    assert twelfth_labled_cell.rowspan is None
    assert twelfth_labled_cell.index == 12

    thirteenth_labled_cell = drawer.td_th_cells[8].labled_cells[1]
    assert thirteenth_labled_cell.colspan is None
    assert thirteenth_labled_cell.rowspan is None
    assert thirteenth_labled_cell.index == 13

def test_page_size(page_size_a4, page_size_letter, document):
    A4_height = 297
    A4_width = 210

    page = PageStyleProcesser(document)
    page.setup_styles(page_size_a4)
    page.apply_styles(page_size_a4)
    
    # convert to int because it saves values like 210.00861111111112 and 297.0036111111111
    assert int(page.document.sections[0].page_height.mm) == A4_height
    assert int(page.document.sections[0].page_width.mm) == A4_width

    letter_height = 279.4
    letter_width = 215.9

    page = PageStyleProcesser(document)
    page.setup_styles(page_size_letter)
    page.apply_styles(page_size_letter)

    assert page.document.sections[0].page_height.mm == letter_height
    assert page.document.sections[0].page_width.mm == letter_width
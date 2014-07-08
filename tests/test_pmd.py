import os
from collections import namedtuple
from nose.tools import *
from nose.plugins.attrib import attr
from reviewbotpmd.pmd import *
import xml.etree.ElementTree as ElementTree

java_source_path = os.path.join(os.path.dirname(__file__),
                                'testdata/HelloWorld.java')
invalid_source_path = os.path.join(os.path.dirname(__file__),
                                   'testdata/IDontExist.java')

@attr('slow')
def test_run_pmd_creates_file():
    results_file_path = run_pmd(java_source_path)
    assert os.path.exists(results_file_path)

@attr('slow')
def test_run_pmd_creates_valid_pmd_result():
    results_file_path = run_pmd(java_source_path)
    tree = ElementTree.parse(results_file_path)
    root = tree.getroot()
    assert root.tag == 'pmd'
    file_elems = root.findall('file')
    assert len(file_elems) == 1

def test_run_pmd_with_invalid_source_file():
    assert not os.path.exists(invalid_source_path)
    results_file_path = run_pmd(invalid_source_path)
    assert_raises(ElementTree.ParseError, ElementTree.parse, results_file_path)

def test_result_from_xml():
    pmd_result_path = os.path.join(os.path.dirname(__file__),
                                   'testdata/HelloWorld_results.xml')
    result = Result.from_xml(pmd_result_path)
    assert len(result.violations) == 6

def test_violation_num_lines():
    one_line_violation = Violation(rule='', text='', url='',
                                   first_line=1, last_line=1)
    assert one_line_violation.num_lines == 1

def test_post_comments():
    pmd_result_path = os.path.join(os.path.dirname(__file__),
                                   'testdata/HelloWorld_results.xml')
    result = Result.from_xml(pmd_result_path)
    reviewed_file = FileMock(java_source_path)
    post_comments(result, reviewed_file)
    assert len(reviewed_file.comments) == 6

def test_post_comments_comment_format():
    pmd_result_path = os.path.join(os.path.dirname(__file__),
                                   'testdata/HelloWorld_results.xml')
    result = Result.from_xml(pmd_result_path)
    reviewed_file = FileMock(java_source_path)
    post_comments(result, reviewed_file)
    violation = result.violations[0]
    assert_equals(
        reviewed_file.comments[0].text,
        "%s: %s\nMore info: %s" % (violation.rule, violation.text, violation.url))

@attr('slow')
def test_handle_file():
    pmdtool = PMDTool()
    reviewed_file = FileMock(java_source_path, java_source_path)
    assert pmdtool.handle_file(reviewed_file) == True
    assert len(reviewed_file.comments) == 6

def test_handle_file_unsupported_file_type():
    pmdtool = PMDTool()
    reviewed_file = FileMock(dest_file='test.php')
    assert pmdtool.handle_file(reviewed_file) == False

def test_handle_file_invalid_file():
    pmdtool = PMDTool()
    reviewed_file = FileMock(dest_file=invalid_source_path)
    assert pmdtool.handle_file(reviewed_file) == False

Comment = namedtuple('Comment', ['text', 'first_line', 'num_lines'])

class FileMock(object):

    def __init__(self, patched_file_path=None, dest_file=None):
        self.comments = []
        self.patched_file_path = patched_file_path
        self.dest_file = dest_file

    def get_patched_file_path(self):
        return self.patched_file_path

    def comment(self, text, first_line, num_lines=1, issue=None,
                        original=False):
        self.comments.append(Comment(text, first_line, num_lines))


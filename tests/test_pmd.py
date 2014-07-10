import os
from collections import namedtuple
from nose import SkipTest
from nose.tools import *
from nose.plugins.attrib import attr
from reviewbotpmd.pmd import *
import xml.etree.ElementTree as ElementTree

java_source_path = os.path.join(os.path.dirname(__file__),
                                'testdata/HelloWorld.java')
invalid_source_path = os.path.join(os.path.dirname(__file__),
                                   'testdata/IDontExist.java')

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

def test_post_comments_comment_plain_text():
    pmd_result_path = os.path.join(os.path.dirname(__file__),
                                   'testdata/HelloWorld_results.xml')
    result = Result.from_xml(pmd_result_path)
    reviewed_file = FileMock(java_source_path)
    post_comments(result, reviewed_file, use_markdown=False)
    violation = result.violations[0]
    assert_equals(
        reviewed_file.comments[0].text,
        "%s: %s\n\nMore info: %s" % (violation.rule,
                                     violation.text,
                                     violation.url))

def test_post_comments_comment_markdown():
    pmd_result_path = os.path.join(os.path.dirname(__file__),
                                   'testdata/HelloWorld_results.xml')
    result = Result.from_xml(pmd_result_path)
    reviewed_file = FileMock(java_source_path)
    post_comments(result, reviewed_file, use_markdown=True)
    violation = result.violations[0]
    assert_equals(
        reviewed_file.comments[0].text,
        "[%s](%s): %s" % (violation.rule, violation.url, violation.text))


class TestPMDTool(object):

    def setup(self):
        self.pmd = PMDTool()
        pmd_install_path = os.environ.get('PMD_INSTALL_PATH', '/opt/pmd/')
        if not os.path.exists(pmd_install_path):
            raise SkipTest("Cannot run run test as no valid "
                           "$PMD_INSTALL_PATH was provided")
        default_settings = {'markdown': False, 'pmd_install_path': pmd_install_path}
        self.pmd.settings = default_settings
        self.pmd._setup(default_settings)
        self.pmd.processed_files = set()
        self.pmd.ignored_files = set()

    @attr('slow')
    def test_run_pmd_creates_file(self):
        results_file_path = self.pmd.run_pmd(java_source_path)
        assert os.path.exists(results_file_path)

    @attr('slow')
    def test_run_pmd_creates_valid_pmd_result(self):
        results_file_path = self.pmd.run_pmd(java_source_path)
        tree = ElementTree.parse(results_file_path)
        root = tree.getroot()
        assert root.tag == 'pmd'
        file_elems = root.findall('file')
        assert len(file_elems) == 1

    def test_run_pmd_with_invalid_source_file(self):
        assert not os.path.exists(invalid_source_path)
        results_file_path = self.pmd.run_pmd(invalid_source_path)
        assert_raises(ElementTree.ParseError, ElementTree.parse, results_file_path)

    @attr('slow')
    def test_handle_file(self):
        reviewed_file = FileMock(java_source_path, java_source_path)
        assert self.pmd.handle_file(reviewed_file) == True
        assert len(reviewed_file.comments) == 6

    def test_handle_file_unsupported_file_type(self):
        reviewed_file = FileMock(dest_file='test.php')
        assert self.pmd.handle_file(reviewed_file) == False

    def test_handle_file_invalid_file(self):
        reviewed_file = FileMock(dest_file=invalid_source_path)
        assert self.pmd.handle_file(reviewed_file) == False

    def test_handle_files(self):
        reviewed_file = FileMock(java_source_path, java_source_path)
        self.pmd.handle_files([reviewed_file])
        assert self.pmd.processed_files == set([reviewed_file.dest_file])
        assert self.pmd.ignored_files == set()
        assert len(reviewed_file.comments) == 6

    def test_handle_files_invalid_pmd_install(self):
        self.pmd.settings['pmd_install_path'] = 'invalid_path'
        reviewed_file = FileMock(java_source_path, java_source_path)
        self.pmd.handle_files([reviewed_file])
        assert self.pmd.processed_files == set()
        assert self.pmd.ignored_files == set([reviewed_file.dest_file])

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


import os
import subprocess
import shutil
import tempfile
from collections import namedtuple
from nose import SkipTest
from nose.tools import *
from nose.plugins.attrib import attr
from reviewbotpmd.pmd import *
import xml.etree.ElementTree as ElementTree

def setup_module():
    global pmd_install_path, pmd_script_path;
    pmd_install_path = os.environ.get('PMD_INSTALL_PATH', '/opt/pmd/')
    pmd_script_path = os.path.join(pmd_install_path, 'bin/run.sh')
    if not os.path.exists(pmd_install_path):
        raise SkipTest("Cannot run run tests as no valid "
                       "$PMD_INSTALL_PATH was provided")

java_source_path = os.path.join(os.path.dirname(__file__),
                                'testdata/HelloWorld.java')
invalid_source_path = os.path.join(os.path.dirname(__file__),
                                   'testdata/IDontExist.java')

def test_violation_num_lines():
    one_line_violation = Violation(rule='', severity=1, text='', url='',
                                   first_line=1, last_line=1)
    assert one_line_violation.num_lines == 1

def test_violation_is_consecutive():
    violation_text = "Text"
    v1 = Violation('', 1, violation_text, '', first_line=1, last_line=1)
    v2 = Violation('', 1, violation_text, '', first_line=2, last_line=2)
    assert v1.is_consecutive(v2)
    assert v2.is_consecutive(v1)

def test_violation_is_consecutive_text_different():
    v1 = Violation('', 1, "Text", '', first_line=1, last_line=1)
    v2 = Violation('', 1, "Different text", '', first_line=2, last_line=2)
    assert not v1.is_consecutive(v2)
    assert not v2.is_consecutive(v1)

def test_violation_combine():
    violation_text = "Text"
    v1 = Violation('', 1, violation_text, '', first_line=1, last_line=1)
    v2 = Violation('', 1, violation_text, '', first_line=2, last_line=2)
    combined = v1.combine(v2)
    assert_equals(combined.first_line, 1)
    assert_equals(combined.last_line, 2)
    assert_equals(combined.text, violation_text)

def test_violation_combine_not_consecutive():
    v1 = Violation('', 1, "Banana", '', first_line=1, last_line=1)
    v2 = Violation('', 1, "Strawberry", '', first_line=2, last_line=2)
    assert_raises(ValueError, v1.combine, v2)

def test_violation_group_consecutive():
    violation_text = "Text"
    v1 = Violation('', 1, violation_text, '', first_line=1, last_line=1)
    v2 = Violation('', 1, violation_text, '', first_line=2, last_line=2)
    v1_v2_combined = v1.combine(v2)
    assert_equals(Violation.group_consecutive([v1, v2]), [v1_v2_combined])

def test_violation_group_consecutive_empty():
    violation_text = "Text"
    assert_equals(Violation.group_consecutive([]), [])

def test_violation_group_consecutive_nothing_consecutive():
    violation_text = "Text"
    v1 = Violation('', 1, violation_text, '', first_line=1, last_line=1)
    v2 = Violation('', 1, violation_text, '', first_line=3, last_line=3)
    v3 = Violation('', 1, violation_text, '', first_line=5, last_line=10)
    assert_equals(Violation.group_consecutive([v1, v2, v3]), [v1, v2, v3])

def test_violation_group_consecutive_2():
    violation_text = "Text"
    v1 = Violation('', 1, violation_text, '', first_line=1, last_line=1)
    v2 = Violation('', 1, violation_text, '', first_line=2, last_line=2)
    v3 = Violation('', 1, violation_text, '', first_line=5, last_line=10)
    v1_v2_combined = v1.combine(v2)
    assert_equals(Violation.group_consecutive([v1, v2, v3]),
        [v1_v2_combined, v3])

class TestResult(object):

    @classmethod
    def setup_class(cls):
        cls.testdir = tempfile.mkdtemp()
        cls.pmd_result_path = os.path.join(
            cls.testdir, 'HelloWorld_result.xml')
        with open(os.devnull, 'w') as devnull:
            subprocess.check_call(
                [pmd_script_path,
                 'pmd',
                 '-d', java_source_path,
                 '-R', 'rulesets/internal/all-java.xml',
                 '-f', 'xml',
                 '-r', cls.pmd_result_path],
                stdout=devnull,
                stderr=devnull)
        assert os.path.exists(cls.pmd_result_path)


    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.testdir)

    def test_result_from_xml(self):
        result = Result.from_xml(self.pmd_result_path, java_source_path)
        assert len(result.violations) == 6


class TestPMDTool(object):

    def setup(self):
        self.pmd = PMDTool()
        default_settings = {
            'markdown': False,
            'pmd_install_path': pmd_install_path,
            'rulesets': 'java-comments',
            'min_severity_for_issue': 5,
        }
        self.num_violations = 2
        self.pmd.settings = default_settings
        self.pmd._setup(default_settings)
        self.pmd.processed_files = set()
        self.pmd.ignored_files = set()

    def is_valid_ruleset_file(self, filepath):
        if not os.path.exists(filepath):
            return False
        try:
            tree = ElementTree.parse(filepath)
        except ElementTree.ParseError:
            return False
        root = tree.getroot()
        if root.tag != 'pmd':
            return False
        file_elems = root.findall('file')
        return len(file_elems) == 1


    @attr('slow')
    def test_run_pmd_creates_file(self):
        results_file_path = self.pmd.run_pmd(java_source_path,
                                             rulesets=['java-basic'])
        assert os.path.exists(results_file_path)

    @attr('slow')
    def test_run_pmd_invalid_ruleset(self):
        assert_raises(PMDError,
                      self.pmd.run_pmd,
                      java_source_path,
                      ['invalid-ruleset-path'])

    @attr('slow')
    def test_run_pmd_absolute_path_to_ruleset(self):
        ruleset_full_path = os.path.join(os.path.dirname(__file__),
            'testdata/test_ruleset.xml')
        results_file_path = self.pmd.run_pmd(
            java_source_path, rulesets=[ruleset_full_path])
        assert self.is_valid_ruleset_file(results_file_path)

    @attr('slow')
    def test_run_pmd_relative_path_to_ruleset_in_classpath(self):
        ruleset_path = 'rulesets/java/comments.xml'
        results_file_path = self.pmd.run_pmd(
            java_source_path, rulesets=[ruleset_path])
        assert self.is_valid_ruleset_file(results_file_path)

    @attr('slow')
    def test_run_pmd_creates_valid_pmd_result(self):
        results_file_path = self.pmd.run_pmd(
            java_source_path, rulesets=self.pmd.rulesets)
        assert self.is_valid_ruleset_file(results_file_path)

    def test_run_pmd_with_invalid_source_file(self):
        assert not os.path.exists(invalid_source_path)
        results_file_path = self.pmd.run_pmd(
            invalid_source_path, rulesets=['java-basic'])
        assert_raises(ElementTree.ParseError, ElementTree.parse, results_file_path)

    @attr('slow')
    def test_handle_file(self):
        reviewed_file = FileMock(java_source_path, java_source_path)
        assert self.pmd.handle_file(reviewed_file) == True
        assert len(reviewed_file.comments) == self.num_violations

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
        assert len(reviewed_file.comments) == self.num_violations

    def test_handle_files_opens_issues(self):
        reviewed_file = FileMock(
            java_source_path, java_source_path, open_issues=True)
        self.pmd.settings['min_severity_for_issue'] = Severity.MIN
        self.pmd.handle_files([reviewed_file])
        assert self.pmd.processed_files == set([reviewed_file.dest_file])
        assert self.pmd.ignored_files == set()
        assert all(c.issue == True for c in reviewed_file.comments)

    def test_handle_files_invalid_pmd_install(self):
        self.pmd.settings['pmd_install_path'] = 'invalid_path'
        reviewed_file = FileMock(java_source_path, java_source_path)
        self.pmd.handle_files([reviewed_file])
        assert self.pmd.processed_files == set()
        assert self.pmd.ignored_files == set([reviewed_file.dest_file])

    def test_handle_files_invalid_ruleset(self):
        self.pmd.settings['rulesets'] = 'invalid-ruleset-path'
        reviewed_file = FileMock(java_source_path, java_source_path)
        self.pmd.handle_files([reviewed_file])
        assert self.pmd.processed_files == set()
        assert self.pmd.ignored_files == set([reviewed_file.dest_file])

    def test_post_comments(self):
        result = mock_result()
        reviewed_file = FileMock(java_source_path)
        self.pmd.post_comments(result, reviewed_file)
        assert len(reviewed_file.comments) == 2

    def test_post_comments_opens_issues(self):
        self.pmd.min_severity_for_issue = Severity.MIN
        result = mock_result()
        reviewed_file = FileMock(java_source_path, open_issues=True)
        self.pmd.post_comments(result, reviewed_file)
        assert len(reviewed_file.comments) == 2
        assert all(c.issue == True for c in reviewed_file.comments)

    def test_post_comments_open_issues_disabled(self):
        self.pmd.min_severity_for_issue = Severity.MIN
        result = mock_result()
        reviewed_file = FileMock(java_source_path, open_issues=False)
        self.pmd.post_comments(result, reviewed_file)
        assert len(reviewed_file.comments) == 2
        assert all(c.issue == False for c in reviewed_file.comments)

    def test_post_comments_open_issues_consecutive_violation(self):
        self.pmd.min_severity_for_issue = Severity.MIN
        result = mock_result()
        v = result.violations[-1]
        consecutive_violation = Violation(
            v.rule, v.severity, v.text,
            v.url, v.last_line + 1, v.last_line + 5)
        result.violations.append(consecutive_violation)
        reviewed_file = FileMock(java_source_path, open_issues=True)
        self.pmd.post_comments(result, reviewed_file)
        assert len(reviewed_file.comments) == 2
        combined_violation_comment = next(c for c in reviewed_file.comments
                                          if v.text in c.text)
        assert_equals(combined_violation_comment.first_line, v.first_line)
        expected_num_lines = consecutive_violation.last_line - v.first_line + 1
        assert_equals(combined_violation_comment.num_lines, expected_num_lines)

    def test_post_comments_consecutive_violations(self):
        result = mock_result()
        result.violations = [Violation('', Severity.MAX, '', '', 1, 1,)]
        reviewed_file = FileMock(java_source_path, open_issues=True)
        self.pmd.post_comments(result, reviewed_file)
        assert len(reviewed_file.comments) == 1
        assert all(c.issue == True for c in reviewed_file.comments)

    def test_post_comments_comment_plain_text(self):
        result = mock_result()
        reviewed_file = FileMock(java_source_path)
        self.pmd.post_comments(result, reviewed_file, use_markdown=False)
        violation = result.violations[0]
        assert_equals(
            reviewed_file.comments[0].text,
            "%s: %s\n\nMore info: %s" % (violation.rule,
                                         violation.text,
                                         violation.url))

    def test_post_comments_comment_markdown(self):
        result = mock_result()
        reviewed_file = FileMock(java_source_path)
        self.pmd.post_comments(result, reviewed_file, use_markdown=True)
        violation = result.violations[0]
        assert_equals(
            reviewed_file.comments[0].text,
            "[%s](%s): %s" % (violation.rule, violation.url, violation.text))


def mock_result():
    v1 = Violation('TestRule1', 1, 'A test rule', 'dummy_url', 1, 10)
    v2 = Violation('TestRule2', 4, 'Another test rule', 'dummy_url', 14, 14)
    return Result('', [v1, v2])


Comment = namedtuple('Comment', ['text', 'first_line', 'num_lines', 'issue'])


class FileMock(object):

    class Object:
        pass

    def __init__(self, patched_file_path=None, dest_file=None,
                 open_issues=False):
        self.comments = []
        self.patched_file_path = patched_file_path
        self.dest_file = dest_file
        self.review = FileMock.Object()
        self.review.settings = {'open_issues': open_issues}

    def get_patched_file_path(self):
        return self.patched_file_path

    def comment(self, text, first_line, num_lines=1, issue=None,
                original=False):
        self.comments.append(Comment(text, first_line, num_lines, issue))


import os
import tempfile
import logging
from collections import namedtuple
import xml.etree.ElementTree as ElementTree

from reviewbot.tools import Tool
from reviewbot.tools.process import execute
from reviewbot.utils import is_exe_in_path
from reviewbot.processing.filesystem import make_tempfile
import reviewbot.processing.review as review

from rbtools.api.request import APIError


class FileWithMarkdownSupport(review.File):
    def _comment(self, text, first_line, num_lines, issue):
        """Add a comment to the list of comments."""
        data = {
            'filediff_id': self.id,
            'first_line': first_line,
            'num_lines': num_lines,
            'text': text,
            'issue_opened': issue,
            'text_type': 'markdown'
        }
        self.review.comments.append(data)

# Monkey-patch File to add markdown support
review.File = FileWithMarkdownSupport

class SetupError(Exception):
    pass

class PMDTool(Tool):
    name = 'PMD Source Code Analyzer'
    version = '0.1'
    description=("A Review Bot tool that runs PMD, "
                 "a rule-set based source code analyzer that identifies "
                 "potential problems")
    options = [
        {
            'name': 'markdown',
            'field_type': 'django.forms.BooleanField',
            'default': False,
            'field_options': {
                'label': 'Enable Markdown',
                'help_text': 'Allow ReviewBot to use Markdown in the '
                             'review body and for comments',
                'required': False,
            },
        },
        {
            'name': 'pmd_install_path',
            'field_type': 'django.forms.CharField',
            'default': '/opt/pmd/',
            'field_options': {
                'label': 'PMD installation path',
                'help_text': 'Path to the root directory where PMD is '
                             'installed',
            },
        },
    ]

    supported_file_types = ('.java', '.js')

    def check_dependencies(self):
        # We need java installed to run PMD
        return is_exe_in_path('java')

    def _setup(self, settings):
        self.use_markdown = settings['markdown']
        self.pmd_script_path = os.path.join(
            settings['pmd_install_path'], 'bin/run.sh')
        if not os.path.exists(self.pmd_script_path):
            raise SetupError("Could not find valid PMD executable at '%s'" %
                             self.pmd_script_path)

        logging.debug("Markdown is %s" %
                      ("enabled" if self.use_markdown else "disabled"))

    def handle_files(self, files):
        try:
            self._setup(self.settings)
        except SetupError as e:
            # Setup failed, we can't proceeed: mark every file as ignored,
            # log the error and return
            self.ignored_files.update(f.dest_file for f in files)
            logging.error(e.message)
            return
        super(PMDTool, self).handle_files(files)

    def handle_file(self, reviewed_file):
        if not any(reviewed_file.dest_file.lower().endswith(extension)
                   for extension in self.supported_file_types):
            # Ignore the file.
            return False

        logging.debug('PMD will start analyzing file %s' %
                      reviewed_file.dest_file)
        # Careful: get_patched_file_path() returns a different result each
        # time it's called, so we need to cache this value.
        try:
            temp_source_file_path = reviewed_file.get_patched_file_path()
        except APIError:
            logging.warn("Failed to get patched file for %s - ignoring file" %
                         reviewed_file.source_file)
            return False
        if not temp_source_file_path:
            return False

        pmd_result_file_path = self.run_pmd(temp_source_file_path)
        try:
            pmd_result = Result.from_xml(pmd_result_file_path)
            assert pmd_result.source_file_path == temp_source_file_path
            logging.info('PMD detected %s violations in file %s' %
                         (len(pmd_result.violations), reviewed_file.dest_file))
        except ValueError as e:
            logging.error(e.message)
            return False
        post_comments(
            pmd_result, reviewed_file, use_markdown=self.use_markdown)

        return True

    def run_pmd(self, source_file_path):
        pmd_result_file_path = make_tempfile(extension='.xml')
        output = execute(
            [
                self.pmd_script_path,
                'pmd',
                '-d', source_file_path,
                '-R', 'rulesets/internal/all-java.xml',
                '-f', 'xml',
                '-r', pmd_result_file_path
            ],
            split_lines=True,
            ignore_errors=True)
        return pmd_result_file_path

class Violation(namedtuple('Violation', 'rule text url first_line last_line')):
    __slots__ = ()
    @property
    def num_lines(self):
        return self.last_line - self.first_line + 1

class Result(object):

    def __init__(self, source_file_path, violations=None):
        self.source_file_path = source_file_path
        self.violations = violations or []


    @staticmethod
    def from_xml(xml_result_path):
        xml_tree = ElementTree.parse(xml_result_path)
        root = xml_tree.getroot()
        files = root.findall('file')
        if len(files) != 1:
            raise ValueError("PMD Result should contain results "
                             "for one and only one file")
        file_elem = files.pop()
        file_name = file_elem.attrib['name']
        result = Result(source_file_path=file_name)
        violations = file_elem.findall('violation')
        for violation in violations:
            first_line = int(violation.attrib['beginline'])
            last_line = int(violation.attrib['endline'])
            text = violation.text.strip()
            rule = violation.attrib['rule']
            url = violation.attrib['externalInfoUrl']
            result.violations.append(
                Violation(rule, text, url, first_line, last_line))
        return result





def post_comments(pmd_result, reviewed_file, use_markdown=False):
    for v in pmd_result.violations:
        if use_markdown:
            logging.debug("Posting markdown comment on line %s" % v.first_line)
            comment = "[%s](%s): %s" % (v.rule, v.url, v.text)
        else:
            logging.debug("Posting plain text comment on line %s" % v.first_line)
            comment = "%s: %s\n\nMore info: %s" % (v.rule, v.text, v.url)
        reviewed_file.comment(comment, v.first_line, v.num_lines)


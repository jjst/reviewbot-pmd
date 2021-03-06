import os
import logging
import subprocess
from collections import namedtuple
import xml.etree.ElementTree as ElementTree

from reviewbot.tools import Tool
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
    """
    An error occuring while setting up the extension and
    loading the settings.
    """
    pass


class PMDError(Exception):
    """
    An error occuring while trying to run the PMD command line tool.
    """
    pass


class Priority(object):
    """
    Priority of a violation, ranges from MIN to MAX.
    """
    MIN = 1
    MAX = 5
    values = range(MIN, MAX + 1)


class PMDTool(Tool):
    name = 'PMD Source Code Analyzer'
    version = '0.2.1'
    description = ("A Review Bot tool that runs PMD, "
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
                             'review body and for comments.',
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
                             'installed.',
            },
        },
        {
            'name': 'rulesets',
            'field_type': 'django.forms.CharField',
            'default': 'java-basic',
            'field_options': {
                'label': 'PMD rulesets',
                'help_text': 'Comma-separated list of rulesets PMD will use. '
                             'Either the name or the relative path of a '
                             'ruleset can be used if it is in the Java class '
                             'path. Otherwise, use the full path to the '
                             'ruleset file on the filesystem.'
            },
        },
        {
            'name': 'max_priority_for_issue',
            'field_type': 'django.forms.ChoiceField',
            'default': Priority.MIN,
            'field_options': {
                'label': 'Maximum priority for open issues',
                'help_text': 'This is the maximum rule priority a violation '
                             'must be for an issue to be opened if "Open '
                             'issues" is enabled. PMD violations have a '
                             'priority ranging from 1 to 5, with 1 being the '
                             'highest.',
                'choices': tuple((i, str(i)) for i in Priority.values),
                'required': False,
            },
        },
    ]

    supported_file_types = ('.java', '.js', '.xml', '.xsl')

    def check_dependencies(self):
        # We need java installed to run PMD
        return is_exe_in_path('java')

    def _setup(self, settings):
        self.use_markdown = settings['markdown']
        self.max_priority_for_issue = int(settings['max_priority_for_issue'])
        logging.debug("Will open issues for violations of priority %s or more"
                      % self.max_priority_for_issue)
        self.rulesets = set(settings['rulesets'].split(','))
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

        try:
            pmd_result_file_path = self.run_pmd(
                temp_source_file_path, self.rulesets)
        except PMDError as e:
            logging.error(e)
            return False
        try:
            pmd_result = Result.from_xml(pmd_result_file_path,
                                         temp_source_file_path)
            assert pmd_result.source_file_path == temp_source_file_path
            logging.info('PMD detected %s violations in file %s' %
                         (len(pmd_result.violations), reviewed_file.dest_file))
        except ValueError as e:
            logging.error(e.message)
            return False
        self.post_comments(
            pmd_result, reviewed_file, use_markdown=self.use_markdown)

        return True

    def run_pmd(self, source_file_path, rulesets):
        pmd_result_file_path = make_tempfile(extension='.xml')
        args = (
            self.pmd_script_path,
            'pmd',
            '-d', source_file_path,
            '-R', ','.join(rulesets),
            '-f', 'xml',
            '-r', pmd_result_file_path
        )
        process = subprocess.Popen(args,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        _, stderr = process.communicate()
        if stderr:
            raise PMDError("Error running PMD command line tool, "
                           "command output:\n" + stderr)
        return pmd_result_file_path

    def post_comments(self, pmd_result, reviewed_file, use_markdown=False):
        for v in Violation.group_consecutive(pmd_result.violations):
            if use_markdown:
                comment = "[%s](%s): %s" % (v.rule, v.url, v.text)
            else:
                comment = "%s: %s\n\nMore info: %s" % (v.rule, v.text, v.url)
            open_issue = (reviewed_file.review.settings['open_issues'] and
                          v.priority <= self.max_priority_for_issue)
            if open_issue:
                logging.debug("Opening issue for violation %s" % v.rule)
            reviewed_file.comment(
                comment, v.first_line, v.num_lines, issue=open_issue)

_BaseViolation = namedtuple(
    'Violation', 'rule priority text url first_line last_line')


class Violation(_BaseViolation):
    __slots__ = ()

    def combine(self, other_violation):
        """
        Combine 2 violations together if they can be.
        """
        if not self.is_consecutive(other_violation):
            raise ValueError("Cannot combine non-consecutive violations")
        first_line = min(self.first_line, other_violation.first_line)
        last_line = max(self.last_line, other_violation.last_line)
        return Violation(self.rule, self.priority, self.text, self.url,
                         first_line, last_line)

    @property
    def num_lines(self):
        return self.last_line - self.first_line + 1

    def is_consecutive(self, v):
        return (self.text == v.text and
                self.rule == v.rule and
                self.url == v.url and
                self.priority == v.priority and
                (self.first_line == v.last_line + 1 or
                 self.last_line + 1 == v.first_line))

    @staticmethod
    def group_consecutive(violations):
        if not violations:
            return []
        current_group = [violations[0]]
        groups = [current_group]
        for i, v in enumerate(violations[1:]):
            if v.is_consecutive(violations[i]):
                current_group.append(v)
            else:
                current_group = [v]
                groups.append(current_group)
        def combine_violations(violations):
            return reduce(lambda v1, v2: v1.combine(v2), violations)
        return [combine_violations(violation_group)
                for violation_group in groups]


class Result(object):

    def __init__(self, source_file_path, violations=None):
        self.source_file_path = source_file_path
        self.violations = violations or []

    @staticmethod
    def from_xml(xml_result_path, source_file_path):
        xml_tree = ElementTree.parse(xml_result_path)
        root = xml_tree.getroot()
        files = root.findall('file')
        if len(files) > 1:
            raise ValueError("PMD Result should contain results "
                             "for one and only one file")
        elif not files:
            # This means that there were no violations in this file
            return Result(source_file_path)
        file_elem = files.pop()
        file_name = file_elem.attrib['name']
        if file_name != source_file_path:
            raise ValueError("PMD result does not contain results for file %s"
                             % source_file_path)
        result = Result(source_file_path=file_name)
        violations = file_elem.findall('violation')
        for violation in violations:
            first_line = int(violation.attrib['beginline'])
            last_line = int(violation.attrib['endline'])
            text = violation.text.strip()
            rule = violation.attrib['rule']
            priority = int(violation.attrib['priority'])
            url = violation.attrib['externalInfoUrl']
            result.violations.append(
                Violation(rule, priority, text, url, first_line, last_line))
        return result

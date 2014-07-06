import os
import tempfile
import logging
from collections import namedtuple
import xml.etree.ElementTree as ElementTree

from reviewbot.tools import Tool
from reviewbot.tools.process import execute
from reviewbot.utils import is_exe_in_path
from reviewbot.processing.filesystem import make_tempfile

from rbtools.api.request import APIError

class PMDTool(Tool):
    name = 'PMD Source Code Analyzer'
    version = '0.1'
    description=("A Review Bot tool that runs PMD, "
                 "a rule-set based source code analyzer that identifies "
                 "potential problems")
    options = [
        {
            'name': 'debug',
            'field_type': 'django.forms.BooleanField',
            'default': False,
            'field_options': {
                'label': 'Debug Enabled',
                'help_text': 'Allow debugger statements',
                'required': False,
            },
        },
    ]

    supported_file_types = ('.java', '.js')

    def check_dependencies(self):
        return is_exe_in_path('java')

    def handle_file(self, reviewed_file):
        if not any(reviewed_file.dest_file.lower().endswith(extension)
                   for extension in self.supported_file_types):
            # Ignore the file.
            return False

        logging.debug('PMD will start analyzing file %s' % reviewed_file.dest_file)
        # Careful: get_patched_file_path() returns a different result each
        # time it's called, so we need to cache this value.
        try:
            temp_source_file_path = reviewed_file.get_patched_file_path()
        except APIError:
            return False
        if not temp_source_file_path:
            return False

        pmd_result_file_path = run_pmd(temp_source_file_path)
        try:
            pmd_result = Result.from_xml(
                pmd_result_file_path,
                temp_source_file_path)
            logging.info('PMD detected %s violations in file %s' %
                         (len(pmd_result.violations), reviewed_file.dest_file))
        except ValueError as e:
            logging.error(e.message)
            return False
        post_comments(pmd_result, reviewed_file)

        return True

class Violation(namedtuple('Violation', 'text first_line last_line')):
    __slots__ = ()
    @property
    def num_lines(self):
        return self.last_line - self.first_line + 1

class Result(object):

    def __init__(self, source_file_path, results_file_path, violations=None):
        self.source_file_path = source_file_path
        self.results_file_path = results_file_path
        self.violations = violations or []


    @staticmethod
    def from_xml(xml_result_path, source_file_path):
        xml_tree = ElementTree.parse(xml_result_path)
        root = xml_tree.getroot()
        files = root.findall('file')
        if len(files) != 1:
            raise ValueError("PMD Result should contain results "
                             "for one and only one file")
        file_elem = files.pop()
        name = file_elem.attrib['name']
        if name != source_file_path:
            raise ValueError("PMD Result doesn't contain result for file '%s' "
                             "but for file '%s'" % (source_file_path, name))
        violations = file_elem.findall('violation')
        result = Result(source_file_path, xml_result_path)
        for violation in violations:
            first_line = int(violation.attrib['beginline'])
            last_line = int(violation.attrib['endline'])
            text = violation.text.strip()
            result.violations.append(Violation(text, first_line, last_line))
        return result



def run_pmd(source_file_path):
    pmd_result_file_path = make_tempfile(extension='.xml')
    output = execute(
        [
            'pmdtools',
            'pmd',
            '-d', source_file_path,
            '-R', 'rulesets/internal/all-java.xml',
            '-f', 'xml',
            '-r', pmd_result_file_path
        ],
        split_lines=True,
        ignore_errors=True)
    return pmd_result_file_path


def post_comments(pmd_result, reviewed_file):
    for v in pmd_result.violations:
        reviewed_file.comment(v.text, v.first_line, v.num_lines)


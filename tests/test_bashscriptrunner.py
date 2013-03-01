
import unittest
import tempfile
import os

from opencenteragent.plugins.lib.bashscriptrunner import \
    BashScriptRunner, BashExecTimer
from opencenteragent.exceptions import BashScriptTimeoutFail
from opencenteragent.exceptions import BashScriptTimeout
import logging
import stat


class TestBashScriptRunner(unittest.TestCase):

    def setUp(self):
        self.log = logging.getLogger('opencenter.output')

    def write_script(self,script_string):
        tmp = open(tempfile.mktemp(), 'w')
        tmp.write(script_string)
        tmp.close()
        os.chmod(tmp.name, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        return os.path.split(tmp.name)

    def test_script_succeed(self):
        try:
            script_path, script_name = \
                self.write_script('#! /bin/bash'
                                  '\necho noop')

            bsr = BashScriptRunner(script_path=[script_path],
                                   log=self.log)

            response = bsr.run(script_name)
        finally:
            try:
                os.path.remove(os.join(script_path, script_name))
            except:
                pass

    def test_script_timeout(self):
        try:
            script_path, script_name = \
                self.write_script('#!/bin/bash'
                                  '\n top -l 0 >/dev/null')

            #The above script should run top infinitely, in order to
            #prompt a timeout.

            bsr = BashScriptRunner(script_path=[script_path],
                                   log=self.log)

            with self.assertRaises(BashScriptTimeout):
                bsr.run(script_name, timeout=2)
        finally:
            try:
                os.path.remove(os.join(script_path, script_name))
                pass
            except:
                pass


import unittest
import tempfile
import os

from opencenteragent.plugins.lib.bashscriptrunner import \
    BashScriptRunner, BashExecTimer
from opencenteragent.exceptions import BashScriptTimeoutFail
from opencenteragent.exceptions import BashScriptTimeout

class TestBashScriptRunner(unittest.TestCase):

    def test_script_succeed(self):
        try:
            tmp = open(tempfile.mktemp(), 'w')
            tmp.write('#! /bin/bash'
                      '\necho -e "test_script_succeed\0\0'
                      'running $(date)\0" '
                      '1>&3')
            tmp.close()
            script_path, script_name = os.path.split(tmp.name)
            bsr = BashScriptRunner(script_path=[script_path], timeout=5)
            response = bsr.run(script_name)
            print "response: ", response
        finally:
            try:
                os.path.remove(tmp.name)
            except:
                pass

    def test_script_timeout(self):
        try:
            bsr = BashScriptRunner(timeout=5)
            tmp = open(tempfile.mktemp(), 'w')
            tmp.write('#! /bin/bash'
                      '\nsleep 120'
                      '\necho -e "test_script_timeout\0\0'
                      'running $(date)\0" 2>&3')
            tmp.close()
            self.assertRaises(BashScriptTimeout, bsr.run, tmp.name)
        finally:
            try:
                os.path.remove(tmp.name)
            except:
                pass



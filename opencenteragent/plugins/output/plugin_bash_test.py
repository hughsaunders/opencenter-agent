#!/usr/bin/env python
#
# Copyright 2012, Rackspace US, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

name = 'bash_test_plugin'

from bashscriptrunner import BashScriptRunner
import tempfile


def setup(config={}):
    LOG.debug('Doing setup in plugin_bash_test.py')
    register_action('bash_timeout_test', handle_bash_timeout_test)


def handle_bash_timeout_test(input_data):
    payload = input_data['payload']
    action = input_data['action']

    iterations = payload['iterations']
    timeout = payload['timeout']

    print 'Handling action "%s" for payload "%s"' % (action, payload)
    script_file = open(tempfile.mktemp(), 'w')
    script_file.write('#!/usr/bin/env bash'
                      'top -l %s || top -d 1 -b -n %s' % (iterations,
                                                          iterations))
    script_file.close()
    script = BashScriptRunner(timeout_default=timeout)
    result = script.run(script_file.name)

    return {'result_code': result['result_code'],
            'result_str': result['result_string'],
            'result_data': None}

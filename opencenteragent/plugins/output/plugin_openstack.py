#!/usr/bin/env python
#               OpenCenter(TM) is Copyright 2013 by Rackspace US, Inc.
##############################################################################
#
# OpenCenter is licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.  This
# version of OpenCenter includes Rackspace trademarks and logos, and in
# accordance with Section 6 of the License, the provision of commercial
# support services in conjunction with a version of OpenCenter which includes
# Rackspace trademarks and logos is prohibited.  OpenCenter source code and
# details are available at: # https://github.com/rcbops/opencenter or upon
# written request.
#
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0 and a copy, including this
# notice, is available in the LICENSE file accompanying this software.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the # specific language governing permissions and limitations
# under the License.
#
##############################################################################
#

import sys
import os
from bashscriptrunner import BashScriptRunner
import json
name = 'openstack'


def setup(config={}):
    LOG.debug('doing setup for openstack handler')
    if not 'bash_path' in global_config['main']:
        LOG.error("bash_path not configured")
        raise ValueError("Expecting bash_path in configuration")
    script_path = [os.path.join(global_config['main']['bash_path'], name)]
    env = {"OPENCENTER_BASH_DIR": global_config['main']['bash_path']}
    script = BashScriptRunner(script_path=script_path, log=LOG,
                              environment=env)
    openstack = OpenStackThing(script, config)
    register_action('openstack_upload_images', openstack.dispatch,
                    timeout=300)
    register_action('openstack_disable_host', openstack.dispatch,
                    timeout=30)
    register_action('openstack_enable_host', openstack.dispatch,
                    timeout=30)
    register_action('openstack_evacuate_host', openstack.dispatch,
                    timeout=1200)


def get_environment(required, optional, payload):
    env = dict([(k, v) for k, v in payload.iteritems()
                if k in required + optional])
    for r in required:
        if not r in env:
            return False, {'result_code': 22,
                           'result_str': 'Bad Request (missing %s)' % r,
                           'result_data': None}
    return True, env


def retval(result_code, result_str, result_data):
    print "retval: returning %d %s %s" % (result_code, result_str, result_data)
    return {'result_code': result_code,
            'result_str': result_str,
            'result_data': result_data}


class OpenStackThing(object):
    def __init__(self, script, config):
        self.script = script
        self.config = config

    def openstack_upload_images(self, input_data):
        payload = input_data['payload']
        action = input_data['action']
        required = []
        optional = []
        good, env = get_environment(required, optional, payload)
        if not good:
            return env
        return self.script.run_env("upload_images.sh", env, "")

    def openstack_enable_host(self, input_data):
        payload = input_data['payload']
        action = input_data['action']
        required = []
        optional = []
        good, env = get_environment(required, optional, payload)
        if not good:
            return env
        return self.script.run_env("enable_host.sh", env, "")

    def openstack_disable_host(self, input_data):
        payload = input_data['payload']
        action = input_data['action']
        required = []
        optional = []
        good, env = get_environment(required, optional, payload)
        if not good:
            return env
        return self.script.run_env("disable_host.sh", env, "")

    def openstack_evacuate_host(self, input_data):
        payload = input_data['payload']
        action = input_data['action']
        required = []
        optional = []
        good, env = get_environment(required, optional, payload)
        if not good:
            return env
        return self.script.run_env("evacuate_host.sh", env, "")

    def dispatch(self, input_data):
        self.script.log = LOG
        f = getattr(self, input_data['action'])
        if callable(f):
            return f(input_data)

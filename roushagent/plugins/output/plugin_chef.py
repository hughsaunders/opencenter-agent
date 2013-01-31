#!/usr/bin/env python

import netifaces

from bashscriptrunner import BashScriptRunner
import os

name = 'chef'


def setup(config={}):
    LOG.debug('Doing setup in plugin_chef.py using bash_path %s' %
              global_config['main']['bash_path'])
    if not 'bash_path' in global_config['main']:
        LOG.error('bash_path is not set')
        raise ValueError('bash_path not set')
    script_path = [os.path.join(global_config['main']['bash_path'], name)]
    env = {'ROUSH_BASH_DIR': global_config['main']['bash_path']}
    script = BashScriptRunner(script_path=script_path, log=LOG,
                              environment=env)
    chef = ChefThing(script, config)
    register_action(
        'install_chef', chef.dispatch, [],
        ['facts.backends := union(facts.backends, "chef-client")'],
        {'chef_server': {'type': 'interface',
                         'name': 'chef-server',
                         'required': True},
         'CHEF_SERVER_URL': {'type': 'evaluated',
                             'expression': 'nodes.{chef_serv'
                             'er}.facts.chef_server_uri'},
         'CHEF_SERVER_PEM': {'type': 'evaluated',
                             'expression': 'nodes.{chef_'
                             'server}.facts.chef_server_pem'}})
    register_action('run_chef', chef.dispatch)
    register_action('install_chef_server', chef.dispatch)
    register_action('get_chef_info', chef.dispatch)
    register_action('download_cookbooks', chef.dispatch)
    register_action('uninstall_chef', chef.dispatch)
    register_action('rollback_install_chef', chef.dispatch)
    register_action('update_cookbooks', chef.dispatch)


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
    return {'result_code': result_code,
            'result_str': result_str,
            'result_data': result_data}


def success(result_str='success', result_data=None):
    return retval(0, result_str, result_data)


class ChefThing(object):
    def __init__(self, script, config):
        self.script = script
        self.config = config

    def install_chef(self, input_data):
        payload = input_data['payload']
        action = input_data['action']
        required = ['CHEF_SERVER_URL', 'CHEF_SERVER_PEM']
        optional = ['CHEF_RUNLIST', 'CHEF_ENVIRONMENT', 'CHEF_VALIDATION_NAME']
        good, env = get_environment(required, optional, payload)
        if not good:
            return env
        return self.script.run_env('install-chef.sh', env, '')

    def rollback_install_chef(self, input_data):
        return self.uninstall_chef(input_data)

    def uninstall_chef(self, input_data):
        return self.script.run('uninstall-chef.sh')

    def run_chef(self, input_data):
        LOG.info('Running chef')
        payload = input_data['payload']
        action = input_data['action']
        return self.script.run('run-chef.sh')

    def install_chef_server(self, input_data):
        payload = input_data['payload']
        action = input_data['action']
        good, env = get_environment([],
                                    ['CHEF_URL', 'CHEF_WEBUI_PASSWORD'],
                                    payload)
        if not good:
            return env
        return self.script.run_env('install-chef-server.sh', env, '')

    def download_cookbooks(self, input_data):
        payload = input_data['payload']
        action = input_data['action']
        good, env = get_environment([],
                                    ['CHEF_REPO_DIR', 'CHEF_REPO',
                                     'CHEF_REPO_BRANCH'],
                                    payload)

        if not good:
            return env
        return self.script.run_env('cookbook-download.sh', env, '')

    def update_cookbooks(self, input_data):
        return self.download_cookbooks(input_data)

    def get_chef_info(self, input_data):
        pem = ''
        ipaddr = ''

        try:
            with open('/etc/chef/validation.pem', 'r') as f:
                pem = f.read()
        except IOError as e:
            return retval(e.errno, str(e), None)

        try:
            ipaddr = netifaces.ifaddresses('eth0')[
                netifaces.AF_INET][0]['addr']
        except Exception as e:
            return retval(e.errno, str(e), None)

        return retval(0, 'success',
                      {'validation_pem': pem,
                       'chef_endpoint': 'http://%s:4000' % ipaddr})

    def dispatch(self, input_data):
        self.script.log = LOG
        f = getattr(self, input_data['action'])
        if callable(f):
            return f(input_data)

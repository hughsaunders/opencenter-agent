
import fcntl
import os
import string
import threading
import psutil
import signal
import time
from opencenteragent.exceptions import BashScriptTimeoutFail
from opencenteragent.exceptions import BashScriptTimeout


def name_mangle(s, prefix=""):
    # we only support upper case variables and as a convenience convert
    # - to _, as - is not valid in bash variables.
    prefix = prefix.upper()
    r = s.upper().replace("-", "_")
    # first character must be _ or alphabet
    if not r[0] == '_' and not (r[0].isalpha() and len(prefix) == 0):
        r = "".join(["_", r])
    # rest of the characters must be alphanumeric or _
    valid = string.digits + string.ascii_uppercase + "_"
    r = "".join([l for l in r if l in valid])
    if len(r) >= 1:
        #valid r, prefix it unless it is already prefixed
        return r if r.find(prefix) == 0 else prefix + r
    raise ValueError("Failed to convert %s to valid bash identifier" % s)


def posix_escape(s):
    #The only special character inside of a ' is ', which terminates
    #the '.  We will surround s with single quotes.  If we encounter a
    #single quote inside of s, we need to close with ',
    #escape the valid single quote in s with "'", then reopen our enclosure
    #with '.
    return "'%s'" % (s.replace("'", "'\"'\"'"))


def find_script(script, script_path):
    for path in script_path:
        filename = os.path.join(path, script)
        #allow directory to be a symlink, but not scripts
        if os.path.exists(filename) and \
            os.path.dirname(os.path.realpath(filename)) == \
                os.path.realpath(path):
            return filename
    return None


class BashScriptRunner(object):
    def __init__(self, script_path=["scripts"],
                 environment=None,
                 log=None,
                 timeout=None):
        self.script_path = script_path
        self.environment = environment or {"PATH":
                                           "/usr/sbin:/usr/bin:/sbin:/bin"}
        self.log = log

        # get a default timeout, first check args, then config file,
        # then hardcoded value
        if timeout is not None:
            self.timeout = timeout
        elif  'global_config' in globals():
            global_config = globals()['global_config']
            if 'bash_timeout' in global_config['main']:
                self.timeout = \
                    int(global_config['main']['bash_timeout'])
        else:
            self.timeout = 600


    def run(self, script, *args, **kwargs):
        return self.run_env(script, {}, "RCB", *args, **kwargs)

    def run_env(self, script, environment, prefix, *args, **kwargs):
        if 'timeout' in kwargs:
            timeout = int(kwargs['timeout'])
        else:
            timeout = self.timeout
        env = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"}
        env.update(self.environment)
        env.update(dict([(name_mangle(k, prefix), v)
                         for k, v in environment.iteritems()]))
        response = {"response": {}}
        path = find_script(script, self.script_path)

        if path is None:
            response['result_code'] = 127
            response['result_str'] = "%s not found in %s" % (
                script, ":".join(self.script_path))
            response['result_data'] = {"script": script}
            return response

        to_run = [path] + list(args)
        try:
            fh = [h for h in self.log.handlers if hasattr(h, "stream") and
                  h.stream.fileno() > 2][0].stream.fileno()
        except IndexError:
            fh = 2
        #first pass, never use bash to run things
        c = BashExec(to_run,
                     stdout=fh,
                     stderr=fh,
                     env=env,
                     timeout=timeout)
        response['result_data'] = {"script": path}
        ret_code, outputs = c.wait()
        response['result_data'].update(outputs)
        response['result_code'] = ret_code
        # not os.strerror... bash return values are not posix errnos
        response['result_str'] = 'Success' if ret_code == 0 else \
            'Failure'
        return response


class BashExecTimer(threading.Thread):
    # Exceptions must be raised in the main thread not the timer thread
    # so these status codes are used to tell the main thread which
    # exception if any should be raised.
    RUNNING = 0
    EXITED = 1
    KILLED = 2
    KILL_FAILED = 3

    def __init__(self, timeout, child_pid):
        super(BashExecTimer, self).__init__()
        self.timeout = timeout
        self.pid = child_pid
        self.status = BashExecTimer.RUNNING

    def pid_exists(self, pid=None):
        if pid is None:
            pid = self.pid
        pid_list = [p.pid for p in psutil.get_process_list()]
        return pid in pid_list

    def get_children(self):
        """the process we forked to run the script, may have created
        child processes. We must find all of those in order to kill
        them all if a timeout occurs"""

        pid_list = psutil.get_process_list()

        child_pids = set([self.pid])

        while True:
            new_pids = []

            for pid in pid_list:
                if pid.ppid in child_pids and pid.pid not in child_pids:
                    new_pids.append(pid.pid)

            child_pids = child_pids.union(new_pids)

            if not new_pids:
                #no new pids added to the list, break
                break

        return child_pids

    def run(self):

        for _ in range(self.timeout):
            if self.pid_exists():
                time.sleep(1)
            else:
                self.status = BashExecTimer.EXITED
                return
        try:
            children = self.get_children()

            for child in children:
                os.kill(child, signal.SIGTERM)

            time.sleep(1)

            for child in children:
                if self.pid_exists(child):
                    os.kill(self.pid, signal.SIGKILL)
        finally:
            if True in [self.pid_exists(p) for p in children]:
                self.status = BashExecTimer.KILL_FAILED
            else:
                self.status = BashExecTimer.KILLED


class BashExec(object):
    def __init__(self, cmd, stdin=None, stdout=None, stderr=None,
                 env=None, timeout=600):
        self.env = env
        self.pipe_read, self.pipe_write = os.pipe()
        self.timer_thread = None
        self.timeout = timeout
        self.cmd = cmd

        pid = os.fork()
        if pid != 0:
            # parent process
            self.child_pid = pid
            print "child_pid", pid
            os.close(self.pipe_write)
            self.timer_thread = BashExecTimer(self.timeout, pid)
            self.timer_thread.start()
        else:
            # child process
            os.close(self.pipe_read)
            if stdin is None:
                f = open("/dev/null", "r")
                stdin = f.fileno()
                os.dup2(stdin, os.sys.stdin.fileno())
            if stdout is not None:
                os.dup2(stdout, os.sys.stdout.fileno())
            if stderr is not None:
                os.dup2(stderr, os.sys.stderr.fileno())
            # FD 3 will be for communicating output variables
            os.dup2(self.pipe_write, 3)
            os.close(self.pipe_write)
            os.execvpe(cmd[0], cmd, env)

    def wait(self, output_variables=None):
        if output_variables is None:
            output_variables = []

        # Wait for process to run
        status_code = os.waitpid(self.child_pid, 0)[1]
        ret_code = status_code >> 8

        fl = fcntl.fcntl(self.pipe_read, fcntl.F_GETFL)
        fcntl.fcntl(self.pipe_read, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        output_str = ""
        while True:
            try:
                n = os.read(self.pipe_read, 1024)
            except OSError:  # EWOULDBLOCK/EAGAIN
                break

            output_str += n
            if n == "":
                break

            #break exit loop if we have run out of time.
            if not self.timer_thread.is_alive():
                break

        #can't reliably read thread attrs until it has died
        self.timer_thread.join()
        if self.timer_thread.status == BashExecTimer.KILLED:
            raise BashScriptTimeout
        elif self.timer_thread.status == BashExecTimer.KILL_FAILED:
            raise BashScriptTimeoutFail

        outputs = {"consequences": []}
        if len(output_str) > 0:
            stuff = output_str.strip("\0").split("\0")
            #output is in the form of type\0key\0value\0
            while(len(stuff) > 0):
                if len(stuff) % 3 == 0:
                    # facts and attrs have convenience functions and
                    # may be returned as key/value pairs.  The format
                    # is type\0key\0value\0.  Consequences may be
                    # returned directly using a format
                    # consequence\0\0consequence_string\0.
                    vtype, key, value = stuff[0:3]
                    stuff = stuff[3:]
                    if vtype == "consequences":
                        outputs['consequences'].append(value)
                    else:
                        c = '%s.%s := %s' % (vtype, key, value)
                        outputs['consequences'].append(c)
                else:
                    break

        return ret_code, outputs

#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2017 Red Hat, Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#

# based on ansible/lib/ansible/plugins/callback/logstash.py

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
import os
import pprint
import re


from collections import defaultdict
from datetime import datetime

from ansible.plugins.callback import CallbackBase

from dateutil import tz

__metaclass__ = type


DOCUMENTATION = '''
    callback: ovirt_logger
    type: notification
    short_description: Logs to file also without utils/display.py
    description:
      - Logs to file also without utils/display.py, see
        https://github.com/ansible/ansible/issues/25761#issuecomment-324890228
    requirements:
      - whitelisting in configuration
    options:
      log file:
        description: log file
        env:
          - name: HE_ANSIBLE_LOG_PATH
        default: None
      filtered tokens var:
        description:
          - The name of a variable, that contains a list of tokes
          - These tokens are filtered out in the log
        env:
          - name: HE_ANSIBLE_LOG_FILTERED_TOKENS_VAR
        default: he_filtered_tokens
      filtered regular expressions var:
        description: >
          The name of a variable, that contains a list of regular expressions.
          The expressions must each include a group called 'filter'.
          Filter out content of the group 'filter', on matches.
          Example: 'a(?P<filter>.*)b' will cause 'axyzb' to be replaced
          with: 'a**FILTERED**b'.
        env:
          - name: HE_ANSIBLE_LOG_FILTERED_TOKENS_RE_VAR
        default: he_filtered_tokens_re
      filtered variables var:
        description:
          - The name of a variable, that contains a list of variable names
          - The content of these variables is filtered out in the log
        env:
          - name: HE_ANSIBLE_LOG_FILTERED_TOKENS_VARS_VAR
        default: he_filtered_tokens_vars
'''


class CallbackModule(CallbackBase):
    """
    ansible ovirt_logger callback plugin
    This plugin makes use of the following environment variables:
        HE_ANSIBLE_LOG_PATH   (mandatory): defaults to None
    """

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'ovirt_logger'
    CALLBACK_NEEDS_WHITELIST = True

    # Copied from otopi:src/plugins/otopi/core/log.py
    # and changed a bit
    class _MyFormatter(logging.Formatter):
        """Filter strings from log entries."""

        def _get_re_objects(self, regexps):
            for exp in regexps:
                if exp not in self._re_objects:
                    obj = re.compile(exp)
                    if 'filter' in obj.groupindex:
                        self._re_objects[exp] = obj
                    else:
                        # TODO consider log that we ignored an RE because
                        # it has no group 'filter', but not sure this is
                        # a good idea (log from inside a formatter).
                        pass
            return self._re_objects.values()

        def _filter(self, content, tokens, regexps):
            """
            Filter overlapping tokens within content.
            regexps is a list of regular expressions, each having a group named
            'filter'. The content of this group will be filtered.

            Examples:
            content=abcabca, tokens=('abca')
            content=aaabbbccc, tokens=('bbb', 'abbba')
            content=aaaababbbb, tokens=('aaab', 'aaa', 'bbb')
            content=a BS some secret ES b, regexps=('BS (?P<filter>.*) ES')
            """

            def _insertFilter(content, begin, end):
                return content[:begin] + '**FILTERED**' + content[end:]

            tofilter = []

            for token in tokens:
                if token not in (None, ''):
                    index = -1
                    while True:
                        index = content.find(token, index+1)
                        if index == -1:
                            break
                        tofilter.append((index, index + len(token)))

            for reobj in self._get_re_objects(regexps):
                if reobj is not None:
                    index = -1
                    while True:
                        matchobj = reobj.search(content, index)
                        if matchobj is None:
                            break
                        index = matchobj.start('filter')
                        tofilter.append((index, matchobj.end('filter')))

            tofilter = sorted(tofilter, key=lambda e: e[1], reverse=True)
            begin = None
            end = None
            for entry in tofilter:
                if begin is None or entry[1] < begin:
                    if begin is not None:
                        content = _insertFilter(content, begin, end)
                    begin = entry[0]
                    end = entry[1]
                elif entry[0] < begin:
                    begin = entry[0]
            else:
                if begin is not None:
                    content = _insertFilter(content, begin, end)

            return content

        def __init__(
            self,
            fmt=None,
            datefmt=None,
            vars_cache=None,
            filtered_tokens_var=None,
            filtered_tokens_re_var=None,
            filtered_vars_var=None,
        ):
            logging.Formatter.__init__(self, fmt=fmt, datefmt=datefmt)
            self._vars_cache = vars_cache
            self._filtered_tokens_var = filtered_tokens_var
            self._filtered_tokens_re_var = filtered_tokens_re_var
            self._filtered_vars_var = filtered_vars_var
            self._re_objects = {}

        def converter(self, timestamp):
            return datetime.fromtimestamp(
                timestamp,
                tz.tzlocal()
            )

        def formatTime(self, record, datefmt=None):
            ct = self.converter(record.created)
            if datefmt:
                s = ct.strftime(datefmt, ct)
            else:
                s = "%s,%03d%s" % (
                    ct.strftime('%Y-%m-%d %H:%M:%S'),
                    record.msecs,
                    ct.strftime('%z')
                )
            return s

        def _get_filtered_tokens(self):
            res = []
            for host, hostvars in self._vars_cache.items():
                res.extend(hostvars.get(self._filtered_tokens_var, []))
                res.extend([
                    hostvars.get(k, None)
                    for k in
                    hostvars.get(self._filtered_vars_var, [])
                ])
            return res

        def _get_filtered_regexps(self):
            res = []
            for hostvars in self._vars_cache.values():
                res.extend(
                    hostvars.get(self._filtered_tokens_re_var, [])
                )
            return res

        def format(self, record):
            return self._filter(
                content=logging.Formatter.format(self, record),
                tokens=self._get_filtered_tokens(),
                regexps=self._get_filtered_regexps()
            )

    _logger = None
    _handler = None

    def _setup_logging(self):
        if CallbackModule._logger is None:
            # ansible instantiates callbacks twice in load_callbacks.
            # Setup logging only once, or we get too much logging...
            CallbackModule._handler = logging.StreamHandler(self.handle)
            CallbackModule._handler.setLevel(logging.DEBUG)
            CallbackModule._handler.setFormatter(self._MyFormatter(
                fmt='%(asctime)s %(levelname)s %(message)s',
                vars_cache=self._vars_cache,
                filtered_tokens_var=self._filtered_tokens_var,
                filtered_tokens_re_var=self._filtered_tokens_re_var,
                filtered_vars_var=self._filtered_tokens_vars_var,
            ))
            CallbackModule._logger = logging.getLogger(
                "ovirt-hosted-engine-setup-ansible"
            )
            CallbackModule._logger.addHandler(CallbackModule._handler)
            CallbackModule._logger.setLevel(logging.DEBUG)
        self.logger = CallbackModule._logger

    def _collect_vars_changes(self, hostname, newvars):
        res = []
        for k, v in newvars.items():
            if (
                hostname not in self._vars_cache or
                k not in self._vars_cache[hostname] or
                str(v) != str(self._vars_cache[hostname][k]) or
                not isinstance(v, type(self._vars_cache[hostname][k]))
            ):
                res.append(
                    'var changed: host "{h}" var "{k}" type "{t}" '
                    'value: "{v}"'.format(
                        h=hostname,
                        k=k,
                        t=type(v),
                        v=str(v),
                    )
                )
        return res

    def _update_vars_cache(self):
        vars_changes = []
        if self.varmgr:
            for host in self.varmgr._inventory.get_hosts():
                vars_changes.extend(
                    self._collect_vars_changes(
                        str(host),
                        self.varmgr.get_vars(host=host)
                    )
                )
                self._vars_cache[str(host)].update(
                    self.varmgr.get_vars(host=host)
                )
                if self.play:
                    vars_changes.extend(
                        self._collect_vars_changes(
                            str(host),
                            self.varmgr.get_vars(play=self.play, host=host)
                        )
                    )
                    self._vars_cache[str(host)].update(
                        self.varmgr.get_vars(play=self.play, host=host)
                    )
            # Log changes after applying them, so that our filter handles
            # changes before we log them.
            for line in vars_changes:
                self.logger.debug(line)

    def dump_obj(self, obj):
        name = repr(obj)[:100]
        return '\n'.join([
            'type: %s' % type(obj),
            'str: %s' % str(obj)[:300],
            'repr: %s' % repr(obj)[:300],
            'dir: %s' % dir(obj),
            'pprint: %s' % pprint.pformat(obj)[:300],
        ] + [
            '%s.%s: %s' % (
                name,
                attr,
                pprint.pformat(getattr(obj, attr))
            )
            for attr in dir(obj)
            if not callable(getattr(obj, attr))
        ])

    def __init__(self):
        super(CallbackModule, self).__init__()

        logFileName = os.getenv('HE_ANSIBLE_LOG_PATH', None)
        self._filtered_tokens_var = os.getenv(
            'HE_ANSIBLE_LOG_FILTERED_TOKENS_VAR',
            'he_filtered_tokens'
        )
        self._filtered_tokens_re_var = os.getenv(
            'HE_ANSIBLE_LOG_FILTERED_TOKENS_RE_VAR',
            'he_filtered_tokens_re'
        )
        self._filtered_tokens_vars_var = os.getenv(
            'HE_ANSIBLE_LOG_FILTERED_TOKENS_VARS_VAR',
            'he_filtered_tokens_vars'
        )
        self.playbook = None
        self.play = None
        self.varmgr = None
        self._vars_cache = defaultdict(dict)

        if not logFileName:
            self.disabled = True
            self._display.warning(
                "No log file specified with HE_ANSIBLE_LOG_PATH"
            )
        else:
            try:
                self.handle = open(
                    logFileName,
                    mode='a',
                    buffering=1,
                )
            except IOError:
                self.handle = open(
                    os.devnull,
                    mode='a',
                    buffering=1,
                )
            self._setup_logging()

        self.start_time = datetime.utcnow()
        self.errors = 0

    def v2_playbook_on_start(self, playbook):
        self.playbook = playbook
        data = {
            'status': "OK",
            'ansible_type': "start",
            'ansible_playbook': self.playbook._file_name,
        }
        self.logger.info("ansible start playbook %s", self.playbook._file_name)
        self.logger.debug("ansible start %s" % data)

    def v2_playbook_on_stats(self, stats):
        end_time = datetime.utcnow()
        runtime = end_time - self.start_time
        summarize_stat = {}
        for host in stats.processed.keys():
            summarize_stat[host] = stats.summarize(host)

        if self.errors == 0:
            status = "OK"
        else:
            status = "FAILED"

        data = {
            'status': status,
            'ansible_type': "finish",
            'ansible_playbook': self.playbook,
            'ansible_playbook_duration': runtime.total_seconds(),
            'ansible_result': self.dump_obj(summarize_stat),
        }
        self.logger.info("ansible stats %s " % data)

    def v2_runner_on_ok(self, result, **kwargs):
        self._update_vars_cache()
        data = {
            'status': "OK",
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'ansible_task': result._task,
        }
        self.logger.info("ansible ok %s " % data)
        self.logger.info(
            "ansible ok result._result %s " %
            self.dump_obj(result._result)
        )

    def v2_runner_on_skipped(self, result, **kwargs):
        self._update_vars_cache()
        data = {
            'status': "SKIPPED",
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_task': result._task,
            'ansible_host': result._host.name
        }
        self.logger.info("ansible skipped %s" % data)

    def v2_playbook_on_import_for_host(self, result, imported_file):
        self._update_vars_cache()
        data = {
            'status': "IMPORTED",
            'ansible_type': "import",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'imported_file': imported_file
        }
        self.logger.info("ansible import %s" % data)

    def v2_playbook_on_not_import_for_host(self, result, missing_file):
        self._update_vars_cache()
        data = {
            'status': "NOT IMPORTED",
            'ansible_type': "import",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'missing_file': missing_file
        }
        self.logger.info("ansible import %s" % data)

    def v2_runner_on_failed(self, result, **kwargs):
        self._update_vars_cache()
        data = {
            'status': "FAILED",
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'ansible_task': result._task,
            'ansible_result': self.dump_obj(result._result)
        }
        self.errors += 1
        self.logger.error("ansible failed %s" % data)

    def v2_runner_on_unreachable(self, result, **kwargs):
        self._update_vars_cache()
        data = {
            'status': "UNREACHABLE",
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'ansible_task': result._task,
            'ansible_result': self.dump_obj(result._result)
        }
        self.logger.error("ansible unreachable %s" % data)

    def v2_runner_on_async_failed(self, result, **kwargs):
        self._update_vars_cache()
        data = {
            'status': "FAILED",
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'ansible_task': result._task,
            'ansible_result': self.dump_obj(result._result)
        }
        self.errors += 1
        self.logger.error("ansible async %s" % data)

    def v2_playbook_on_play_start(self, play):
        self.play = play
        self.varmgr = self.play.get_variable_manager()
        data = {
            'status': "OK",
            'ansible_type': "play start",
            'ansible_play': self.play.name,
        }
        self.logger.info("ansible play start %s" % data)

    def v2_on_any(self, *args, **kwargs):
        self.logger.debug("ansible on_any args %s kwargs %s" % (args, kwargs))


# vim: expandtab tabstop=4 shiftwidth=4

# =============================================================
# drift_reporter.py  –  notification callback plugin
# =============================================================
#
# This plugin is a more realistic example that ties into the
# Cisco drift-detection playbook in this project.  It shows:
#
#   1. Tracking results by host across the whole playbook run
#   2. Inspecting result._result (the module's return dict)
#   3. Writing a JSON summary file in v2_playbook_on_stats
#   4. Emitting colour-coded output with self._display
#
# ACTIVATION – add to ansible.cfg:
#   [defaults]
#   callback_enabled = drift_reporter
# =============================================================

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
    name: drift_reporter
    type: notification
    short_description: Drift-detection reporter for Cisco IOS-XE playbooks
    description:
      - Watches every task result and builds a per-host summary.
      - Detects the config_drift_detected fact set by detect_drift.yml.
      - Writes drift_reports/callback_summary.json at the end of the run.
    requirements:
      - Add "drift_reporter" to callback_enabled in ansible.cfg
'''

import json
import os
from datetime import datetime
from ansible.plugins.callback import CallbackBase

# ANSI colour codes for terminal output.
# self._display.display() prints to stdout and respects these.
C_GREEN  = '\033[32m'
C_YELLOW = '\033[33m'
C_RED    = '\033[31m'
C_RESET  = '\033[0m'

# Task names that contain any of these words are treated as drift tasks.
_DRIFT_KEYWORDS = ('drift', 'baseline', 'compare', 'detect')


def _is_drift_task(task_name):
    lower = task_name.lower()
    return any(kw in lower for kw in _DRIFT_KEYWORDS)


class CallbackModule(CallbackBase):

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'drift_reporter'
    CALLBACK_NEEDS_ENABLED = True

    def __init__(self):
        super(CallbackModule, self).__init__()
        self._summary = {
            'playbook': None,
            'started_at': None,
            'finished_at': None,
            'hosts': {},          # keyed by hostname
        }

    # ----------------------------------------------------------
    # Playbook lifecycle
    # ----------------------------------------------------------

    def v2_playbook_on_start(self, playbook):
        # playbook._file_name is the path to the .yml file
        self._summary['playbook'] = playbook._file_name
        self._summary['started_at'] = datetime.utcnow().isoformat()
        self._display.banner(
            'DRIFT REPORTER ACTIVE  |  {}'.format(playbook._file_name)
        )

    def v2_playbook_on_play_start(self, play):
        # play.get_name() returns the 'name:' field from the playbook
        self._display.display(
            '  [drift_reporter] Watching play: "{}"'.format(play.get_name())
        )

    # ----------------------------------------------------------
    # Per-host task result hooks
    #
    # The `result` argument has three important attributes:
    #   result._host.name   – the hostname string
    #   result._task        – the Task object
    #   result._result      – dict returned by the Ansible module, e.g.:
    #                           {'changed': False, 'msg': '...', ...}
    #
    # For set_fact tasks, result._result contains:
    #   {'ansible_facts': {'my_var': value}, 'changed': False}
    # ----------------------------------------------------------

    def v2_runner_on_ok(self, result):
        host      = result._host.name
        task_name = result._task.get_name()
        changed   = result._result.get('changed', False)

        self._ensure_host(host)
        bucket = 'changed_tasks' if changed else 'ok_tasks'
        self._summary['hosts'][host][bucket].append(task_name)

        # If this looks like a drift task, fish the drift flag out of the
        # ansible_facts dict that set_fact puts in result._result.
        if _is_drift_task(task_name):
            drift_flag = result._result.get('ansible_facts', {}).get(
                'config_drift_detected'
            )
            if drift_flag is not None:
                self._summary['hosts'][host]['drift_detected'] = bool(drift_flag)

                colour = C_RED if drift_flag else C_GREEN
                status = 'DRIFT DETECTED' if drift_flag else 'No drift'
                self._display.display(
                    '{}  [drift_reporter] {} on {}{}'.format(
                        colour, status, host, C_RESET
                    )
                )

    def v2_runner_on_failed(self, result, ignore_errors=False):
        host      = result._host.name
        task_name = result._task.get_name()
        msg       = result._result.get('msg', '(no message)')

        self._ensure_host(host)
        self._summary['hosts'][host]['failed_tasks'].append(task_name)

        self._display.display(
            '{}  [drift_reporter] FAILED on {} | task: {} | {}{}'.format(
                C_RED, host, task_name, msg, C_RESET
            )
        )

    def v2_runner_on_skipped(self, result):
        host      = result._host.name
        task_name = result._task.get_name()
        self._ensure_host(host)
        self._summary['hosts'][host]['skipped_tasks'].append(task_name)

    def v2_runner_on_unreachable(self, result):
        host = result._host.name
        self._ensure_host(host)
        self._summary['hosts'][host]['unreachable'] = True
        self._display.display(
            '{}  [drift_reporter] UNREACHABLE: {}{}'.format(
                C_RED, host, C_RESET
            )
        )

    # ----------------------------------------------------------
    # Final stats hook – runs after all tasks on all hosts finish.
    #
    # stats.processed  -> set of all hostnames that had activity
    # stats.summarize(host) -> dict:
    #   {'ok': N, 'changed': N, 'failures': N, 'unreachable': N, 'skipped': N}
    # ----------------------------------------------------------

    def v2_playbook_on_stats(self, stats):
        self._summary['finished_at'] = datetime.utcnow().isoformat()

        # Attach Ansible's own counters to each host entry
        for host in stats.processed:
            self._ensure_host(host)
            self._summary['hosts'][host]['ansible_stats'] = stats.summarize(host)

        # Write the JSON report
        report_dir  = 'drift_reports'
        report_path = os.path.join(report_dir, 'callback_summary.json')
        os.makedirs(report_dir, exist_ok=True)
        with open(report_path, 'w') as fh:
            json.dump(self._summary, fh, indent=2)

        # Print a per-host drift summary banner
        self._display.banner('DRIFT REPORTER SUMMARY')
        for host, data in self._summary['hosts'].items():
            drift = data.get('drift_detected')
            if drift is True:
                line = '{}  DRIFT DETECTED  – {}{}'.format(C_RED, host, C_RESET)
            elif drift is False:
                line = '{}  No drift        – {}{}'.format(C_GREEN, host, C_RESET)
            else:
                line = '{}  (no drift data) – {}{}'.format(C_YELLOW, host, C_RESET)
            self._display.display(line)

        self._display.display('')
        self._display.display(
            '  Full JSON report: {}'.format(report_path)
        )

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    def _ensure_host(self, host):
        """Initialise the per-host dict on first encounter."""
        if host not in self._summary['hosts']:
            self._summary['hosts'][host] = {
                'ok_tasks':       [],
                'changed_tasks':  [],
                'failed_tasks':   [],
                'skipped_tasks':  [],
                'unreachable':    False,
                'drift_detected': None,
                'ansible_stats':  {},
            }

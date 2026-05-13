# =============================================================
# HOW ANSIBLE CALLBACK PLUGINS WORK  (read this first)
# =============================================================
#
# A callback plugin is a Python class that Ansible calls at
# specific moments during a playbook run:
#
#   v2_playbook_on_start      – playbook file is loaded
#   v2_playbook_on_play_start – each 'play' block begins
#   v2_playbook_on_task_start – each task is about to execute
#   v2_runner_on_ok           – one host finished a task successfully
#   v2_runner_on_failed       – one host failed a task
#   v2_runner_on_skipped      – task was skipped for one host
#   v2_runner_on_unreachable  – Ansible couldn't reach the host
#   v2_playbook_on_stats      – final summary (very end of run)
#
# PLUGIN TYPES
#   stdout       – replaces the normal terminal output (only one active)
#   notification – runs alongside stdout; used for side-effects like logging
#   aggregate    – accumulates data across multiple runs
#
# ACTIVATION
#   Notification plugins that set CALLBACK_NEEDS_ENABLED = True
#   must be listed in ansible.cfg:
#     [defaults]
#     callback_enabled = task_timer
# =============================================================

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
    name: task_timer
    type: notification
    short_description: Adds per-task and total playbook timing
    description:
      - Measures how long each task takes.
      - Prints a timing table at the end of the playbook run.
    requirements:
      - Add "task_timer" to callback_enabled in ansible.cfg
'''

from datetime import datetime
from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    """
    Simple timing callback plugin.

    Required class-level attributes:
      CALLBACK_VERSION  – must be 2.0 for Ansible 2.x+
      CALLBACK_TYPE     – 'notification' so it runs alongside stdout output
      CALLBACK_NAME     – name used in the callback_enabled config list
      CALLBACK_NEEDS_ENABLED – True means opt-in via ansible.cfg is required
    """

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'task_timer'
    CALLBACK_NEEDS_ENABLED = True

    def __init__(self):
        super(CallbackModule, self).__init__()
        self._task_start_times = {}   # task uuid -> datetime
        self._task_durations = []     # list of {name, elapsed, status}
        self._playbook_start = None

    # ----------------------------------------------------------
    # HOOK: playbook file loaded
    # ----------------------------------------------------------
    def v2_playbook_on_start(self, playbook):
        self._playbook_start = datetime.utcnow()

    # ----------------------------------------------------------
    # HOOK: task is about to run on all hosts
    # We store the start time keyed on the task's unique ID so
    # we can compute elapsed when the per-host results come back.
    # ----------------------------------------------------------
    def v2_playbook_on_task_start(self, task, is_conditional):
        self._task_start_times[task._uuid] = datetime.utcnow()

    # ----------------------------------------------------------
    # HOOKS: called once per host as each result arrives.
    # result._task  -> Task object (has ._uuid and .get_name())
    # result._host  -> Host object (has .name)
    # result._result -> dict of all module return values
    # ----------------------------------------------------------
    def v2_runner_on_ok(self, result):
        self._record(result._task, 'ok')

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._record(result._task, 'failed')

    def v2_runner_on_skipped(self, result):
        self._record(result._task, 'skipped')

    def v2_runner_on_unreachable(self, result):
        self._record(result._task, 'unreachable')

    def _record(self, task, status):
        start = self._task_start_times.get(task._uuid)
        if start:
            elapsed = (datetime.utcnow() - start).total_seconds()
            self._task_durations.append({
                'name': task.get_name(),
                'elapsed': elapsed,
                'status': status,
            })

    # ----------------------------------------------------------
    # HOOK: very end of the run – aggregate stats are available.
    # stats.summarize(hostname) -> {ok, changed, failures, skipped, ...}
    # This is the right place to print summaries or write reports.
    # ----------------------------------------------------------
    def v2_playbook_on_stats(self, stats):
        total = (
            (datetime.utcnow() - self._playbook_start).total_seconds()
            if self._playbook_start else 0
        )

        self._display.banner('TASK TIMING SUMMARY')

        # Multiple hosts can run the same task; keep only the slowest entry
        # per unique task name to avoid duplicates in the table.
        seen = {}
        for entry in self._task_durations:
            name = entry['name']
            if name not in seen or entry['elapsed'] > seen[name]['elapsed']:
                seen[name] = entry

        for entry in seen.values():
            self._display.display(
                '  [{status:<10s}] {elapsed:6.2f}s  {name}'.format(**entry)
            )

        self._display.display('')
        self._display.display(
            '  Total playbook runtime: {:.2f}s'.format(total)
        )

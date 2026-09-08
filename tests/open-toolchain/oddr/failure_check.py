"""Require the intended nextpnr rejection without an emitted configuration.

An unrelated failure is not evidence that a diagnostic barrier works.
"""


def require_rejection(code, log, configuration, expected):
    if code != 125 or 'ERROR: ' + expected not in log.read_text():
        raise AssertionError(f'wrong rejection: exit={code}, expected={expected}, log={log}')
    if configuration.exists():
        raise AssertionError(f'rejected run emitted configuration: {configuration}')

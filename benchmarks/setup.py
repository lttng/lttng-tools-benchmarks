#!/usr/bin/env python3

import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time

import tailleur


class FirstCommand(tailleur.BenchmarkBase):

    version = 1

    def __init__(self):
        self.time_started = None
        self.time_sig_received = None

    def metrics():
        return {
            "time_to_sigusr1": {
                "unit": "seconds",
                "interpretation": "lower is better",
                "description": "The time between starting lttng-sessiond and when the parent process receives SIGUSR1 to signal that the sessiond daemon is ready",
            }
        }

    def handle_sigusr1(self, signum, frame):
        self.time_sig_received = time.monotonic()

    def pre_run(self):
        signal.signal(signal.SIGUSR1, self.handle_sigusr1)

    def post_run(self):
        signal.signal(signal.SIGUSR1, signal.SIG_DFL)

    def run(self):
        self.time_sig_received = None
        self.time_started = time.monotonic()
        # Likely it is better to drop into a C~ helper binary here to avoid
        # measuring the python subprocess overhead.
        proc = subprocess.Popen(["lttng-sessiond", "--sig-parent"])
        while self.time_sig_received is None:
            continue

        proc.terminate()
        proc.wait()
        return {
            "time_to_sigusr1": self.time_sig_received - self.time_started,
        }


class SessionSetupTime(tailleur.BenchmarkBase):
    version = 1

    def __init__(self):
        self.sessiond = None

    def metrics():
        return {
            "session_load_time": {
                "unit": "seconds",
                "interpretation": "lower is better",
                "description": "The time it takes to execute `lttng load` with all sessions from the input file",
            }
        }

    def handle_sigusr1(self, signum, frame):
        self.ready = True

    def pre_run(self):
        self.ready = False
        signal.signal(signal.SIGUSR1, self.handle_sigusr1)
        self.sessiond = subprocess.Popen(
            ["lttng-sessiond", "--sig-parent"], stdout=sys.stderr
        )
        while not self.ready:
            continue
        signal.signal(signal.SIGUSR1, signal.SIG_DFL)

    def post_run(self):
        if self.sessiond:
            self.sessiond.terminate()
            self.sessiond.wait()
            self.sessiond = None

    def default_parameter_sets():
        return [
            {
                "session_file": str(
                    pathlib.Path(__file__).parents[0] / "data/session.lttng"
                ),
            }
        ]

    def run(self, session_file):
        t0 = time.monotonic()
        p = subprocess.Popen(
            ["lttng", "load", "--input-path", str(session_file), "--all"],
            stdout=sys.stderr,
        )
        p.wait()
        t1 = time.monotonic()
        return {
            "session_load_time": t1 - t0,
        }


class SessionStartTime(tailleur.BenchmarkBase):
    version = 1

    def __init__(self):
        self.children = list()
        self.sessiond = None
        self.session_file = pathlib.Path(__file__).parents[0] / "data/session.lttng"

    def metrics():
        return {
            "session_start_time": {
                "unit": "seconds",
                "interpretation": "lower is better",
                "description": "The time it takes to execute `lttng start` with all sessions from the input file and some number of traced applications",
            }
        }

    def handle_sigusr1(self, signum, frame):
        self.ready = True

    def setup(self):
        self.ready = False
        signal.signal(signal.SIGUSR1, self.handle_sigusr1)
        self.sessiond = subprocess.Popen(
            ["lttng-sessiond", "--sig-parent"], stdout=sys.stderr
        )
        while not self.ready:
            continue
        signal.signal(signal.SIGUSR1, signal.SIG_DFL)

    def teardown(self):
        if self.sessiond:
            self.sessiond.terminate()
            self.sessiond.wait()
            self.sessiond = None

    def pre_run(self):
        p = subprocess.Popen(
            ["lttng", "load", "--input-path", str(self.session_file), "--all"],
            stdout=sys.stderr,
        )
        p.wait()

    def post_run(self):
        p = subprocess.Popen(["lttng", "destroy", "--all"], stdout=sys.stderr)
        p.wait()

    def default_parameter_sets():
        return [
            {"traced_applications": 0},
            {"traced_applications": 10},
            {"traced_applications": 100},
        ]

    def run(self, traced_applications=0):
        self.children = list()
        wait_before_first_event_file = tempfile.NamedTemporaryFile()
        os.unlink(wait_before_first_event_file.name)

        for i in range(traced_applications):
            self.children.append(
                subprocess.Popen(
                    [
                        "..//lttng-tools/tests/utils/testapp/gen-ust-events",
                        "-b",
                        wait_before_first_event_file.name,
                    ],
                    stdout=sys.stderr,
                    env=os.environ.copy() | {"LTTNG_UST_REGISTER_TIMEOUT": "-1"},
                )
            )

        t0 = time.monotonic()
        p = subprocess.Popen(["lttng", "start", "--all"], stdout=sys.stderr)
        p.wait()
        t1 = time.monotonic()

        with open(wait_before_first_event_file.name, "w") as f:
            f.write("\n")

        for child in self.children:
            child.wait()

        self.children = list()
        return {
            "session_start_time": t1 - t0,
        }

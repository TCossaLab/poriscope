#!/usr/bin/env python3
"""Run a command, keep its complete output, and report the verdict honestly.

Why this exists: a harness's "exit code 0" can belong to a shell wrapper while the
command inside never ran; a progress line is not a result; ``| tail`` discards the top
of a crash dump, which is where the crashing test is named; and a process can print a
green summary line and then die in teardown. This script:

1. runs the command with stdout+stderr merged into a log file (never truncated),
2. appends a sentinel line ``REALEXIT=<code>`` written after the process has exited,
3. prints every line matching the summary pattern (not just the last one),
4. flags the dangerous combinations: no summary line at all, a green summary with a
   non-zero exit, and a failure summary with exit code 0.

Usage:
    python run_logged.py --log out.log -- pytest -q
    python run_logged.py --log hooks.log --summary "Passed|Failed|Skipped" -- pre-commit run --all-files

Exit status mirrors the command's own exit status, or 3 if the verdict is inconsistent.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Default: pytest-style final summary, e.g. "==== 12 passed, 1 skipped in 3.2s ====".
DEFAULT_SUMMARY = r"\b\d+ (passed|failed|errors?|skipped|xfailed|xpassed|deselected)\b"
FAILURE_WORDS = re.compile(r"\b[1-9]\d* (failed|errors?)\b|\bFailed\b|\bFAILED\b|\bERROR\b")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log", required=True, help="log file to write (overwritten)")
    parser.add_argument("--summary", default=DEFAULT_SUMMARY, help="regex identifying summary/verdict lines")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="command to run, after --")
    args = parser.parse_args(argv)

    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("no command given (put it after --)")

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        log.write(f"COMMAND={' '.join(command)}\n")
        log.flush()
        try:
            # Unbuffered child and a flush per line, so the log shows where a run is while
            # it runs: a Python child block-buffers output written to a pipe, and a hung
            # run otherwise leaves only the COMMAND= line behind.
            env = dict(os.environ, PYTHONUNBUFFERED="1")
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    encoding="utf-8", errors="replace", env=env)
        except FileNotFoundError as exc:
            log.write(f"LAUNCH FAILED: {exc}\nREALEXIT=127\n")
            print(f"LAUNCH FAILED: {exc} - nothing ran. Log: {log_path}")
            return 127
        assert proc.stdout is not None
        for line in proc.stdout:
            log.write(line)
            log.flush()
        code = proc.wait()
        log.write(f"\nREALEXIT={code}\n")
    elapsed = time.time() - start

    text = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    pattern = re.compile(args.summary)
    body = text[1:]  # skip the COMMAND= header line the script itself wrote
    summary = [ln for ln in body if pattern.search(ln) and not ln.startswith("REALEXIT=")]

    print(f"Command : {' '.join(command)}")
    print(f"Log     : {log_path}  ({len(text)} lines, {elapsed:.1f}s)")
    print(f"REALEXIT: {code}")
    if summary:
        print("Summary lines (all of them):")
        for ln in summary:
            print(f"  {ln.strip()}")
    failure_seen = any(FAILURE_WORDS.search(ln) for ln in summary)

    verdict_ok = True
    if not summary:
        print("WARNING: no summary line found - do not call this run green. Read the log.")
        verdict_ok = False
    elif code != 0 and not failure_seen:
        print("WARNING: summary looks green but the process exited non-zero - it died after the "
              "tests (teardown, threads, atexit). Treat as a failure and read the end of the log.")
        verdict_ok = False
    elif code == 0 and failure_seen:
        print("WARNING: a summary line reports failures but the exit code is 0 - the wrapper may be "
              "swallowing the real status.")
        verdict_ok = False
    if code == 0 and verdict_ok:
        print("VERDICT: green (summary read, exit 0)")
    elif verdict_ok:
        print("VERDICT: failed")
    return code if verdict_ok or code != 0 else 3


if __name__ == "__main__":
    sys.exit(main())

"""Run one native case and atomically record unittest outcomes for the parent."""
import argparse
import json
from pathlib import Path
import sys
import unittest


def run_case(name, report):
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName(name))
    data = dict(testsRun=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                skipped=len(result.skipped), expectedFailures=len(result.expectedFailures),
                unexpectedSuccesses=len(result.unexpectedSuccesses))
    temporary = report.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(report)
    return int(not result.wasSuccessful())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    sys.exit(run_case(args.test, args.report))

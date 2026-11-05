import argparse
import json
import sys
from . import __version__
from .audit import audit


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, self.prog + ': error: ' + message + '\n')


def main(argv=None):
    parser = Parser(prog='lemmatization-claim-audit')
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command', required=True)
    scan = sub.add_parser('audit')
    scan.add_argument('repo', nargs='?', default='.')
    scan.add_argument('--json', action='store_true')
    scan.add_argument('--verbose', action='store_true')
    scan.add_argument('--ignore', action='append', default=[])
    scan.add_argument('--fail-on', choices=['high', 'medium'], default='high')
    args = parser.parse_args(argv)
    decisions = []
    try:
        findings = audit(args.repo, args.ignore, decisions)
    except (OSError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    failed = any(f['severity'] == 'HIGH' or args.fail_on == 'medium' for f in findings)
    if args.verbose:
        print('Scope: README.md, docs/**/*.md, tests/**/*.md; Python sources throughout repository', file=sys.stderr)
        print('\n'.join(decisions), file=sys.stderr)
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        print('FAIL' if failed else 'PASS')
        for finding in findings:
            print('{id} {severity} {path}: {message}'.format(**finding))
    return 2 if failed else 0


if __name__ == '__main__':
    sys.exit(main())

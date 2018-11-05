#!/usr/bin/env python

"""

Copyright (c) 2018 Dan Hallgren  <dan.hallgren@gmail.com>

"""

import io
import os
import sys

from pkg_resources import resource_string
from subprocess import Popen, PIPE
from time import strftime

import argparse
import ConfigParser
import contextlib
import lockscreen
import ledgers
import report


CONFIG = """[bundyclock]
# ledger_type, choose from (text, json, sqlite, http-rest)
ledger_type = sqlite
ledger_file = in_out_times.db
# jinja2 report template used with --report option
template = default_report.j2
url = http://localhost:8000/bundyclock/api/workdays/

"""

curr_dir = os.getcwd()


@contextlib.contextmanager
def working_dir(work_dir):
    try:
        os.chdir(work_dir)
        yield
    finally:
        os.chdir(curr_dir)


def main():
    """
    bundyclock CLI
    """
    parser = argparse.ArgumentParser(description='bundyclock')
    parser.add_argument('--workdir',
                        default='.bundyclock',
                        help='dir path under home')
    parser.add_argument('--install',
                        help='Install systemd user service',
                        action='store_true')
    parser.add_argument('-d', '--daemon',
                        help='start daemon mode',
                        action='store_true')
    parser.add_argument('--report', nargs='?', metavar='YYYY-MM',
                        help='Generate monthly report', const=strftime('%Y-%m'))
    parser.add_argument('--config', nargs=1, metavar='CONFIG_FILE',
                        help='alternative configuration', default=['~/.bundyclock/bundyclock.cfg'])

    args = parser.parse_args()

    home = os.path.expanduser('~')
    work_dir = os.path.join(home, args.workdir)
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)

    if args.install:
        sysd_user_dir = os.path.join(home, '.config', 'systemd', 'user')
        if not os.path.exists(sysd_user_dir):
            print('Creating systemd user dir')
            os.mkdir(sysd_user_dir)

        service_file = resource_string(__name__, 'service_files/bundyclock.service')

        with open(os.path.join(sysd_user_dir, 'bundyclock.service'), 'w+') as s:
            s.write(service_file)

        p = Popen('systemctl --user daemon-reload'.split(), stdout=PIPE, stderr=PIPE)
        std_out, std_err = p.communicate()
        if p.returncode:
            raise Exception(' '.join([std_out, std_err]))

        p = Popen('systemctl --user enable bundyclock.service'.split(), stdout=PIPE, stderr=PIPE)
        std_out, std_err = p.communicate()
        if p.returncode:
            raise Exception(' '.join([std_out, std_err]))

        p = Popen('systemctl --user start bundyclock.service'.split(), stdout=PIPE, stderr=PIPE)
        std_out, std_err = p.communicate()
        if p.returncode:
            raise Exception(' '.join([std_out, std_err]))

        print("Install was successful")
        sys.exit(0)

    with working_dir(work_dir):
        config = ConfigParser.SafeConfigParser()

        if not config.read(os.path.join(curr_dir, os.path.expanduser(args.config[0]))):
            config.readfp(io.BytesIO(CONFIG))
            with open(os.path.join(curr_dir, os.path.expanduser(args.config[0])), 'a') as s:
                s.writelines(CONFIG)

        ledger = ledgers.ledger_factory(**config._sections['bundyclock'])

        if args.daemon:
            lock_screen_logger = lockscreen.LockScreen(ledger)
            ledger.in_signal()
            lock_screen_logger.start()

        elif args.report:
            if ledger.can_report:
                print(report.render(args.report, ledger, config.get('bundyclock', 'template')))
            else:
                sys.exit('\t--report not supported by "{}" ledger type'.format(config.get('bundyclock', 'ledger_type')))

        else:
            ledger.out_signal()
            print(ledger.get_today())


if __name__ == "__main__":
    main()

#!/usr/bin/env python

"""

Copyright (c) 2018 Dan Hallgren  <dan.hallgren@gmail.com>

"""

import os
import sys

from subprocess import Popen, PIPE

import argparse
import contextlib
import lockscreen
import ledgers

from pkg_resources import resource_string


@contextlib.contextmanager
def working_dir(work_dir):
    curr_dir = os.getcwd()
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
    parser.add_argument('--file',
                        default='in_out_times.db',
                        help='file with date times')
    parser.add_argument('--workdir',
                        default='.bundyclock',
                        help='dir path under home')
    parser.add_argument('--install',
                        help='Install systemd user service',
                        action='store_true')
    parser.add_argument('-d', '--daemon',
                        help='start daemon mode',
                        action='store_true')
    parser.add_argument('-o', '--output',
                        help='output format "json|sqlite|text"', nargs=1, metavar='FORMAT',
                        choices=['json', 'sqlite', 'text'], default=['sqlite'])

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
        ledger = ledgers.ledger_factory(args.file, args.output)

        if args.daemon:
            lock_screen_logger = lockscreen.LockScreen(ledger)
            ledger.in_signal()
            lock_screen_logger.start()
        else:
            ledger.out_signal()
            print(ledger.get_today())


if __name__ == "__main__":
    main()

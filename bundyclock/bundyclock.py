#!/usr/bin/env python3

"""

Copyright (c) 2018 Dan Hallgren  <dan.hallgren@gmail.com>

"""

import io
import os
import sys
import argparse
import configparser
import contextlib
import logging

from pkg_resources import resource_string
from subprocess import Popen, PIPE
from time import strftime
from sys import platform

import bundyclock
if platform == "linux" or platform == "linux2":
    # linux
    from . import lockscreen
elif platform == "darwin":
    from . import cocoaevent as lockscreen
    # OS X
elif platform == "win32":
    # Windows
    from . import wmilockscreen as lockscreen

from . import ledgers
from . import report


logger = logging.getLogger(__name__)


CONFIG = """[bundyclock]
# ledger_type, choose from (text, json, sqlite, http-rest)
ledger_type = sqlite
ledger_file = in_out_times.db

# logging, default is to stdout. Uncomment to log to file
# log_file = bundyclock.log

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


def setup_file_logger(log_file):
    fileHandler = logging.FileHandler(log_file)
    logFormatter = logging.Formatter(bundyclock.LOG_FORMAT)
    fileHandler.setFormatter(logFormatter)
    rootLogger = logging.getLogger()
    rootLogger.addHandler(fileHandler)


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
            logger.info('Creating systemd user dir')
            os.mkdir(sysd_user_dir)

        service_file = resource_string(__name__, 'service_files/bundyclock.service')

        with open(os.path.join(sysd_user_dir, 'bundyclock.service'), 'wb+') as s:
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

        logger.info("Install was successful")
        sys.exit(0)

    with working_dir(work_dir):
        config = configparser.SafeConfigParser()

        if not config.read(os.path.join(curr_dir, os.path.expanduser(args.config[0]))):
            config.readfp(io.StringIO(CONFIG))
            with open(os.path.join(curr_dir, os.path.expanduser(args.config[0])), 'a') as s:
                s.writelines(CONFIG)

        log_file_name = config._sections['bundyclock'].get('log_file', None)
        if log_file_name:
            setup_file_logger(log_file=log_file_name)

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

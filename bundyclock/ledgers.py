"""
Created on Apr 6, 2013

Copyright (c) 2018 Dan Hallgren  <dan.hallgren@gmail.com>
"""
import datetime
import json
import os
import re
import requests
import sqlite3
import time

from abc import ABCMeta, abstractmethod
from calendar import monthrange

import logging

logger = logging.getLogger(__name__)


class BundyLedger:
    __metaclass__ = ABCMeta
    can_report = False

    @abstractmethod
    def in_signal(self):
        pass

    @abstractmethod
    def out_signal(self):
        pass

    @abstractmethod
    def get_today(self):
        pass

    @staticmethod
    def calc_tot_time(t_in, t_out):
        delta_t = (datetime.datetime(*time.strptime(t_out, '%H:%M:%S')[:7]) -
                   datetime.datetime(*time.strptime(t_in, '%H:%M:%S')[:7]))

        h, s = divmod(delta_t.seconds, 3600)
        m, s = divmod(s, 60)

        total_time = "%02d:%02d:%02d" % (h, m, s)
        return total_time


class PunchTime(object):
    def __init__(self, day, intime, outtime, total):
        self.day = day
        self.intime = intime
        self.outtime = outtime
        self.total = total

    def __str__(self):
        return '{} - In: {} Out: {} Total: {}'.format(self.day, self.intime, self.outtime, self.total)


def ledger_factory(**kwargs):
    output = kwargs.get('ledger_type')

    if 'sqlite' in output:
        filename = '{}.db'.format(kwargs.get('ledger_file').split('.')[0])
        return SqLiteOutput(filename)
    elif 'json' in output:
        filename = '{}.json'.format(kwargs.get('ledger_file').split('.')[0])
        return JsonOutput(filename)
    elif 'text' in output:
        filename = '{}.txt'.format(kwargs.get('ledger_file').split('.')[0])
        return TextOutput(filename)
    elif 'http-rest' in output:
        return BundyHttpRest(kwargs.get('url'))


class TextOutput(BundyLedger):
    def __init__(self, file_name):
        self.file = file_name

    def in_signal(self):
        current = self.get_last_day()
        today = time.strftime('%Y.%m.%d')

        if current is None or current['day'] != today:
            with open(self.file, 'a') as fd:
                if current is not None:
                    fd.seek(-1, os.SEEK_END)  # Skip last newline
                fd.write('{} - In: {} Out: {} Total: {}\n'.format(
                    today,
                    time.strftime('%H:%M:%S'),
                    time.strftime('%H:%M:%S'),
                    '00:00:00'
                ))

    def out_signal(self):
        out_time = time.strftime('%H:%M:%S')
        current = self.get_last_day()
        total = self.calc_tot_time(current['in'], out_time)
        self.update_last_day(current['day'], current['in'], out_time, total)

    def get_last_day(self):
        try:
            with open(self.file, 'r') as fd:
                fd.seek(-56, os.SEEK_END)
                lastline = fd.readline()
            r = re.match(r'(?P<day>.*) - In: (?P<in>.*) Out: (?P<out>.*) Total: (?P<total>.*)\s*$', lastline)
            return r.groupdict()
        except IOError:
            pass

        return None

    def get_today(self):
        today = time.strftime('%Y.%m.%d')
        with open(self.file, 'r') as fd:
            for line in reversed(fd.readlines()):
                r = re.match(
                    r'(?P<day>{today}) - In: (?P<in>.*) Out: (?P<out>.*) Total: (?P<total>.*)\s*$'
                    .format(today=today), line)
                if r:
                    return PunchTime(r.groupdict()['day'],
                                     r.groupdict()['in'],
                                     r.groupdict()['out'],
                                     r.groupdict()['total'])

    def update_last_day(self, day, t_in, t_out, total):
        with open(self.file, 'r+') as fd:
            fd.seek(-56, os.SEEK_END)
            fd.write('{} - In: {} Out: {} Total: {}\n'.format(
                day,
                t_in,
                t_out,
                total
            ))
            fd.truncate()  # Remove dangling newlines at the end


class JsonOutput(BundyLedger):
    """

    """
    def __init__(self, filename):
        self.file = filename

    def update_in_out(self):
        try:
            with open(self.file, 'r') as s:
                my_times = json.load(s)
        except IOError:
            my_times = {}

        key = time.strftime('%Y.%m.%d - %a')

        today = my_times.get(key, {'out': '17:00:00', 'total': '08:00:00'})

        # Update 'in'
        if 'in' not in today:
            # in key should only be updated once a day
            today.update({'in': time.strftime('%H:%M:%S')})

        # Update 'out'
        today.update({'out': time.strftime('%H:%M:%S')})

        # Update 'total'
        total = self.calc_tot_time(today['in'], today['out'])
        today.update({'total': total})

        # Update dict with new today's values
        my_times[key] = today

        with open(self.file, 'w') as s:
            json.dump(my_times, s, indent=2, sort_keys=True)

    def in_signal(self):
        self.update_in_out()

    def out_signal(self):
        self.update_in_out()

    def get_today(self):
        key = time.strftime('%Y.%m.%d - %a')

        with open(self.file, 'r') as s:
            my_times = json.load(s)
            return PunchTime(key,
                             my_times.get(key)['in'],
                             my_times.get(key)['out'],
                             my_times.get(key)['total'])


class SqLiteOutput(BundyLedger):
    """

    """
    can_report = True

    def __init__(self, filename):

        db = sqlite3.connect(filename)
        db.row_factory = sqlite3.Row  # Make sure we can access columns by name

        db.executescript(
            '''
            CREATE TABLE IF NOT EXISTS workdays (
                day TEXT UNIQUE,
                intime TEXT,
                outtime TEXT,
                total TEXT
            );
            ''')

        self.db = db

        user_version = db.execute('PRAGMA user_version').fetchone()[0]
        if user_version < 1:
            self._migrate_00_01_date_format()

    def _migrate_00_01_date_format(self):
        logger.info("Applying migration 'date format'")
        cur = self.db.execute('SELECT day from workdays')
        updated_rows = 0
        all_rows = cur.fetchall()
        for day in all_rows:
            dot_day = day[0]
            try:
                dash_day = datetime.datetime.strptime(dot_day, '%Y.%m.%d').strftime('%Y-%m-%d')
                self.db.execute('UPDATE workdays SET day=? WHERE day=?', (dash_day, dot_day))
                updated_rows += 1
            except ValueError:
                continue

        self.db.execute('PRAGMA user_version = 1')
        self.db.commit()

        logger.info("Updated {} of {} rows".format(updated_rows, len(all_rows)))

    def update_in_out(self):
        cur = self.db.execute("SELECT day, intime, outtime, total FROM workdays WHERE day=date('now')")
        current = cur.fetchone()
        if current is not None:
            current = dict(current)

        if current:
            # Update 'out'
            out = time.strftime('%H:%M:%S')
            total = self.calc_tot_time(current['intime'], out)

            cur = self.db.execute("UPDATE workdays SET outtime=?, total=? WHERE day=date('now')", (
                out,
                total,
                ))
            self.db.commit()
        else:
            # Create 'intime', new day
            cur = self.db.execute("INSERT INTO workdays VALUES (date('now'),?,?,?)", (
                time.strftime('%H:%M:%S'),
                time.strftime('%H:%M:%S'),
                '08:00:00'
                ))
            self.db.commit()

    def in_signal(self):
        self.update_in_out()

    def out_signal(self):
        self.update_in_out()

    def insert_new_entry(self, day, intime, outtime, total):
        self.db.execute(
            'INSERT INTO workdays VALUES (?,?,?,?)', (
                day,
                intime,
                outtime,
                total
            ))
        self.db.commit()

    def get_today(self, day=None):
        cur = self.db.execute("SELECT day, intime, outtime, total FROM workdays WHERE day = date('now')")
        current = cur.fetchone()

        return PunchTime(**dict(current))

    def get_month(self, month=None):
        if not month:
            month = time.strftime('%Y-%m' + '-%')
        else:
            month = re.sub(r'(\d{4})-(\d{2}).*', r'\1-\2-%', month)

        cur = self.db.execute(
            """
            SELECT *
            from workdays
            WHERE day LIKE ?
            """, (month,))

        return cur.fetchall()

    def get_total_report(self, start_date=None, end_date=None):
        if not start_date:
            start_date = time.strftime('%Y-%m-01')
        if not end_date:
            end_date = time.strftime('%Y-%m-%d')

        cur = self.db.execute(
            """
            SELECT SUM(strftime('%s', total)-strftime('%s', '00:00:00'))
            from workdays
            WHERE strftime('%s', day) BETWEEN strftime('%s', ?) AND strftime('%s', ?)
            """, (start_date, end_date))

        try:
            h, s = divmod(cur.fetchone()[0], 3600)
            m, s = divmod(s, 60)
        except TypeError:
            h, m, s = (0, 0, 0)

        total_time = "%02d:%02d:%02d" % (h, m, s)
        return total_time


class BundyHttpRest(BundyLedger):
    """

    """
    can_report = True

    def __init__(self, url):
        self.url = url

    def update_in_out(self):
        current_date = time.strftime('%Y-%m-%d')
        item_url = self.url + current_date + r'/'

        try:
            r = requests.get(item_url)
            if r.status_code == 404:
                # Current date not found, lets create it
                r = requests.post(self.url, data=dict(
                    date=current_date,
                    intime=time.strftime('%H:%M:S'),
                    outtime=time.strftime('%H:%M:S'),
                ))
                r.raise_for_status()

            elif r.status_code == 200:
                # Update current data
                punch_time = r.json()
                punch_time['outtime'] = time.strftime('%H:%M:S')
                r = requests.put(item_url, data=punch_time)
                r.raise_for_status()

            else:
                logger.error("Something went wrong: {}".format(r.status_code))
                r.raise_for_status()

        except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            logger.exception("Connection proplem: {}".format(e))

    def in_signal(self):
        self.update_in_out()

    def out_signal(self):
        self.update_in_out()

    def get_today(self):
        current_date = time.strftime('%Y-%m-%d')
        item_url = self.url + current_date + r'/'
        try:
            r = requests.get(item_url)
            if r.status_code == requests.codes.ok:
                punch_time = r.json()
                # rename pk
                self._rename_pk(punch_time)

                return PunchTime(**punch_time)
            else:
                r.raise_for_status()

        except requests.exceptions.ConnectionError as e:
            logger.exception("Connection proplem: {}".format(e))

    def _rename_pk(self, punch_time):
        punch_time['day'] = punch_time.pop('date')
        return punch_time

    def get_total_report(self, start_date=None, end_date=None):
        if not start_date:
            start_date = time.strftime('%Y-%m-01')
        if not end_date:
            end_date = time.strftime('%Y-%m-%d')

        url = '{base_url}total_sum/?start_date={start_date}&end_date={end_date}'.format(
            base_url=self.url,
            start_date=start_date,
            end_date=end_date
        )
        try:
            r = requests.get(url)
            if r.status_code == requests.codes.ok:
                total_sum = r.json()

                return total_sum['total_sum']
            else:
                r.raise_for_status()

        except requests.exceptions.ConnectionError as e:
            logger.exception("Connection proplem: {}".format(e))

    def get_month(self, year_month=None):
        if not year_month:
            year_month = time.strftime('%Y-%m')

        start_date = year_month + '-01'
        last_day_of_month = monthrange(*map(int, year_month.split('-')[:2]))[1]
        end_date = '{}-{}'.format(year_month, last_day_of_month)

        url = self.url + '?start_date={}&end_date={}'.format(start_date, end_date)
        try:
            r = requests.get(url)
            if r.status_code == requests.codes.ok:
                workdays = r.json()
                workdays = map(self._rename_pk, workdays)

                return workdays
            else:
                r.raise_for_status()

        except requests.exceptions.ConnectionError as e:
            logger.exception("Connection proplem: {}".format(e))


def migrate_from_json(jsonfile, dbfile):
    db = SqLiteOutput(dbfile)

    with open(jsonfile, 'r') as s:
        data = json.load(s)

    for day, times in sorted(data.items()):
        try:
            db.insert_new_entry(day, times['in'], times['out'], times['total'])
        except sqlite3.IntegrityError as e:
            logger.exception(day)
            raise e

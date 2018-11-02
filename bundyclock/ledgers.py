"""
Created on Apr 6, 2013

@author: dan
"""
import datetime
import json
import os
import re
import sqlite3
import time

from abc import ABCMeta, abstractmethod


class BundyLedger:
    __metaclass__ = ABCMeta

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


def ledger_factory(filename, output):
    if 'sqlite' in output:
        filename = '{}.db'.format(filename.split('.')[0])
        return SqLiteOutput(filename)
    elif 'json' in output:
        filename = '{}.json'.format(filename.split('.')[0])
        return JsonOutput(filename)
    elif 'text' in output:
        filename = '{}.txt'.format(filename.split('.')[0])
        return TextOutput(filename)


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
        print("Applying migration 'date format'")
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

        print("Updated {} of {} rows".format(updated_rows, len(all_rows)))

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
        cur = self.db.execute("SELECT day, intime, outtime, total FROM workdays WHERE day LIKE date('now')")
        current = cur.fetchone()

        return PunchTime(**dict(current))

    def get_total_report(self, start_date=None, end_date=None):
        if not start_date:
            start_date = time.strftime('%Y-%m-01')
        if not end_date:
            end_date = time.strftime('%Y-%m-%d')

        cur = self.db.execute(
            """
            SELECT time(SUM(strftime('%s', total)-strftime('%s', '00:00:00')), 'unixepoch')
            from workdays
            WHERE strftime('%s', day) BETWEEN strftime('%s', ?) AND strftime('%s', ?)
            """, (start_date, end_date))

        return cur.fetchone()[0]


def migrate_from_json(jsonfile, dbfile):
    db = SqLiteOutput(dbfile)

    with open(jsonfile, 'r') as s:
        data = json.load(s)

    for day, times in sorted(data.items()):
        try:
            db.insert_new_entry(day, times['in'], times['out'], times['total'])
        except sqlite3.IntegrityError as e:
            print(day)
            raise e

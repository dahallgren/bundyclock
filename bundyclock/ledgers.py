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

    @staticmethod
    def calc_tot_time(t_in, t_out):
        delta_t = (datetime.datetime(*time.strptime(t_out, '%H:%M:%S')[:7]) -
                   datetime.datetime(*time.strptime(t_in, '%H:%M:%S')[:7]))

        h, s = divmod(delta_t.seconds, 3600)
        m, s = divmod(s, 60)

        total_time = "%02d:%02d:%02d" % (h, m, s)
        return total_time


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

        now = time.localtime()
        key = time.strftime('%Y.%m.%d - %a', now)

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

    def update_in_out(self):
        now = time.localtime()
        today = time.strftime('%Y.%m.%d', now)

        cur = self.db.execute('SELECT day, intime, outtime, total FROM workdays WHERE day=?', (today,))
        current = cur.fetchone()
        if current is not None:
            current = dict(current)

        if current:
            # Update 'out'
            out = time.strftime('%H:%M:%S')
            total = self.calc_tot_time(current['intime'], out)

            cur = self.db.execute('UPDATE workdays SET outtime=?, total=? WHERE day=?', (
                out,
                total,
                today,
                ))
            self.db.commit()
        else:
            # Create 'intime', new day
            cur = self.db.execute('INSERT INTO workdays VALUES (?,?,?,?)', (
                today,
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
        if not day:
            day = time.strftime('%Y.%m.%d')

        cur = self.db.execute('SELECT day, intime, outtime, total FROM workdays WHERE day LIKE ?', (day + '%',))
        current = cur.fetchone()

        return dict(current)


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

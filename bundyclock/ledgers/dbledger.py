import sqlite3
import datetime
import re
import time

from .ledgers import BundyLedger, PunchTime

import logging

logger = logging.getLogger(__name__)

class SqLiteOutput(BundyLedger):
    """

    """
    can_report = True

    def __init__(self, filename):

        db = sqlite3.connect(filename, check_same_thread=False)
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
            user_version = self._migrate_00_01_date_format()

        if user_version == 1:
            user_version = self._migrate_01_02_create_breaks_table()

        if user_version == 2:
            user_version = self._migrate_02_03_create_notes_table()

    def _migrate_00_01_date_format(self):
        logger.info("Applying migration 'date format'")
        NEXT_VERSION = 1

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

        self.db.execute(f'PRAGMA user_version = {NEXT_VERSION}')
        self.db.commit()

        logger.info("Updated {} of {} rows".format(updated_rows, len(all_rows)))
        return NEXT_VERSION

    def _migrate_01_02_create_breaks_table(self):
        logger.info("Starting 01->02 migration...")
        NEXT_VERSION = 2

        self.db.executescript(
            '''
            CREATE TABLE IF NOT EXISTS breaks (
                id  INTEGER PRIMARY KEY,
                day TEXT NOT NULL,
                start TEXT NOT NULL,
                end TEXT NULL
            );
            ''')

        self.db.execute(f'PRAGMA user_version = {NEXT_VERSION}')
        self.db.commit()

        logger.info("Finished migration. Created breaks table")
        return NEXT_VERSION

    def _migrate_02_03_create_notes_table(self):
        logger.info("Starting 02->03 migration...")
        NEXT_VERSION = 3

        self.db.executescript(
            '''
            CREATE TABLE IF NOT EXISTS notes (
                id  INTEGER PRIMARY KEY,
                day TEXT NOT NULL,
                note TEXT NOT NULL
            );
            ''')

        self.db.execute(f'PRAGMA user_version = {NEXT_VERSION}')
        self.db.commit()

        logger.info("Finished migration. Created notes table")
        return NEXT_VERSION


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
        self._handle_return_from_break()
        self.update_in_out()

    def out_signal(self):
        self.update_in_out()

    def get_today(self, day=None):
        cur = self.db.execute("""
                              SELECT w.*, COUNT(b.id) AS num_breaks,
                                SUM(strftime('%s', b.end)-strftime('%s', b.start)) AS break_secs
                              FROM workdays w
                              LEFT OUTER JOIN breaks b on w.day=b.day
                              WHERE w.day = date('now')
                              """
                              )
        current = cur.fetchone()

        return PunchTime(**dict(current))

    def get_month(self, month=None):
        if not month:
            month = time.strftime('%Y-%m' + '-%')
        else:
            month = re.sub(r'(\d{4})-(\d{2}).*', r'\1-\2-%', month)

        cur = self.db.execute(
            """
            SELECT w.*, COUNT(b.id) AS num_breaks,
                SUM(strftime('%s', b.end)-strftime('%s', b.start)) AS break_secs,
                (SELECT GROUP_CONCAT(n.note, ", ") FROM notes n WHERE n.day=w.day) AS notes
            FROM workdays w
                 LEFT OUTER JOIN breaks b on w.day=b.day
            LEFT OUTER JOIN notes n on w.day=n.day
            WHERE w.day LIKE ?
            GROUP BY w.day
            ORDER BY w.day
            """, (month,))

        return cur.fetchall()

    def get_total_report(self, start_date=None, end_date=None):
        if not start_date:
            start_date = time.strftime('%Y-%m-01')
        if not end_date:
            end_date = time.strftime('%Y-%m-%d')

        cur = self.db.execute(
            """
            SELECT SUM(DISTINCT(strftime('%s', total))-strftime('%s', '00:00:00')) AS total_day,
                SUM(strftime('%s', b.end)-strftime('%s', b.start)) AS total_break
            from workdays w
            LEFT OUTER JOIN breaks b ON w.day=b.day
            WHERE strftime('%s', w.day) BETWEEN strftime('%s', ?) AND strftime('%s', ?)
            """, (start_date, end_date))

        return cur.fetchone()

    def take_a_break(self):
        # start break by saving break record
        self.db.execute("INSERT INTO breaks (day, start) VALUES (date('now'),?)", (
                time.strftime('%H:%M:%S'),
                ))
        self.db.commit()
        logger.debug("Saved start break time")

    def _handle_return_from_break(self):
        cur = self.db.execute("""
                              SELECT * FROM breaks WHERE day = date('now') AND end is NULL ORDER BY start DESC;
                              """
                              )
        latest_break_record = cur.fetchone()
        if latest_break_record:
            cur = self.db.execute("UPDATE breaks SET end=? WHERE id=?", (
                time.strftime('%H:%M:%S'),
                latest_break_record['id'],
                ))
            self.db.commit()
            logger.info("End break")
            self._prune_stale_break_records()

    def _prune_stale_break_records(self):
        cur = self.db.execute("DELETE FROM breaks WHERE end is NULL")
        if cur.rowcount:
            logger.info(f"Deleting {cur.rowcount} stale break records")
            self.db.commit()

    def add_note(self, note, date):
        self.db.execute("INSERT INTO notes (day, note) VALUES (?,?)", (
            date,
            note,
            ))
        self.db.commit()

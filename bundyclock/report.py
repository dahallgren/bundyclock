import re

from calendar import monthrange

import jinja2


# jinja2 filters
def _subtract_minutes(time_hms, minute_subtrahend):
    """"
    jinja2 filter that subtracts given minutes from time in HH:MM:SS format
    """
    (h, m, s) = map(int, time_hms.split(':'))
    seconds = h * 3600 + m * 60 + s - minute_subtrahend * 60

    return _sec2str(seconds)


def _sec2str(seconds):
    try:
        h, s = divmod(seconds, 3600)
        m, s = divmod(s, 60)
    except TypeError:
        (h, m, s) = (0, 0, 0)

    return "%02d:%02d:%02d" % (h, m, s)


def _str2sec(time_hms):
    (h, m, s) = map(int, time_hms.split(':'))
    seconds = h * 3600 + m * 60 + s

    return seconds


def render(year_month, ledger, template):
    start_date = re.sub(r'(\d{4})-(\d{2}).*', r'\1-\2-01', year_month)
    last_day_of_month = monthrange(*map(int, year_month.split('-')[:2]))[1]
    end_date = re.sub(r'(\d{4})-(\d{2}).*', r'\1-\2-{}', year_month) \
        .format(last_day_of_month)

    try:
        template_env = jinja2.Environment(loader=jinja2.PackageLoader('bundyclock', 'templates'))
    except jinja2.exceptions.TemplateNotFound:
        template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath="./"))

    template_env.filters['lunch'] = _subtract_minutes
    template_env.filters['sec2str'] = _sec2str
    template_env.filters['str2sec'] = _str2sec
    template = template_env.get_template(template)

    totals = ledger.get_total_report(start_date, end_date)
    context = dict(
        month=end_date,
        total_month=_sec2str(totals['total_day']),
        totals=totals,
        workdays=ledger.get_month(year_month)
    )
    rendered_report = template.render(context)

    return rendered_report

import re

from calendar import monthrange
from dateutil.parser import parse as guess_date

import jinja2


# jinja2 filters
def lunch(total_time, total_lunch_minutes):
    """"
    jinja2 filter that subtracts given minutes from time in HH:MM:SS format
    """
    (h, m, s) = map(int, total_time.split(':'))
    seconds = h*3600 + m*60 + s - total_lunch_minutes*60

    h, s = divmod(seconds, 3600)
    m, s = divmod(s, 60)

    return "%02d:%02d:%02d" % (h, m, s)


def render(some_date, ledger, template):
    year_month = guess_date(some_date).strftime('%Y-%m')
    template_env = jinja2.Environment(loader=jinja2.PackageLoader('bundyclock', 'templates'))
    template_env.filters['lunch'] = lunch
    start_date = re.sub(r'(\d{4})-(\d{2}).*', r'\1-\2-01', year_month)
    last_day_of_month = monthrange(*map(int, year_month.split('-')[:2]))[1]
    end_date = re.sub(r'(\d{4})-(\d{2}).*', r'\1-\2-{}', year_month) \
        .format(last_day_of_month)

    try:
        template = template_env.get_template(template)
    except jinja2.exceptions.TemplateNotFound:
        template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath="./"))
        template = template_env.get_template(template)

    context = dict(
        month=end_date,
        total_month=ledger.get_total_report(start_date, end_date),
        workdays=ledger.get_month(year_month)
    )
    rendered_report = template.render(context)

    return rendered_report

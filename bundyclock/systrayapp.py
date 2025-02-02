import pystray

from pkg_resources import resource_filename
from PIL import Image

import logging

logger = logging.getLogger(__name__)


class SystrayApp(pystray.Icon):
    def __init__(self, ledger,  actioncb=None, cb_arg=None, **kwargs):
        super().__init__(
            'bundyclock',
            icon=Image.open(resource_filename(__name__, 'service_files/bundyclock.png')),
            menu=pystray.Menu(
                pystray.MenuItem('take a break', self.after_click),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('show time today', self.after_click),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('quit', self.after_click),
            ))
        self.ledger = ledger
        self.actioncb = actioncb

    def after_click(self, icon, query):
        if str(query) == "quit":
            self.ledger.update_in_out()
            logger.info("quit by user")
            icon.stop()
        elif str(query) == 'show time today':
            self.ledger.update_in_out()
            today_time = self.ledger.get_today()
            self.notify(f"Start: {today_time.intime}. Time elapsed: {today_time.total}\n"
                            f"Breaks {today_time.num_breaks} - {today_time.break_time}",
                            "Bundyclock")
        elif str(query) == "take a break":
            self.ledger.take_a_break()
        
        if self.actioncb:
            self.actioncb(str(query))

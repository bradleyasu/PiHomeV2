from kivy.clock import Clock
from kivy.network.urlrequest import UrlRequest
from util.helpers import random_hash
from util.phlog import PIHOME_LOGGER

class Poller:

    registered_calls = {}
    MAX_TICK = 86400
    tick = 0

    def __init__(self, **kwargs):
        super(Poller, self).__init__(**kwargs)
        Clock.schedule_interval(lambda _: self._tick(), 1)

    def _tick(self):
        self.tick = self.tick + 1
        if self.tick >= self.MAX_TICK:
            self.tick = 0
        # check if registered calls has items()
        if not self.registered_calls or len(self.registered_calls) == 0:
            return
        try:
            for k,v in self.registered_calls.items():
                if self.tick % int(v["interval"]) == 0:
                    # info("[ {} ] Poller triggering {}".format(k, v["url"]))
                    self.api_call(v["url"], v["on_resp"])
        except Exception as e:
            PIHOME_LOGGER.error("An error occurred while polling the api. {}".format(e))

    def register_api(self, url, interval, on_resp):
        phash = random_hash()
        Clock.schedule_once(lambda _: self.api_call(url, on_resp), 2)
        self.registered_calls[phash] = {"url": url, "interval": interval, "on_resp": on_resp}
        PIHOME_LOGGER.info("Poller registered {} with {} at interval {} seconds".format(phash, url, interval))
        return phash


    def unregister_api(self, key):
        if key in self.registered_calls:
            self.registered_calls.pop(key)
            PIHOME_LOGGER.info("{} has be removed from the poller.  Associated API will no longer be polled".format(key))
        else:
            PIHOME_LOGGER.warn("{} does not exist in the poller.  No changes were made".format(key))

    def api_call(self, url, on_resp):
        url = url.replace(" ", "%20")
        # info("[ POLL ] Initializing API Call: {}".format(url))
        req = UrlRequest(
            url=url, 
            on_success = lambda request, 
            result: on_resp(result),
            # set the user agent to firefox to avoid 403 errors
            req_headers={'User-Agent': 'Mozilla/5.0'},
            on_error=lambda r, d: PIHOME_LOGGER.error("An Error Occurred while polling api. {}".format(d)),
            on_failure=lambda r, d: PIHOME_LOGGER.error("A failure occurred while polling api. {}".format(d))
        )

        # Log any errors from the request
        if req.error:
            PIHOME_LOGGER.error("An Error Occurred while polling api. {}".format(req.error))


POLLER = Poller()

from components.Image.networkimage import NetworkImage
from kivy.network.urlrequest import UrlRequest
from util.const import TEMP_DIR
from util.helpers import get_config
import re

class AlbumArtFactory:
    api = "https://api.discogs.com/database/search?q={}&token={}"
    token = ""

    ignore_list = [
        "Official Video",
        "{",
        "}",
        "Official Music Video",
        "Music Video"
    ]
    def __init__(self, **kwargs):
        super(AlbumArtFactory, self).__init__(**kwargs)
        self.token = get_config().get("music", "album_art_source", "")

    
    def find(self, query, on_resp):
        query = self._refine_query(query)
        if self.token == "":
            return
        url = self.api.format(query, self.token)
        url = url.replace(" ", "%20")
        UrlRequest(
            url=url, 
            on_success = lambda request, result: on_resp(result),
            on_error=lambda r, d: print(r, d),
            on_failure=lambda r, d: print(r, d),
            user_agent="PiHome"
        )

    def _refine_query(self, query):
        query = re.sub("[\(\[].*?[\)\]]", "", query)
        for x in self.ignore_list:
            query = query.replace(x, "")
        return query
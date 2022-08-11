import qrcode

from components.Image.networkimage import NetworkImage
from util.const import TEMP_DIR

class QR:
    def __init__(self, **kwargs):
        super(QR, self).__init__(**kwargs)

    
    def from_url(self, url):
        out = "{}/url_qr.png".format(TEMP_DIR)
        img = qrcode.make(url)
        type(img)
        img.save(out)
        return out
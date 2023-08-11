

'''
Convert a Hex color, #00FF00, into an RGBA floating point
value that can be used with kivy components.  Opacity can optionally be passed
and will be returned as passed.  Opacity should be a value between 0 and 1
'''
import ssl
import tempfile
import urllib

def hex(hex_string, opacity = 1.0):
    hex_string = hex_string.replace('#', '')
    r_hex = hex_string[0:2]
    g_hex = hex_string[2:4]
    b_hex = hex_string[4:6]
    return (int(r_hex, 16) / 255, int(g_hex, 16) / 255, int(b_hex, 16) / 255, opacity)


'''
Download an image from a URL and save it to a temporary file.  The temporary
file will be returned.
'''
def download_image_to_temp(url):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(urllib.request.urlopen(url, context=ctx).read())
    temp_file.close()
    return temp_file

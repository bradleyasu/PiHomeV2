from util.helpers import update_pihome
from kivy.gesture import GestureDatabase
from system.brightness import set_brightness

CONF_FILE = "base.ini"
THEME_FILE = "theme.ini"
SERVER_PORT = 8989
GESTURE_DATABASE = GestureDatabase()

CDN_ASSET = "https://cdn.pihome.io/assets/{}"

MQTT_COMMANDS = {
    'update': update_pihome,
    'soften': lambda _: set_brightness(30),
    'brighten': lambda _: set_brightness(100)
}

_DISPLAY_SCREEN = "_display"
_DISPLAY_IMAGE_SCREEN = "_display_image"
_DEVTOOLS_SCREEN = "_devtools"
_HOME_SCREEN = "_home"
_SETTINGS_SCREEN = "_settings"
_MUSIC_SCREEN = "_music"
_TIMERS_SCREEN = "_timers"

TEMP_DIR = "./.temp"



"""

GESTURE DEFINITIONS

"""
GESTURE_CHECK = GESTURE_DATABASE.str_to_gesture(b'eNq9lVtIU2EcwI/gFRRdXigf7FCG1oMJpmWCO4RxhB4SFBJEdz3ubM5t7aJ5SZeKD3ECwaOUoY1AGggq5KUMm5mXqQWjLCw0zbxUUEmRhFi27+x8+zzoyyA6Lxu/3////S87O8fq3xIZjHEXE1qiLqtIUlEms8VIsUwQyX9rZo9fY6+yiUxAuVppplmSUNk8GYE0pVbRZjeRSz0knE+XGIx6pUUBVGyPaNOZmcsEmcxGfQllYgtZGmPC+NNzOYhqBBr0ap0ZBCW6o0L5qBwAUZDfFZZ0uOwdFzvSMhm/CpYU39sOiTtb0WSR0yJPDB1FOp5/LZhoSMuho0lxQ4yojkokhH5mLSOrOtrl9o6u6nrHx8e40E+9ix01/cwGfjC9IXNs84HQT77aIkpmncA/6T/aWTm/IvQTVemfHjlw4McP+tekREYI/ZjpkOp+hw346fqAuR/qMaF3aDYMrZ1W4GeSi/0vmG8Kff+3btFEGNf/JH4My0hhhb47d26k69wI8E+HsxLqfiuFvnXIHhiVgAE/vHN+I1URLPDitmDlie5VAvhe0+iNvOv5Qt+zNfDi111uvtvL2FD4tFXonV9EG5dO02D/A7NBWe2f8f/rXQuVovXleOBHT47nOmRa3/zr7Cqt/cws8NM5ZMHih2rf/NsebaOyFuxP7DqVZ9g+UuObX4wptOHjvcDPZrVYQhV1vvnl0cH2763c/f8mf20I75v4t37ljjU6vi8O+IUD5faGjSLf/Cr4+0xNA78UnpfqbGoW+vXj9sHueXD/it9HKsue2V5a5BQTalIYKUqHnhMkUTzCPX1IguK++DWyu5kNsaW9TIVDJt4BF8ekPFN6EjhmhUyKmA0yHDFYVyHxnkdjkGHeOC+Toxo07EVuRYyAjEAM9idb8s5Bw/5kqD8a9ifblQv7k44gBvciRblq2J8U99ZADEPsMDfm/kxSCz7/cAzOIUF7Vkv4uCLHPgztQA1n28U02N7zNPvMUcKl+Ll3gHav3Wd/pbCGAv2WOimfq0SzGeD+itH+LjfxjEY1jJB5mudyTbCuxuaNMyfzTIvqWmCcDp1XFsEzPZqtDNYwEN4a5XAvBlSjHNYwuHhGWeQyJsSs11JGmU5Bud+gD2+Bq43x18lK3W9/zP0uSfoLWtXZrg==')

GESTURE_TRIANGLE = GESTURE_DATABASE.str_to_gesture(b'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')


GESTURE_SWIPE_DOWN = GESTURE_DATABASE.str_to_gesture(b'eNqN129oG2UcB/ArXVY2Wow6N8UXC4NuK4Ua5xtR4U4UwmC6oigVq82/s5d1TdIk17VO3XXtNjdPKfZ80Vm6Q/Kie6HE7oXb2tlTZKzMYEb2vyo3VlQQJIyJirC5nImXeL/n9r03OT7f57l7nt+TPHdRVnwUWcdZh9rcFxsc7ugV0xk5JWpqU6ByNqG1jWhva5tVz65YNCNpAeHBSo+VkhjrlTJ3ZMfC7fKh3lPp3pNMJaJypBx5ZtuW+/dNqE3pTCrRJ6a11zSJU1sqV3/RQvseK5OJWDxTbrT5TqvmSqvOMtqNGoa0wIKczbf//BSnNgxrAf6HL6a7X5+KymHp3n/bSGv+ayE9EOCXjnyuPP2TVp+PRbueXLXJyq8c+Cbb6jeY+aX53pce3eRn5heybw6vGehi5kX1/ak/5saY+bmMbix5csz8uxf2X8//+TgzP7vh03ZNHWfmp28U06/6TGb+ddtVvdDNvv+pjYKnMOFl1veY9nxwbrXBzGfys1svLHLMfPKzdwd/P/W//Nmm7S3XguV84eCWt54wFtn50eTerqVn6nM++clfUnzZymePDT328VqDmc/d355t+c3LzL86kTgkhOvrw49cj7+y7W8rP71X6j670WTmi0qjGbqmMPP82i/f2XpzhpkXXp7/4KHGX5h5senM2IH7BGZ+vtha3P3weWZ+cXp0Q6K1/vfDvyf33AqPWvnlmDkQ6bjJzK+O5J/bs/wtM/9+8mTb1OFpZv6juG5oPLulPv9wdObcvEcp52Z0sfRrY6scFtXmdCQlinF7nwgIynFrPwoIg49Y29B+rdZ81sndjcNMNsufDXc3g+hLWQ403d1yVVNAS4IWBK0TNN5eI1fzE30p84LGYZYp2WvpaibRl7ICaAZoOdDGQVNAS4IWBG27c81JE4i+lPlB84HmBY0jvhuEpUvOvqSZoBVAy4Gmg6aAlgStEzQBNB9oHGapEmgF0HTQxkELgiaA5sVswAStAJoO2h7nHkEaUYNaqz5DB/zOZzdpxLsAZckSaCZoBmg6aApone5mVM0Pmhc0DrOEDlrNu4Wr+ew1d7O4DpriHEutnakah1m/DpoCWs3c3GznbbtWrkaMhTQBsz7T3QpVM0AT7Lm52np7bm62Q3fegzQBs5gJmu4cM2m8c8ykrcdMImpKWhA0DrNeYm6kKaARNSCNGgthbxig6aApoAXd7XLVBNA4zMSa/7quZoCmg9Zjr5Gr8ZhFTefcSFNAC4LGOedGWcQAjagBacSa15pZsbAJmgGaApoAWk2t3CxkgrZg18rVjriYKIdD6qpMYqeYCsUjohbgT0yWj8PqinioX9RUTpPDHf8Arl6FWA==')

GESTURE_SWIPE_UP = GESTURE_DATABASE.str_to_gesture(b'eNqd139IE1EAwPGb+KtU0kgKMbyw0igs/8hMQY/+8KSULAkyLDe3y7um29p2uWXlJRQYF5Sd4A/ShRiFJAYJGuQOCldU/siS5UBHQf1jkNIfBaLtx9Fm99756v7Z7fN9t3vvDY6Ni2zVJmCBg4/XMxfsWTWUxcqaKYGPIaWzO8Kuq8JlIZOPqmd0VlogiUTpimiaYmpoq08qiKBskC6vMpmNOlbrT1Gj9qSC/kE+xmI1G/WURTgt0BifIH16eQBD94g2GRmD1T8o0zcqXhpV5sfQIJVNIJ23t55p6SnCeJXd92Z2qbQht6+SraaTgmPoTX9G0Mmk0zOZ06c5WAztM7xrR1zcA2h330/zNLsIaJ922lpimyag/X1O+7XKDAHa3x1dzJ/5nArtE8zhxYquAWh/G0UeG3jCQfurAz9H+nf/tb6Gr82NLl2gv9iZ13uC3Qft4sn5jcfnV6+/kCkZa11qC/ThzXnLjtEJaH986a67czBxdb/RsWf9p4hAb8pP1fE3uf/tha0lX6gxFQbtDz2Priyki9A+3JG9PH0Kh/aRvu9b9iY6oP15elF3SlImtL/cHzlkdg1A+5uI8iNs2S1oHx+/N1v/0QTtk2O23GfZ8PlPDaY1FbBt0P6hc/S182kstLu397prk4uhfSaudNu3iiFo9yz80Bu64PObvThlS/lFQ/uc89Dy+Qzf90vx8RatmaIMoecESdiDTx+S0ARPrgvhpka0xhX/sbZ1I5rX/6pa06pxROPkcwaaiGheNNNiiIYjGoFoVfI9BVojonUjmijfe5DpMEQD7AHQ1IjGIZoD0bzKViYZhSNa2HekaGF7CrLgJSRxNuweisYhmqhsJmkuNYWhOSuaIzRnJaMx+T2ApkY0B6J50YwBrA1onHxtQAPsKcjO4YhGIBqHaHPytYFMT8jXBjTA3gNNRLNaHNE4RHMgGmAPgLaCZnW4fK+ApkY0wJyBJiob96/mVTCKrdbw66zGWsqsMWgpwfeLst1/dPCRBk2d798U5vvtn/UbglEWSA==')

GESTURE_SWIPE_LEFT_TO_RIGHT = GESTURE_DATABASE.str_to_gesture(b'eNqV129IE2EcwPFb+BcmbqHSi4JZCPpCWUVEUOzsD1cpOIoGFdamXt6yttt2p440ToSSuGzmGRhUBmUFZiMtEIOdhlbkn9laf5DVGRFGIvNFZK/qNifii1/8et7c8fn+nj0vBg+ckNTRl0HEl6itsdd6i6ppD8e7aUlMpRJv7VJBk9Qo5YvJdfYqjpEo0iIv7UhhaHs1w0mU6U98CWJmYvtJ1u2s4ivVRCaHXk9uLMwSUz2c21lDe6RyiSHEjMSvH47jyhkprNPu4GJD+eqUNjFljuHKkKZeogKfHy5MFm/1iRqvev6VupG7ub0CX8Hol2aYLCoQaQtm5OlfMtlAn+Z7S9KiaWD/eFRsmZvYD/b3u06PBntawB7OPZDUf0kGe2hgS3MpR8a6a25wA9lKrO5TN3RDxkMC2Mc7XzTIJQTYX9maF1tSWbCPFJBc2fMo2AP6sciJkKL2wLmc7Mzh3f/Zn97e93a+VAZ799Cm9uObBbBfFCzps60E1E3XNAvrx8PgflN3cU/nvZvg+aa+tvIjey1WsD/TfC3vj8B9eMe2vrWPSbCPurzbD/6Ezx/Th3b+KIP7xBfCNNgA96nLuTO/lXywhx7suZOjmQV7WH8s7/w6BuzvvGz3tyJ4/4eOq/Y1Zj/Yp+lAzZvG+2CPNM0Uzt+qB/un778eWZ4sruq0qPVUumnasXJPUKSrK34fUeSppavsgnrtuPxIC+LMTSBNhzQD0oxII5FmRpoVaSzSBKT5kLb8X9JK7KkBLYg0BWceAmkGpBmRZkaagDQf0uRlk/9tUZxxBNKMSLMijUWaD2ldSPMjTUZaEGkK0qI443VIMyCNRBqLNAFpfqQFkabgrJZAmhFpZqRZkcYiTUBaF9JkpCk4q9MhzYA0I9JIpJkxRvMVNjGdc56h3TZHJa1+4Qx0xtZ1MclhO6t+nRESX1H0F9U/uhc=')

GESTURE_SWIPE_RIGHT_TO_LEFT = GESTURE_DATABASE.str_to_gesture(b'eNqN129IE2EAx/ET5j/wX2Q1epMvJNcbGxg1jNxFyIkVCYIZtNympzfU29pu/qGkmVh7caDhJevPiysIJIpGkEyxtmDUUkIzt4aYLOiPb4JRo0ZJdepCKp/43avj832e556D44FzqS5/zqNWLzGn1dLRXdrCOgSnnZXETCZ1NyTt6pV6JI2Y3mlpEjiJoU/QazMyONbSwgkSo4+n1shPTW+w2a1NzkYl0ekXXzzsn7khZjoEu7WVdUgGiaPE3NTqtau4/owMm9XCCyuDNMqonNSomhVcH5TWpTwypqv8FH7rE9O6JcbfechdHHdQTjO3aW0MV8joX3+4E/3Ja7ktjP50NXcrfPCvPj8xnF2yXETu209VLr+rIfZo2ejyGTlG7JGj+fe/nbQR+1wzZ+lWU8Q+e+7xjq8vB4l9+mNw53BcJvbJhYzcinLy+4VqS6hLi+T9B/uj7QN15P09Wtoz0q4n97FIx0Ch20Xs99iE78k+8nxZO942sZk8v8Gm2lpBEef7rzuEOm8Lud/lE53mOuL6ft/8F97soZW+4fflD5Q/mywLU8QezFIb9hpixP403BzXvQ8Q+9TNB337rTKxTyvvfyDpIvZZ+s22qePkPlfiNh25Fif2SN7u289jRmJ/lYgkjhXPEPt8zyj13VVA7AtNhuqzQfL+Fg+rhn5k/bk/VsxxNNpZll8/Jxi6z7h6+jA0t3YwXVCOnb4a0OjfZvy/aUFTg1aA2fkkaDHQZkALgRYAzQeaFzQZNA9og6C5QLOBxoFmBK0etCrQaNB0oGlAU4OWBRqFWW8StDhoS6DFQIuCFgLNB5oXtBHQZNA8oLn/Pds3tC7QbKAZQasCjQZNC5oGtCLQ1KAVgEZh5kqCFgMtBFoANC9oI6DJoHlA6wLNCFo9aFWg0aDpEGOdZpOYLVjbWLuJb2SV38WxKyvXVVHFm9qVv1tKcppLfwHSeOb4')



GESTURE_W = GESTURE_DATABASE.str_to_gesture(b'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')


"""
Register Gestures With Gesture Database
"""
GESTURE_DATABASE.add_gesture(GESTURE_CHECK)
GESTURE_DATABASE.add_gesture(GESTURE_TRIANGLE)
GESTURE_DATABASE.add_gesture(GESTURE_SWIPE_DOWN)
GESTURE_DATABASE.add_gesture(GESTURE_SWIPE_UP)
GESTURE_DATABASE.add_gesture(GESTURE_SWIPE_LEFT_TO_RIGHT)
GESTURE_DATABASE.add_gesture(GESTURE_SWIPE_RIGHT_TO_LEFT)
GESTURE_DATABASE.add_gesture(GESTURE_W)
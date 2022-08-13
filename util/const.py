from util.helpers import update_pihome
from kivy.gesture import GestureDatabase

GESTURE_DATABASE = GestureDatabase()

MQTT_COMMANDS = {
    'update': update_pihome
}

_DISPLAY_SCREEN = "_display"
_DEVTOOLS_SCREEN = "_devtools"
_HOME_SCREEN = "_home"
_SETTINGS_SCREEN = "_settings"

TEMP_DIR = "./.temp"


GESTURE_CHECK = GESTURE_DATABASE.str_to_gesture(b'eNq9lVtIU2EcwI/gFRRdXigf7FCG1oMJpmWCO4RxhB4SFBJEdz3ubM5t7aJ5SZeKD3ECwaOUoY1AGggq5KUMm5mXqQWjLCw0zbxUUEmRhFi27+x8+zzoyyA6Lxu/3////S87O8fq3xIZjHEXE1qiLqtIUlEms8VIsUwQyX9rZo9fY6+yiUxAuVppplmSUNk8GYE0pVbRZjeRSz0knE+XGIx6pUUBVGyPaNOZmcsEmcxGfQllYgtZGmPC+NNzOYhqBBr0ap0ZBCW6o0L5qBwAUZDfFZZ0uOwdFzvSMhm/CpYU39sOiTtb0WSR0yJPDB1FOp5/LZhoSMuho0lxQ4yojkokhH5mLSOrOtrl9o6u6nrHx8e40E+9ix01/cwGfjC9IXNs84HQT77aIkpmncA/6T/aWTm/IvQTVemfHjlw4McP+tekREYI/ZjpkOp+hw346fqAuR/qMaF3aDYMrZ1W4GeSi/0vmG8Kff+3btFEGNf/JH4My0hhhb47d26k69wI8E+HsxLqfiuFvnXIHhiVgAE/vHN+I1URLPDitmDlie5VAvhe0+iNvOv5Qt+zNfDi111uvtvL2FD4tFXonV9EG5dO02D/A7NBWe2f8f/rXQuVovXleOBHT47nOmRa3/zr7Cqt/cws8NM5ZMHih2rf/NsebaOyFuxP7DqVZ9g+UuObX4wptOHjvcDPZrVYQhV1vvnl0cH2763c/f8mf20I75v4t37ljjU6vi8O+IUD5faGjSLf/Cr4+0xNA78UnpfqbGoW+vXj9sHueXD/it9HKsue2V5a5BQTalIYKUqHnhMkUTzCPX1IguK++DWyu5kNsaW9TIVDJt4BF8ekPFN6EjhmhUyKmA0yHDFYVyHxnkdjkGHeOC+Toxo07EVuRYyAjEAM9idb8s5Bw/5kqD8a9ifblQv7k44gBvciRblq2J8U99ZADEPsMDfm/kxSCz7/cAzOIUF7Vkv4uCLHPgztQA1n28U02N7zNPvMUcKl+Ll3gHav3Wd/pbCGAv2WOimfq0SzGeD+itH+LjfxjEY1jJB5mudyTbCuxuaNMyfzTIvqWmCcDp1XFsEzPZqtDNYwEN4a5XAvBlSjHNYwuHhGWeQyJsSs11JGmU5Bud+gD2+Bq43x18lK3W9/zP0uSfoLWtXZrg==')

GESTURE_TRIANGLE = GESTURE_DATABASE.str_to_gesture(b'eNp9mWtsHNUVx8fKA1DcZiOoamjUbIUIRq3iBfWDJVp5QqtuEkKzUVThPhyPvQ+P7fXu+LnvnbslBYtsG0dsC0So3iSIWm3abFvRGISym1BCGoPYJISYV7JCUDVFNI5QUFsoqWc95547ucf2J/t37r1zzv+c+zRb/kvvOqX+k2/s7x1LbOgJDo+MDgUL+Ru89m+PFe7KFTKF5vyKWG9gRC941b7aQo+VerC3Rx+ZJwF1gay2u3caQ9HAqN8yrfng5u3/MTbmbxgeGYr2B4cLHQVdyX/BHn1HHeI3VhrR3siI1ah5vlWj3cpnQWzUEC94y7UjLV/P7duUb0jM/3Fqc8MjgSvfHe3W1yy00W/xlt/d8+x9L21R9C95y8d3H955aa3baX8zcP7UT59qtuxHPu/4uTLlcdrPnfHftnnkHcs+9Y0fz+7a4nPaT3/8/MpVj26dt7ftvv3PdxxqVp32mb3PfWXv9Jxl/9PF2579fUu70/7SitaHmudqlv34J7e+HVUMp/2FK9FzbHvRss+8/+3H/vfeIaf9cOndzR0PqZb9zNrP7ts4ucFp/9mn/b++lLfib3vD++bzux5Y6bC3/eaWU/u+eL7e/62hI/ec+O8Fp336YCgz+2n9+xe2a97lH0Sc9vLJbRfu37LQ/+iHv5o5ut5p/+vqFT36Dpdlf/3U2RPh9DNO+8v7k1/en/RZ9uqOY/+8Y9WjTvvMKw/ueb/ZbdlPjP9i99SdLzjt1cKyrWuvjFv26bP3PNxo1Jz2M1efCX9n1bRlf7wpdHMk48xP27mDmbmBSx4rv4cuH2iqZq/rP7via67CMt2yl2//3kdDn1Sd9rfv7/rJyZ66/aT5csumjqLTfmHv/qnPZgzLXv3L1eEPJ/913fiXjn7rwAOtlv30srvOz/m/6bSf3fhW1ftavX5Pb9t579X1ycX0oe2V9MT8HCktaj+wfdcPjx9UFvt++bcfPX7Tmu9XFvO/fGzoxTOX/1Zc1P7qjz4e/sPW8UXtr/+gY/3dT7O6ve/Y6r+/8/R18/OPjRse6VzQ76v53713687R7mC+cdg/FAxGcJ3wqqOV+urjVbu0+i8Pzy87o1Vg5jXrp85qBJsDNsnZmAKsjMwFrD5IQ525bdatIPMsxdzIVGAq93nMB0wjGEOmASsiMwjGgFWQTQCrycyvICsuxdzISsCEOCAf/k7UD/LhR+3H5mQWA+39kwSrcP1ioL0f8xEDnQOofQz0C6DPMdAvgD7HQL8Aah8D/QKoaay4FEOdY6BLAHWOgQZBhWCCf1CnwTbUgDPUNDYnszjUabDINYh7lmKoaRy0CtZkFkKf46BfCH2Og34h1DQO+oVQ0zjUWgjrOQ76hVDTONRQCPWLVwkGGvSgfwmolx7UL7Gu/us8Yzy2BMzBHtQg0Wm304XxIDYd401AHDrGm5iEvhhvAuLQMbYExKFjvSQuQl+MLVGPrWGeXeNxJCG23jaCaTyOJMyPXsx50mOP14vfTUIu+1SCYRxJw+7bh3EkQYO+i+gL5LLvmsz61yE7bMfbr6J/oFU/5igJWvUL370MfVGrFGgQxhylYC6EMbZUi903jOOlVDu2MK73yDC2FMyFAVzHU6DVAMaRYnbfAazxFGg1gNqnQJcBIY6K3TcixAEaRDAfKaj7CH4jrUBfzDkyjC0NukQwR2lYD6IYW7rN1iqK302DBlHUL60RDOZMFGNLm/Z4Bs6tNOhiuJCBLgZqkIb11PAgK8N4qH26asdr+LAdaGUYBBP0uwbj7eG6ZFwwHsaWAa0MzGVGXYpVkflgvDlkoN+gQjDUJQOaDqIuGVhjBz1cg8yE/Y1BrHtkqEsGdBYZ6DyIOc9UlmKoaeY1W79B3M8zsG8NTmA7zgRNIR+DJYKhplmFYKvhu1WCYf1lYU0kGeYj61mKCX1V2WdkGFt2G/iCWmU1yAdqmjXkXCJzEe2wXrJ7oHarBKsQTPCvCDWJdY8M50eWz0HB54o8L5FhnWZhDRPmfrZmf0NYN7KQ8ygjGK5NJtRBBM8qJl/XcP0z3bD+4XjI0D8T8htB/0xVXp+RoaYm3xcwDhPOEQO4J5uGvH9wFsa12IQ5Lew9JqyTwh6FTPgunEHCGsHcBBPiLcl7rUnsySbfkzWC4VpswplGOAuYcKYRzgwMcimcLZAxgmFs7Eb5/MKgDvrcBMN4WROckTCXjJ+bMF5kGC9rls9hDGpIOK+xVmBYQ8iEeKGudEYwId5N8rmTQf0JZ1bWDmdb4buwpwhnYKbLZ2UGNdmD5zUWl8/ejC3FhNjG5TM/m5DvC+wJ+f7BivLdhU3J9x5kQhwl+W7FpuV7GYMaDwj+VeU7IjJhvFn5HspqBPuHfK9lxP2X/Vu+O+cU+d6NDHOeu1G+2+dc8htAzi2/KeSa5bcHZKhBjnjfyLXKbyM5VX5DyW2S31py7fLbDTLhu1C7XYIGULuaEC/UribEC7WrFQkmaAC1qwm+jBMMalfDdRyZoAvUc2ddg8+dzEQ2QbBxgjGCxQmmEaydYD6CqQTzEMxNsCaCuQimyIzPD5HNEqxCMJj7ncLcf4JgOsHaCdZKsCaZ8b1MZLDniaxE9J0gmEEwD8FcMuNnKZFViHaEL1lGMEPWmZ9jRUbUS5aolyxRL/x8LzIiv/yeIjLCvwxR9xnCP36nExi/+4kM7pLC/OX3WpF5COaSGb/Hi6xIsAmCRcE/gfmIdi1EO7fcjr+hiKxCtDtMtCN8ThI+8/cmkRG+8LcvkZXkvglC+4RLXnf5O6HISgRjBPMRTCWYh2CUL4rMYoR//L1Y2FP4u7LIGMEMgmkEUwnmIZibYC6CKTLjb/oiqxGsQjAi3jFirx0jNBgjNBgjNOD/T9GI/8WITNIlONrdlb9pJBoODnVF/MGCt+25J62fffnlka6BYCGvFEa7N/wftaAGjw==')


GESTURE_SWIPE_DOWN = GESTURE_DATABASE.str_to_gesture(b'eNqN129oG2UcB/ArXVY2Wow6N8UXC4NuK4Ua5xtR4U4UwmC6oigVq82/s5d1TdIk17VO3XXtNjdPKfZ80Vm6Q/Kie6HE7oXb2tlTZKzMYEb2vyo3VlQQJIyJirC5nImXeL/n9r03OT7f57l7nt+TPHdRVnwUWcdZh9rcFxsc7ugV0xk5JWpqU6ByNqG1jWhva5tVz65YNCNpAeHBSo+VkhjrlTJ3ZMfC7fKh3lPp3pNMJaJypBx5ZtuW+/dNqE3pTCrRJ6a11zSJU1sqV3/RQvseK5OJWDxTbrT5TqvmSqvOMtqNGoa0wIKczbf//BSnNgxrAf6HL6a7X5+KymHp3n/bSGv+ayE9EOCXjnyuPP2TVp+PRbueXLXJyq8c+Cbb6jeY+aX53pce3eRn5heybw6vGehi5kX1/ak/5saY+bmMbix5csz8uxf2X8//+TgzP7vh03ZNHWfmp28U06/6TGb+ddtVvdDNvv+pjYKnMOFl1veY9nxwbrXBzGfys1svLHLMfPKzdwd/P/W//Nmm7S3XguV84eCWt54wFtn50eTerqVn6nM++clfUnzZymePDT328VqDmc/d355t+c3LzL86kTgkhOvrw49cj7+y7W8rP71X6j670WTmi0qjGbqmMPP82i/f2XpzhpkXXp7/4KHGX5h5senM2IH7BGZ+vtha3P3weWZ+cXp0Q6K1/vfDvyf33AqPWvnlmDkQ6bjJzK+O5J/bs/wtM/9+8mTb1OFpZv6juG5oPLulPv9wdObcvEcp52Z0sfRrY6scFtXmdCQlinF7nwgIynFrPwoIg49Y29B+rdZ81sndjcNMNsufDXc3g+hLWQ403d1yVVNAS4IWBK0TNN5eI1fzE30p84LGYZYp2WvpaibRl7ICaAZoOdDGQVNAS4IWBG27c81JE4i+lPlB84HmBY0jvhuEpUvOvqSZoBVAy4Gmg6aAlgStEzQBNB9oHGapEmgF0HTQxkELgiaA5sVswAStAJoO2h7nHkEaUYNaqz5DB/zOZzdpxLsAZckSaCZoBmg6aApone5mVM0Pmhc0DrOEDlrNu4Wr+ew1d7O4DpriHEutnakah1m/DpoCWs3c3GznbbtWrkaMhTQBsz7T3QpVM0AT7Lm52np7bm62Q3fegzQBs5gJmu4cM2m8c8ykrcdMImpKWhA0DrNeYm6kKaARNSCNGgthbxig6aApoAXd7XLVBNA4zMSa/7quZoCmg9Zjr5Gr8ZhFTefcSFNAC4LGOedGWcQAjagBacSa15pZsbAJmgGaApoAWk2t3CxkgrZg18rVjriYKIdD6qpMYqeYCsUjohbgT0yWj8PqinioX9RUTpPDHf8Arl6FWA==')

GESTURE_DATABASE.add_gesture(GESTURE_CHECK)
GESTURE_DATABASE.add_gesture(GESTURE_TRIANGLE)
GESTURE_DATABASE.add_gesture(GESTURE_SWIPE_DOWN)
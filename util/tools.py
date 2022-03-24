

'''
Convert a Hex color, #00FF00, into an RGBA floating point
value that can be used with kivy components.  Opacity can optionally be passed
and will be returned as passed.  Opacity should be a value between 0 and 1
'''
def hex(hex_string, opacity = 1.0):
    hex_string = hex_string.replace('#', '')
    r_hex = hex_string[0:2]
    g_hex = hex_string[2:4]
    b_hex = hex_string[4:6]
    return (int(r_hex, 16) / 255, int(g_hex, 16) / 255, int(b_hex, 16) / 255, opacity)
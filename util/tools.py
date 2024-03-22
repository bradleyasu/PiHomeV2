import random
import subprocess

from PIL import Image, ImageDraw, ImageFilter
from kivy.graphics.texture import Texture
from kivy.core.image import Image as CoreImage
from util.const import TEMP_DIR
from util.phlog import PIHOME_LOGGER

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


'''
Execute a bash command and return the results as a dictionary.  The dictionary
will contain the following keys:
    return_code: The return code of the command
    stdout: The standard output of the command
    stderr: The standard error of the command
'''
def execute_command(command):
    PIHOME_LOGGER.info("Executing Command: " + command)
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return {
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except Exception as e:
        return {
            "error": str(e)
        }


def get_semi_transparent_gaussian_blur_png_from_color(color, as_texture = True, name = "_blur_", width = 100, height = 100):
    # use PIL to create a get_app().width by get_app().height image
    # with a semi-transparent gaussian blur
    noise = generate_noise(width, height)
    image = Image.new('RGBA', (width, height), (0,0,0, 170))
    image.paste(noise, (0,0), noise)
    # generate static/snow effect on image layer
    image = image.filter(ImageFilter.GaussianBlur(radius=10.0))
    image.save(fp="{}/{}.png".format(TEMP_DIR, name), format="png")
    if as_texture == True:
        return create_texture_from_image_file("{}/{}.png".format(TEMP_DIR, name))
    return "{}/{}.png".format(TEMP_DIR, name)


def create_texture_from_image_file(file):
    try:
        image = CoreImage(file, keep_data=True)
        texture = Texture.create(size=(image.width, image.height), colorfmt='rgba')
        texture.blit_buffer(image.texture.pixels, colorfmt='rgba', bufferfmt='ubyte')
        return texture
    except Exception as e:
        print(f"Error creating texture: {e}")
        return None  # Return None in case of an error

def generate_noise(width, height):
    noise = Image.new('L', (width, height))
    for y in range(height):
        for x in range(width):
            noise.putpixel((x, y), (random.randint(0, 255)))
    return noise


def generate_blob_noise(width, height, num_blobs=50, max_blob_size=100):
    noise = Image.new('L', (width, height))
    draw = ImageDraw.Draw(noise)
    for _ in range(num_blobs):
        blob_size = random.randint(10, max_blob_size)
        x = random.randint(0, width - blob_size)
        y = random.randint(0, height - blob_size)
        color = random.randint(0, 255)
        # color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), random.randint(50, 150))
        draw.ellipse([x, y, x + blob_size, y + blob_size], fill=color)
    return noise


def get_cpu_temp():
    try:
        temp = subprocess.run(["vcgencmd", "measure_temp"], stdout=subprocess.PIPE)
        return temp.stdout.decode("utf-8").replace("temp=", "").replace("'C\n", "")
    except Exception as e:
        PIHOME_LOGGER.error(f"Error getting CPU temp: {e}")
        return "N/A"
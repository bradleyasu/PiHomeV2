import sys
import time


can_use_rotary = False

if sys.platform == 'linux':
    import RPi.GPIO as GPIO
    from time import sleep

    can_use_rotary = True
else:
    GPIO = None
    sleep = None

class RotaryEncoder():

    # LONG_PRESS_THRESHOLD IS 2 seconds
    LONG_PRESS_THRESHOLD = 1
    a_pin = 17      # DT
    b_pin = 18      # CLK
    button_pin = 27 # SW
    # rotary counter is the number of clicks
    rotary_counter = 0
    # last state is the last state of the rotary encoder
    last_state = 0
    # direction is the direction of the rotary encoder.  1 is clockwise, -1 is counter clockwise, 0 is no movement
    direction = 0
    button_pressed = False
    button_callback = lambda long_press: ()
    update_callback = lambda direction: ()
    is_initialized = False
    press_time = 0
    press_duration = 0

    def __init__(self, **kwargs):
        super(RotaryEncoder, self).__init__(**kwargs)
        if can_use_rotary and not self.is_initialized:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.a_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(self.b_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(self.button_pin, GPIO.BOTH, callback=self.on_press_up, bouncetime=300)
            GPIO.add_event_detect(self.a_pin, GPIO.BOTH, callback=self.update)
            GPIO.add_event_detect(self.b_pin, GPIO.BOTH, callback=self.update)
            self.is_initialized = True

    def on_press_up(self, channel):
        if GPIO.input(channel):
            self.button_pressed = False
            self.press_duration = time.time() - self.press_time
            if self.press_duration > self.LONG_PRESS_THRESHOLD:
                self.button_callback(long_press=True)
            else:
                self.button_callback(long_press=False)
        else:
            self.button_pressed = True
            self.press_time = time.time()

    def update(self, data):
        if can_use_rotary:
            sleep(0.002)
            state = GPIO.input(self.a_pin)
            if state != self.last_state:
                if GPIO.input(self.b_pin) != state:
                    self.rotary_counter -= 1
                    self.direction = -1
                else:
                    self.rotary_counter += 1
                    self.direction = 1
            else:
                self.direction = 0
            self.update_callback(self.direction)
            self.last_state = state

    def reset(self):
        self.rotary_counter = 0
        self.direction = 0
        self.button_pressed = False

    def cleanup(self):
        if can_use_rotary:
            GPIO.cleanup()

    def __del__(self):
        self.cleanup()

    def __str__(self):
        return "Rotary Encoder: {}, {}, {}".format(self.rotary_counter, self.direction, self.button_pressed)
    

ROTARY_ENCODER = RotaryEncoder()
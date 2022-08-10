from time import time
from kivy.clock import Clock
from kivy.network.urlrequest import UrlRequest
from util.helpers import get_app, toast
import paho.mqtt.client as mqtt_client

class MQTT:
    
    client = None
    def __init__(self, host, port = 1883, keep_alive = 60, feed = "pihome", user = "", password = "", **kwargs):
        super(MQTT, self).__init__(**kwargs)
        self.host = host
        self.port = port
        self.keep_alive = keep_alive
        self.user = user
        self.password = password
        self.feed = feed
        self.init_connection()

    
    def init_connection(self):
        if self.client is not None:
            return
        self.client = mqtt_client.Client()

        if self.user != "" and self.password != "":
            self.client.username_pw_set(self.user, self.password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        if self.port == 8883:
            self.client.tls_set_context()

        self.client.connect(self.host, self.port, self.keep_alive)
        self.client.loop_start()

    def on_message(self, client, userdata, msg):
        print(str(msg.payload))

    def on_connect(self, client, userdata, msg, rc):
        self.client.subscribe(self.feed)
import json
from time import time
from kivy.clock import Clock
from kivy.network.urlrequest import UrlRequest
from util.helpers import error, get_app, info, toast
import paho.mqtt.client as mqtt_client

class MQTT:
    
    client = None
    app_listeners = []
    display_listeners = []
    notification_listeners = []
    command_listeners = []
    toast_listeners = []
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

    def process_webhook(self, webhook):
        """
        Process a webhook from the server
        """
        if "type" in webhook:
            self.notify(webhook["type"], webhook)
        else:
            error("Webhook does not contain a type")

    def on_message(self, client, userdata, msg):
        try: 
            info("[ MQTT ] Message Recieved: {} | {} | {}".format(str(client), str(userdata), str(msg.payload)))
            payload = json.loads(msg.payload)
            self.notify(payload["type"], payload)
        except Exception as e:
            error("[ MQTT ] Failed to process and notify listeners. {}".format(str(e)))

    def on_connect(self, client, userdata, msg, rc):
        self.client.subscribe(self.feed)
        info("[ MQTT ] Client active and actively listening for messages!")

    
    def add_listener(self, type, callback):
        """
        type: The type of event to listen for.  `app`, `display`, `notification`
        callback: The function to execute with the payload as the single parameter
        """
        if type == "app":
            self.app_listeners.append(callback)
        if type == "display":
            self.display_listeners.append(callback)
        if type == "image":
            self.display_listeners.append(callback)
        if type == "notification":
            self.notification_listeners.append(callback)
        if type == "command":
            self.command_listeners.append(callback)
        if type == "toast":
            self.toast_listeners.append(callback)

    def notify(self, type, payload):
        if type == "app":
            for callback in self.app_listeners:
                callback(payload)

        if type == "display" or type == "image":
            for callback in self.display_listeners:
                callback(payload)

        if type == "notification":
            for callback in self.notification_listeners:
                callback(payload)

        if type == "command":
            for callback in self.command_listeners:
                callback(payload)

        if type == "toast":
            for callback in self.toast_listeners:
                callback(payload)

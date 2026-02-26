import json
from time import time
from kivy.clock import Clock
from kivy.network.urlrequest import UrlRequest
from events.pihomeevent import PihomeEventFactory
from util.helpers import get_app, toast
import paho.mqtt.client as mqtt_client

from util.phlog import PIHOME_LOGGER

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

    def process_webhook(self, webhook):
        """
        Process a webhook from the server
        """
        if "type" in webhook:
            self.notify(webhook["type"], webhook)
        else:
            PIHOME_LOGGER.error("Webhook does not contain a type")

    def on_message(self, client, userdata, msg):
        try: 
            PIHOME_LOGGER.info("[ MQTT ] Message Recieved: {} | {} | {}".format(str(client), str(userdata), str(msg.payload)))
            PihomeEventFactory.create_event_from_json(msg.payload).execute()
        except Exception as e:
            PIHOME_LOGGER.error("[ MQTT ] Failed to process and notify listeners. {}".format(str(e)))

    def on_connect(self, client, userdata, msg, rc):
        self.client.subscribe(self.feed)
        PIHOME_LOGGER.info("[ MQTT ] Client active and actively listening for messages!")

    def disconnect(self):
        """Properly disconnect and cleanup MQTT client"""
        if self.client is not None:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                PIHOME_LOGGER.info("[ MQTT ] Client disconnected and cleaned up")
            except Exception as e:
                PIHOME_LOGGER.error(f"[ MQTT ] Error during disconnect: {e}")

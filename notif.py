import paho.mqtt.client as mqtt
import requests
from time import monotonic
from threading import Thread
from json import dumps
from registry import Object_register



client = mqtt.Client()

TOPIC_CATCH = 'nano/events/catch'
TOPIC_WATCH = 'nano/events/watch'
WATCH_INTERVAL = 60

MQTT_BROKER = 'localhost'
MQTT_PORT = 1883


def _on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[Notif Service] Connected to on-device MQTT broker" )
    else:
        print(f"[Notif Service] Connection to MQTT broker failed")

def _on_publish(client, userdata, mid):
    print(f"[Notif Service] Notification {mid} sent")

client.on_connect = _on_connect
client.on_publish = _on_publish


def update_system(event_name, event):
    if event_name == 'watch':
        obj = event['detected']
        now = event['time']
        last = Object_register.watch.get(obj)
        if not last or (now - last) > WATCH_INTERVAL:
            Object_register.watch[obj] = now
            _publish_watch_event(event)
            
    elif event_name == 'catch':
        obj = event['detected']
        now = event['time']
        last = Object_register.catch.get(obj)
        if not last:
            Object_register.catch[obj] = now




def _publish_watch_event(event):
    notification = dumps(event)
    client.publish(TOPIC_WATCH, notification, qos=1)


def _publish_catch_summary():
    summary = {'detected':[], 'time':[]}
    for obj in Object_register.catch:
        if Object_register.catch[obj]:
            summary['detected'].append(obj)
            summary['time'].append(Object_register.catch[obj])
    notification = dumps(summary)
    client.publish(TOPIC_CATCH, notification, qos=1)


def start_surveillance_notifications():
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start() #background thread for callback execution
    
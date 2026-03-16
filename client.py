"""
client.py  —  runs on the Mac

Usage:
    python3 client.py --nano 192.168.99.24 --watch person bird --catch car person

    --watch   labels to receive a notification for each time they are first
              seen within a 60-second window
    --catch   labels to count; a summary is published when you disconnect
              from the RTSP stream

Install deps:
    pip3 install paho-mqtt requests

Workflow:
    1. POST watch/catch config to the Nano's Flask endpoint
    2. Subscribe to MQTT topics and print events as they arrive
    3. Run your GStreamer pipeline separately to view the video
    4. When you close the GStreamer pipeline, the Nano detects the
       disconnect and publishes the catch summary automatically
"""

import argparse
import datetime
import json
import signal
import sys
import requests
import paho.mqtt.client as mqtt


FLASK_PORT   = 5001
MQTT_PORT    = 1883
TOPIC_WATCH  = "nano/events/watch"
TOPIC_CATCH  = "nano/events/catch"


# ---------------------------------------------------------------------------
# Config POST
# ---------------------------------------------------------------------------
def post_config(nano_ip: str, watch: list, catch: list):
    url     = f"http://{nano_ip}:{FLASK_PORT}/surveillance"
    payload = {"watch": watch, "catch": catch}
    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        print(f"[CONFIG] watch={data['watch']}")
        print(f"[CONFIG] catch={data['catch']}")
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Could not reach Nano at {url} — is run.py running?")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Config POST failed: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# MQTT callbacks
# ---------------------------------------------------------------------------
def on_connect(client, userdata, flags, rc):
    if rc != 0:
        print(f"[MQTT] Connection failed, rc={rc}")
        sys.exit(1)
    print("[MQTT] Connected to broker")
    client.subscribe(TOPIC_WATCH, qos=1)
    client.subscribe(TOPIC_CATCH, qos=1)
    print(f"[MQTT] Subscribed — waiting for events (Ctrl-C to exit)\n")


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except Exception:
        print(f"[MQTT] Unreadable message on {msg.topic}: {msg.payload}")
        return

    if msg.topic == TOPIC_WATCH:
        # Payload: {"detected": "person", "time": 1234567890.0}
        label = data.get("detected", "?")
        ts    = data.get("time", 0)
        t     = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        print(f"[WATCH]  {label} detected at {t}")

    elif msg.topic == TOPIC_CATCH:
        # Payload: {"detected": ["car", "person"], "time": [ts1, ts2]}
        detected = data.get("detected", [])
        times    = data.get("time",     [])
        print("[CATCH]  Session summary:")
        if detected:
            for label, ts in zip(detected, times):
                t = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                print(f"         {label:20s} first seen at {t}")
        else:
            print("         (none of the watched objects were detected)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Nano surveillance client")
    parser.add_argument("--nano",  default="192.168.99.24", help="Nano IP address")
    parser.add_argument("--watch", nargs="*", default=[],
                        help="Labels to receive live notifications for")
    parser.add_argument("--catch", nargs="*", default=[],
                        help="Labels to count and summarise on disconnect")
    args = parser.parse_args()

    post_config(args.nano, args.watch, args.catch)

    mqttc = mqtt.Client()
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message

    try:
        mqttc.connect(args.nano, MQTT_PORT, keepalive=60)
    except Exception as e:
        print(f"[ERROR] Could not connect to MQTT broker at {args.nano}:{MQTT_PORT}: {e}")
        sys.exit(1)

    def _stop(signum, frame):
        print("\n[INFO] Disconnecting...")
        mqttc.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)

    mqttc.loop_forever()


if __name__ == "__main__":
    main() 
"""
client.py

Usage:
    python3 client.py --camera 192.168.99.24 --watch person bird --catch car person

Workflow:
    1. POST watch/catch config to the Nano's Flask endpoint
    2. Subscribe to MQTT topics and log events as they arrive
    3. Run GStreamer pipeline separately to view the video
    4. When GStreamer pipeline closes, the Nano detects the
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


def post_config(nano_ip: str, watch: list, catch: list):
    url     = f"http://{nano_ip}:{FLASK_PORT}/surveillance"
    payload = {"watch": watch, "catch": catch}
    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        print(f"[API Client] Successful POST: watch={data['watch']}")
        print(f"[API Client] Successful POST: catch={data['catch']}")
    except requests.exceptions.ConnectionError:
        print(f"[API Client] Error: Could not reach Nano at {url} — is run.py running?")
        sys.exit(1)
    except Exception as e:
        print(f"[API Client] Error: Config POST failed: {e}")
        sys.exit(1)


def _on_connect(client, userdata, flags, rc):
    if rc != 0:
        print(f"[Notif Client] Connection failed, rc={rc}")
        sys.exit(1)
    print("[Notif Client] Connected to broker")
    client.subscribe(TOPIC_WATCH, qos=1)
    client.subscribe(TOPIC_CATCH, qos=1)
    print(f"[Notif Client] Subscribed — waiting for events \n")


def _on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except Exception:
        print(f"[Notif Client] Unreadable message on {msg.topic}: {msg.payload}")
        return

    if msg.topic == TOPIC_WATCH:
        # Ex payload: {"detected": "person", "time": 1234567890.0}
        label = data.get("detected", "?")
        ts    = data.get("time", 0)
        t     = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        print(f"[Notif Client]  {label} detected at {t}")

    elif msg.topic == TOPIC_CATCH:
        # Ex payload: {"detected": ["car", "person"], "time": [ts1, ts2]}
        detected = data.get("detected", [])
        times    = data.get("time",     [])
        print("[Notif Client]  Session summary:")
        if detected:
            for label, ts in zip(detected, times):
                t = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                print(f"         {label:20s} first seen at {t}")
        else:
            print("         (none of the watched objects were detected)")


def main():
    parser = argparse.ArgumentParser(description="Nano surveillance client")
    parser.add_argument("--camera",  default="192.168.99.24", help="Nano IP address")
    parser.add_argument("--device", default="", help="MAC address or similar identifying value for optional Persistent Sessions" )
    parser.add_argument("--watch", nargs="*", default=[],
                        help="Watch all appearances; get real-time notifications during session")
    parser.add_argument("--catch", nargs="*", default=[],
                        help="Catch the first appearance only; see timestamp in session summary")
    args = parser.parse_args()

    post_config(args.camera, args.watch, args.catch)

    client = mqtt.Client(client_id=args.device)
    if args.device != "":
        client._clean_session = False #enables persistent sessions
    client.on_connect = _on_connect
    client.on_message = _on_message

    try:
        client.connect(args.camera, MQTT_PORT, keepalive=60)
    except Exception as e:
        print(f"[Notif Client] Could not connect to MQTT broker at {args.nano}:{MQTT_PORT}: {e}")
        sys.exit(1)

    def _stop(signum, frame):
        print("\n[Info] Disconnecting...")
        client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)

    client.loop_forever()


if __name__ == "__main__":
    main() 
from flask import Flask, request, jsonify
from threading import Thread
from registry import Object_register
from cvconfig import Object_classes


app = Flask(__name__)

FLASK_PORT = 5001


@app.route('/surveillance', methods=['POST'])
def set_surveillance():
    data = request.get_json(force=True)
    if not isinstance(data, dict):
        return jsonify({"error": "expected JSON object"}), 400

    valid_objects = set(Object_classes)

    _catch = data.get("catch", [])
    _watch = data.get("watch", [])

    Object_register.catch = {obj:None for obj in _catch if obj in valid_objects}
    Object_register.watch = {obj:None for obj in _watch if obj in valid_objects}

    return jsonify({
        "catch": list(Object_register.catch.keys()),
        "watch": list(Object_register.watch.keys()),
    })

@app.route("/surveillance", methods=["GET"])
def get_surveillance():
    return jsonify({
        "catch": list(Object_register.catch.keys()),
        "watch": list(Object_register.watch.keys()),
    })


def start_surveillance_api():
    t = Thread(
        target=lambda: app.run(host="0.0.0.0", port=FLASK_PORT),
        daemon=True,
    )
    t.start()
    print(f"[API Service] HTTP endpoint listening on port {FLASK_PORT}")


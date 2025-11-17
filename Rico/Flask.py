from flask import Flask, render_template_string, jsonify, request
from datetime import datetime
import threading
import zmq
import time

app = Flask(__name__)

# Global Telemetry Storage

telemetry_data = {
    "altitude": 0.0,
    "speed": 0.0,
    "latitude": 0.0,
    "longitude": 0.0
}

altitude_history = []
telemetry_lock = threading.Lock()

# Flask API Routes

@app.route("/")
def index():
    return render_template(dashboard.html)

@app.route("/telemetry")
def telemetry():
    with telemetry_lock:
        return jsonify({
            **telemetry_data,
            "history": altitude_history
        })

@app.route("/simulate", methods=["POST"])
def simulate():
    data = request.get_json()
    with telemetry_lock:
        telemetry_data.update({
            "altitude": data["altitude"],
            "speed": data["speed"],
            "latitude": data["latitude"],
            "longitude": data["longitude"]
        })
        altitude_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "altitude": telemetry_data["altitude"]
        })
    return jsonify({"status": "Telemetry updated"})



# Background ZeroMQ Listener

def zmq_listener():
    ctx = zmq.Context()
    socket = ctx.socket(zmq.SUB)
    socket.connect("tcp://localhost:5556")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    print("[ZMQ] Listening for drone telemetry...")

    while True:
        message = socket.recv_json()
        print("[ZMQ] Received:", message)

        with telemetry_lock:
            telemetry_data["altitude"] = message["z"]
            telemetry_data["speed"] = (message["vx"]**2 + message["vy"]**2 + message["vz"]**2) ** 0.5
            telemetry_data["latitude"] = message["x"]
            telemetry_data["longitude"] = message["y"]

            altitude_history.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "altitude": telemetry_data["altitude"]
            })

            if len(altitude_history) > 60:
                altitude_history.pop(0)


# Start ZMQ Listener Thread
listener_thread = threading.Thread(target=zmq_listener, daemon=True)
listener_thread.start()


# Start Server

if __name__ == "__main__":
    print("[SERVER] Flask dashboard running at http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)

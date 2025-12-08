from flask import Flask, render_template_string, jsonify, request, send_from_directory
from flask_socketio import SocketIO
from datetime import datetime
import threading
import zmq
import time
import os

# -------------------------
# Configuration / App Init
# -------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
socketio = SocketIO(app, cors_allowed_origins="*")

# Ensure static files serve with correct MIME types (ES module requirement)
@app.route('/static/<path:path>')
def static_proxy(path):
    return send_from_directory("static", path)

# -------------------------
# Telemetry storage
# -------------------------
telemetry_data = {
    "altitude": 0.0,
    "speed": 0.0,
    "latitude": 0.0,
    "longitude": 0.0
}
altitude_history = []
telemetry_lock = threading.Lock()

# -------------------------
# HTML Dashboard Template
# -------------------------
dashboard_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real-Time Drone Dashboard</title>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>

    <style>
        body {
            background: #111;
            color: #fff;
            font-family: Arial;
        }
        .title {
            width: 90%;
            margin: 20px auto;
            font-size: 24px;
        }
        .panel {
            width: 90%;
            margin: auto;
            background: #2b2b2b;
            padding: 15px;
            border-radius: 12px;
        }
        .row {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
        }
        input {
            flex: 1;
            background: #444;
            color: white;
            padding: 10px;
            border-radius: 8px;
            border: none;
        }
        button {
            background: #0a84ff;
            color: white;
            border: none;
            border-radius: 12px;
            padding: 10px 20px;
            cursor: pointer;
            font-weight: bold;
        }
        canvas {
            background: #000;
            border-radius: 12px;
        }
        #droneContainer {
            width: 90%;
            height: 400px;
            margin: 20px auto;
            background: #2b2b2b;
            border-radius: 12px;
        }
    </style>
</head>
<body>

    <div class="title">Real-Time Drone Dashboard</div>

    <div class="panel">
        <div class="row">
            <input id="altitudeInput" type="number" placeholder="Altitude (manual override)">
            <button onclick="sendManual()">Send</button>
        </div>
    </div>

    <div class="panel" style="margin-top:20px;">
        <canvas id="altitudeChart"></canvas>
    </div>

    <div id="droneContainer"></div>

    <script>
        /* -------------------------
           WEBSOCKET TELEMETRY
        -------------------------- */

        const ws = new WebSocket("ws://localhost:8765");

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const altitude = data.z; // using Z as altitude

            updateCharts(altitude);
            updateDroneRotation(data.vx, data.vy, data.vz);
        };

        function sendManual() {
            const val = parseFloat(document.getElementById("altitudeInput").value);
            if (!isNaN(val)) updateCharts(val);
        }

        /* -------------------------
           ALTITUDE CHART
        -------------------------- */

        const ctx = document.getElementById("altitudeChart");

        const labels = [];
        const altitudeData = [];

        const altitudeChart = new Chart(ctx, {
            type: "line",
            data: {
                labels,
                datasets: [{
                    label: "Altitude (m)",
                    data: altitudeData,
                    borderColor: "#0a84ff",
                    backgroundColor: "#0a84ff",
                    borderWidth: 3,
                    pointRadius: 5,
                    pointBackgroundColor: "#0a84ff",
                    pointBorderColor: "#fff"
                }]
            },
            options: {
                responsive: true,
                scales: {
                    x: { ticks: { color: "#aaa" } },
                    y: { ticks: { color: "#aaa" } }
                }
            }
        });

        function updateCharts(alt) {
            const time = new Date().toLocaleTimeString();

            labels.push(time);
            altitudeData.push(alt);
            altitudeChart.update();
        }

        /* -------------------------
           3D DRONE MODEL (Three.js)
        -------------------------- */

        const container = document.getElementById("droneContainer");
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(
            70,
            container.clientWidth / container.clientHeight,
            0.1,
            1000
        );
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        container.appendChild(renderer.domElement);

        const geometry = new THREE.BoxGeometry(2, 0.5, 1.5);
        const material = new THREE.MeshStandardMaterial({ color: 0x00aaff });
        const drone = new THREE.Mesh(geometry, material);
        scene.add(drone);

        const light = new THREE.PointLight(0xffffff, 1);
        light.position.set(5, 5, 5);
        scene.add(light);

        camera.position.z = 5;

        function animate() {
            requestAnimationFrame(animate);
            renderer.render(scene, camera);
        }
        animate();

        function updateDroneRotation(vx, vy, vz) {
            drone.rotation.x += vy * 0.05;
            drone.rotation.y += vx * 0.05;
            drone.rotation.z += vz * 0.05;
        }
    </script>

</body>
</html>
"""

# -------------------------
# Flask Routes
# -------------------------
@app.route("/")
def index():
    return render_template_string(dashboard_html)

@app.route("/telemetry")
def telemetry():
    with telemetry_lock:
        return jsonify({ **telemetry_data, "history": altitude_history })

@app.route("/simulate", methods=["POST"])
def simulate():
    data = request.get_json()
    with telemetry_lock:
        telemetry_data.update({
            "altitude": float(data.get("altitude", telemetry_data["altitude"])),
            "speed": float(data.get("speed", telemetry_data["speed"])),
            "latitude": float(data.get("latitude", telemetry_data["latitude"])),
            "longitude": float(data.get("longitude", telemetry_data["longitude"]))
        })
        altitude_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "altitude": telemetry_data["altitude"]
        })
        if len(altitude_history) > 200:
            altitude_history.pop(0)

    socketio.emit("drone_state", {
        "x": telemetry_data["latitude"],
        "y": telemetry_data["longitude"],
        "z": telemetry_data["altitude"],
        "vx": 0.0, "vy": 0.0, "vz": 0.0
    })

    return jsonify({"status": "Telemetry updated"})

# -------------------------
# ZMQ Listener Thread
# -------------------------
def zmq_listener():
    ctx = zmq.Context()
    socket = ctx.socket(zmq.SUB)
    socket.connect("tcp://127.0.0.1:5556")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    print("[ZMQ] Listening for drone telemetry on tcp://127.0.0.1:5556 ...")
    while True:
        try:
            message = socket.recv_json()
        except Exception as e:
            print("ZMQ recv error:", e)
            time.sleep(0.5)
            continue

        with telemetry_lock:
            telemetry_data["altitude"] = float(message.get("z", telemetry_data["altitude"]))
            telemetry_data["speed"] = float(message.get("speed",
                                    (message.get("vx",0)**2 + message.get("vy",0)**2 + message.get("vz",0)**2)**0.5))
            telemetry_data["latitude"] = float(message.get("x", telemetry_data["latitude"]))
            telemetry_data["longitude"] = float(message.get("y", telemetry_data["longitude"]))

            altitude_history.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "altitude": telemetry_data["altitude"]
            })
            if len(altitude_history) > 200:
                altitude_history.pop(0)

        try:
            socketio.emit("drone_state", {
                "x": telemetry_data["latitude"],
                "y": telemetry_data["longitude"],
                "z": telemetry_data["altitude"],
                "vx": message.get("vx", 0.0),
                "vy": message.get("vy", 0.0),
                "vz": message.get("vz", 0.0)
            })
        except Exception as e:
            print("SocketIO emit error:", e)

zmq_thread = threading.Thread(target=zmq_listener, daemon=True)
zmq_thread.start()

# -------------------------
# Run Server
# -------------------------
if __name__ == "__main__":
    expected = [
        "static/js/three.module.js",
        "static/js/GLTFLoader.js",
        "static/js/OrbitControls.js",
        "static/models/dji_mavic_air.glb"
    ]
    for path in expected:
        if not os.path.exists(path):
            print(f"[WARNING] Missing expected file: {path}")

    ip_addr = os.popen("hostname -I | awk '{print $1}'").read().strip()
    print(f"[SERVER] Running at http://{ip_addr}:5000 or http://127.0.0.1:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)

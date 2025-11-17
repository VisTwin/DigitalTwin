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

dashboard_html = """

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Drone Dashboard</title>

    <style>
        body { margin: 0; background: #121212; color: white; font-family: Arial; }
        #viewer {
            width: 100%;
            height: 400px;
            background: black;
        }
        #altitude {
            width: 100%;
            height: 200px;
        }
    </style>
</head>

<body>
    <h2>Real-Time Drone Dashboard</h2>
    <div id="viewer"></div>
    <canvas id="altitude"></canvas>

    <!-- Three.js Module Loader -->
    <script type="module">
        import * as THREE from "/static/js/three.module.js";
        import { GLTFLoader } from "/static/js/GLTFLoader.js";

        const container = document.getElementById("viewer");

        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        container.appendChild(renderer.domElement);

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(
            45,
            container.clientWidth / container.clientHeight,
            0.1,
            100
        );
        camera.position.set(2, 2, 4);

        scene.add(new THREE.HemisphereLight(0xffffff, 0x222222, 1.2));

        // Load drone
        const loader = new GLTFLoader();
        let droneObj = null;

        loader.load(
            "/static/models/dji_mavic_air.glb",
            gltf => {
                droneObj = gltf.scene;
                droneObj.scale.set(1, 1, 1);
                scene.add(droneObj);
            },
            undefined,
            err => console.error("Failed to load GLB", err)
        );

        function animate() {
            requestAnimationFrame(animate);
            renderer.render(scene, camera);
        }
        animate();

        // --- LIVE DATA (WebSocket) ---
        const socket = io();

        socket.on("drone_state", msg => {
            if (!droneObj) return;

            droneObj.position.set(
                msg.x / 2,
                msg.z / 2,
                msg.y / 2
            );

            updateAltitude(msg.z);
        });

        // --- Altitude Chart ---
        let altCanvas = document.getElementById("altitude");
        let altCtx = altCanvas.getContext("2d");

        let altHistory = [];

        function updateAltitude(a) {
            if (altHistory.length > 100) altHistory.shift();
            altHistory.push(a);

            // Draw
            altCtx.clearRect(0, 0, altCanvas.width, altCanvas.height);

            altCtx.beginPath();
            altCtx.strokeStyle = "lime";
            altCtx.lineWidth = 2;

            altHistory.forEach((v, i) => {
                let x = (i / 100) * altCanvas.width;
                let y = altCanvas.height - (v / 5) * altCanvas.height;
                if (i === 0) altCtx.moveTo(x, y);
                else altCtx.lineTo(x, y);
            });

            altCtx.stroke();
        }
    </script>

    <!-- Socket.IO -->
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>

</body>
</html>

"""

# Flask API Routes

@app.route("/")
def index():
    return render_template_string(dashboard_html)

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

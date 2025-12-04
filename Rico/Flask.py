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
<meta charset="utf-8" />
<title>Drone Dashboard</title>
<style>
  body { margin: 0; background: #121212; color: #eee; font-family: Arial, Helvetica, sans-serif; }
  #viewer { width: 100%; height: 480px; min-height: 480px; background: #000; display:block; }
  #altitude { width: 100%; height: 200px; display:block; background:#111; }
  .row { max-width: 1000px; margin: 0 auto; padding: 8px; }

  /* New 2-column telemetry form */
  .form-grid {
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    background: #1a1a1a;
    padding: 12px;
    border-radius: 6px;
  }
  .form-grid .col {
    flex: 1;
    min-width: 220px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .form-grid label {
    display: flex;
    flex-direction: column;
    font-size: 0.9rem;
  }
  .form-grid input {
    padding: 6px 8px;
    background: #222;
    border: 1px solid #444;
    color: #fff;
    border-radius: 4px;
  }
  .submit-btn {
    margin-top: auto;
    padding: 10px 16px;
    background: #0099ff;
    color: #000;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  .submit-btn:hover { background: #33adff; }
</style>
</head>
<body>

  <div class="row"><h2>Real-Time Drone Dashboard</h2></div>

  <div class="row" id="controls">
    <form id="simForm" class="form-grid">

      <div class="col">
        <label>Altitude (m)
          <input id="sim_alt" type="number" step="0.1" required>
        </label>

        <label>Speed (m/s)
          <input id="sim_spd" type="number" step="0.1" required>
        </label>
      </div>

      <div class="col">
        <label>Latitude
          <input id="sim_lat" type="number" step="0.000001" required>
        </label>

        <label>Longitude
          <input id="sim_lon" type="number" step="0.000001" required>
        </label>
      </div>

      <button class="submit-btn" type="submit">Send</button>
    </form>
  </div>

  <div class="row"><div id="viewer"></div></div>
  <div class="row"><canvas id="altitude" width="1000" height="200"></canvas></div>

  <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>

  <!-- Three.js modules -->
  <script type="module">
    import * as THREE from "/static/js/three.module.js";
    import { GLTFLoader } from "/static/js/GLTFLoader.js";
    import { OrbitControls } from "/static/js/OrbitControls.js";

    // --- 3D Scene ---
    const container = document.getElementById("viewer");
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a0a);

    const camera = new THREE.PerspectiveCamera(50, container.clientWidth/container.clientHeight, 0.1, 1000);
    camera.position.set(3, 2, 5);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x080820, 1.0));
    const dir = new THREE.DirectionalLight(0xffffff, 0.6);
    dir.position.set(10, 10, 10);
    scene.add(dir);
    scene.add(new THREE.GridHelper(10, 20));

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0.5, 0);
    controls.update();

    let drone = null;
    const loader = new GLTFLoader();
    loader.load(
      "/static/models/dji_mavic_air.glb",
      (gltf) => {
        drone = gltf.scene;
        drone.scale.set(0.8, 0.8, 0.8);
        drone.position.set(0, 0, 0);
        scene.add(drone);
        console.log("GLB loaded successfully");
      },
      undefined,
      (err) => console.error("GLB load error:", err)
    );

    function animate() {
      requestAnimationFrame(animate);
      renderer.render(scene, camera);
    }
    animate();

    // --- Altitude Plot ---
    const altCanvas = document.getElementById("altitude");
    const altCtx = altCanvas.getContext("2d");
    let altHistory = [];

    function drawAltitude() {
      const w = altCanvas.width;
      const h = altCanvas.height;
      altCtx.clearRect(0,0,w,h);

      altCtx.fillStyle = "#070707";
      altCtx.fillRect(0,0,w,h);

      if (!altHistory.length) return;

      const maxA = Math.max(...altHistory, 5);
      altCtx.beginPath();
      altCtx.strokeStyle = "lime";
      altCtx.lineWidth = 2;

      altHistory.forEach((a, i) => {
        const x = (i / Math.max(altHistory.length-1,1)) * w;
        const y = h - (a / maxA) * h;
        if (i === 0) altCtx.moveTo(x,y);
        else altCtx.lineTo(x,y);
      });
      altCtx.stroke();
    }

    function pushAltitude(a) {
      if (altHistory.length > 200) altHistory.shift();
      altHistory.push(a);
      drawAltitude();
    }

    // --- Socket.IO ---
    const socket = io();

    socket.on("drone_state", (msg) => {
      const sx = (msg.x || 0) / 2;
      const sy = (msg.z || 0) / 2;
      const sz = (msg.y || 0) / 2;

      if (drone) drone.position.set(sx, sy, sz);
      if (typeof msg.z === "number") pushAltitude(msg.z);
    });

    // --- Manual telemetry submission ---
    document.getElementById("simForm").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const payload = {
        altitude: parseFloat(sim_alt.value),
        speed: parseFloat(sim_spd.value),
        latitude: parseFloat(sim_lat.value),
        longitude: parseFloat(sim_lon.value)
      };

      await fetch("/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      socket.emit("manual_update", payload);
    });

    // Handle resizing
    window.addEventListener("resize", () => {
      renderer.setSize(container.clientWidth, container.clientHeight);
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
    });
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

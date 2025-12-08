from flask import Flask, render_template_string, jsonify, request
from datetime import datetime
import threading
import zmq

app = Flask(__name__)

telemetry_data = {"altitude": 0.0, "speed": 0.0, "latitude": 0.0, "longitude": 0.0}
altitude_history = []
telemetry_lock = threading.Lock()

# ------------------ HTML TEMPLATE -------------------

dashboard_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Drone Telemetry Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r152/three.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.152/examples/js/loaders/GLTFLoader.js"></script>

  <style>
    body {
      background-color: #111;
      color: #000;
      font-family: Arial, sans-serif;
      margin: 20px;
    }

    h1, h2, h3 {
      text-align: center;
      color: white;
    }

    .container {
      background: #ddd;        /* LIGHT GREY */
      padding: 20px;
      border-radius: 10px;
      margin-bottom: 25px;
      width: 90%;
      margin-left: auto;
      margin-right: auto;
    }

    #sceneContainer {
      width: 600px;
      height: 400px;
      margin: auto;
    }

    .blue-btn {
      background: #007BFF;
      border: none;
      padding: 10px 20px;
      border-radius: 12px;
      color: white;
      cursor: pointer;
      font-size: 16px;
    }

    .value-box {
      background: #bbb;
      color: green;
      padding: 10px 20px;
      border-radius: 10px;
      min-width: 150px;
      text-align: center;
      font-size: 18px;
      margin: 10px;
      display: inline-block;
    }

    /* Center manual form horizontally */
    #manual-form-container {
      display: flex;
      justify-content: center;
      width: 100%;
    }

    #manualForm {
      display: flex;
      flex-direction: row;
      gap: 20px;
      align-items: center;
      justify-content: center;
      flex-wrap: wrap;
    }

    #manualForm input {
      width: 120px;
      padding: 8px;
      border-radius: 6px;
      border: 1px solid #444;
    }

    /* Center Live Telemetry row */
    #telemetryRow {
      display: flex;
      justify-content: center;
      flex-wrap: wrap;
    }
  </style>
</head>
<body>

<h1>Real-Time Drone Dashboard</h1>

<!-- 3D MODEL -->
<div class="container">
  <h2>3D Drone Visualization</h2>
  <div id="sceneContainer"></div>
</div>

<script>
let scene, camera, renderer, droneModel;

function init3D() {
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);

    camera = new THREE.PerspectiveCamera(60, 600/400, 0.1, 1000);
    camera.position.set(0, 1.5, 4);

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(600, 400);
    document.getElementById("sceneContainer").appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight(0xffffff, 1.4);
    scene.add(ambient);

    const loader = new THREE.GLTFLoader();
    loader.load("/static/models/dji_mavic_air.glb", function(gltf) {
        droneModel = gltf.scene;

        droneModel.traverse(n => {
            if (n.isMesh) n.material.color.set(0xffffff);
        });

        droneModel.scale.set(0.6, 0.6, 0.6);
        droneModel.position.set(0, 0, 0);
        scene.add(droneModel);
    });

    animate();
}

function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}

function updateDronePosition(altitude) {
    if (!droneModel) return;
    const y = altitude * 0.05;
    droneModel.position.y += (y - droneModel.position.y) * 0.1;
}

init3D();
</script>

<!-- MANUAL INPUT -->
<div class="container">
  <h2>Manual Input</h2>

  <div id="manual-form-container">
    <form id="manualForm">
      <div>
        <label>Altitude (m)</label><br>
        <input type="number" id="sim_altitude">
      </div>

      <div>
        <label>Speed (m/s)</label><br>
        <input type="number" id="sim_speed">
      </div>

      <div>
        <label>Latitude</label><br>
        <input type="text" id="sim_lat">
      </div>

      <div>
        <label>Longitude</label><br>
        <input type="text" id="sim_lon">
      </div>

      <button class="blue-btn" type="submit">Update</button>
    </form>
  </div>
</div>

<!-- LIVE TELEMETRY -->
<div class="container">
  <h2>Live Telemetry</h2>

  <div id="telemetryRow">
    <div class="value-box">Altitude: <span id="altitude">0</span></div>
    <div class="value-box">Speed: <span id="speed">0</span></div>
    <div class="value-box">Latitude: <span id="latitude">0</span></div>
    <div class="value-box">Longitude: <span id="longitude">0</span></div>
  </div>
</div>

<!-- CHART -->
<div class="container">
  <h2>Altitude Chart</h2>
  <canvas id="altChart" height="200"></canvas>
</div>

<script>
async function fetchTelemetry() {
    const r = await fetch('/telemetry');
    const data = await r.json();

    document.getElementById("altitude").textContent = data.altitude.toFixed(2);
    document.getElementById("speed").textContent = data.speed.toFixed(2);
    document.getElementById("latitude").textContent = data.latitude.toFixed(6);
    document.getElementById("longitude").textContent = data.longitude.toFixed(6);

    updateChart(data.history);
    updateDronePosition(data.altitude);
}

const ctx = document.getElementById("altChart").getContext("2d");

const chart = new Chart(ctx, {
    type: "line",
    data: {
        labels: [],
        datasets: [{
            label: "Altitude (m)",
            data: [],
            borderColor: "blue",
            pointBackgroundColor: "blue",
            borderWidth: 2,
            fill: false,
            pointRadius: 4
        }]
    },
    options: {
        scales: {
            x: { ticks: { color: "black" } },   // BLACK AXIS LABELS
            y: { ticks: { color: "black" } }
        },
        animation: false
    }
});

function updateChart(history) {
    chart.data.labels = history.map(v => v.time);
    chart.data.datasets[0].data = history.map(v => v.altitude);
    chart.update();
}

document.getElementById("manualForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const d = {
        altitude: parseFloat(document.getElementById("sim_altitude").value),
        speed: parseFloat(document.getElementById("sim_speed").value),
        latitude: parseFloat(document.getElementById("sim_lat").value),
        longitude: parseFloat(document.getElementById("sim_lon").value),
    };

    await fetch("/simulate", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(d)
    });

    fetchTelemetry();
});

setInterval(fetchTelemetry, 1000);
</script>

</body>
</html>
"""

# ------------------ FLASK ROUTES -------------------

@app.route("/")
def index():
    return render_template_string(dashboard_html)

@app.route("/telemetry")
def telemetry():
    with telemetry_lock:
        return jsonify({**telemetry_data, "history": altitude_history})

@app.route("/simulate", methods=["POST"])
def simulate():
    data = request.get_json()
    with telemetry_lock:
        telemetry_data.update(data)
        altitude_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "altitude": telemetry_data["altitude"]
        })
        if len(altitude_history) > 60:
            altitude_history.pop(0)
    return jsonify({"status": "ok"})

# ------------- ZEROMQ LISTENER --------------
def zmq_listener():
    ctx = zmq.Context()
    socket = ctx.socket(zmq.SUB)
    socket.connect("tcp://localhost:5556")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    while True:
        msg = socket.recv_json()
        with telemetry_lock:
            telemetry_data["altitude"] = msg["z"]
            telemetry_data["speed"] = (msg["vx"]**2 + msg["vy"]**2 + msg["vz"]**2) ** 0.5
            telemetry_data["latitude"] = msg["x"]
            telemetry_data["longitude"] = msg["y"]

            altitude_history.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "altitude": telemetry_data["altitude"]
            })
            if len(altitude_history) > 60:
                altitude_history.pop(0)

threading.Thread(target=zmq_listener, daemon=True).start()

if __name__ == "__main__":
    app.run(debug=True)

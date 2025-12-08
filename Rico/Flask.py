# app.py
from flask import Flask, render_template_string, jsonify, request, send_from_directory
from flask_socketio import SocketIO
from datetime import datetime
import threading
import zmq
import time
import os

# -------------------------
# App init
# -------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
socketio = SocketIO(app, cors_allowed_origins="*")

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
MAX_HISTORY = 200

# -------------------------
# HTML Template (single-file)
# -------------------------
dashboard_html = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Real-Time Drone Dashboard</title>

  <!-- Socket.IO -->
  <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>

  <!-- Chart.js -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

  <!-- Three.js and GLTFLoader (from CDN) -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r152/three.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.152.2/examples/js/loaders/GLTFLoader.js"></script>

  <meta name="viewport" content="width=device-width, initial-scale=1" />

  <style>
    :root{
      --bg: #0f0f10;
      --panel: #2b2b2b;
      --muted: #444;
      --blue: #0a84ff;
      --green: #00c46a;
      --card-radius: 12px;
    }
    html,body { height:100%; margin:0; background:var(--bg); color:#fff; font-family: Inter, Arial, sans-serif; }
    .container { max-width:1100px; margin:18px auto; padding:12px; }
    h1 { margin:0 0 12px 0; font-weight:600; font-size:20px; }

    /* Panel */
    .panel { background: var(--panel); padding:14px; border-radius: var(--card-radius); margin-bottom:14px; box-shadow: 0 2px 0 rgba(0,0,0,0.4); }

    /* Manual form layout */
    .form-row { display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
    .form-group { flex:1; min-width:160px; display:flex; flex-direction:column; gap:6px; }
    label { font-size:0.85rem; color:#ddd; }
    input[type="number"], input[type="text"] {
      padding:8px 10px; border-radius:8px; border:1px solid #3a3a3a; background:#111; color:#fff;
      outline:none; box-sizing:border-box;
    }

    /* Button */
    .btn { background: var(--blue); color:#fff; padding:10px 16px; border-radius:12px; border:none; cursor:pointer; font-weight:600; min-width:88px; }
    .btn:active{ transform: translateY(1px); }

    /* Numeric values row (green on grey) */
    .values-row { display:flex; gap:12px; margin-top:12px; }
    .value-box { flex:1; min-width:120px; background:#3a3a3a; border-radius:10px; padding:12px; text-align:center; }
    .value-box .label { font-size:0.8rem; color:#cfcfcf; margin-bottom:6px; }
    .value-box .value { font-size:1.1rem; color: var(--green); font-weight:700; }

    /* Chart area */
    .chart-wrap { margin-top:12px; }
    canvas { background:#000; border-radius:8px; display:block; width:100%; height:360px !important; }

    /* 3D container */
    #viewer { width:100%; height:420px; background:#101010; border-radius:8px; margin-top:14px; }

    /* Responsive */
    @media (max-width:800px){
      .form-row { flex-direction:column; }
      .values-row { flex-direction:column; }
      #viewer { height:300px; }
      canvas { height:260px !important; }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Real-Time Drone Dashboard</h1>

    <div class="panel">
      <form id="simForm" onsubmit="return false;">
        <div class="form-row">
          <div class="form-group">
            <label for="sim_alt">Altitude (m)</label>
            <input id="sim_alt" type="number" step="0.1" placeholder="e.g. 3.5">
          </div>

          <div class="form-group">
            <label for="sim_lat">Latitude</label>
            <input id="sim_lat" type="number" step="0.000001" placeholder="e.g. 37.123456">
          </div>

          <div class="form-group">
            <label for="sim_lon">Longitude</label>
            <input id="sim_lon" type="number" step="0.000001" placeholder="e.g. -122.123456">
          </div>

          <div class="form-group" style="max-width:160px;">
            <label for="sim_spd">Speed (m/s)</label>
            <input id="sim_spd" type="number" step="0.1" placeholder="e.g. 1.2">
          </div>

          <div style="display:flex; align-items:end;">
            <button id="sendBtn" class="btn">Send</button>
          </div>
        </div>

        <div class="values-row" style="margin-top:14px;">
          <div class="value-box">
            <div class="label">Altitude</div>
            <div id="val_alt" class="value">0.00</div>
          </div>
          <div class="value-box">
            <div class="label">Latitude</div>
            <div id="val_lat" class="value">0.000000</div>
          </div>
          <div class="value-box">
            <div class="label">Longitude</div>
            <div id="val_lon" class="value">0.000000</div>
          </div>
          <div class="value-box">
            <div class="label">Speed</div>
            <div id="val_spd" class="value">0.00</div>
          </div>
        </div>
      </form>
    </div>

    <div class="panel">
      <div class="chart-wrap">
        <canvas id="altChart"></canvas>
      </div>

      <div id="viewer"></div>
    </div>
  </div>

<script>
  // ---- Client-side SocketIO ----
  const socket = io();

  // Local history for chart (same length as server MAX_HISTORY)
  const labels = [];
  const altData = [];

  // Chart.js setup (blue line + blue dots)
  const ctx = document.getElementById('altChart').getContext('2d');
  const altChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Altitude (m)',
        data: altData,
        borderColor: '#0a84ff',
        backgroundColor: '#0a84ff',
        borderWidth: 2,
        pointRadius: 5,
        pointBackgroundColor: '#0a84ff',
        pointBorderColor: '#fff',
        tension: 0.25,
        fill: false
      }]
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: '#bbb' } },
        y: { beginAtZero: true, ticks: { color: '#bbb' } }
      },
      plugins: { legend: { labels: { color: '#ddd' } } }
    }
  });

  // Update chart with incoming history or single point
  function updateChartFromHistory(history) {
    labels.length = 0;
    altData.length = 0;
    history.forEach(h => {
      labels.push(h.time);
      altData.push(h.altitude);
    });
    altChart.update();
  }
  function pushAltitudePoint(alt) {
    const t = new Date().toLocaleTimeString();
    labels.push(t);
    altData.push(alt);
    if (labels.length > 200) { labels.shift(); altData.shift(); }
    altChart.update();
  }

  // ---- Values update ----
  function updateNumericDisplays(data) {
    document.getElementById('val_alt').textContent = data.altitude.toFixed(2);
    document.getElementById('val_lat').textContent = data.latitude.toFixed(6);
    document.getElementById('val_lon').textContent = data.longitude.toFixed(6);
    document.getElementById('val_spd').textContent = data.speed.toFixed(2);
  }

  // ---- Socket events ----
  socket.on('connect', () => console.log('Socket.IO connected'));
  socket.on('telemetry', (msg) => {
    // msg contains: x (lat), y (lon), z (alt), vx,vy,vz, history (optional)
    try {
      const data = {
        altitude: Number(msg.z || 0),
        speed: Number(msg.speed || 0),
        latitude: Number(msg.x || 0),
        longitude: Number(msg.y || 0)
      };
      updateNumericDisplays(data);

      if (Array.isArray(msg.history)) {
        updateChartFromHistory(msg.history);
      } else {
        pushAltitudePoint(data.altitude);
      }

      // update 3D drone (y axis)
      update3DDrone(data.altitude);
    } catch (e) {
      console.warn('Telemetry parse error', e);
    }
  });

  // ---- Manual form submit ----
  document.getElementById('sendBtn').addEventListener('click', async (ev) => {
    ev.preventDefault();
    const alt = parseFloat(document.getElementById('sim_alt').value || '0');
    const lat = parseFloat(document.getElementById('sim_lat').value || '0');
    const lon = parseFloat(document.getElementById('sim_lon').value || '0');
    const spd = parseFloat(document.getElementById('sim_spd').value || '0');

    // Basic validation
    if (Number.isNaN(alt) || Number.isNaN(lat) || Number.isNaN(lon) || Number.isNaN(spd)) {
      alert('Please enter valid numeric values for all fields.');
      return;
    }

    // Send to server - server will validate and broadcast
    try {
      await fetch('/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ altitude: alt, latitude: lat, longitude: lon, speed: spd })
      });
      // local immediate update (server will also broadcast)
      updateNumericDisplays({ altitude: alt, latitude: lat, longitude: lon, speed: spd });
      pushAltitudePoint(alt);
      update3DDrone(alt);
    } catch (err) {
      console.error('Failed to send manual telemetry', err);
    }
  });

  // -----------------------
  // Three.js 3D viewer
  // -----------------------
  let scene, camera, renderer, droneModel, clock;
  function init3D() {
    const container = document.getElementById('viewer');
    scene = new THREE.Scene();

    const w = container.clientWidth;
    const h = container.clientHeight;

    camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 1000);
    camera.position.set(4, 3, 6);
    camera.lookAt(0, 0, 0);

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    container.appendChild(renderer.domElement);

    // lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.9));
    const dir = new THREE.DirectionalLight(0xffffff, 0.7);
    dir.position.set(5, 10, 7);
    scene.add(dir);

    // grid
    const grid = new THREE.GridHelper(10, 20);
    scene.add(grid);

    // try to load GLB model; fallback to a simple box if not found or on error
    const loader = new THREE.GLTFLoader();
    const modelPath = '/static/models/dji_mavic_air.glb';
    loader.load(modelPath,
      (gltf) => {
        droneModel = gltf.scene;
        droneModel.scale.set(0.8, 0.8, 0.8);
        droneModel.position.set(0, 0.0, 0);
        scene.add(droneModel);
      },
      undefined,
      (err) => {
        console.warn('GLB load failed, using fallback box model.', err);
        const g = new THREE.BoxGeometry(2.4, 0.6, 1.6);
        const m = new THREE.MeshStandardMaterial({ color: 0x00aaff });
        droneModel = new THREE.Mesh(g, m);
        scene.add(droneModel);
      }
    );

    clock = new THREE.Clock();
    animate3D();

    // handle resize
    window.addEventListener('resize', () => {
      const W = container.clientWidth;
      const H = container.clientHeight;
      renderer.setSize(W, H);
      camera.aspect = W / H;
      camera.updateProjectionMatrix();
    });
  }

  function animate3D() {
    requestAnimationFrame(animate3D);
    // slight bobbing so the model looks alive if no telemetry movement
    if (droneModel) droneModel.rotation.y += 0.002;
    renderer.render(scene, camera);
  }

  function update3DDrone(altitude) {
    if (!droneModel) return;
    // scale altitude into visible height (tweak multiplier as needed)
    const targetY = altitude * 0.3 + 0.05;
    droneModel.position.y += (targetY - droneModel.position.y) * 0.12;
  }

  // Start 3D
  init3D();

  // Request initial state when page loads
  (async () => {
    try {
      const res = await fetch('/telemetry');
      const json = await res.json();
      updateNumericDisplays(json);
      if (Array.isArray(json.history)) updateChartFromHistory(json.history);
    } catch (e) {
      console.warn('Failed initial telemetry fetch', e);
    }
  })();

</script>
</body>
</html>
"""

# -------------------------
# Flask routes
# -------------------------
@app.route("/")
def index():
    return render_template_string(dashboard_html)

@app.route("/telemetry")
def telemetry():
    with telemetry_lock:
        # Provide history as a copy to avoid mutation races
        return jsonify({ **telemetry_data, "history": list(altitude_history) })

@app.route("/simulate", methods=["POST"])
def simulate():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "invalid json"}), 400

    # Validate and coerce
    try:
        alt = float(data.get("altitude", telemetry_data["altitude"]))
        spd = float(data.get("speed", telemetry_data["speed"]))
        lat = float(data.get("latitude", telemetry_data["latitude"]))
        lon = float(data.get("longitude", telemetry_data["longitude"]))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid numeric values"}), 400

    with telemetry_lock:
        telemetry_data.update({
            "altitude": alt,
            "speed": spd,
            "latitude": lat,
            "longitude": lon
        })
        altitude_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "altitude": telemetry_data["altitude"]
        })
        if len(altitude_history) > MAX_HISTORY:
            altitude_history.pop(0)

        # Emit to connected websocket clients
        try:
            socketio.emit('telemetry', {
                "x": telemetry_data["latitude"],
                "y": telemetry_data["longitude"],
                "z": telemetry_data["altitude"],
                "vx": 0.0, "vy": 0.0, "vz": 0.0,
                "speed": telemetry_data["speed"],
                "history": list(altitude_history)
            })
        except Exception as e:
            print("SocketIO emit error (simulate):", e)

    return jsonify({"status": "ok"})

# -------------------------
# Background ZMQ listener (thread)
# -------------------------
def zmq_listener():
    ctx = zmq.Context()
    socket = ctx.socket(zmq.SUB)
    try:
        socket.connect("tcp://127.0.0.1:5556")
        socket.setsockopt_string(zmq.SUBSCRIBE, "")
        print("[ZMQ] Subscribed to tcp://127.0.0.1:5556")
    except Exception as e:
        print("[ZMQ] connect error:", e)
        return

    while True:
        try:
            message = socket.recv_json()
        except Exception as e:
            # keep alive on error
            print("[ZMQ] recv error:", e)
            time.sleep(0.5)
            continue

        # Expected message fields: id,x,y,z,vx,vy,vz (twin_agent format)
        try:
            alt = float(message.get("z", telemetry_data["altitude"]))
            vx = float(message.get("vx", 0.0))
            vy = float(message.get("vy", 0.0))
            vz = float(message.get("vz", 0.0))
            lat = float(message.get("x", telemetry_data["latitude"]))
            lon = float(message.get("y", telemetry_data["longitude"]))
            spd = (vx**2 + vy**2 + vz**2) ** 0.5
        except Exception as e:
            print("[ZMQ] message parse error:", e)
            continue

        with telemetry_lock:
            telemetry_data.update({
                "altitude": alt,
                "speed": spd,
                "latitude": lat,
                "longitude": lon
            })
            altitude_history.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "altitude": telemetry_data["altitude"]
            })
            if len(altitude_history) > MAX_HISTORY:
                altitude_history.pop(0)

            # emit to clients (push)
            try:
                socketio.emit('telemetry', {
                    "x": telemetry_data["latitude"],
                    "y": telemetry_data["longitude"],
                    "z": telemetry_data["altitude"],
                    "vx": vx, "vy": vy, "vz": vz,
                    "speed": telemetry_data["speed"]
                })
            except Exception as e:
                print("[SocketIO] emit error:", e)

# Start background listener thread
zmq_thread = threading.Thread(target=zmq_listener, daemon=True)
zmq_thread.start()

# -------------------------
# Run server
# -------------------------
if __name__ == "__main__":
    # quick static-file note
    expected = "static/models/dji_mavic_air.glb"
    if not os.path.exists(expected):
        print(f"[NOTICE] GLB model not found at {expected}. Dashboard will use fallback box model.")
    print("[SERVER] Starting Flask + SocketIO server at http://127.0.0.1:5000")
    # Disable debug in production; set debug=True only for local development
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)

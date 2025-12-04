from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO
from datetime import datetime
import threading
import zmq
import time
import os

# ------------------------- # Configuration / App Init # -------------------------

app = Flask(__name__, static_folder="static", static_url_path="/static")
# Key Fix: Disable debug in socketio.run if you encounter multiple connections/updates when using debug=True
# in the main run block, but leave cors_allowed_origins for development.
socketio = SocketIO(app, cors_allowed_origins="*")
# allow cross-origin for local testing
# ------------------------- # Telemetry storage
telemetry_data = {
    "altitude": 0.0,
    "speed": 0.0,
    "latitude": 0.0,
    "longitude": 0.0
}
# Store history as simple altitudes (float) for easier chart processing on client
altitude_history = []
telemetry_lock = threading.Lock()

# ------------------------- # HTML Dashboard Template # -------------------------
# Note: This template expects these local files to exist:
# static/js/three.module.js
# static/js/GLTFLoader.js
# static/js/OrbitControls.js
# static/models/dji_mavic_air.glb
dashboard_html = """
<!DOCTYPE html> <html lang="en"> <head> <meta charset="utf-8" /> <title>Drone Dashboard</title> <style>
body { margin: 0; background: #121212; color: #eee; font-family: Arial, Helvetica, sans-serif; }
#viewer { width: 100%; height: 480px; background: #000; display:block; }
#controls { padding: 12px; max-width: 1000px; margin: 8px auto; }
#altitude { width: 100%; height: 200px; display:block; background:#111; border: 1px solid #333;}
.row { max-width: 1000px; margin: 0 auto; padding: 8px; }

/* New Styles for Telemetry Table */
#telemetry_display { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; text-align: center; border: 1px solid #333; padding: 10px; background: #1a1a1a; margin-top: 10px; }
.telemetry-item { padding: 5px; border-right: 1px solid #333; }
.telemetry-item:last-child { border-right: none; }
.telemetry-label { font-size: 0.8em; color: #aaa; }
.telemetry-value { font-size: 1.4em; font-weight: bold; color: #00ff00; }
</style> </head> <body> <div class="row"> <h2>Real-Time Drone Dashboard</h2> </div> <div class="row">
<div id="telemetry_display">
    <div class="telemetry-item"><div class="telemetry-label">ALTITUDE (m)</div><div class="telemetry-value" id="disp_alt">0.00</div></div>
    <div class="telemetry-item"><div class="telemetry-label">SPEED (m/s)</div><div class="telemetry-value" id="disp_spd">0.00</div></div>
    <div class="telemetry-item"><div class="telemetry-label">LATITUDE</div><div class="telemetry-value" id="disp_lat">0.000000</div></div>
    <div class="telemetry-item"><div class="telemetry-label">LONGITUDE</div><div class="telemetry-value" id="disp_lon">0.000000</div></div>
</div>
</div> <div class="row" id="controls">
<form id="simForm" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
<label>Altitude (m): <input id="sim_alt" type="number" step="0.1" value="0.0" required></label> <label>Speed (m/s):
<input id="sim_spd" type="number" step="0.1" value="0.0" required></label> <label>Lat: <input id="sim_lat" type="number" step="0.000001" value="0.0" required></label> <label>Lon: <input id="sim_lon" type="number" step="0.000001" value="0.0" required></label> <button type="submit">Send</button>
</form> </div> <div class="row"> <div id="viewer"></div> </div> <div class="row">
<canvas id="altitude" width="1000" height="200"></canvas> </div> <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script> <script type="module">
import * as THREE from "/static/js/three.module.js"; import { GLTFLoader } from "/static/js/GLTFLoader.js"; import { OrbitControls } from "/static/js/OrbitControls.js";

// --- Scene setup ---
const container = document.getElementById("viewer");
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio || 1); renderer.setSize(container.clientWidth, container.clientHeight);
container.appendChild(renderer.domElement); const scene = new THREE.Scene(); scene.background = new THREE.Color(0x0a0a0a);
const camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 1000);
camera.position.set(3, 2, 5); const hemi = new THREE.HemisphereLight(0xffffff, 0x080820, 1.0); scene.add(hemi);
const dir = new THREE.DirectionalLight(0xffffff, 0.6); dir.position.set(10, 10, 10); scene.add(dir);
const grid = new THREE.GridHelper(10, 20); scene.add(grid);
// Orbit controls const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0.5, 0); controls.update();
// load GLB const loader = new GLTFLoader(); let drone = null;
loader.load("/static/models/dji_mavic_air.glb", (gltf) => { drone = gltf.scene; drone.scale.set(0.8, 0.8, 0.8);
// center on ground drone.position.set(0, 0, 0); scene.add(drone); console.log("GLB loaded successfully"); }, undefined, (err) => { console.error("GLB load error:", err); } );
// animate loop function animate() { requestAnimationFrame(animate); renderer.render(scene, camera); } animate();

// --- Telemetry Display Elements (NEW) ---
const dispAlt = document.getElementById("disp_alt");
const dispSpd = document.getElementById("disp_spd");
const dispLat = document.getElementById("disp_lat");
const dispLon = document.getElementById("disp_lon");

// --- Altitude chart (MODIFIED) ---
const altCanvas = document.getElementById("altitude");
const altCtx = altCanvas.getContext("2d");
let altHistory = [];

function drawAltitude() {
    const w = altCanvas.width;
    const h = altCanvas.height;
    altCtx.clearRect(0,0,w,h);
    // background grid
    altCtx.fillStyle = "#070707";
    altCtx.fillRect(0,0,w,h);

    if (altHistory.length === 0) return;

    // Use current altitude as the last point
    const currentAlt = altHistory[altHistory.length - 1];
    // Calculate max altitude, ensuring a minimum of 5 for scaling
    const maxA = Math.max(...altHistory, 5); 

    // 1. Draw Altitude Line (Lime Green)
    altCtx.beginPath();
    altCtx.strokeStyle = "lime";
    altCtx.lineWidth = 2;
    let lastX, lastY;

    altHistory.forEach((a, i) => {
        const x = (i / Math.max(altHistory.length-1,1)) * w;
        // Map altitude 'a' to a canvas height 'y'. High altitude = Low y (near top of canvas)
        const y = h - (a / maxA) * h;
        if (i === 0) altCtx.moveTo(x,y);
        else altCtx.lineTo(x,y);
        if (i === altHistory.length - 1) { lastX = x; lastY = y; }
    });
    altCtx.stroke();

    // 2. Draw Blue Dot for Current Altitude (NEW)
    if (altHistory.length > 0) {
        altCtx.beginPath();
        altCtx.fillStyle = "#4a90e2"; // Blue color
        altCtx.arc(lastX, lastY, 4, 0, Math.PI * 2, true); // Draw circle
        altCtx.fill();

        // Label for current altitude
        altCtx.fillStyle = "white";
        altCtx.font = "12px Arial";
        altCtx.textAlign = "center";
        // Ensure label doesn't overlap the top edge
        const labelY = (lastY < 20) ? lastY + 20 : lastY - 10;
        altCtx.fillText(currentAlt.toFixed(1) + "m", lastX, labelY);
    }
}

function pushAltitude(a) {
    if (altHistory.length > 200) altHistory.shift();
    // Sanity check to ensure 'a' is a number before pushing
    if (typeof a === 'number' && isFinite(a)) {
        altHistory.push(a);
        drawAltitude();
    }
}

// --- WebSocket connection (MODIFIED) ---
const socket = io();

socket.on("connect", () => { console.log("Socket.IO connected:", socket.id); });
socket.on("connect_error", (err) => { console.error("Socket.IO connect error:", err); });

socket.on("drone_state",
(msg) => {
    // msg fields: x=latitude, y=longitude, z=altitude, speed
    // apply scaling for visualization:
    const lat = msg.x || 0;
    const lon = msg.y || 0;
    const alt = msg.z || 0;

    // SCALING: Divide position/altitude by a factor for better 3D visualization.
    const pos_x = lat / 2.0;
    const pos_y = alt / 2.0; // Altitude (z) is vertical (y) in Three.js
    const pos_z = lon / 2.0;

    // 1. Update 3D Model Position
    if (drone) {
        drone.position.set(pos_x, pos_y, pos_z);
    }

    // 2. Update Telemetry Display Columns
    dispAlt.textContent = alt.toFixed(2);
    pushAltitude(alt);
    
    dispSpd.textContent = (msg.speed || 0.0).toFixed(2);
    dispLat.textContent = lat.toFixed(6);
    dispLon.textContent = lon.toFixed(6);
});

// Manual input form
const form = document.getElementById("simForm");
form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const alt = parseFloat(document.getElementById("sim_alt").value);
    const spd = parseFloat(document.getElementById("sim_spd").value);
    const lat = parseFloat(document.getElementById("sim_lat").value);
    const lon = parseFloat(document.getElementById("sim_lon").value);
    const payload = { altitude: alt, speed: spd, latitude: lat, longitude: lon };
    
    try {
        await fetch("/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        // **CORRECTION:** Removed redundant manual_update emit. 
        // The /simulate route on the server now broadcasts the 'drone_state' 
        // which all clients, including this one, will receive and process.
    }
    catch (err) { console.error("Failed to POST simulate:", err); }
});

// resize handling
window.addEventListener("resize", () => { renderer.setSize(container.clientWidth, container.clientHeight); camera.aspect = container.clientWidth
/ container.clientHeight; camera.updateProjectionMatrix(); }); </script> </body> </html>
"""
# ------------------------- # Flask routes # -------------------------#
@app.route("/")
def index():
    return render_template_string(dashboard_html)

@app.route("/telemetry")
def telemetry():
    with telemetry_lock:
        # Use a list of just altitudes for history to match client expectation
        history_data = [item["altitude"] for item in altitude_history]
        return jsonify({ **telemetry_data, "history": history_data })

@app.route("/simulate", methods=["POST"])
def simulate():
    data = request.get_json()
    alt = float(data.get("altitude", telemetry_data["altitude"]))
    
    with telemetry_lock:
        telemetry_data.update({
            "altitude": alt,
            "speed": float(data.get("speed", telemetry_data["speed"])),
            "latitude": float(data.get("latitude", telemetry_data["latitude"])),
            "longitude": float(data.get("longitude", telemetry_data["longitude"]))
        })
        
        # Store only the altitude in the history list (for client-side simplicity)
        altitude_history.append(telemetry_data["altitude"])
        
        if len(altitude_history) > 200:
            altitude_history.pop(0)
            
    # Broadcast update to connected clients
    socketio.emit("drone_state", {
        "x": telemetry_data["latitude"],
        "y": telemetry_data["longitude"],
        "z": telemetry_data["altitude"],
        "vx": 0.0,
        "vy": 0.0,
        "vz": 0.0,
        "speed": telemetry_data["speed"] 
    })
    return jsonify({"status": "Telemetry updated"})

# ------------------------- # Background ZMQ listener # -------------------------
def zmq_listener():
    ctx = zmq.Context()
    socket = ctx.socket(zmq.SUB)
    # Use a faster local host binding
    socket.connect("tcp://127.0.0.1:5556") 
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    print("[ZMQ] Listening for drone telemetry on tcp://127.0.0.1:5556 ...")
    
    # Simple rate limiting for better performance, if ZMQ publisher is too fast
    last_emit_time = 0
    min_interval = 0.05 # 20 updates per second max

    while True:
        try:
            # Use non-blocking with timeout to allow thread shutdown and better error handling
            message = socket.recv_json(zmq.NOBLOCK) 
        except zmq.Again:
            time.sleep(0.001)
            continue
        except Exception as e:
            print("ZMQ recv error:", e)
            time.sleep(0.5)
            continue
        
        # print("[ZMQ] Received:", message) # Commented out for high-rate data to reduce console load
        
        current_time = time.time()
        
        # Update local telemetry store
        with telemetry_lock:
            alt = float(message.get("z", telemetry_data["altitude"]))
            lat = float(message.get("x", telemetry_data["latitude"]))
            lon = float(message.get("y", telemetry_data["longitude"]))
            
            vx = message.get("vx", 0.0)
            vy = message.get("vy", 0.0)
            vz = message.get("vz", 0.0)
            
            # Calculate speed from velocity components
            calculated_speed = (vx**2 + vy**2 + vz**2) ** 0.5
            
            telemetry_data["altitude"] = alt
            telemetry_data["latitude"] = lat
            telemetry_data["longitude"] = lon
            telemetry_data["speed"] = float(message.get("speed", calculated_speed))
            
            # Store only the altitude
            altitude_history.append(telemetry_data["altitude"]) 
            
            if len(altitude_history) > 200:
                altitude_history.pop(0)

        # Emit to web clients with rate limiting
        if current_time - last_emit_time > min_interval:
            try:
                # Use a separate thread safe emit method
                socketio.emit("drone_state", {
                    "x": telemetry_data["latitude"],
                    "y": telemetry_data["longitude"],
                    "z": telemetry_data["altitude"],
                    "vx": vx,
                    "vy": vy,
                    "vz": vz,
                    "speed": telemetry_data["speed"]
                })
                last_emit_time = current_time
            except Exception as e:
                print("SocketIO emit error:", e)

# Start listener thread after socketio object exists
zmq_thread = threading.Thread(target=zmq_listener, daemon=True)
zmq_thread.start()

# ------------------------ # Start server # -------------------------#
if __name__ == "__main__":
    # quick sanity checks for expected files
    expected = [
        "static/js/three.module.js",
        "static/js/GLTFLoader.js",
        "static/js/OrbitControls.js",
        "static/models/dji_mavic_air.glb"
    ]
    for path in expected:
        if not os.path.exists(path):
            print(f"Error: Required file not found: {path}")

    # Use a simpler way to get the IP address for portability
    ip_addr = "127.0.0.1" 
    
    print(f"[SERVER] Flask dashboard will run at http://{ip_addr}:5000")
    # Use allow_unsafe_werkzeug=True for newer Flask versions in debug mode
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)

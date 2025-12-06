from flask import Flask, request, render_template_string, jsonify, send_file, Response
import numpy as np
import pandas as pd
import time
import threading
import math
import cv2
try:
    from quanser.hardware import HIL
    QUANSER_AVAILABLE = True
except ImportError:
    QUANSER_AVAILABLE = False
    print("[WARNING] Quanser hardware module not found. Running in simulation mode.")
import webbrowser
import os
import atexit

# ------------------------------------------------------------
# Flask Initialization
# ------------------------------------------------------------
app = Flask(__name__)
CSV_FILE_PATH = "tank_data.csv"

# ------------------------------------------------------------
# Thread-Safe State
# ------------------------------------------------------------
state_lock = threading.Lock()
state = {
    "running": False,
    "data": []
}

# ------------------------------------------------------------
# Camera Initialization
# ------------------------------------------------------------
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 1))
camera = None

def initialize_camera():
    """Initialize camera with fallback search."""
    global camera
    tried_indices = []

    # 1. DSHOW primary attempt
    print(f"[Camera] Trying index {CAMERA_INDEX} (DSHOW)")
    camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    if camera.isOpened():
        print(f"[Camera] Success at index {CAMERA_INDEX} (DSHOW)")
        return True

    # 2. MSMF fallback
    print(f"[Camera] Trying index {CAMERA_INDEX} (MSMF)")
    camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)
    if camera.isOpened():
        print(f"[Camera] Success at index {CAMERA_INDEX} (MSMF)")
        return True

    # 3. Fallback search (DSHOW)
    print("[Camera] Starting fallback search (DSHOW)")
    for idx in range(5):
        if idx == CAMERA_INDEX:
            continue
        temp = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if temp.isOpened():
            print(f"[Camera] Found working camera at index {idx} (DSHOW)")
            camera = temp
            return True
        temp.release()

    # 4. MSMF fallback search
    print("[Camera] Starting fallback search (MSMF)")
    for idx in range(5):
        temp = cv2.VideoCapture(idx, cv2.CAP_MSMF)
        if temp.isOpened():
            print(f"[Camera] Found working camera at index {idx} (MSMF)")
            camera = temp
            return True
        temp.release()

    print("[Camera] ERROR: No camera found")
    return False

def release_camera():
    global camera
    if camera and camera.isOpened():
        camera.release()
        print("[Camera] Released")

atexit.register(release_camera)
initialize_camera()

# ------------------------------------------------------------
# HTML Template
# ------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Coupled Tank Control</title>
    <style>
        * { 
            margin: 0; 
            padding: 0; 
            box-sizing: border-box; 
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 25px 70px rgba(0,0,0,0.4);
            padding: 40px;
        }
        
        h1 {
            text-align: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 35px;
            font-size: 2.8em;
            font-weight: 700;
            letter-spacing: -1px;
        }
        
        .controls {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 25px;
            margin-bottom: 35px;
        }
        
        .control-group {
            background: linear-gradient(145deg, #f8f9fa, #e9ecef);
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .control-group:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.12);
        }
        
        label {
            display: block;
            margin-bottom: 10px;
            color: #495057;
            font-weight: 600;
            font-size: 0.95em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        input[type="number"] {
            width: 100%;
            padding: 14px;
            border: 2px solid #dee2e6;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s;
            background: white;
        }
        
        input[type="number"]:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
        }
        
        .button-group {
            display: flex;
            gap: 18px;
            margin-bottom: 35px;
            flex-wrap: wrap;
        }
        
        button {
            flex: 1;
            min-width: 150px;
            padding: 16px 32px;
            font-size: 16px;
            font-weight: 700;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.15);
        }
        
        .btn-start {
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
        }
        
        .btn-start:hover:not(:disabled) {
            background: linear-gradient(135deg, #059669, #047857);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
        }
        
        .btn-stop {
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: white;
        }
        
        .btn-stop:hover:not(:disabled) {
            background: linear-gradient(135deg, #dc2626, #b91c1c);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(239, 68, 68, 0.4);
        }
        
        .btn-download {
            background: linear-gradient(135deg, #3b82f6, #2563eb);
            color: white;
        }
        
        .btn-download:hover {
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
        }
        
        .btn-mic {
            background: linear-gradient(135deg, #8b5cf6, #7c3aed);
            color: white;
            position: relative;
        }
        
        .btn-mic:hover {
            background: linear-gradient(135deg, #7c3aed, #6d28d9);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(139, 92, 246, 0.4);
        }
        
        .btn-mic.listening {
            background: linear-gradient(135deg, #ef4444, #dc2626);
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { 
                box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
            }
            50% { 
                box-shadow: 0 0 0 20px rgba(239, 68, 68, 0);
            }
        }
        
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .data-display {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
            margin-bottom: 35px;
        }
        
        .chart-container {
            background: linear-gradient(145deg, #f8f9fa, #e9ecef);
            padding: 25px;
            border-radius: 15px;
            height: 420px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
        }
        
        canvas {
            width: 100% !important;
            height: 100% !important;
        }
        
        .camera-feed {
            background: linear-gradient(145deg, #000, #1a1a1a);
            border-radius: 15px;
            overflow: hidden;
            margin-top: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        
        .camera-feed img {
            width: 100%;
            height: auto;
            display: block;
        }
        
        .voice-feedback {
            position: fixed;
            top: 25px;
            right: 25px;
            background: linear-gradient(135deg, rgba(0,0,0,0.9), rgba(0,0,0,0.8));
            color: white;
            padding: 18px 30px;
            border-radius: 12px;
            display: none;
            animation: slideIn 0.4s;
            z-index: 1000;
            font-size: 16px;
            font-weight: 600;
            box-shadow: 0 10px 40px rgba(0,0,0,0.4);
        }
        
        @keyframes slideIn {
            from { 
                transform: translateX(450px);
                opacity: 0;
            }
            to { 
                transform: translateX(0);
                opacity: 1;
            }
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <h1>🌊 Coupled Tank Control System</h1>

        <div class="controls">
            <div class="control-group">
                <label for="base">Base Voltage (0-10V)</label>
                <input type="number" id="base" min="0" max="10" step="0.1" value="5">
            </div>
            <div class="control-group">
                <label for="freq">Frequency (0-10 Hz)</label>
                <input type="number" id="freq" min="0" max="10" step="0.1" value="0.1">
            </div>
            <div class="control-group">
                <label for="amp">Amplitude (0-5V)</label>
                <input type="number" id="amp" min="0" max="5" step="0.1" value="2">
            </div>
        </div>

        <div class="button-group">
            <button class="btn-start" onclick="startSim()">▶ Start</button>
            <button class="btn-stop" onclick="stopSim()">■ Stop</button>
            <button class="btn-download" onclick="downloadData()">⬇ Download CSV</button>
            <button class="btn-mic" id="micBtn" onclick="toggleMic()">🎤 Voice Control</button>
        </div>

        <div class="data-display">
            <div class="chart-container">
                <canvas id="tank1Chart"></canvas>
            </div>
            <div class="chart-container">
                <canvas id="tank2Chart"></canvas>
            </div>
        </div>

        {% if camera_available %}
        <div class="camera-feed">
            <img src="/video_feed" alt="Live Camera Feed">
        </div>
        {% endif %}

        <div id="voiceFeedback" class="voice-feedback"></div>
    </div>

    <script>
        let micActive = false;
        let recognition = null;

        const ctx1 = document.getElementById('tank1Chart').getContext('2d');
        const ctx2 = document.getElementById('tank2Chart').getContext('2d');

        const tank1Chart = new Chart(ctx1, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Tank 1 Height (cm)',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    tension: 0.4,
                    fill: true,
                    borderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: 'Height (cm)' } },
                    x: { title: { display: true, text: 'Time (s)' } }
                },
                plugins: {
                    title: { display: true, text: 'Tank 1 Water Level', font: { size: 16, weight: 'bold' } }
                }
            }
        });

        const tank2Chart = new Chart(ctx2, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Tank 2 Height (cm)',
                    data: [],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.4,
                    fill: true,
                    borderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: 'Height (cm)' } },
                    x: { title: { display: true, text: 'Time (s)' } }
                },
                plugins: {
                    title: { display: true, text: 'Tank 2 Water Level', font: { size: 16, weight: 'bold' } }
                }
            }
        });

        function toggleMic() {
            micActive = !micActive;
            const btn = document.getElementById('micBtn');
            
            if (micActive) {
                btn.classList.add('listening');
                btn.textContent = '🔴 Listening...';
                startVoiceRecognition();
            } else {
                btn.classList.remove('listening');
                btn.textContent = '🎤 Voice Control';
                stopVoiceRecognition();
            }
        }

        function startVoiceRecognition() {
            if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
                showVoiceFeedback('Voice recognition not supported');
                toggleMic();
                return;
            }

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = false;
            recognition.lang = 'en-US';

            recognition.onresult = (event) => {
                const last = event.results.length - 1;
                const command = event.results[last][0].transcript.toLowerCase().trim();
                showVoiceFeedback(`Heard: "${command}"`);
                processVoiceCommand(command);
            };

            recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                if (event.error === 'no-speech') {
                    // Continue listening
                } else {
                    showVoiceFeedback('Error: ' + event.error);
                }
            };

            recognition.onend = () => {
                if (micActive) {
                    recognition.start();
                }
            };

            recognition.start();
        }

        function stopVoiceRecognition() {
            if (recognition) {
                recognition.stop();
                recognition = null;
            }
        }

        function processVoiceCommand(command) {
            if (command.includes('start')) {
                showVoiceFeedback('✓ Starting simulation');
                startSim();
            } else if (command.includes('stop')) {
                showVoiceFeedback('✓ Stopping simulation');
                stopSim();
            }
        }

        function showVoiceFeedback(message) {
            const feedback = document.getElementById('voiceFeedback');
            feedback.textContent = message;
            feedback.style.display = 'block';
            setTimeout(() => {
                feedback.style.display = 'none';
            }, 2000);
        }

        function startSim() {
            const params = {
                base_voltage: parseFloat(document.getElementById('base').value),
                frequency: parseFloat(document.getElementById('freq').value),
                amplitude: parseFloat(document.getElementById('amp').value)
            };

            fetch('/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params)
            })
            .then(r => r.text())
            .then(msg => console.log(msg))
            .catch(err => console.error(err));
        }

        function stopSim() {
            fetch('/stop', { method: 'POST' })
                .then(r => r.text())
                .then(msg => console.log(msg))
                .catch(err => console.error(err));
        }

        function downloadData() {
            window.location.href = '/download';
        }

        function updateCharts() {
            fetch('/data')
                .then(r => r.json())
                .then(resp => {
                    if (resp.data.length === 0) return;

                    const times = resp.data.map(d => d[0]);
                    const tank1 = resp.data.map(d => d[1]);
                    const tank2 = resp.data.map(d => d[2]);

                    tank1Chart.data.labels = times;
                    tank1Chart.data.datasets[0].data = tank1;
                    tank1Chart.update('none');

                    tank2Chart.data.labels = times;
                    tank2Chart.data.datasets[0].data = tank2;
                    tank2Chart.update('none');
                })
                .catch(err => console.error(err));
        }

        setInterval(updateCharts, 500);
    </script>
</body>
</html>
"""

# ------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------
@app.route("/")
def index():
    return render_template_string(
        HTML_TEMPLATE,
        camera_available=camera is not None and camera.isOpened()
    )

@app.route("/start", methods=["POST"])
def start_sim():
    params = request.get_json()
    try:
        base = float(params["base_voltage"])
        freq = float(params["frequency"])
        amp = float(params["amplitude"])
        if not (0 <= base <= 10 and 0 <= freq <= 10 and 0 <= amp <= 5):
            return "Invalid parameter range", 400
    except:
        return "Invalid parameters", 400

    with state_lock:
        if state["running"]:
            return "Already running", 400
        state["running"] = True
        state["data"] = []

    threading.Thread(
        target=run_simulation,
        args=(base, freq, amp),
        daemon=True
    ).start()

    return "Started", 200

@app.route("/stop", methods=["POST"])
def stop_sim():
    with state_lock:
        state["running"] = False
    return "Stopped", 200

@app.route("/data")
def data():
    with state_lock:
        return jsonify({"running": state["running"], "data": state["data"]})

@app.route("/download")
def download():
    with state_lock:
        df = pd.DataFrame(state["data"], columns=["Time (s)", "Tank 1 Height (cm)", "Tank 2 Height (cm)"])

    if df.empty:
        return "No data", 400
    
    df.index += 1
    df.to_csv(CSV_FILE_PATH, index_label="Sample")
    return send_file(CSV_FILE_PATH, as_attachment=True)

@app.route("/video_feed")
def video_feed():
    if not camera or not camera.isOpened():
        return Response("Camera not available", status=503)
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

# ------------------------------------------------------------
# CAMERA FRAME GENERATOR
# ------------------------------------------------------------
def gen_frames():
    """Stream MJPEG video frames safely."""
    global camera
    while True:
        if not camera or not camera.isOpened():
            print("[Camera] Lost connection")
            break

        ok, frame = camera.read()
        if not ok:
            print("[Camera] Frame read failed")
            time.sleep(0.2)
            continue

        success, buffer = cv2.imencode(".jpg", frame)
        if not success:
            continue

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" +
               buffer.tobytes() +
               b"\r\n")

# ------------------------------------------------------------
# SIMULATION THREAD
# ------------------------------------------------------------
def run_simulation(base, freq, amp):

    duration = 30
    dt = 1
    slope = 9.8
    offset = 0

    if not QUANSER_AVAILABLE:
        # Simulation mode - generate mock data
        print("[SIM] Running in simulation mode (no hardware)")
        t1_height = 5.0  # Initial height for tank 1
        t2_height = 5.0  # Initial height for tank 2
        
        try:
            for i in range(int(duration / dt)):
                with state_lock:
                    if not state["running"]:
                        break

                t = i * dt
                voltage = base + amp * math.sin(2 * math.pi * freq * t)
                
                # Simulate tank dynamics based on voltage input
                # Tank 1 responds to input voltage
                t1_target = (voltage / 10.0) * 20.0  # Scale to 0-20 cm
                t1_height = t1_height + 0.3 * (t1_target - t1_height)  # First order response
                
                # Tank 2 responds to tank 1 (coupled system)
                t2_target = t1_height * 0.8  # Coupling factor
                t2_height = t2_height + 0.2 * (t2_target - t2_height)
                
                # Add some noise for realism
                t1_height += np.random.normal(0, 0.1)
                t2_height += np.random.normal(0, 0.1)
                
                # Clamp values to reasonable range
                t1_height = max(0, min(20, t1_height))
                t2_height = max(0, min(20, t2_height))

                with state_lock:
                    state["data"].append((round(t,1), round(t1_height,2), round(t2_height,2)))

                time.sleep(dt)
        finally:
            with state_lock:
                state["running"] = False
        return

    # Hardware mode
    card = HIL()

    try:
        card.open("q2_usb", "0")
    except Exception as e:
        print("[HIL] Error opening:", e)
        with state_lock:
            state["running"] = False
        return

    output_ch = np.array([0], dtype=np.uint32)
    input_ch = np.array([0, 1], dtype=np.uint32)

    try:
        for i in range(int(duration / dt)):
            with state_lock:
                if not state["running"]:
                    break

            t = i * dt
            voltage = base + amp * math.sin(2 * math.pi * freq * t)

            try:
                card.write_analog(output_ch, 1, np.array([voltage], dtype=np.float64))

                buffer = np.zeros(2, dtype=np.float64)
                card.read_analog(input_ch, 2, buffer)

                t1 = slope * buffer[0] + offset
                t2 = slope * buffer[1] + offset

                with state_lock:
                    state["data"].append((round(t,1), round(t1,2), round(t2,2)))

            except Exception as e:
                print("[HIL] Step error:", e)

            time.sleep(dt)

        card.write_analog(output_ch, 1, np.array([0.0], dtype=np.float64))

    finally:
        card.close()
        with state_lock:
            state["running"] = False

# ------------------------------------------------------------
# AUTO OPEN BROWSER
# ------------------------------------------------------------
def open_browser():
    webbrowser.open("http://127.0.0.1:5000")

# ------------------------------------------------------------
# RUN APP
# ------------------------------------------------------------
if __name__ == "__main__":
    threading.Timer(1, open_browser).start()
    app.run(debug=True, use_reloader=False)


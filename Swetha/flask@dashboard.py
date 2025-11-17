import time
import threading
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from xarm.wrapper import XArmAPI  # Lite6 SDK

ROBOT_IP = "192.168.1.152"

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lite6secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

arm = None
arm_lock = threading.Lock()

def connect_robot():
    global arm
    try:
        with arm_lock:
            arm = XArmAPI(ROBOT_IP)
        print(f"Connected to xArm at {ROBOT_IP}")
    except Exception as e:
        print("Failed to connect to robot:", e)
        arm = None

def poll_robot():
    while True:
        try:
            if arm is not None:
                with arm_lock:
                    try:
                        angles = arm.angles
                    except Exception:
                        ok, angles = arm.get_servo_angle()
                        if not ok:
                            angles = [None]*6
                    try:
                        pos = arm.position
                    except Exception:
                        ok2, pos = arm.get_position()
                        if not ok2:
                            pos = [None]*6
                    try:
                        moving = arm.get_is_moving()[1]
                    except Exception:
                        moving = False

                    payload = {
                        "angles": angles if angles else [],
                        "position": pos if pos else [],
                        "moving": bool(moving)
                    }
                    socketio.emit('robot_state', payload)
        except Exception as e:
            socketio.emit('robot_error', {"error": str(e)})
        time.sleep(0.2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/voice', methods=['POST'])
def voice_cmd():
    data = request.json or {}
    spoken = data.get('text', '')
    heard = f"Server received: {spoken}"
    socketio.emit('voice_log', {"said": spoken, "heard": heard})
    return jsonify({"status":"ok","heard":heard})

@socketio.on('connect')
def handle_connect():
    print("Client connected")

if __name__ == '__main__':
    connect_robot()
    thr = threading.Thread(target=poll_robot, daemon=True)
    thr.start()
    socketio.run(app, host='0.0.0.0', port=5050)

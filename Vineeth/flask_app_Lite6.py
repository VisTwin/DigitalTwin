
from flask import Flask, request, jsonify, render_template, Response
from xarm.wrapper import XArmAPI
import threading
import cv2
import time

app = Flask(__name__)
robot = XArmAPI('192.168.1.152')  # your robot’s IP
robot.connect()
robot.motion_enable(True)
robot.set_mode(0)
robot.set_state(0)

DEFAULT_SPEED = 20
DEFAULT_ACCEL = 50
lock = threading.Lock()

# ----- Robot control endpoints -----
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/move_joint', methods=['POST'])
def move_joint():
    data = request.json
    joint = int(data.get('joint', 1))
    angle = float(data.get('angle', 0))
    with lock:
        code = robot.set_servo_angle(
            servo_id=joint, angle=angle,
            speed=DEFAULT_SPEED, mvacc=DEFAULT_ACCEL, wait=True
        )
    return jsonify({'status': 'ok' if code == 0 else 'error', 'code': code})

@app.route('/home', methods=['POST'])
def home():
    with lock:
        code = robot.set_servo_angle(
            angle=[0] * 6,
            speed=DEFAULT_SPEED, mvacc=DEFAULT_ACCEL, wait=True
        )
    return jsonify({'status': 'ok' if code == 0 else 'error', 'code': code})

@app.route('/clear_error', methods=['POST'])
def clear_error():
    with lock:
        robot.clean_error()
        code = robot.clean_warn()
    return jsonify({'status': 'cleared', 'code': code})

@app.route('/re_enable', methods=['POST'])
def re_enable():
    with lock:
        robot.motion_enable(True)
        robot.set_state(0)
    return jsonify({'status': 're_enabled'})

@app.route('/disconnect', methods=['POST'])
def disconnect():
    robot.disconnect()
    return jsonify({'status': 'disconnected'})

# ----- Live Camera Feed -----
camera = cv2.VideoCapture(0)

def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            continue
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ----- Start App for Remote Access -----
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)

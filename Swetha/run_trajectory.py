# run_trajectory_flask.py
import time
import pandas as pd
from xarm.wrapper import XArmAPI
import socketio

# ================= CONFIG =================
ROBOT_IP = "192.168.1.152"
EXCEL_FILE = "trajectory.xlsx"
DELAY = 0.3                 # seconds between trajectory points
FLASK_URL = "http://127.0.0.1:5050"   # Flask dashboard
NUM_JOINTS = 6
# ==========================================

# --- Connect robot ---
print("Connecting to xArm...")
arm = XArmAPI(ROBOT_IP)
arm.connect()
arm.clean_warn()
arm.clean_error()
arm.motion_enable(True)
arm.set_mode(0)  # Position control
arm.set_state(0)
time.sleep(0.5)
print("xArm connected and initialized.")

# --- Read trajectory Excel ---
df = pd.read_excel(EXCEL_FILE)
trajectory = df.iloc[:, :NUM_JOINTS].values.tolist()  # ensure only J1-J6 columns

# --- Connect to Flask dashboard SocketIO ---
sio = socketio.Client()
sio.connect(FLASK_URL)
print(f"Connected to Flask dashboard at {FLASK_URL}")

# --- Main continuous loop ---
print("Starting continuous trajectory loop. Press Ctrl+C to stop.")
try:
    while True:
        for angles in trajectory:
            # Move robot
            arm.set_servo_angle(servo_id=None, angle=angles, is_radian=False)

            # Emit to Flask dashboard for simulation
            sio.emit("robot_state", {"angles": angles, "position": [0]*6, "moving": True})

            time.sleep(DELAY)

except KeyboardInterrupt:
    print("\nInterrupted! Returning robot to home position...")
    home = [0]*NUM_JOINTS
    arm.set_servo_angle(servo_id=None, angle=home, is_radian=False)
    time.sleep(1)
    arm.motion_enable(False)
    arm.disconnect()
    print("Done. Robot disconnected and Flask simulation stops updating.")

finally:
    if sio.connected:
        sio.disconnect()


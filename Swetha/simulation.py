# lite6_viz.py
from vpython import canvas, vector, sphere, cylinder, color, rate, box, arrow
import requests
import numpy as np
import time
from collections import deque

# ---------------- CONFIG ----------------
FLASK_URL = "http://127.0.0.1:5000/joints"   # change if your Flask runs elsewhere
POLL_HZ = 30                                 # how often to fetch joint angles
SMOOTHING = 0.6                              # 0=no smoothing, 1=strong smoothing

# ---------------- DH PARAMETERS (Lite 6) ----------------
# Using standard DH: (d, a, alpha) and theta is taken from the robot (in degrees)
# These numbers are typical Lite 6 approximate parameters (meters)
dh_params = [
    (0.1519, 0.0,       np.pi/2),   # joint 1
    (0.0,    0.24365,   0.0),       # joint 2
    (0.0,    0.21325,   0.0),       # joint 3
    (0.13105,0.0,       np.pi/2),   # joint 4
    (0.08535,0.0,      -np.pi/2),   # joint 5
    (0.0921, 0.0,       0.0)        # joint 6 (tool)
]

NUM_JOINTS = 6

# ----------------- Forward Kinematics -----------------
def dh_transform(theta_rad, d, a, alpha):
    c = np.cos(theta_rad)
    s = np.sin(theta_rad)
    ca = np.cos(alpha)
    sa = np.sin(alpha)
    return np.array([
        [c,    -s*ca,   s*sa,   a*c],
        [s,     c*ca,  -c*sa,   a*s],
        [0,       sa,     ca,    d ],
        [0,        0,      0,    1 ]
    ])

def compute_fk(joints_deg):
    """Return a list of 7 points (base + 6 joint positions) in meters in world frame"""
    T = np.eye(4)
    pts = [T[:3,3].copy()]  # base at origin
    for i in range(NUM_JOINTS):
        theta = np.radians(joints_deg[i])  # assume SDK gives degrees
        d, a, alpha = dh_params[i]
        A = dh_transform(theta, d, a, alpha)
        T = T @ A
        pts.append(T[:3,3].copy())
    return pts  # length 7: base + 6 joints/end-effector



scene = canvas(
    title="UFactory Lite 6 — Real-time Digital Twin",
    width=1200,
    height=800,
    background=color.gray(0.15)
)

# ---- CAMERA & VIEW IMPROVEMENTS ----
scene.autoscale = False
scene.range = 0.7
scene.center = vector(0, 0.2, 0)
scene.forward = vector(-1, -1, -1)
scene.up = vector(0, 1, 0)

# allow user to rotate/zoom/pan
scene.userzoom = True
scene.userspin = True
scene.userpan  = True

# set a stable camera angle so all joints are visible
scene.forward = vector(-1, -1, -1)
scene.up      = vector(0, 1, 0)

# Add axis helper (optional but recommended)
arrow(pos=vector(0,0,0), axis=vector(0.25,0,0), color=color.red)   # X axis
arrow(pos=vector(0,0,0), axis=vector(0,0.25,0), color=color.green) # Y axis
arrow(pos=vector(0,0,0), axis=vector(0,0,0.25), color=color.blue)  # Z axis

# Ground plane
ground = box(pos=vector(0, -0.02, 0), size=vector(1.2, 0.01, 1.2), color=color.gray(0.2))

# joint spheres and link cylinders
joint_spheres = [sphere(radius=0.025, color=color.red) for _ in range(NUM_JOINTS + 1)]
link_cylinders = [cylinder(radius=0.012, color=color.white) for _ in range(NUM_JOINTS)]

# base visualization
base = cylinder(pos=vector(0, -0.02, 0), axis=vector(0, 0.02, 0), radius=0.05, color=color.gray(0.35))

# initialize positions in a default pose (all zeros)
default_angles = [0]*NUM_JOINTS
pts = compute_fk(default_angles)
for i in range(NUM_JOINTS + 1):
    p = pts[i]
    joint_spheres[i].pos = vector(p[0], p[2], p[1])  # note: swap axes if you prefer different orientation

for i in range(NUM_JOINTS):
    p1 = pts[i]; p2 = pts[i+1]
    link_cylinders[i].pos = vector(p1[0], p1[2], p1[1])
    link_cylinders[i].axis = vector(p2[0]-p1[0], p2[2]-p1[2], p2[1]-p1[1])
    link_cylinders[i].length = np.linalg.norm(p2 - p1)

# ---------------- Data smoothing helper ----------------
# keep a running filtered angle set to smooth network jitter
filtered = np.array(default_angles, dtype=float)

# ---------------- Main loop ----------------
last_fetch = 0.0
poll_interval = 1.0 / POLL_HZ

print("Starting visualization. Press Ctrl+C to stop.")
while True:
    rate(60)  # cap GUI update to 60 fps

    # Poll Flask endpoint at POLL_HZ
    now = time.time()
    if now - last_fetch >= poll_interval:
        last_fetch = now
        try:
            r = requests.get(FLASK_URL, timeout=0.5)
            payload = r.json()
            joints = payload.get("joints", None)
            if joints is None:
                print("Flask returned JSON but no 'joints' key.")
                continue
            if len(joints) != NUM_JOINTS:
                print(f"Expected {NUM_JOINTS} joints but got {len(joints)}. Received: {joints}")
                continue

            # convert to numpy array of floats
            joints_arr = np.array(joints, dtype=float)

            # simple exponential smoothing
            filtered = SMOOTHING * filtered + (1.0 - SMOOTHING) * joints_arr

            # compute FK and update visuals
            pts = compute_fk(filtered.tolist())

            # Update spheres and links
            for i in range(NUM_JOINTS + 1):
                p = pts[i]
                # map robot frame (x,y,z) to VPython axes if needed
                # here we use VPython: x = p[0], y = p[2], z = p[1] (so arm rises in +y)
                joint_spheres[i].pos = vector(p[0], p[2], p[1])

            for i in range(NUM_JOINTS):
                p1 = pts[i]; p2 = pts[i+1]
                pos = vector(p1[0], p1[2], p1[1])
                axis = vector(p2[0]-p1[0], p2[2]-p1[2], p2[1]-p1[1])
                link_cylinders[i].pos = pos
                link_cylinders[i].axis = axis
                # length is automatically magnitude of axis; radius defined earlier

        except requests.exceptions.RequestException as ex:
            # network timeout or connection refused
            # print only once per second to avoid console spam
            if int(time.time()) % 5 == 0:
                print("Warning: cannot reach Flask endpoint:", ex)
            continue
        except Exception as e:
            print("Error while fetching/updating:", e)
            continue

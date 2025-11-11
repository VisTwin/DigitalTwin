import zmq
import time
import json
from random import uniform

ctx = zmq.Context()
socket = ctx.socket(zmq.PUB)
socket.bind("tcp://*:5556")

drone_id = "drone_1"

while True:
    # Simulated drone state (mock data)
    state = {
        "id": drone_id,
        "x": round(uniform(0, 10), 2),
        "y": round(uniform(0, 10), 2),
        "z": round(uniform(1, 5), 2),
        "vx": round(uniform(-1, 1), 2),
        "vy": round(uniform(-1, 1), 2),
        "vz": round(uniform(-0.5, 0.5), 2)
    }
    socket.send_json(state)
    print(f"Sent: {json.dumps(state)}")
    time.sleep(1)

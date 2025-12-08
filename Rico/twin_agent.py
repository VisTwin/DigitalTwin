import asyncio
import websockets
import zmq
import zmq.asyncio
import json

ctx = zmq.asyncio.Context()
socket = ctx.socket(zmq.SUB)
socket.connect("tcp://localhost:5556")
socket.setsockopt_string(zmq.SUBSCRIBE, "")

clients = set()

async def zmq_listener():
    while True:
        msg = await socket.recv_json()
        # forward message to all websocket clients
        dead_clients = set()
        for ws in clients:
            try:
                await ws.send(json.dumps(msg))
            except:
                dead_clients.add(ws)
        clients.difference_update(dead_clients)

async def ws_handler(websocket):
    clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        clients.remove(websocket)

async def main():
    ws_server = websockets.serve(ws_handler, "localhost", 8765)
    await asyncio.gather(ws_server, zmq_listener())

asyncio.run(main())

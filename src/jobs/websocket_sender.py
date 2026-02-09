import asyncio
import json
from threading import Thread, Event
from queue import Queue, Empty
from collections import deque

import websockets
import numpy as np
from obspy import Trace, UTCDateTime


class WebSocketSender(Thread):
    def __init__(
        self,
        data_queue: Queue,
        shutdown_event: Event,
        host: str = "localhost",
        port: int = 8765,
        downsample_rate: int = 10,
    ):
        super().__init__()
        self.data_queue = data_queue
        self.shutdown_event = shutdown_event
        self.host = host
        self.port = port
        self.downsample_rate = downsample_rate

        self._buffers = {}  # {channel_name: deque[(timestamp, value)]}
        self._clients = set()  # connected websocket clients

    def run(self):
        asyncio.run(self._start_server())

    async def _start_server(self):
        async with websockets.serve(self._handle_connection, self.host, self.port):
            print(f"WebSocket server started on ws://{self.host}:{self.port}")
            await self._producer_loop()

    async def _handle_connection(self, websocket):
        self._clients.add(websocket)
        print(f"Client connected ({len(self._clients)} total)")
        try:
            await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)
            print(f"Client disconnected ({len(self._clients)} total)")

    async def _producer_loop(self):
        """Consumes queue data and broadcasts to all clients."""
        while not self.shutdown_event.is_set():
            try:
                channel, value, timestamp = self.data_queue.get(timeout=1)
            except Empty:
                await asyncio.sleep(0.01)
                continue

            name = channel.name
            if name not in self._buffers:
                self._buffers[name] = deque(maxlen=self.downsample_rate)

            self._buffers[name].append((timestamp, value))

            if len(self._buffers[name]) == self.downsample_rate:
                times, values = zip(*self._buffers[name])

                trace = Trace()
                trace.data = np.array(values, dtype=np.float32)
                trace.stats.network = "XX"
                trace.stats.station = name
                trace.stats.starttime = UTCDateTime(times[0])

                trace.decimate(factor=self.downsample_rate)

                await self._broadcast(trace)
                self._buffers[name].clear()

    async def _broadcast(self, trace):
        if not self._clients:
            return

        message = json.dumps(
            {
                "channel": trace.stats.station,
                "timestamp": trace.stats.starttime.isoformat(),
                "data": trace.data.tolist(),
            }
        )

        dead_clients = set()

        send_tasks = []
        for ws in self._clients:
            send_tasks.append(self._safe_send(ws, message, dead_clients))

        await asyncio.gather(*send_tasks, return_exceptions=True)
        self._clients.difference_update(dead_clients)

    async def _safe_send(self, websocket, message, dead_clients):
        try:
            await websocket.send(message)
        except websockets.exceptions.ConnectionClosed:
            dead_clients.add(websocket)

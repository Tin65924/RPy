import asyncio
import json
import time
import gzip
import hashlib
from collections import deque
from aiohttp import web
from pathlib import Path
from typing import Dict, Optional, Any

class DevServer:
    def __init__(self, host: str = "localhost", port: int = 8000, config: Optional[Dict] = None):
        self.host = host
        self.port = port
        self.config = config or {}
        self.app = web.Application()
        self.app.add_routes([
            web.get('/sync', self.handle_sync),
            web.get('/status', self.handle_status),
        ])
        
        # In-memory virtual filesystem for transpiled Luau code
        # Path (str) -> { "code": str, "mtime": float, "type": str, "sid": str }
        self.vfs: Dict[str, Dict[str, Any]] = {}
        self.events = deque(maxlen=1000) # Deque of { "id": int, "path": str, "type": str, "code": str/None }
        self.next_event_id = 1
        self.oldest_event_id = 1
        
        self.last_sync_time = time.time()
        self.start_time = time.time()
        
        # Telemetry
        self.stats = {
            "files_synced": 0,
            "total_errors": 0,
            "avg_latency": 0.0,
            "last_latency": 0.0
        }

    async def handle_status(self, request: web.Request) -> web.Response:
        status_data = {
            "status": "active",
            "uptime": time.time() - self.start_time,
            "files_in_memory": len(self.vfs),
            "stats": self.stats,
            "last_sync": self.last_sync_time
        }
        return web.json_response(status_data)

    async def handle_sync(self, request: web.Request) -> web.Response:
        """
        Plugin polls this to get changed files since its last requested event ID.
        Query Param: after (int)
        """
        try:
            after_id = int(request.query.get("after", 0))
        except ValueError:
            after_id = 0
            
        # Robustness check: If after_id is too old or server restart (no events)
        resync = False
        if after_id > 0:
            if not self.events or after_id < self.oldest_event_id - 1:
                resync = True
        
        if resync:
            return web.json_response({"resync": True, "latest_event_id": self.next_event_id - 1})
            
        # Filter events from deque
        new_events = [e for e in self.events if e["id"] > after_id]
        
        response_data = {
            "timestamp": time.time(),
            "events": new_events,
            "latest_event_id": self.next_event_id - 1,
            "config": self.config
        }
        
        json_data = json.dumps(response_data).encode('utf-8')
        
        # Handle Gzip compression if requested
        accept_encoding = request.headers.get('Accept-Encoding', '')
        if 'gzip' in accept_encoding and len(json_data) > 1024:
            compressed = gzip.compress(json_data)
            return web.Response(
                body=compressed,
                content_type='application/json',
                headers={'Content-Encoding': 'gzip'}
            )
        
        return web.Response(body=json_data, content_type='application/json')

    def _generate_sid(self, path: str) -> str:
        """Generate a deterministic stable ID for a file path (normalized)."""
        normalized_path = path.replace("\\", "/")
        return hashlib.md5(normalized_path.encode()).hexdigest()

    def update_file(self, path: str, code: str, script_type: str, latency: float = 0.0):
        """Update a file in the virtual filesystem and log an event."""
        path = path.replace("\\", "/")
        sid = self._generate_sid(path)
        self.vfs[path] = {
            "code": code,
            "mtime": time.time(),
            "type": script_type,
            "sid": sid
        }
        
        # Log event
        event = {
            "id": self.next_event_id,
            "type": "update",
            "script_type": script_type,
            "path": path,
            "code": code,
            "sid": sid
        }
        self.events.append(event)
        self.next_event_id += 1
        
        # Update oldest tracking (deque handles maxlen automatically)
        if self.events:
            self.oldest_event_id = self.events[0]["id"]

        self.stats["files_synced"] += 1
        self.stats["last_latency"] = latency
        # Simple moving average for latency
        current_avg = self.stats.get("avg_latency", 0)
        self.stats["avg_latency"] = (current_avg * 0.9) + (latency * 0.1)
        self.last_sync_time = time.time()

    def remove_file(self, path: str):
        """Remove a file from VFS and log a delete event."""
        path = path.replace("\\", "/")
        if path in self.vfs:
            sid = self.vfs[path]["sid"]
            del self.vfs[path]
            
            event = {
                "id": self.next_event_id,
                "type": "delete",
                "path": path,
                "sid": sid
            }
            self.events.append(event)
            self.next_event_id += 1
            if self.events:
                self.oldest_event_id = self.events[0]["id"]
            return True
        return False

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        print(f"RPy Dev Server started at http://{self.host}:{self.port}")

if __name__ == "__main__":
    server = DevServer()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(server.start())
    loop.run_forever()

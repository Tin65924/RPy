import asyncio
import json
import time
import gzip
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
        # Path (str) -> { "code": str, "mtime": float, "type": str }
        self.vfs: Dict[str, Dict[str, Any]] = {}
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
        Plugin polls this to get changed files since its last requested timestamp.
        Query Param: since (float)
        """
        since = float(request.query.get("since", 0))
        
        changed = {}
        for path, data in self.vfs.items():
            if data["mtime"] > since:
                changed[path] = data
        
        response_data = {
            "timestamp": time.time(),
            "files": changed,
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

    def update_file(self, path: str, code: str, script_type: str, latency: float = 0.0):
        """Update a file in the virtual filesystem."""
        self.vfs[path] = {
            "code": code,
            "mtime": time.time(),
            "type": script_type
        }
        self.stats["files_synced"] += 1
        self.stats["last_latency"] = latency
        # Simple moving average for latency
        self.stats["avg_latency"] = (self.stats["avg_latency"] * 0.9) + (latency * 0.1)
        self.last_sync_time = time.time()

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

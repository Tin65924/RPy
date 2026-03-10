import time
import threading
import json
import gzip
import requests
from pathlib import Path
from sync.server import DevServer
from cli.main import CompilerFlags

def test_sync_flow_manual():
    """Manual integration test: start server and hit it with requests."""
    server = DevServer(port=8001)
    
    # Run server in thread
    def run_server():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.start())
        loop.run_forever()

    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(1) # wait for start
    
    # 1. Check status
    resp = requests.get("http://localhost:8001/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"
    
    # 2. Update a file
    code = "print('hello')"
    server.update_file("main.py", code, "server")
    
    # 3. Sync
    resp = requests.get("http://localhost:8001/sync?since=0")
    assert resp.status_code == 200
    data = resp.json()
    assert "main.py" in data["files"]
    assert data["files"]["main.py"]["code"] == code
    
    # 4. Gzip test
    large_code = "print('long')\n" * 500
    server.update_file("large.py", large_code, "module")
    
    headers = {"Accept-Encoding": "gzip"}
    resp = requests.get("http://localhost:8001/sync?since=0", headers=headers)
    assert resp.status_code == 200
    
    # requests often decompresses automatically
    if resp.headers.get("Content-Encoding") == "gzip":
        try:
            decompressed = gzip.decompress(resp.content)
            data = json.loads(decompressed)
        except gzip.BadGzipFile:
            # Already decompressed by requests
            data = resp.json()
    else:
        data = resp.json()
        
    assert "large.py" in data["files"]
    
    print("Integration test passed!")

if __name__ == "__main__":
    test_sync_flow_manual()

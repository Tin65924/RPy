import json
import pytest
from collections import deque
from sync.server import DevServer

def test_event_log_overflow():
    server = DevServer()
    # Re-initialize events with small maxlen for test
    server.events = deque(maxlen=5)
    
    # Add 10 files
    for i in range(10):
        server.update_file(f"test{i}.py", f"print({i})", "server")
        
    assert len(server.events) == 5
    assert server.events[0]["id"] == 6
    assert server.events[-1]["id"] == 10
    assert server.oldest_event_id == 6

@pytest.mark.asyncio
async def test_resync_flag_on_overflow():
    server = DevServer()
    server.events = deque(maxlen=5)
    for i in range(10):
        server.update_file(f"test{i}.py", "code", "server")
        
    # Plugin asks for event 1 (which is long gone)
    class FakeRequest:
        def __init__(self, query):
            self.query = query
            self.headers = {}
    
    req = FakeRequest({"after": "1"})
    resp = await server.handle_sync(req)
    data = json.loads(resp.body.decode())
    
    assert data.get("resync") is True

@pytest.mark.asyncio
async def test_resync_flag_on_restart():
    server = DevServer() # Fresh server, no events
    
    # Plugin asks for event 42 from a previous session
    class FakeRequest:
        def __init__(self, query):
            self.query = query
            self.headers = {}
            
    req = FakeRequest({"after": "42"})
    resp = await server.handle_sync(req)
    data = json.loads(resp.body.decode())
    
    assert data.get("resync") is True

def test_path_normalization():
    server = DevServer()
    server.update_file("sub\\folder\\test.py", "print(1)", "server")
    
    # Check VFS Key
    assert "sub/folder/test.py" in server.vfs
    assert "sub\\folder\\test.py" not in server.vfs
    
    # Check Event Path
    assert server.events[0]["path"] == "sub/folder/test.py"
    
    # Check SID (should be same for both)
    sid1 = server._generate_sid("sub/folder/test.py")
    sid2 = server._generate_sid("sub\\folder\\test.py")
    assert sid1 == sid2

def test_deletion_event():
    server = DevServer()
    server.update_file("test.py", "code", "server")
    server.remove_file("test.py")
    
    assert "test.py" not in server.vfs
    assert len(server.events) == 2
    assert server.events[1]["type"] == "delete"
    assert "sid" in server.events[1]

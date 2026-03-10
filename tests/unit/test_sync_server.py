import json
import gzip
import pytest
import aiohttp
from aiohttp import web
from sync.server import DevServer

@pytest.fixture
async def dev_server(aiohttp_client):
    server = DevServer()
    return await aiohttp_client(server.app)

@pytest.mark.asyncio
async def test_status_endpoint(dev_server):
    resp = await dev_server.get('/status')
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "active"
    assert "uptime" in data

@pytest.mark.asyncio
async def test_sync_empty(dev_server):
    resp = await dev_server.get('/sync?since=0')
    assert resp.status == 200
    data = await resp.json()
    assert data["files"] == {}

async def test_sync_with_files(dev_server):
    # Simulate a file update directly on the server object
    # The fixture aiohttp_client wraps the site, but we can't easily access the DevServer instance 
    # unless we pass it specifically. Let's redefine the fixture.
    pass

@pytest.fixture
async def dev_server_instance():
    server = DevServer()
    return server

@pytest.mark.asyncio
async def test_sync_gzip(aiohttp_client, dev_server_instance):
    # Add a large file to trigger gzip
    large_code = "print('hello world')\n" * 200 # > 1024 bytes
    dev_server_instance.update_file("test.py", large_code, "server")
    
    client = await aiohttp_client(dev_server_instance.app)
    
    # Request with gzip
    headers = {"Accept-Encoding": "gzip"}
    resp = await client.get('/sync?since=0', headers=headers)
    assert resp.status == 200
    assert resp.headers.get("Content-Encoding") == "gzip"
    
    # Decompress and verify
    body = await resp.read()
    json_data = json.loads(gzip.decompress(body))
    assert "test.py" in json_data["files"]
    assert json_data["files"]["test.py"]["code"] == large_code

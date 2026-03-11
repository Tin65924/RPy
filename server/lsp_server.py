"""
server/lsp_server.py — Lightweight LSP implementation for RPy.
"""

from __future__ import annotations
import json
import socketserver
import sys
from typing import Any, Dict, List, Optional
from transpiler.query_service import query_service

class LSPHandler(socketserver.StreamRequestHandler):
    document_cache: Dict[str, str] = {}

    def handle(self):
        print(f"LSP connection from {self.client_address}")
        while True:
            try:
                # Read Content-Length header
                line = self.rfile.readline().decode("utf-8")
                if not line: break
                
                if line.startswith("Content-Length:"):
                    length = int(line.split(":")[1].strip())
                    self.rfile.readline() # Consume the empty line
                    
                    data = self.rfile.read(length).decode("utf-8")
                    request = json.loads(data)
                    self.process_request(request)
            except Exception as e:
                print(f"LSP Error: {e}")
                break

    def process_request(self, request: Dict[str, Any]):
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "initialize":
            self.send_response(request_id, {
                "capabilities": {
                    "textDocumentSync": 1, # Full sync
                    "hoverProvider": True,
                    "completionProvider": {
                        "triggerCharacters": ["."]
                    }
                }
            })
        elif method == "textDocument/didOpen":
            self.handle_sync(params)
        elif method == "textDocument/didChange":
            self.handle_sync(params)
        elif method == "textDocument/hover":
            self.handle_hover(request_id, params)
        elif method == "textDocument/completion":
            self.handle_completion(request_id, params)
        elif method == "shutdown":
            self.send_response(request_id, {})
        elif method == "exit":
            sys.exit(0)

    def handle_sync(self, params: Dict[str, Any]):
        doc = params.get("textDocument", {})
        uri = doc.get("uri", "")
        
        # In didChange, it might be in 'contentChanges'
        changes = params.get("contentChanges")
        if changes:
            text = changes[0].get("text")
        else:
            text = doc.get("text")
            
        if text and uri:
            self.document_cache[uri] = text
            filename = uri.replace("file://", "")
            diagnostics = query_service.get_diagnostics(text, filename=filename)
            self.send_notification("textDocument/publishDiagnostics", {
                "uri": uri,
                "diagnostics": [
                    {
                        "range": {
                            "start": {"line": d["line"] - 1, "character": d["col"]},
                            "end": {"line": d["line"] - 1, "character": d["col"] + 1} # Minimal range
                        },
                        "severity": 1 if d["severity"] == "ERROR" else 2,
                        "message": d["message"],
                        "source": "RPy"
                    }
                    for d in diagnostics if d.get("line") is not None
                ]
            })

    def handle_hover(self, request_id: Any, params: Dict[str, Any]):
        pos = params.get("position", {})
        uri = params.get("textDocument", {}).get("uri", "")
        line = pos.get("line", 0) + 1
        col = pos.get("character", 0)
        
        text = self.document_cache.get(uri)
        if text:
            hover_text = query_service.get_hover(text, line, col, filename=uri.replace("file://", ""))
            if hover_text:
                self.send_response(request_id, {
                    "contents": {
                        "kind": "markdown",
                        "value": f"```python\n{hover_text}\n```"
                    }
                })
                return
        
        self.send_response(request_id, None)

    def handle_completion(self, request_id: Any, params: Dict[str, Any]):
        pos = params.get("position", {})
        uri = params.get("textDocument", {}).get("uri", "")
        line = pos.get("line", 0) + 1
        col = pos.get("character", 0)
        
        text = self.document_cache.get(uri)
        if text:
            items = query_service.get_completions(text, line, col, filename=uri.replace("file://", ""))
            # Map kinds: Property -> 10, Method -> 2
            for item in items:
                k = item.get("kind")
                if k == "Property": item["kind"] = 10
                elif k == "Method": item["kind"] = 2
            
            self.send_response(request_id, {"isIncomplete": False, "items": items})
            return

        self.send_response(request_id, {"isIncomplete": False, "items": []})

    def send_response(self, request_id: Any, result: Any):
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        self._send(response)

    def send_notification(self, method: str, params: Any):
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        self._send(notification)

    def _send(self, data: Dict[str, Any]):
        body = json.dumps(data)
        message = f"Content-Length: {len(body)}\r\n\r\n{body}"
        self.wfile.write(message.encode("utf-8"))
        self.wfile.flush()

def start_lsp_server(host: str = "127.0.0.1", port: int = 8080):
    print(f"Starting RPy LSP server on {host}:{port}")
    with socketserver.TCPServer((host, port), LSPHandler) as server:
        server.serve_forever()

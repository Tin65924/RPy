import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Callable, Optional

class RPyWatcher(FileSystemEventHandler):
    def __init__(self, src_path: Path, on_changed: Callable[[Path], None]):
        self.src_path = src_path
        self.on_changed = on_changed
        self._last_trigger = {} # debounce

    def on_modified(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith(".py"):
            return
            
        path = Path(event.src_path)
        
        # Simple debounce: 100ms
        now = time.time()
        if path in self._last_trigger and (now - self._last_trigger[path]) < 0.1:
            return
            
        self._last_trigger[path] = now
        self.on_changed(path)

    def on_created(self, event):
        self.on_modified(event)

    def on_deleted(self, event):
        # Handle deletions if needed
        pass

def start_watcher(src_path: Path, callback: Callable[[Path], None]):
    event_handler = RPyWatcher(src_path, callback)
    observer = Observer()
    observer.schedule(event_handler, str(src_path), recursive=True)
    observer.start()
    return observer

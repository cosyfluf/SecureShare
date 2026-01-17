import os
import uuid
import socket

#define directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

# Global server status
SERVER_CONFIG = {
    "folder_path": os.getcwd(),
    "password": "admin",
    "is_running": True,
    "is_paused": False,
    "require_approval": False,
    "session_token": str(uuid.uuid4()),
    "config_id": str(uuid.uuid4())
}

# In-Memory storage for downloads
DOWNLOAD_REQUESTS = {}

#looking for dynamic port for admin-panel
def get_free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port

ADMIN_PORT = get_free_port()
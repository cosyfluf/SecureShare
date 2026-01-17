import math
import os
from functools import wraps
from flask import session, redirect, url_for
from config import SERVER_CONFIG

def format_file_size(size_bytes):
    """Formatiert Bytes in KB, MB, GB."""
    if size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def login_required(f):
    """Prüft, ob der Client eingeloggt ist und der Server läuft."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not SERVER_CONFIG['is_running'] or not session.get('logged_in') or session.get('token') != SERVER_CONFIG['session_token']:
            session.clear()
            return redirect(url_for('client_login'))
        return f(*args, **kwargs)
    return decorated_function
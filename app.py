import os
import uuid
import time
import socket
import threading
import webbrowser
import math
import tkinter as tk
from tkinter import filedialog
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify

# ==========================================
# CONFIGURATION & SHARED STATE
# ==========================================

# Define absolute paths to ensure resources are found regardless of execution context
# BASE_DIR: The root directory of the application script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# TEMPLATE_DIR: Path to the HTML templates
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
# STATIC_DIR: Path to static assets like CSS and JS
STATIC_DIR = os.path.join(BASE_DIR, 'static')

# Global Server Configuration Dictionary
# This dictionary acts as shared memory between the Admin and Client interfaces.
# It maintains the runtime state of the application.
SERVER_CONFIG = {
    "folder_path": os.getcwd(),          # The directory currently being shared with clients
    "password": "admin",                 # The password required for client authentication
    "is_running": True,                  # Master switch: if False, clients are logged out/blocked
    "is_paused": False,                  # Toggles UI blur on client side and blocks downloads
    "require_approval": False,           # If True, downloads enter a 'pending' state for admin review
    "session_token": str(uuid.uuid4()),  # Unique token regenerated on 'Logout All' to invalidate sessions
    "config_id": str(uuid.uuid4())       # Unique ID updated when critical config changes (like folder path)
}

# In-memory storage for active download requests
# Keys are UUID strings. Values are dictionaries containing file details and status.
DOWNLOAD_REQUESTS = {}

# ==========================================
# INITIALIZE FLASK APPS
# ==========================================

# 1. Client App (Public Interface)
# This Flask instance serves the user-facing file browser.
# It listens on all network interfaces (0.0.0.0).
client_app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
client_app.secret_key = os.urandom(24)

# 2. Admin App (Localhost Only)
# This Flask instance serves the control panel.
# It is strictly bound to 127.0.0.1 for security.
admin_app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
admin_app.secret_key = os.urandom(24)

# Determine a random free port for the Admin Panel
# We bind a socket to port 0, let the OS assign a free port, then close the socket.
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('127.0.0.1', 0))
ADMIN_PORT = sock.getsockname()[1]
sock.close()


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def format_file_size(size_bytes):
    """
    Converts a file size in raw bytes into a human-readable string.

    Args:
        size_bytes (int): The size of the file in bytes.

    Returns:
        str: Formatted string (e.g., "1.5 MB", "500 KB").
             Returns "0 B" if the file is empty.
    """
    if size_bytes == 0:
        return "0 B"

    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"


# ==========================================
# CLIENT APP ROUTES (Public Port 5000)
# ==========================================

def login_required(f):
    """
    Decorator to ensure the client is authenticated via session.

    Performs the following checks:
    1. Is the server currently running?
    2. Does the session have the 'logged_in' flag?
    3. Does the session token match the current server token?

    If any check fails, the user is redirected to the login page
    and their session is cleared.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not SERVER_CONFIG['is_running'] or not session.get('logged_in') or session.get('token') != SERVER_CONFIG['session_token']:
            session.clear()
            return redirect(url_for('client_login'))
        return f(*args, **kwargs)
    return decorated_function

@client_app.route('/')
def index():
    """
    Root endpoint.
    Redirects all visitors to the client login page.
    """
    return redirect(url_for('client_login'))

@client_app.route('/login', methods=['GET', 'POST'])
def client_login():
    """
    Handles the client authentication process.

    GET: Renders the login form. Checks for logout messages.
    POST: Validates the password against SERVER_CONFIG.
          Sets session variables on success.
    """
    if request.args.get('reason') == 'logout':
        flash('You have been logged out by the administrator.')

    # If the server is marked as offline, show the error state
    if not SERVER_CONFIG["is_running"]:
        return render_template('client/login.html', error="Server is currently offline.")

    if request.method == 'POST':
        password_input = request.form.get('password')
        if password_input == SERVER_CONFIG["password"]:
            session['logged_in'] = True
            session['token'] = SERVER_CONFIG['session_token']
            return redirect(url_for('client_files'))
        else:
            flash('Invalid Password')

    return render_template('client/login.html')

@client_app.route('/logout')
def client_logout():
    """
    Logs the user out by clearing their session data.
    Redirects back to the login page.
    """
    session.clear()
    return redirect(url_for('client_login'))

@client_app.route('/files')
@login_required
def client_files():
    """
    Renders the file browser interface.

    Logic:
    1. Resolves the requested path relative to the shared root.
    2. Prevents directory traversal attacks.
    3. Lists files and folders.
    4. Formats file sizes for display using format_file_size().
    """
    root = SERVER_CONFIG["folder_path"]
    req_path = request.args.get('path', '')
    abs_path = os.path.join(root, req_path)

    # Security: Ensure the resolved path is actually inside the root folder
    try:
        if os.path.commonpath([root, abs_path]) != os.path.normpath(root):
            return "Invalid Path", 403
    except Exception:
        return "Invalid Path", 403

    # If the directory doesn't exist (e.g., admin changed root), reload to root
    if not os.path.exists(abs_path):
        return redirect(url_for('client_files'))

    files_list = []
    folders_list = []

    try:
        for item in os.listdir(abs_path):
            full = os.path.join(abs_path, item)
            # Use forward slashes for URL consistency
            rel = os.path.join(req_path, item).replace("\\", "/")

            if os.path.isdir(full):
                folders_list.append({'name': item, 'path': rel})
            else:
                raw_size = os.path.getsize(full)
                # Format size to KB/MB/GB
                formatted_size = format_file_size(raw_size)
                files_list.append({'name': item, 'size': formatted_size, 'path': rel})
    except Exception as e:
        return f"Error reading directory: {e}", 500

    parent = os.path.dirname(req_path) if req_path else None

    return render_template('client/files.html',
                           files=files_list,
                           folders=folders_list,
                           current_path=req_path,
                           parent=parent)

# --- Client API Endpoints ---

@client_app.route('/api/client/status')
def client_status():
    """
    Provides the current server state to the client via AJAX.

    Returns JSON containing:
        paused: UI blur state.
        running: Connection acceptance state.
        force_logout: Boolean if the session is invalid.
        config_id: Hash to detect file system changes.
    """
    token_valid = session.get('token') == SERVER_CONFIG['session_token']
    is_logged_in = session.get('logged_in')
    force_logout = is_logged_in and not token_valid

    return jsonify({
        "paused": SERVER_CONFIG["is_paused"],
        "running": SERVER_CONFIG["is_running"],
        "force_logout": force_logout,
        "config_id": SERVER_CONFIG["config_id"]
    })

@client_app.route('/api/client/request_download', methods=['POST'])
@login_required
def request_download():
    """
    Handles a download initiation request.

    If 'Require Approval' is OFF: Returns a direct download link.
    If 'Require Approval' is ON: Creates a request ticket and returns the ID.
    """
    data = request.json
    filename = data.get('filename')
    rel_path = data.get('path')

    # Fallback if path is missing
    if not rel_path:
        rel_path = filename

    # Verify file existence on disk
    full_path = os.path.join(SERVER_CONFIG["folder_path"], rel_path)

    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404

    file_rel_path = rel_path.replace("\\", "/")

    # Check approval mode
    if not SERVER_CONFIG["require_approval"]:
        return jsonify({
            "status": "approved",
            "direct_link": url_for('download_content', filepath=file_rel_path)
        })

    # Generate Request ID
    req_id = str(uuid.uuid4())
    DOWNLOAD_REQUESTS[req_id] = {
        'file': filename,
        'filepath': file_rel_path,
        'status': 'pending',
        'timestamp': time.time()
    }
    return jsonify({"status": "pending", "req_id": req_id})

@client_app.route('/api/client/cancel_request', methods=['POST'])
@login_required
def cancel_request():
    """
    Allows a client to cancel their own pending download request.
    Removes the request from the memory store.
    """
    req_id = request.json.get('req_id')
    if req_id in DOWNLOAD_REQUESTS:
        del DOWNLOAD_REQUESTS[req_id]
        return jsonify({"status": "cancelled"})
    return jsonify({"status": "not_found"})

@client_app.route('/api/client/check_request/<req_id>')
@login_required
def check_request(req_id):
    """
    Polled by the client to check if a specific request ID has been approved or rejected.
    """
    if req_id not in DOWNLOAD_REQUESTS:
        return jsonify({"status": "error"})

    req = DOWNLOAD_REQUESTS[req_id]
    response = {"status": req['status']}

    if req['status'] == 'approved':
        response['link'] = url_for('download_content', filepath=req['filepath'], token=req_id)

    return jsonify(response)

@client_app.route('/download_final')
@login_required
def download_content():
    """
    Serves the binary file content to the user.
    Final security check happens here (Pause state, Approval Token validation).
    """
    filepath = request.args.get('filepath')
    token = request.args.get('token')

    if SERVER_CONFIG["is_paused"]:
        return "Server Paused", 403

    if SERVER_CONFIG["require_approval"]:
        if not token or token not in DOWNLOAD_REQUESTS or DOWNLOAD_REQUESTS[token]['status'] != 'approved':
            return "Access Denied / Not Approved", 403

        # Cleanup request after successful token validation
        if token in DOWNLOAD_REQUESTS:
            del DOWNLOAD_REQUESTS[token]

    full_path = os.path.join(SERVER_CONFIG["folder_path"], filepath)
    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)

    return send_from_directory(directory, filename, as_attachment=True)


# ==========================================
# ADMIN APP ROUTES (Localhost Random Port)
# ==========================================

@admin_app.route('/')
def admin_root():
    """Redirects admin root to the dashboard."""
    return redirect('/admin')

@admin_app.route('/admin')
def admin_dashboard():
    """Renders the main Admin Control Panel."""
    return render_template('server/index.html', config=SERVER_CONFIG)

@admin_app.route('/admin/api/status', methods=['GET', 'POST'])
def admin_api_status():
    """
    Handles reading and writing server configuration.
    POST updates are atomic. Changing the folder path triggers a config_id update.
    """
    if request.method == 'POST':
        data = request.json
        if 'password' in data:
            SERVER_CONFIG['password'] = data['password']
        if 'folder_path' in data:
            if os.path.exists(data['folder_path']):
                SERVER_CONFIG['folder_path'] = data['folder_path']
                SERVER_CONFIG['config_id'] = str(uuid.uuid4())
        if 'is_running' in data:
            SERVER_CONFIG['is_running'] = data['is_running']
        if 'is_paused' in data:
            SERVER_CONFIG['is_paused'] = data['is_paused']
        if 'require_approval' in data:
            SERVER_CONFIG['require_approval'] = data['require_approval']

        return jsonify({"status": "updated"})

    return jsonify({
        "config": SERVER_CONFIG,
        "active_users": 1 if session.get('logged_in') else 0,
        "pending_count": len([r for r in DOWNLOAD_REQUESTS.values() if r['status'] == 'pending'])
    })

@admin_app.route('/admin/api/browse', methods=['GET'])
def admin_api_browse():
    """
    Invokes the OS native directory picker dialog on the server machine.
    Uses Tkinter as a hidden window to spawn the dialog.
    """
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        path = filedialog.askdirectory(initialdir=SERVER_CONFIG['folder_path'], title="Select Shared Folder")
        root.destroy()
        return jsonify({"path": path if path else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_app.route('/admin/api/logout_all', methods=['POST'])
def admin_api_logout_all():
    """
    Invalidates all client sessions by rotating the global session token.
    """
    SERVER_CONFIG['session_token'] = str(uuid.uuid4())
    return jsonify({"success": True})

@admin_app.route('/admin/api/requests')
def admin_api_requests():
    """
    Returns the list of pending download requests for the Admin UI table.
    """
    pending = {k: v for k, v in DOWNLOAD_REQUESTS.items() if v['status'] == 'pending'}
    return jsonify(pending)

@admin_app.route('/admin/api/decision', methods=['POST'])
def admin_api_decision():
    """
    Applies the admin's decision (Approve/Reject) to a request.
    """
    data = request.json
    req_id = data.get('req_id')
    decision = data.get('decision')

    if req_id in DOWNLOAD_REQUESTS:
        DOWNLOAD_REQUESTS[req_id]['status'] = decision
        return jsonify({"success": True})
    return jsonify({"error": "Request not found"}), 404


# ==========================================
# RUNNER
# ==========================================

def open_browser():
    """
    Utility to open the Admin Dashboard in the default web browser
    after a short delay to ensure the server is up.
    """
    time.sleep(1)
    admin_url = f"http://127.0.0.1:{ADMIN_PORT}/admin"
    print(f"\n[INFO] Admin Panel started at: {admin_url}")
    print(f"[INFO] Client Server running on port 5000\n")
    webbrowser.open(admin_url)

def run_client():
    """Starts the client-facing server thread."""
    client_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def run_admin():
    """Starts the admin-facing server thread."""
    admin_app.run(host='127.0.0.1', port=ADMIN_PORT, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Start the browser launcher
    threading.Thread(target=open_browser).start()

    # Start the Client App in a background daemon thread
    client_thread = threading.Thread(target=run_client)
    client_thread.daemon = True
    client_thread.start()

    # Run the Admin App in the main thread (blocking)
    run_admin()
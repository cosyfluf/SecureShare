import os
import uuid
import time
import socket
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify

# ==========================================
# CONFIGURATION & SHARED STATE
# ==========================================

# Define absolute paths to ensure resources are found regardless of execution context
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

# Global Server Configuration Dictionary
# This acts as shared memory between the Admin and Client interfaces.
SERVER_CONFIG = {
    "folder_path": os.getcwd(),          # The directory currently being shared
    "password": "admin",                 # Password required for client access
    "is_running": True,                  # Master switch for client access
    "is_paused": False,                  # Toggles UI blur and blocks downloads
    "require_approval": False,           # Determines if downloads need admin intervention
    "session_token": str(uuid.uuid4()),  # Unique token to validate active sessions
    "config_id": str(uuid.uuid4())       # ID that updates when the root folder changes
}

# In-memory storage for active download requests
# Structure: { uuid: { 'file': name, 'filepath': relative_path, 'status': 'pending'|'approved', 'timestamp': float } }
DOWNLOAD_REQUESTS = {}

# ==========================================
# INITIALIZE FLASK APPS
# ==========================================

# 1. Client App (Public Interface)
# Serves the user-facing file browser on 0.0.0.0
client_app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
client_app.secret_key = os.urandom(24)

# 2. Admin App (Localhost Only)
# Serves the control panel on 127.0.0.1
admin_app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
admin_app.secret_key = os.urandom(24)

# Determine a random free port for the Admin Panel to avoid conflicts
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('127.0.0.1', 0)) # Binding to port 0 assigns an available ephemeral port
ADMIN_PORT = sock.getsockname()[1]
sock.close()


# ==========================================
# CLIENT APP ROUTES (Public Port 5000)
# ==========================================

def login_required(f):
    """
    Decorator to ensure the client is authenticated via session.

    Validates:
    1. If the server is in 'running' state.
    2. If the user has a logged_in session.
    3. If the session token matches the current server token.

    If any condition fails, the session is cleared and the user is redirected to login.
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
    """Redirects the root URL to the login page."""
    return redirect(url_for('client_login'))

@client_app.route('/login', methods=['GET', 'POST'])
def client_login():
    """
    Handles the client authentication process.
    Displays error messages if the server is offline or credentials are invalid.
    """
    if request.args.get('reason') == 'logout':
        flash('You have been logged out by the administrator.')

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
    """Clears the user session and redirects to the login screen."""
    session.clear()
    return redirect(url_for('client_login'))

@client_app.route('/files')
@login_required
def client_files():
    """
    Renders the file browser interface.

    Handles directory navigation via the 'path' query parameter.
    Prevents directory traversal attacks using os.path.commonpath.
    """
    root = SERVER_CONFIG["folder_path"]
    req_path = request.args.get('path', '')
    abs_path = os.path.join(root, req_path)

    # Security check: Ensure the requested path is within the shared root folder
    try:
        if os.path.commonpath([root, abs_path]) != os.path.normpath(root):
            return "Invalid Path", 403
    except Exception:
        return "Invalid Path", 403

    # If the directory doesn't exist (e.g., admin changed root), redirect to base
    if not os.path.exists(abs_path):
        return redirect(url_for('client_files'))

    files_list = []
    folders_list = []

    try:
        for item in os.listdir(abs_path):
            full = os.path.join(abs_path, item)
            rel = os.path.join(req_path, item).replace("\\", "/")

            if os.path.isdir(full):
                folders_list.append({'name': item, 'path': rel})
            else:
                size = round(os.path.getsize(full) / (1024 * 1024), 2)
                files_list.append({'name': item, 'size': size, 'path': rel})
    except Exception as e:
        return f"Error reading directory: {e}", 500

    parent = os.path.dirname(req_path) if req_path else None

    return render_template('client/files.html',
                           files=files_list,
                           folders=folders_list,
                           current_path=req_path,
                           parent=parent)

# --- Client API ---

@client_app.route('/api/client/status')
def client_status():
    """
    API endpoint polled by the client JS.

    Returns:
        paused: Boolean indicating if UI should be blurred.
        running: Boolean indicating if the server is accepting connections.
        force_logout: Boolean indicating if the session token is invalid.
        config_id: String hash used to detect if the shared folder has changed.
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
    Initiates a file download sequence.

    If 'Require Approval' is enabled, creates a pending request and returns an ID.
    If disabled, returns a direct download link immediately.
    """
    data = request.json
    filename = data.get('filename')
    rel_path = data.get('path') # The relative path from the shared root to the file

    # Fallback: If no specific path is provided, assume root level
    if not rel_path:
        rel_path = filename

    # verify file existence
    full_path = os.path.join(SERVER_CONFIG["folder_path"], rel_path)

    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404

    # Normalize path for URL compatibility
    file_rel_path = rel_path.replace("\\", "/")

    # Check if admin approval is required
    if not SERVER_CONFIG["require_approval"]:
        return jsonify({
            "status": "approved",
            "direct_link": url_for('download_content', filepath=file_rel_path)
        })

    # Create pending request
    req_id = str(uuid.uuid4())
    DOWNLOAD_REQUESTS[req_id] = {
        'file': filename,
        'filepath': file_rel_path,
        'status': 'pending',
        'timestamp': time.time()
    }
    return jsonify({"status": "pending", "req_id": req_id})

@client_app.route('/api/client/check_request/<req_id>')
@login_required
def check_request(req_id):
    """
    Checks the status of a specific download request.
    Called repeatedly by the client while waiting for approval.
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
    Serves the actual file content to the client.
    Final validation of token and pause state is performed here.
    """
    filepath = request.args.get('filepath')
    token = request.args.get('token')

    if SERVER_CONFIG["is_paused"]:
        return "Server Paused", 403

    if SERVER_CONFIG["require_approval"]:
        # Validate that the token exists and was approved
        if not token or token not in DOWNLOAD_REQUESTS or DOWNLOAD_REQUESTS[token]['status'] != 'approved':
            return "Access Denied / Not Approved", 403

        # Cleanup request token
        if token in DOWNLOAD_REQUESTS:
            del DOWNLOAD_REQUESTS[token]

    # Serve the file
    full_path = os.path.join(SERVER_CONFIG["folder_path"], filepath)
    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)

    return send_from_directory(directory, filename, as_attachment=True)


# ==========================================
# ADMIN APP ROUTES (Localhost Random Port)
# ==========================================

@admin_app.route('/')
def admin_root():
    """Redirects root to the admin dashboard."""
    return redirect('/admin')

@admin_app.route('/admin')
def admin_dashboard():
    """Renders the Admin Control Panel."""
    return render_template('server/index.html', config=SERVER_CONFIG)

@admin_app.route('/admin/api/status', methods=['GET', 'POST'])
def admin_api_status():
    """
    GET: Returns current server configuration and statistics.
    POST: Updates server configuration (toggles, passwords, paths).
    """
    if request.method == 'POST':
        data = request.json
        if 'password' in data:
            SERVER_CONFIG['password'] = data['password']
        if 'folder_path' in data:
            if os.path.exists(data['folder_path']):
                SERVER_CONFIG['folder_path'] = data['folder_path']
                # Trigger a config update ID to force clients to refresh
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
    Opens a native OS directory selection dialog on the server machine.
    Uses Tkinter to render the dialog.
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
    Rotates the session token, invalidating all currently active client sessions.
    """
    SERVER_CONFIG['session_token'] = str(uuid.uuid4())
    return jsonify({"success": True})

@admin_app.route('/admin/api/requests')
def admin_api_requests():
    """Returns a list of all pending download requests."""
    pending = {k: v for k, v in DOWNLOAD_REQUESTS.items() if v['status'] == 'pending'}
    return jsonify(pending)

@admin_app.route('/admin/api/decision', methods=['POST'])
def admin_api_decision():
    """
    Processes the admin's decision (Approve/Reject) for a specific request ID.
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
    """Waits briefly and then opens the Admin Dashboard in the default web browser."""
    time.sleep(1)
    admin_url = f"http://127.0.0.1:{ADMIN_PORT}/admin"
    print(f"\n[INFO] Admin Panel started at: {admin_url}")
    print(f"[INFO] Client Server running on port 5000\n")
    webbrowser.open(admin_url)

def run_client():
    """Starts the public-facing Flask app on all interfaces."""
    client_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def run_admin():
    """Starts the local-only Admin Flask app."""
    admin_app.run(host='127.0.0.1', port=ADMIN_PORT, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Start browser automation thread
    threading.Thread(target=open_browser).start()

    # Run the Client App in a separate daemon thread so it runs concurrently
    client_thread = threading.Thread(target=run_client)
    client_thread.daemon = True
    client_thread.start()

    # Run the Admin App in the main thread
    run_admin()
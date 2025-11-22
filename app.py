import os
import uuid
import time
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify

# Initialize Flask with specific template folder structure
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.urandom(24)

# Global Server Configuration and State
SERVER_CONFIG = {
    "folder_path": os.getcwd(),  # Default to current working directory
    "password": "admin",         # Default access password
    "is_running": True,          # Controls client login ability
    "is_paused": False,          # Controls visibility of client content
    "require_approval": False,   # Controls if admin must approve downloads
    "session_token": str(uuid.uuid4()), # Unique token to validate active sessions
    "config_id": str(uuid.uuid4())      # Unique ID that changes when the root folder changes
}

# In-memory storage for download requests
DOWNLOAD_REQUESTS = {}


def login_required(f):
    """
    Decorator to ensure the client is authenticated via session.
    Validates the session token against the server's current token.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in') or session.get('token') != SERVER_CONFIG['session_token']:
            session.clear()
            return redirect(url_for('client_login'))
        return f(*args, **kwargs)
    return decorated_function


# ==========================================
# ADMIN ROUTES
# ==========================================

@app.route('/admin')
def admin_dashboard():
    """
    Renders the main Admin Dashboard template.
    """
    return render_template('server/index.html', config=SERVER_CONFIG)


@app.route('/admin/api/status', methods=['GET', 'POST'])
def admin_api_status():
    """
    API Endpoint for Server Status.
    GET: Returns config and stats.
    POST: Updates config.
    """
    if request.method == 'POST':
        data = request.json
        if 'password' in data:
            SERVER_CONFIG['password'] = data['password']
        if 'folder_path' in data:
            if os.path.exists(data['folder_path']):
                SERVER_CONFIG['folder_path'] = data['folder_path']
                # Update config_id to signal clients that the root folder has changed
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


@app.route('/admin/api/browse', methods=['GET'])
def admin_api_browse():
    """
    Opens a server-side OS dialog to select a folder using tkinter.
    """
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        path = filedialog.askdirectory(initialdir=SERVER_CONFIG['folder_path'], title="Select Shared Folder")
        root.destroy()

        if path:
            return jsonify({"path": path})
        else:
            return jsonify({"path": None})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/api/logout_all', methods=['POST'])
def admin_api_logout_all():
    """
    Regenerates the global session token.
    This action invalidates all existing client sessions immediately.
    """
    SERVER_CONFIG['session_token'] = str(uuid.uuid4())
    return jsonify({"success": True, "message": "All clients have been logged out."})


@app.route('/admin/api/requests')
def admin_api_requests():
    """
    API Endpoint to fetch all pending download requests.
    """
    pending = {k: v for k, v in DOWNLOAD_REQUESTS.items() if v['status'] == 'pending'}
    return jsonify(pending)


@app.route('/admin/api/decision', methods=['POST'])
def admin_api_decision():
    """
    API Endpoint to process Admin decisions on downloads.
    """
    data = request.json
    req_id = data.get('req_id')
    decision = data.get('decision')

    if req_id in DOWNLOAD_REQUESTS:
        DOWNLOAD_REQUESTS[req_id]['status'] = decision
        return jsonify({"success": True})

    return jsonify({"error": "Request not found"}), 404


# ==========================================
# CLIENT ROUTES
# ==========================================

@app.route('/')
def index():
    """Redirects root URL to client login."""
    return redirect(url_for('client_login'))


@app.route('/login', methods=['GET', 'POST'])
def client_login():
    """
    Handles Client Authentication.
    Checks for forced logout flags to display feedback messages.
    """
    # Handle feedback from forced logout redirection
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


@app.route('/logout')
def client_logout():
    """Clears the session and redirects to login."""
    session.clear()
    return redirect(url_for('client_login'))


@app.route('/files')
@login_required
def client_files():
    """
    Renders the File Browser.
    """
    root = SERVER_CONFIG["folder_path"]
    req_path = request.args.get('path', '')
    abs_path = os.path.join(root, req_path)

    try:
        if os.path.commonpath([root, abs_path]) != os.path.normpath(root):
            return "Invalid Path", 403
    except Exception:
        return "Invalid Path", 403

    if not os.path.exists(abs_path):
        # If the path doesn't exist (e.g., after root folder change), redirect to root
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


# ==========================================
# CLIENT API (AJAX)
# ==========================================

@app.route('/api/client/status')
def client_status():
    """
    API used by client.js to poll status.
    Returns 'force_logout' = True if the session token is invalid/expired.
    Returns 'config_id' to detect if the admin has changed the root folder.
    """
    # Check if the token in the user's cookie matches the current server token
    token_valid = session.get('token') == SERVER_CONFIG['session_token']
    is_logged_in = session.get('logged_in')

    # If logged in but token is wrong, they were kicked
    force_logout = is_logged_in and not token_valid

    return jsonify({
        "paused": SERVER_CONFIG["is_paused"],
        "running": SERVER_CONFIG["is_running"],
        "force_logout": force_logout,
        "config_id": SERVER_CONFIG["config_id"]
    })


@app.route('/api/client/request_download', methods=['POST'])
@login_required
def request_download():
    """
    Initiates a download request.
    Returns the Request ID (req_id) which acts as the transaction identifier.
    """
    filename = request.json.get('filename')
    full_path = os.path.join(SERVER_CONFIG["folder_path"], filename)

    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404

    if not SERVER_CONFIG["require_approval"]:
        return jsonify({
            "status": "approved",
            "direct_link": url_for('download_content', filename=filename)
        })

    req_id = str(uuid.uuid4())
    DOWNLOAD_REQUESTS[req_id] = {
        'file': filename,
        'status': 'pending',
        'timestamp': time.time()
    }
    return jsonify({"status": "pending", "req_id": req_id})


@app.route('/api/client/check_request/<req_id>')
@login_required
def check_request(req_id):
    """
    Polled by client.js to check approval status.
    """
    if req_id not in DOWNLOAD_REQUESTS:
        return jsonify({"status": "error"})

    req = DOWNLOAD_REQUESTS[req_id]
    response = {"status": req['status']}

    if req['status'] == 'approved':
        response['link'] = url_for('download_content', filename=req['file'], token=req_id)

    return jsonify(response)


@app.route('/download_final')
@login_required
def download_content():
    """
    Serves the actual file if valid.
    """
    filename = request.args.get('filename')
    token = request.args.get('token')

    if SERVER_CONFIG["is_paused"]:
        return "Server Paused", 403

    if SERVER_CONFIG["require_approval"]:
        if not token or token not in DOWNLOAD_REQUESTS or DOWNLOAD_REQUESTS[token]['status'] != 'approved':
            return "Access Denied / Not Approved", 403
        del DOWNLOAD_REQUESTS[token]

    return send_from_directory(SERVER_CONFIG["folder_path"], filename, as_attachment=True)


def open_browser():
    """Opens the Admin Interface in the default browser on startup."""
    time.sleep(1)
    webbrowser.open("http://localhost:5000/admin")


if __name__ == "__main__":
    threading.Thread(target=open_browser).start()
    app.run(host='0.0.0.0', port=5000, debug=False)
import os
import uuid
import tkinter as tk
from tkinter import filedialog
from flask import Flask, render_template, request, redirect, jsonify, session
from config import SERVER_CONFIG, DOWNLOAD_REQUESTS, TEMPLATE_DIR, STATIC_DIR

admin_app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
admin_app.secret_key = os.urandom(24)

@admin_app.route('/')
def admin_root():
    return redirect('/admin')

@admin_app.route('/admin')
def admin_dashboard():
    return render_template('server/index.html', config=SERVER_CONFIG)

@admin_app.route('/admin/api/status', methods=['GET', 'POST'])
def admin_api_status():
    if request.method == 'POST':
        data = request.json
        for key in ['password', 'is_running', 'is_paused', 'require_approval']:
            if key in data: SERVER_CONFIG[key] = data[key]
        if 'folder_path' in data and os.path.exists(data['folder_path']):
            SERVER_CONFIG['folder_path'] = data['folder_path']
            SERVER_CONFIG['config_id'] = str(uuid.uuid4())
        return jsonify({"status": "updated"})
    
    return jsonify({
        "config": SERVER_CONFIG,
        "pending_count": len([r for r in DOWNLOAD_REQUESTS.values() if r['status'] == 'pending'])
    })

@admin_app.route('/admin/api/browse')
def admin_api_browse():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    path = filedialog.askdirectory(initialdir=SERVER_CONFIG['folder_path'])
    root.destroy()
    return jsonify({"path": path if path else None})

# ... (Hier die restlichen Admin-API-Routen wie logout_all, requests, decision einfügen)

import os
import threading
import socket
import customtkinter as ctk
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
from functools import wraps

# Configuration regarding the Flask application
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Key for session management

# Global variables to store the state of the server
SERVER_CONFIG = {
    "folder_path": None,
    "password": None,
    "is_running": False
}

def login_required(f):
    """
    Decorator to ensure that the user is logged in before accessing a route.
    Checks if 'logged_in' is present in the session.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
def login():
    """
    Handle the login page logic.
    """
    if request.method == 'POST':
        password_input = request.form.get('password')
        if password_input == SERVER_CONFIG["password"]:
            session['logged_in'] = True
            return redirect(url_for('list_files'))
        else:
            flash('Invalid Password')
    return render_template('login.html')

@app.route('/files')
@login_required
def list_files():
    """
    Lists files AND subdirectories.
    Uses a query parameter '?path=' to navigate subfolders.
    """
    root_folder = SERVER_CONFIG["folder_path"]
    if not root_folder or not os.path.exists(root_folder):
        return "Server not configured correctly or folder missing.", 500

    # Get the requested relative path from the URL (default is empty string = root)
    req_path = request.args.get('path', '')

    # Security: Construct absolute path
    abs_path = os.path.join(root_folder, req_path)

    # Security: Prevent Path Traversal (ensure we are still inside the root_folder)
    # commonpath throws an error if paths are on different drives, handle safely
    try:
        if os.path.commonpath([root_folder, abs_path]) != os.path.normpath(root_folder):
            return "Access Denied: Invalid Path", 403
    except ValueError:
        return "Access Denied: Invalid Path", 403

    if not os.path.exists(abs_path):
        return "Directory not found", 404

    files_list = []
    folders_list = []

    try:
        # Iterate over the directory content
        for item_name in os.listdir(abs_path):
            full_item_path = os.path.join(abs_path, item_name)

            # Calculate relative path for links (e.g., "subfolder/image.png")
            # We use replace to ensure forward slashes for URLs even on Windows
            rel_path = os.path.join(req_path, item_name).replace("\\", "/")

            if os.path.isdir(full_item_path):
                folders_list.append({
                    'name': item_name,
                    'rel_path': rel_path
                })
            elif os.path.isfile(full_item_path):
                # Get file size in MB
                size_mb = round(os.path.getsize(full_item_path) / (1024 * 1024), 2)
                files_list.append({
                    'name': item_name,
                    'size': size_mb,
                    'rel_path': rel_path
                })
    except Exception as e:
        return f"Error reading directory: {str(e)}", 500

    # specific logic for "Back" button
    parent_path = None
    if req_path:
        # Remove the last segment of the path
        parent_path = os.path.dirname(req_path)

    return render_template(
        'files.html',
        files=files_list,
        folders=folders_list,
        current_path=req_path if req_path else "Root",
        parent_path=parent_path
    )

@app.route('/download/<path:filename>')
@login_required
def download_file(filename):
    """
    Serves the requested file.
    'filename' can now contain slashes (e.g. "subfolder/file.txt").
    """
    folder = SERVER_CONFIG["folder_path"]
    try:
        return send_from_directory(folder, filename, as_attachment=True)
    except FileNotFoundError:
        return "File not found!", 404

def run_flask():
    """
    Starts the Flask server on port 80.
    """
    try:
        app.run(host='0.0.0.0', port=80, debug=False, use_reloader=False)
    except PermissionError:
        print("Error: Port 80 requires administrative privileges.")
    except Exception as e:
        print(f"Flask Server Error: {e}")

class ServerGUI(ctk.CTk):
    """
    Main GUI Application class (unchanged).
    """
    def __init__(self):
        super().__init__()
        self.title("Secure Local File Server")
        self.geometry("500x400")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3, 4), weight=1)

        self.label_title = ctk.CTkLabel(self, text="Web File Server Configuration", font=("Roboto", 20, "bold"))
        self.label_title.grid(row=0, column=0, padx=20, pady=20)

        self.entry_password = ctk.CTkEntry(self, placeholder_text="Set Web Access Password", show="*")
        self.entry_password.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.selected_folder_label = ctk.CTkLabel(self, text="No folder selected", text_color="gray")
        self.selected_folder_label.grid(row=2, column=0, padx=20, pady=(0, 5))

        self.btn_select_folder = ctk.CTkButton(self, text="Select Folder to Share", command=self.select_folder)
        self.btn_select_folder.grid(row=3, column=0, padx=20, pady=10)

        self.btn_start = ctk.CTkButton(self, text="Start Server (Port 80)", command=self.start_server, fg_color="green")
        self.btn_start.grid(row=4, column=0, padx=20, pady=20)

        self.status_label = ctk.CTkLabel(self, text="Status: Stopped", text_color="red")
        self.status_label.grid(row=5, column=0, padx=20, pady=10)

    def select_folder(self):
        folder = ctk.filedialog.askdirectory()
        if folder:
            SERVER_CONFIG["folder_path"] = folder
            self.selected_folder_label.configure(text=f"Selected: {folder}", text_color="white")

    def start_server(self):
        password = self.entry_password.get()
        folder = SERVER_CONFIG["folder_path"]

        if not folder:
            self.status_label.configure(text="Error: Please select a folder first.", text_color="orange")
            return

        if not password:
            self.status_label.configure(text="Error: Please set a password.", text_color="orange")
            return

        if SERVER_CONFIG["is_running"]:
            self.status_label.configure(text="Server is already running.", text_color="orange")
            return

        SERVER_CONFIG["password"] = password
        SERVER_CONFIG["is_running"] = True

        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()

        self.btn_start.configure(state="disabled", text="Server Running...")
        self.entry_password.configure(state="disabled")
        self.btn_select_folder.configure(state="disabled")

        local_ip = socket.gethostbyname(socket.gethostname())
        self.status_label.configure(text=f"Running on http://{local_ip}:80", text_color="#00ff00")

if __name__ == "__main__":
    app_gui = ServerGUI()
    app_gui.mainloop()
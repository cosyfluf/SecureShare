# Secure Share 🛡️

I built Secure Share because I was tired of hitting the **10MB upload limit on Discord**.

Trying to share a quick game clip, a project zip, or a high-res image shouldn't require uploading it to Google Drive, messing with link permissions, and waiting for the upload to finish before my friends can even start downloading.

I wanted something where **I** am the server. I choose a folder, send a link, and they grab the files directly from my machine. Fast, local, and no cloud middleman.

## What is this?

Secure Share is a local file-sharing server with a dedicated Admin Panel. It gives you complete control over the connection.

*   **You are in Charge:** You host the files. The data never leaves your network until someone downloads it.
*   **Approval System:** Don't want people grabbing everything? Turn on "Require Approval." When a client clicks download, you get a popup on your dashboard to Approve or Reject it.
*   **Emergency Pause:** Need to cut access? Hit the pause switch. The client's screen blurs instantly, and downloads are blocked.
*   **Dynamic Hosting:** You can switch the shared folder on the fly without restarting the server.

## Getting Started

You only need Python. No complex setup.

### 1. Requirements
Just make sure you have Python installed.

### 2. Install
We use Flask for the web server. Install it via terminal:

```bash
pip install flask
```

### 3. Run it
Start the app:

```bash
python app.py
```

The Admin Panel will open automatically in your browser.

## How to use

### 👮 For You ( The Admin)
*   **Dashboard:** Go to `http://localhost:55322/admin`.
*   **Pick a Folder:** Use the browse button to select what you want to share.
*   **Set a Password:** Keep strangers out.
*   **Control:** Use the toggle switches to go Offline, Pause the UI, or enable Approval Mode.

### 👤 For Your Friends (The Clients)
*   Send them your local IP address (e.g., `http://192.168.1.5:5000`).
*   They log in with the password you set.
*   They browse and download. If you enabled approvals, they'll see a "Waiting for Approval" status while you decide their fate.

---

*No limits, no clouds, just files.*
/**
 * Global state for the View Mode (Grid vs List).
 */
let isGridView = true;

/**
 * Global state to track if the UI is currently paused/blurred.
 */
let pausedState = false;

/**
 * Stores the current server configuration ID.
 * If this changes (e.g., admin changes the root folder), the page reloads.
 */
let currentConfigId = null;

/**
 * Interval ID for polling download request status.
 */
let pollInterval = null;

function toggleView() {
    isGridView = !isGridView;
    const container = document.getElementById('fileContainer');
    const icon = document.getElementById('viewIcon');
    const cards = document.querySelectorAll('.file-card');

    if (isGridView) {
        container.classList.remove('flex', 'flex-col');
        container.classList.add('grid', 'grid-cols-1', 'sm:grid-cols-2', 'md:grid-cols-3', 'lg:grid-cols-4');
        icon.className = "fas fa-list-ul";

        cards.forEach(el => {
            el.classList.remove('flex-row', 'items-center', 'min-h-[60px]');
            el.classList.add('flex-col', 'min-h-[180px]');
            const iconBg = el.querySelector('.fa-file, .fa-folder').closest('.absolute');
            if(iconBg) iconBg.classList.remove('hidden');
        });
    } else {
        container.classList.remove('grid', 'grid-cols-1', 'sm:grid-cols-2', 'md:grid-cols-3', 'lg:grid-cols-4');
        container.classList.add('flex', 'flex-col');
        icon.className = "fas fa-th-large";

        cards.forEach(el => {
            el.classList.remove('flex-col', 'min-h-[180px]');
            el.classList.add('flex-row', 'items-center', 'min-h-[60px]', 'gap-4');
            const iconBg = el.querySelector('.fa-file, .fa-folder').closest('.absolute');
            if(iconBg) iconBg.classList.add('hidden');
        });
    }
}

/**
 * Polls status. Checks for force logout flag and root folder changes.
 */
function checkStatus() {
    fetch('/api/client/status')
        .then(response => response.json())
        .then(data => {
            // Handle Forced Logout by Admin
            if (data.force_logout) {
                window.location.href = '/login?reason=logout';
                return;
            }

            // Reload if server goes offline
            if (!data.running) {
                window.location.reload();
                return;
            }

            // Detect if the Admin changed the root folder
            if (currentConfigId === null) {
                currentConfigId = data.config_id;
            } else if (currentConfigId !== data.config_id) {
                // Config ID changed, redirect to base files path to refresh content
                window.location.href = '/files';
                return;
            }

            const overlay = document.getElementById('pauseOverlay');
            const mainContent = document.getElementById('main-content');

            if (data.paused && !pausedState) {
                pausedState = true;
                overlay.classList.remove('opacity-0', 'pointer-events-none');
                mainContent.classList.add('blur-sm');
            }
            else if (!data.paused && pausedState) {
                pausedState = false;
                overlay.classList.add('opacity-0', 'pointer-events-none');
                mainContent.classList.remove('blur-sm');
            }
        });
}

function initiateDownload(filename, path) {
    const modal = document.getElementById('approvalModal');
    const content = document.getElementById('approvalContent');

    modal.classList.remove('opacity-0', 'pointer-events-none');
    content.classList.remove('scale-95');
    content.classList.add('scale-100');

    document.getElementById('statusWaiting').classList.remove('hidden');
    document.getElementById('statusRejected').classList.add('hidden');
    document.getElementById('statusApproved').classList.add('hidden');

    fetch('/api/client/request_download', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({filename: filename})
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'approved') {
                closeModal();
                window.location.href = data.direct_link;
            } else if (data.status === 'pending') {
                // Display the Request ID which matches the Admin table
                document.getElementById('reqIdDisplay').innerText = "ID: " + data.req_id.substring(0, 8);
                pollRequest(data.req_id);
            }
        });
}

function pollRequest(reqId) {
    pollInterval = setInterval(() => {
        fetch('/api/client/check_request/' + reqId)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'approved') {
                    clearInterval(pollInterval);
                    showApproved();
                    setTimeout(() => {
                        window.location.href = data.link;
                        closeModal();
                    }, 1500);
                } else if (data.status === 'rejected') {
                    clearInterval(pollInterval);
                    showRejected();
                }
            });
    }, 1000);
}

function showApproved() {
    document.getElementById('statusWaiting').classList.add('hidden');
    document.getElementById('statusApproved').classList.remove('hidden');
}

function showRejected() {
    document.getElementById('statusWaiting').classList.add('hidden');
    document.getElementById('statusRejected').classList.remove('hidden');
}

function closeModal() {
    const modal = document.getElementById('approvalModal');
    const content = document.getElementById('approvalContent');

    modal.classList.add('opacity-0', 'pointer-events-none');
    content.classList.add('scale-95');
    content.classList.remove('scale-100');

    if (pollInterval) clearInterval(pollInterval);
}

setInterval(checkStatus, 1000);
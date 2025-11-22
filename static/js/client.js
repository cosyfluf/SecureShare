/**
 * Global state for the View Mode (Grid vs List).
 * True indicates Grid View, False indicates List View.
 */
let isGridView = true;

/**
 * Global state to track if the UI is currently paused/blurred.
 */
let pausedState = false;

/**
 * Stores the current server configuration ID to detect folder changes.
 */
let currentConfigId = null;

/**
 * Stores the current active download request ID.
 * Used for polling and cancellation.
 */
let currentReqId = null;

/**
 * Interval ID for polling the status of a specific download request.
 */
let pollInterval = null;

/**
 * Initialization function to restore the user's view preference (Grid/List)
 * from LocalStorage on page load.
 */
function loadViewPreference() {
    const savedMode = localStorage.getItem('viewMode');
    if (savedMode === 'list') {
        toggleView(true);
    }
}

/**
 * Toggles the file browser layout between Grid and List view.
 *
 * Grid View: Vertical cards, large icons.
 * List View: Fixed height rows, horizontal layout, right-aligned buttons.
 *
 * @param {boolean} forceList - If true, force the view to List mode regardless of current state.
 */
function toggleView(forceList = false) {
    if (forceList) {
        isGridView = false;
    } else {
        isGridView = !isGridView;
    }

    // Save preference to LocalStorage
    localStorage.setItem('viewMode', isGridView ? 'grid' : 'list');

    const container = document.getElementById('fileContainer');
    const icon = document.getElementById('viewIcon');
    const cards = document.querySelectorAll('.file-card');

    if (isGridView) {
        // ============================
        // ENABLE GRID VIEW
        // ============================
        container.classList.remove('flex', 'flex-col', 'gap-3');
        container.classList.add('grid', 'grid-cols-1', 'sm:grid-cols-2', 'md:grid-cols-3', 'lg:grid-cols-4', 'gap-4');
        icon.className = "fas fa-list-ul";

        cards.forEach(el => {
            // Restore Card Container for Grid
            el.classList.remove('flex-row', 'items-center', 'h-20', 'px-5', 'py-0', 'w-full');
            el.classList.add('flex-col', 'justify-between', 'min-h-[180px]', 'p-4');

            // Show Background Decorations
            const bgIcon = el.querySelector('.bg-icon');
            if (bgIcon) bgIcon.classList.remove('hidden');

            // Restore Inner Wrapper (Vertical Stack)
            const innerWrapper = el.querySelector('.inner-wrapper');
            if (innerWrapper) {
                innerWrapper.classList.remove('flex-row', 'items-center');
                innerWrapper.classList.add('flex-col');
            }

            // Restore Icon Size (Large)
            const iconWrapper = el.querySelector('.icon-wrapper');
            if (iconWrapper) {
                iconWrapper.classList.remove('w-10', 'h-10', 'mb-0');
                iconWrapper.classList.add('w-12', 'h-12', 'mb-3');
            }

            // Restore Text Alignment (Left, but constrained width)
            const textContent = el.querySelector('.text-content');
            if (textContent) {
                textContent.classList.remove('ml-4', 'flex-1', 'flex', 'flex-col', 'justify-center');
                // Allow line clamping in grid
                const title = textContent.querySelector('h3');
                if (title) {
                    title.classList.remove('truncate');
                    title.classList.add('line-clamp-2', 'break-all');
                }
            }

            // Restore Button Position (Bottom)
            const btnWrapper = el.querySelector('.action-btn-wrapper');
            if (btnWrapper) {
                btnWrapper.classList.remove('w-auto', 'ml-auto', 'pt-0', 'mt-0');
                btnWrapper.classList.add('w-full', 'pt-4', 'mt-auto');

                const btn = btnWrapper.querySelector('button');
                if(btn) btn.classList.remove('px-6', 'py-2');
                if(btn) btn.classList.add('w-full', 'py-2.5');

                const btnText = btnWrapper.querySelector('.btn-text');
                if(btnText) btnText.classList.remove('hidden', 'sm:inline');
            }
        });

    } else {
        // ============================
        // ENABLE LIST VIEW
        // ============================
        container.classList.remove('grid', 'grid-cols-1', 'sm:grid-cols-2', 'md:grid-cols-3', 'lg:grid-cols-4', 'gap-4');
        container.classList.add('flex', 'flex-col', 'gap-3');
        icon.className = "fas fa-th-large";

        cards.forEach(el => {
            // Apply Row Styling (Fixed Height h-20)
            el.classList.remove('flex-col', 'justify-between', 'min-h-[180px]', 'p-4');
            el.classList.add('flex-row', 'items-center', 'h-20', 'px-5', 'py-0', 'w-full');

            // Hide Background Decorations
            const bgIcon = el.querySelector('.bg-icon');
            if (bgIcon) bgIcon.classList.add('hidden');

            // Set Inner Wrapper to Row
            const innerWrapper = el.querySelector('.inner-wrapper');
            if (innerWrapper) {
                innerWrapper.classList.remove('flex-col');
                innerWrapper.classList.add('flex-row', 'items-center');
            }

            // Shrink Icon Size
            const iconWrapper = el.querySelector('.icon-wrapper');
            if (iconWrapper) {
                iconWrapper.classList.remove('w-12', 'h-12', 'mb-3');
                iconWrapper.classList.add('w-10', 'h-10', 'mb-0');
            }

            // Align Text (Left, Middle)
            const textContent = el.querySelector('.text-content');
            if (textContent) {
                textContent.classList.add('ml-4', 'flex-1', 'flex', 'flex-col', 'justify-center');
                // Ensure text truncates nicely in list view instead of breaking
                const title = textContent.querySelector('h3');
                if (title) {
                    title.classList.remove('line-clamp-2', 'break-all');
                    title.classList.add('truncate');
                }
            }

            // Move Button to Right Side
            const btnWrapper = el.querySelector('.action-btn-wrapper');
            if (btnWrapper) {
                btnWrapper.classList.remove('w-full', 'pt-4', 'mt-auto');
                btnWrapper.classList.add('w-auto', 'ml-auto', 'pt-0', 'mt-0');

                const btn = btnWrapper.querySelector('button');
                if(btn) btn.classList.remove('w-full', 'py-2.5');
                if(btn) btn.classList.add('px-6', 'py-2');

                // Optional: Hide text on very small screens in list view if needed
                const btnText = btnWrapper.querySelector('.btn-text');
                if(btnText) btnText.classList.add('hidden', 'sm:inline');
            }
        });
    }
}

/**
 * Periodically polls the server status endpoint.
 */
function checkStatus() {
    fetch('/api/client/status')
        .then(response => response.json())
        .then(data => {
            if (data.force_logout) {
                window.location.href = '/login?reason=logout';
                return;
            }

            if (!data.running) {
                window.location.href = '/logout';
                return;
            }

            if (currentConfigId === null) {
                currentConfigId = data.config_id;
            } else if (currentConfigId !== data.config_id) {
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

/**
 * Initiates the download process.
 */
function initiateDownload(filename, path) {
    const modal = document.getElementById('approvalModal');
    const content = document.getElementById('approvalContent');

    modal.classList.remove('opacity-0', 'pointer-events-none');
    content.classList.remove('scale-95');
    content.classList.add('scale-100');

    document.getElementById('statusWaiting').classList.remove('hidden');
    document.getElementById('statusRejected').classList.add('hidden');
    document.getElementById('statusApproved').classList.add('hidden');
    document.getElementById('reqIdDisplay').innerText = "ID: ...";

    currentReqId = null;

    fetch('/api/client/request_download', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({filename: filename, path: path})
    })
        .then(response => {
            if (!response.ok) throw new Error("File not found or server error");
            return response.json();
        })
        .then(data => {
            if (data.status === 'approved') {
                closeModal();
                window.location.href = data.direct_link;
            } else if (data.status === 'pending') {
                currentReqId = data.req_id;
                document.getElementById('reqIdDisplay').innerText = "ID: " + data.req_id.substring(0, 8);
                pollRequest(data.req_id);
            }
        })
        .catch(err => {
            console.error("Download Request Failed:", err);
            closeModal();
            alert("Could not request file. The shared folder might have changed.");
            window.location.reload();
        });
}

/**
 * Cancels the current download request.
 */
function cancelDownload() {
    if (currentReqId) {
        fetch('/api/client/cancel_request', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({req_id: currentReqId})
        }).catch(e => console.error(e));
    }
    closeModal();
}

/**
 * Polls the specific request ID.
 */
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
    currentReqId = null;
}

// Initialize View Preference
loadViewPreference();

// Start polling
setInterval(checkStatus, 1000);
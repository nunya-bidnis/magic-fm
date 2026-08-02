/**
 * Magic.fm - Listener Track Requests
 *
 * The request box only appears when autoplay is actually active (no DJ live and
 * nothing scheduled). Showing it during a live set would imply listeners can
 * influence what the DJ plays, which is not true and would generate confusion.
 *
 * SECURITY
 * Every value rendered here - track titles, artist names, and especially the
 * requester nickname - is attacker-controlled. Anyone can submit a request with
 * any name. All output goes through textContent, never innerHTML with raw values.
 */

const REQ_POLL_INTERVAL = 15000;
let reqSearchTimer = null;

/** Escape untrusted text for safe insertion into markup. */
function reqEsc(text) {
    const d = document.createElement('div');
    d.textContent = text == null ? '' : text;
    return d.innerHTML;
}

function reqShow(id, msg) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 4000);
}

/**
 * Show or hide the request UI based on whether autoplay is running.
 */
async function refreshRequestVisibility() {
    const section = document.getElementById('request-section');
    if (!section) return;

    try {
        const res = await fetch('/api/autoplay/status', { cache: 'no-store' });
        if (!res.ok) { section.style.display = 'none'; return; }

        const s = await res.json();

        // Hide entirely if there is no library - an empty search box looks broken.
        if (s.autoplay_active && s.library_total > 0) {
            if (section.style.display === 'none') {
                section.style.display = 'block';
                searchTracks('');
                loadPublicQueue();
            }
        } else {
            section.style.display = 'none';
        }
    } catch {
        section.style.display = 'none';
    }
}

/**
 * Search the library.
 */
async function searchTracks(query) {
    const results = document.getElementById('search-results');
    if (!results) return;

    try {
        const res = await fetch(`/api/autoplay/search?q=${encodeURIComponent(query)}&limit=12`);
        if (!res.ok) throw new Error();

        const tracks = await res.json();

        if (!tracks.length) {
            results.innerHTML = '<p class="loading">Nothing found. Try another search.</p>';
            return;
        }

        results.innerHTML = tracks.map(t => `
            <div class="schedule-item">
                <h4>${reqEsc(t.title)}</h4>
                <div class="time">${reqEsc(t.artist || 'Unknown artist')}</div>
                <button class="control-btn js-request-btn"
                        data-library-id="${t.library_id}"
                        style="width:100%; margin-top:10px; font-size:0.9rem;">
                    Request
                </button>
            </div>
        `).join('');

        // Listeners attached programmatically rather than via inline onclick, so
        // no track data is ever interpolated into an executable attribute.
        results.querySelectorAll('.js-request-btn').forEach(btn => {
            btn.addEventListener('click', () => requestTrack(btn.dataset.libraryId));
        });

    } catch {
        results.innerHTML = '<p class="loading">Search unavailable.</p>';
    }
}

/**
 * Submit a request.
 */
async function requestTrack(libraryId) {
    const nameEl = document.getElementById('req-name');
    const name = nameEl ? nameEl.value.trim() : '';

    try {
        const res = await fetch('/api/autoplay/request', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                library_id: parseInt(libraryId, 10),
                requested_by: name
            })
        });

        const data = await res.json();

        if (!res.ok) {
            reqShow('request-err', data.detail || 'Could not add that request.');
            return;
        }

        reqShow('request-msg', `Queued: ${data.artist ? data.artist + ' - ' : ''}${data.title} (#${data.position})`);
        loadPublicQueue();

    } catch {
        reqShow('request-err', 'Could not add that request.');
    }
}

/**
 * Load the public queue.
 */
async function loadPublicQueue() {
    const el = document.getElementById('public-queue');
    if (!el) return;

    try {
        const res = await fetch('/api/autoplay/queue?limit=15', { cache: 'no-store' });
        if (!res.ok) throw new Error();

        const queue = await res.json();

        if (!queue.length) {
            el.innerHTML = '<p class="loading">Queue is empty — be the first.</p>';
            return;
        }

        el.innerHTML = queue.map((item, i) => `
            <div class="schedule-item">
                <h4>${i + 1}. ${reqEsc(item.title)}</h4>
                <div class="time">${reqEsc(item.artist || 'Unknown artist')}</div>
                <div class="dj">Requested by ${reqEsc(item.requested_by)}</div>
            </div>
        `).join('');

    } catch {
        el.innerHTML = '<p class="loading">Queue unavailable.</p>';
    }
}

/**
 * Wire up search and polling.
 */
function initRequests() {
    const search = document.getElementById('req-search');
    if (search) {
        // Debounced so typing does not fire a request per keystroke.
        search.addEventListener('input', (e) => {
            clearTimeout(reqSearchTimer);
            const q = e.target.value;
            reqSearchTimer = setTimeout(() => searchTracks(q), 300);
        });
    }

    refreshRequestVisibility();
    setInterval(refreshRequestVisibility, REQ_POLL_INTERVAL);
    setInterval(() => {
        const section = document.getElementById('request-section');
        if (section && section.style.display !== 'none') loadPublicQueue();
    }, REQ_POLL_INTERVAL);
}

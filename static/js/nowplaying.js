/**
 * Now Playing ticker poller.
 * Not part of the uploaded artifacts - stubbed to match the DJ-facing
 * preview logic in dj-nowplaying.html (textContent only, never innerHTML).
 */
const NP_IDLE = document.getElementById('np-idle');
const NP_CONTENT = document.getElementById('np-content');
const NP_TRACK = document.getElementById('np-track');
const NP_ARTIST = document.getElementById('np-artist');
const NP_DJ = document.getElementById('np-dj');
const NP_ART = document.getElementById('np-art');

let lastTrackKey = null;

function initNowPlaying() {
    fetchNowPlaying();
    setInterval(fetchNowPlaying, 10000);
}

async function fetchNowPlaying() {
    try {
        const res = await fetch('/api/nowplaying', { cache: 'no-store' });
        const data = await res.json();

        if (!data.is_live || !data.track) {
            showIdle();
            return;
        }

        const key = `${data.track}|${data.artist || ''}|${data.dj || ''}`;

        NP_TRACK.textContent = data.track;
        NP_ARTIST.textContent = data.artist || '';
        NP_DJ.textContent = data.dj || '';

        if (data.art_url) {
            NP_ART.src = data.art_url;
            NP_ART.style.display = 'block';
        } else {
            NP_ART.style.display = 'none';
        }

        NP_IDLE.style.display = 'none';
        NP_CONTENT.style.display = 'flex';

        if (key !== lastTrackKey && lastTrackKey !== null) {
            NP_CONTENT.classList.remove('np-flash');
            void NP_CONTENT.offsetWidth;
            NP_CONTENT.classList.add('np-flash');
        }
        lastTrackKey = key;
    } catch {
        showIdle();
    }
}

function showIdle() {
    NP_IDLE.style.display = 'block';
    NP_CONTENT.style.display = 'none';
    lastTrackKey = null;
}

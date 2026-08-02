/**
 * Magic.fm - DASH Player Module
 * Handles stream playback with dash.js
 */

let dashPlayer = null;
const VIDEO_ELEMENT = document.getElementById('video-player');
const PLAY_BTN = document.getElementById('play-btn');
const MUTE_BTN = document.getElementById('mute-btn');
const VOLUME_SLIDER = document.getElementById('volume');
const STREAM_STATUS = document.getElementById('stream-status');
const NOW_PLAYING = document.getElementById('now-playing');
const STREAM_DETAILS = document.getElementById('stream-details');

const DASH_MANIFEST_URL = '/api/stream/dash/manifest.mpd';
const STATUS_CHECK_INTERVAL = 5000; // Check every 5 seconds

/**
 * Initialize DASH player with error handling
 */
function initializePlayer() {
    if (!dashjs.MediaPlayer) {
        console.error('dash.js library not loaded');
        return;
    }

    dashPlayer = dashjs.MediaPlayer().create();
    dashPlayer.initialize(VIDEO_ELEMENT, DASH_MANIFEST_URL, false);

    // Configure player
    dashPlayer.updateSettings({
        streaming: {
            bufferingTimeDefault: 3,
            bufferingTimeMax: 10,
            maxBitrateForPlay: 10000000,
            maxBitrateDefault: 8000000
        }
    });

    // Event listeners
    dashPlayer.on(dashjs.MediaPlayer.events.STREAM_INITIALIZED, onStreamInitialized);
    dashPlayer.on(dashjs.MediaPlayer.events.ERROR, onPlayerError);
    dashPlayer.on(dashjs.MediaPlayer.events.QUALITY_CHANGE_REQUESTED, onQualityChange);

    VIDEO_ELEMENT.addEventListener('play', onVideoPlay);
    VIDEO_ELEMENT.addEventListener('pause', onVideoPause);
    VIDEO_ELEMENT.addEventListener('error', onVideoError);

    // Button controls
    PLAY_BTN.addEventListener('click', togglePlayPause);
    MUTE_BTN.addEventListener('click', toggleMute);
    VOLUME_SLIDER.addEventListener('input', updateVolume);

    // Check stream status
    checkStreamStatus();
    setInterval(checkStreamStatus, STATUS_CHECK_INTERVAL);
}

/**
 * Toggle play/pause
 */
function togglePlayPause() {
    if (!dashPlayer) return;

    if (VIDEO_ELEMENT.paused) {
        VIDEO_ELEMENT.play()
            .catch(err => {
                console.error('Play error:', err);
                showError('Unable to play stream');
            });
        PLAY_BTN.textContent = 'Pause';
    } else {
        VIDEO_ELEMENT.pause();
        PLAY_BTN.textContent = 'Play';
    }
}

/**
 * Toggle mute
 */
function toggleMute() {
    if (VIDEO_ELEMENT.muted) {
        VIDEO_ELEMENT.muted = false;
        MUTE_BTN.textContent = 'Mute';
    } else {
        VIDEO_ELEMENT.muted = true;
        MUTE_BTN.textContent = 'Unmute';
    }
}

/**
 * Update volume
 */
function updateVolume(e) {
    const volume = parseInt(e.target.value) / 100;
    VIDEO_ELEMENT.volume = Math.max(0, Math.min(1, volume));
}

/**
 * Check stream status from API
 */
async function checkStreamStatus() {
    try {
        const response = await fetch('/api/stream/status');

        if (response.ok) {
            const data = await response.json();
            updateStreamStatus(data);
        } else {
            // No active stream
            setStreamOffline();
        }
    } catch (error) {
        console.error('Error checking stream status:', error);
    }
}

/**
 * Update UI with stream status
 */
function updateStreamStatus(status) {
    STREAM_STATUS.textContent = '● Online';
    STREAM_STATUS.classList.remove('offline');
    STREAM_STATUS.classList.add('online');

    NOW_PLAYING.textContent = `${status.username} is live`;
    STREAM_DETAILS.textContent = `Viewers: ${status.viewers || 0}`;

    if (status.bitrate) {
        STREAM_DETAILS.textContent += ` • ${(status.bitrate / 1000).toFixed(0)} kbps`;
    }
    if (status.resolution) {
        STREAM_DETAILS.textContent += ` • ${status.resolution}`;
    }
}

/**
 * Set stream to offline
 */
function setStreamOffline() {
    STREAM_STATUS.textContent = '● Offline';
    STREAM_STATUS.classList.add('offline');
    STREAM_STATUS.classList.remove('online');
    NOW_PLAYING.textContent = 'No stream available';
    STREAM_DETAILS.textContent = '';

    if (dashPlayer && !VIDEO_ELEMENT.paused) {
        VIDEO_ELEMENT.pause();
        PLAY_BTN.textContent = 'Play';
    }
}

/**
 * DASH player event handlers
 */
function onStreamInitialized() {
    console.log('Stream initialized');
}

function onPlayerError(error) {
    console.error('Player error:', error);
    // Attempt to recover
    if (dashPlayer && error.code !== 27) { // Not a manifest update error
        setTimeout(() => {
            if (dashPlayer) {
                dashPlayer.attachView(VIDEO_ELEMENT);
            }
        }, 3000);
    }
}

function onQualityChange(data) {
    console.log('Quality changed:', data.bitrateList[data.newQualityIndex]);
}

/**
 * Video element event handlers
 */
function onVideoPlay() {
    PLAY_BTN.textContent = 'Pause';
}

function onVideoPause() {
    PLAY_BTN.textContent = 'Play';
}

function onVideoError(error) {
    console.error('Video error:', error);
    showError('Stream playback error. Try reloading the page.');
}

/**
 * Utility: Show error message
 */
function showError(message) {
    // Create temporary error display
    const errorEl = document.createElement('div');
    errorEl.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background-color: #ef4444;
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        z-index: 9999;
        max-width: 400px;
    `;
    errorEl.textContent = message;
    document.body.appendChild(errorEl);

    setTimeout(() => {
        errorEl.style.opacity = '0';
        errorEl.style.transition = 'opacity 0.3s';
        setTimeout(() => errorEl.remove(), 300);
    }, 5000);
}

/**
 * Load upcoming schedule from API
 */
async function loadSchedule() {
    try {
        const response = await fetch('/api/schedule');
        if (!response.ok) throw new Error('Failed to load schedule');

        const data = await response.json();
        displaySchedule(data);

    } catch (error) {
        console.error('Error loading schedule:', error);
        document.getElementById('schedule-list').innerHTML =
            '<p class="loading">Failed to load schedule</p>';
    }
}

/**
 * Display schedule on page
 */
function displaySchedule(data) {
    const scheduleList = document.getElementById('schedule-list');

    // Update current show
    if (data.current_show) {
        document.getElementById('current-show-name').textContent = data.current_show.show_name;
        document.getElementById('current-show-time').textContent =
            formatTime(data.current_show.start_time) + ' - ' + formatTime(data.current_show.end_time);
        document.getElementById('current-show-desc').textContent =
            data.current_show.description || 'No description available';
    }

    // Update next show
    if (data.shows && data.shows.length > 0) {
        const nextShow = data.shows[0];
        document.getElementById('next-show-name').textContent = nextShow.show_name;
        document.getElementById('next-show-time').textContent =
            formatTime(nextShow.start_time) + ' - ' + formatTime(nextShow.end_time);

        if (data.next_live_in_minutes) {
            const el = document.querySelector('.next-show p:last-child');
            el.textContent += ` (in ${data.next_live_in_minutes} minutes)`;
        }
    }

    // Display all upcoming shows
    if (data.shows && data.shows.length > 0) {
        scheduleList.innerHTML = data.shows
            .map(show => `
                <div class="schedule-item">
                    <h4>${escapeHtml(show.show_name)}</h4>
                    <div class="time">${formatTime(show.start_time)} - ${formatTime(show.end_time)}</div>
                    ${show.description ? `<p>${escapeHtml(show.description)}</p>` : ''}
                    ${show.is_recurring ? '<p class="dj">🔄 Recurring</p>' : ''}
                </div>
            `)
            .join('');
    } else {
        scheduleList.innerHTML = '<p class="loading">No upcoming shows scheduled</p>';
    }
}

/**
 * Format datetime string to readable format
 */
function formatTime(dateString) {
    try {
        const date = new Date(dateString);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return dateString;
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

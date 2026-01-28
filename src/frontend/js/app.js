const API_URL = 'https://d2ozob9qtyhufv.cloudfront.net';
const LOGGER_URL = null; // Logging endpoint not deployed
let map, stopData, activeBuses = [], selectedRouteKey = null, focusedBusId = null, refreshTimer = null, busMarkers = {}, stopMarker = null;
let followMode = false;
let zoomCycle = 0; // 0: overview, 1: 75% (16), 2: 100% (18)
let lastApiData = null; // Store full API response for navigation
const REFRESH_MS = 30000;
const NEW_SERVICE_DAY_START_HOUR = 5; // 5 AM

function logAction(message, details = {}) {
    if (!LOGGER_URL) return; // Logging not configured
    try {
        if (navigator.sendBeacon) {
            const data = new Blob([JSON.stringify({ message, details })], { type: 'application/json' });
            navigator.sendBeacon(LOGGER_URL, data);
        }
    } catch (e) {
        // Silently ignore logging errors
    }
}

function clearError() {
    document.getElementById('error-msg').style.display = 'none';
}

function updateDisplay() {
    const val = document.getElementById('stopInput').value;
    document.getElementById('display-digits').innerText = val;
}

function appendNumber(num) {
    const input = document.getElementById('stopInput');
    if (input.value.length < 5) {
        input.value += num;
        updateDisplay();
        clearError();
    }
}

function backspace() {
    const input = document.getElementById('stopInput');
    input.value = input.value.slice(0, -1);
    updateDisplay();
    clearError();
}

function initMap() {
    map = L.map('map', { zoomControl: false }).setView([43.4503, -80.4832], 13);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', { attribution: '© CartoDB' }).addTo(map);

    map.on('dragstart', () => { followMode = false; });

    logAction('AppLoaded');
}

function handleEnter(e) { if (e.key === 'Enter') searchStop(); }

async function searchStop() {
    const inputEl = document.getElementById('stopInput');
    const id = inputEl.value;
    const btn = document.getElementById('search-btn');
    if (!id) return;

    const originalText = btn.innerText;
    btn.innerText = "...";
    logAction('SearchStop', { stopId: id });
    try {
        const res = await fetch(`${API_URL}?stop_id=${id}`);
        if (res.status === 404) throw new Error("Stop not found");
        const data = await res.json();
        lastApiData = data;
        stopData = data.stop_details;
        activeBuses = data.nearby_buses || [];
        document.getElementById('search-screen').classList.add('hidden');
        document.querySelector('.back-btn').style.display = 'inline-flex';
        map.invalidateSize();
        map.setView([stopData.lat, stopData.lon], 16);
        if (stopMarker) map.removeLayer(stopMarker);
        stopMarker = L.marker([stopData.lat, stopData.lon], {
            icon: L.divIcon({ className: 'stop-icon', html: '<div style="width:16px;height:16px;background:#28a745;border:3px solid white;border-radius:50%;box-shadow:0 2px 5px rgba(0,0,0,0.3);"></div>', iconSize: [20, 20] })
        }).addTo(map);
        showRoutes(data);
    } catch (e) {
        logAction('SearchError', { stopId: id, error: e.message });
        const errEl = document.getElementById('error-msg');
        errEl.innerText = e.message;
        errEl.style.display = 'block';

        errEl.style.animation = 'none';
        errEl.offsetHeight;
        errEl.style.animation = 'shake 0.4s cubic-bezier(.36,.07,.19,.97) both';

        inputEl.value = '';
        updateDisplay();
    }
    finally { btn.innerText = originalText; }
}

function showRoutes(data = null) {
    if (!data) data = lastApiData;

    if (refreshTimer) clearInterval(refreshTimer);
    selectedRouteKey = null; focusedBusId = null; followMode = false;
    document.getElementById('tracking-card').classList.remove('active');

    const list = document.getElementById('route-list');
    list.innerHTML = '';
    document.getElementById('stop-name-display').innerText = stopData.name;

    document.getElementById('stopInput').value = '';
    updateDisplay();

    const routes = {};
    activeBuses.forEach(bus => {
        const key = `${bus.route_id}|${bus.headsign}`;
        if (!routes[key]) routes[key] = { id: bus.route_id, head: bus.headsign, live: true, time: bus.next_scheduled_arrival };
    });

    if (data && data.offline_schedules && data.offline_schedules.length > 0) {
        const now = new Date();

        data.offline_schedules.forEach(s => {
            const key = `${s.route_id}|${s.headsign}`;
            if (!routes[key]) {
                let displayTime = s.next_scheduled_arrival;
                let label = "Service resumes";
                let isScheduled = false;

                try {
                    const [h, m] = s.next_scheduled_arrival.split(':');
                    const busHour = parseInt(h);

                    const busDate = new Date();
                    busDate.setHours(busHour, parseInt(m), 0, 0);

                    // Correctly handle overnight schedules based on NEW_SERVICE_DAY_START_HOUR
                    if (busDate < now && now.getHours() >= NEW_SERVICE_DAY_START_HOUR) {
                        busDate.setDate(busDate.getDate() + 1);
                        label = "Resumes tomorrow";
                    } else if (busDate < now && now.getHours() < NEW_SERVICE_DAY_START_HOUR) {
                        // If it's past midnight but before NEW_SERVICE_DAY_START_HOUR, it's still 'today's' late service
                        label = "Service ended";
                    }

                    const diffMinutes = (busDate - now) / 60000;

                    if (diffMinutes >= 0 && diffMinutes < 90) {
                        isScheduled = true;
                        label = "Scheduled Departure";
                    } else if (diffMinutes < 0) {
                        label = "Service ended";
                    }

                    displayTime = busDate.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
                } catch (e) { }

                routes[key] = {
                    id: s.route_id,
                    head: s.headsign,
                    live: false,
                    isScheduled: isScheduled,
                    time: displayTime,
                    label: label
                };
            }
        });
    } else if (data && data.all_routes) {
        data.all_routes.forEach(r => {
            const [rid, head] = r;
            const key = `${rid}|${head}`;
            if (!routes[key]) routes[key] = { id: rid, head: head, live: false, isScheduled: false, time: "OFF-LINE", label: "Service currently" };
        });
    }

    const uniqueRoutes = Object.values(routes);

    if (uniqueRoutes.length === 0) {
        list.innerHTML = '<p style="text-align:center; padding: 20px; color: var(--text-secondary);">No routes found for this stop.</p>';
    } else {
        uniqueRoutes.forEach(r => {
            const el = document.createElement('div'); el.className = 'route-option';

            if (!r.live && !r.isScheduled) {
                el.style.opacity = '0.7';
                el.style.background = '#fcfcfc';
                el.style.borderStyle = 'dashed';
                el.style.padding = '20px';
            }

            el.innerHTML = `
                <div class="route-badge" style="${(!r.live && !r.isScheduled) ? 'background:#999' : ''}">${r.id}</div>
                <div style="flex-grow:1">
                    <div class="route-dest" style="${(!r.live && !r.isScheduled) ? 'color:#666' : ''}">${r.head}</div>
                    ${(!r.live && !r.isScheduled) ? `
                        <div style="margin-top:10px">
                            <div style="font-size:0.75rem; color:#888; font-weight:700; text-transform:uppercase; letter-spacing:0.5px">
                                ${r.label}
                            </div>
                            <div style="font-size:1.5rem; font-weight:700; color:var(--text-secondary); line-height:1.1; margin-top:2px">
                                ${r.time}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;

            if (r.live || r.isScheduled) {
                el.onclick = () => startTracking(`${r.id}|${r.head}`);
            } else {
                el.onclick = () => alert(`${r.label} at ${r.time}. Service is currently offline.`);
            }
            list.appendChild(el);
        });
    }

    document.getElementById('route-sheet').classList.add('active');

    setTimeout(() => {
        const sheetHeight = document.getElementById('route-sheet').offsetHeight;
        map.panBy([0, sheetHeight / 2], { animate: true });
    }, 100);

    renderBuses();
}

function startTracking(routeKey) {
    selectedRouteKey = routeKey;
    logAction('StartTracking', { routeKey });
    document.getElementById('route-sheet').classList.remove('active');
    document.getElementById('tracking-card').classList.add('active');
    const [rid, head] = routeKey.split('|');
    document.getElementById('track-route-name').innerText = `Route ${rid}`;
    document.getElementById('track-headsign').innerText = head;

    document.getElementById('arrival-time').innerText = "--";
    document.getElementById('arrival-sub').innerText = "Loading...";
    document.getElementById('bus-id-badge').innerText = "---";
    document.getElementById('late-badge').style.display = 'none';
    document.getElementById('next-stop-container').style.display = 'none';

    refreshData();
    refreshTimer = setInterval(refreshData, REFRESH_MS);
    startProgressBar();
}

async function refreshData() {
    try {
        const res = await fetch(`${API_URL}?stop_id=${stopData.id}`);
        const data = await res.json();
        activeBuses = data.nearby_buses || [];
        const routeBuses = activeBuses.filter(b => `${b.route_id}|${b.headsign}` === selectedRouteKey);
        routeBuses.sort((a, b) => (a.next_scheduled_arrival || '99:99') > (b.next_scheduled_arrival || '99:99') ? 1 : -1);
        const nextBus = routeBuses[0];

        let bottomPadding = 0;
        const trackingCard = document.getElementById('tracking-card');
        if (trackingCard.classList.contains('active')) {
            bottomPadding = trackingCard.offsetHeight;
        }

        if (nextBus) {
            focusedBusId = nextBus.id;
            updateTrackingUI(nextBus);

            if (followMode) {
                const mapSize = map.getSize();
                const effectiveHeight = mapSize.y - bottomPadding;
                const busPoint = map.latLngToContainerPoint([nextBus.lat, nextBus.lon]);

                const marginX = mapSize.x * 0.15;
                const marginY = effectiveHeight * 0.15;

                if (busPoint.x < marginX || busPoint.x > mapSize.x - marginX ||
                    busPoint.y < marginY || busPoint.y > effectiveHeight - marginY) {

                    map.panTo([nextBus.lat, nextBus.lon], {
                        animate: true,
                        paddingBottomRight: [0, bottomPadding]
                    });
                }
            } else {
                const bounds = L.latLngBounds([stopData.lat, stopData.lon], [nextBus.lat, nextBus.lon]);
                map.flyToBounds(bounds, {
                    paddingBottomRight: [50, bottomPadding + 50],
                    paddingTopLeft: [50, 50],
                    maxZoom: 16,
                    animate: true,
                    duration: 1
                });
            }
        } else {
            const [rid, head] = selectedRouteKey.split('|');
            const scheduled = data.offline_schedules ? data.offline_schedules.find(s => String(s.route_id) === String(rid) && s.headsign === head) : null;

            if (scheduled) {
                let timeStr = scheduled.next_scheduled_arrival;
                try {
                    const [h, m] = timeStr.split(':');
                    const d = new Date(); d.setHours(h); d.setMinutes(m);
                    timeStr = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
                } catch (e) { }

                document.getElementById('arrival-time').innerText = timeStr;
                document.getElementById('arrival-time').classList.remove('final-stop');
                document.getElementById('arrival-sub').innerText = "Scheduled Departure";
                document.getElementById('bus-id-badge').innerText = "Scheduled";
                document.getElementById('late-badge').style.display = 'none';
                document.getElementById('next-stop-container').style.display = 'none';

                if (focusedBusId) {
                    focusedBusId = null;
                    map.flyTo([stopData.lat, stopData.lon], 16, { paddingBottomRight: [0, 300] });
                }
            } else {
                document.getElementById('arrival-time').innerText = "Final Stop";
                document.getElementById('arrival-time').classList.add('final-stop');
                document.getElementById('arrival-sub').innerText = "No more buses scheduled";
                document.getElementById('bus-id-badge').innerText = "End of Line";
                document.getElementById('late-badge').style.display = 'none';
                document.getElementById('next-stop-container').style.display = 'none';
            }
        }
        renderBuses();
        startProgressBar();
    } catch (e) { console.error(e); }
}

function updateTrackingUI(bus) {
    const timeEl = document.getElementById('arrival-time');
    const subEl = document.getElementById('arrival-sub');
    const lateBadge = document.getElementById('late-badge');

    timeEl.classList.remove('final-stop');

    // Handle Terminal Turnover (Incoming Bus) separately
    if (bus.is_turnover_incoming) {
        document.getElementById('bus-id-badge').innerText = `Bus ${bus.id}`;
        document.getElementById('track-headsign').innerText = bus.headsign + " (Incoming)";
        document.getElementById('next-stop-name').innerText = bus.next_stop_name || '---';
        document.getElementById('next-stop-container').style.display = bus.next_stop_name ? 'flex' : 'none';

        timeEl.innerText = bus.turnover_target_time;
        subEl.innerText = `Departs for ${bus.turnover_target_headsign}`;
        lateBadge.style.display = 'none';
        return;
    }

    document.getElementById('bus-id-badge').innerText = `Bus ${bus.id}`;
    document.getElementById('next-stop-name').innerText = bus.next_stop_name || '---';
    document.getElementById('next-stop-container').style.display = bus.next_stop_name ? 'flex' : 'none';

    const stopsAway = bus.target_stop_sequence - bus.current_stop_sequence;
    if (stopsAway <= 1 && stopsAway >= 0) {
        timeEl.innerText = "DUE NOW";
        timeEl.classList.add('due-now');
        subEl.innerText = "Arriving at your stop";
        lateBadge.style.display = 'none';
        return;
    }

    timeEl.classList.remove('due-now');
    if (bus.next_scheduled_arrival) {
        let timeStr = bus.next_scheduled_arrival;
        if (timeStr.includes('(Late)')) {
            timeStr = timeStr.replace('(Late)', '').trim();
            lateBadge.style.display = 'block';
        } else { lateBadge.style.display = 'none'; }
        try {
            const [h, m] = timeStr.split(':');
            const d = new Date(); d.setHours(h); d.setMinutes(m);
            timeEl.innerText = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
        } catch (e) { timeEl.innerText = timeStr; }
        subEl.innerText = "Scheduled Arrival";
    } else { timeEl.innerText = "---"; subEl.innerText = "No schedule data"; }
}

function renderBuses() {
    Object.values(busMarkers).forEach(m => map.removeLayer(m));
    busMarkers = {};
    const busesToShow = selectedRouteKey ? activeBuses.filter(b => `${b.route_id}|${b.headsign}` === selectedRouteKey) : activeBuses;
    busesToShow.forEach(bus => {
        const isFocused = bus.id === focusedBusId;
        const rotation = bus.bearing || 0;

        const iconHtml = `
            <div class="bus-hit-area">
                <div style="position: absolute; top: 0; left: 0; width: 90px; height: 44px; transform: rotate(${rotation}deg); transform-origin: center center; pointer-events: none;">
                    ${isFocused ? '<div class="bus-icon-glow"></div>' : ''}
                    <div class="grt-icon"></div>
                </div>
            </div>
        `;

        const icon = L.divIcon({ className: 'leaflet-bus-marker', html: iconHtml, iconSize: [90, 44], iconAnchor: [45, 22] });
        const marker = L.marker([bus.lat, bus.lon], { icon: icon, zIndexOffset: 1000 }).addTo(map);

        marker.on('click', (e) => {
            L.DomEvent.stopPropagation(e);

            let bottomPadding = 0;
            const trackingCard = document.getElementById('tracking-card');
            const routeSheet = document.getElementById('route-sheet');
            if (trackingCard.classList.contains('active')) bottomPadding = trackingCard.offsetHeight;
            else if (routeSheet.classList.contains('active')) bottomPadding = routeSheet.offsetHeight;

            if (focusedBusId !== bus.id) {
                focusedBusId = bus.id;
                zoomCycle = 1;
            } else {
                zoomCycle = (zoomCycle + 1) % 3;
            }

            if (zoomCycle === 1) {
                followMode = true;
                map.flyTo([bus.lat, bus.lon], 16, { animate: true, duration: 1, paddingBottomRight: [0, bottomPadding] });
            } else if (zoomCycle === 2) {
                followMode = true;
                map.flyTo([bus.lat, bus.lon], 18, { animate: true, duration: 1, paddingBottomRight: [0, bottomPadding] });
            } else {
                followMode = false;
                const bounds = L.latLngBounds([stopData.lat, stopData.lon], [bus.lat, bus.lon]);
                map.flyToBounds(bounds, { paddingBottomRight: [50, bottomPadding + 50], paddingTopLeft: [50, 50], maxZoom: 16, animate: true, duration: 1 });
            }
            renderBuses();
        });

        busMarkers[bus.id] = marker;
    });
}

function startProgressBar() {
    const fill = document.getElementById('refresh-fill');
    fill.style.transition = 'none'; fill.style.transform = 'scaleX(1)';
    void fill.offsetWidth; fill.style.transition = `transform ${REFRESH_MS}ms linear`; fill.style.transform = 'scaleX(0)';
}

function resetApp() {
    if (refreshTimer) clearInterval(refreshTimer);
    logAction('ResetApp');
    document.getElementById('stopInput').value = '';
    updateDisplay();
    document.getElementById('search-screen').classList.remove('hidden');
    document.querySelector('.back-btn').style.display = 'none';
    document.getElementById('route-sheet').classList.remove('active');
    document.getElementById('tracking-card').classList.remove('active');
    if (stopMarker) map.removeLayer(stopMarker);
    Object.values(busMarkers).forEach(m => map.removeLayer(m));

    map.getContainer().style.height = '100vh';
    setTimeout(() => { map.invalidateSize(); map.flyTo([43.4503, -80.4832], 13); }, 100);
}
initMap();
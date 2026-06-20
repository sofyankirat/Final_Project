(function () {
    function ensureIconLink() {
        let link = document.querySelector('link[rel~="icon"]');
        if (!link) {
            link = document.createElement('link');
            link.rel = 'icon';
            document.head.appendChild(link);
        }
        return link;
    }

    function drawAndCropToFavicon(img, size) {
        const sampleSize = 256;
        const sampleCanvas = document.createElement('canvas');
        sampleCanvas.width = sampleSize;
        sampleCanvas.height = sampleSize;
        const sampleCtx = sampleCanvas.getContext('2d', { willReadFrequently: true });
        if (!sampleCtx) {
            return null;
        }

        sampleCtx.clearRect(0, 0, sampleSize, sampleSize);
        // Fit image into sample canvas
        const scale = Math.min(sampleSize / img.naturalWidth, sampleSize / img.naturalHeight);
        const drawW = Math.max(1, Math.floor(img.naturalWidth * scale));
        const drawH = Math.max(1, Math.floor(img.naturalHeight * scale));
        const dx = Math.floor((sampleSize - drawW) / 2);
        const dy = Math.floor((sampleSize - drawH) / 2);
        sampleCtx.drawImage(img, dx, dy, drawW, drawH);

        const imageData = sampleCtx.getImageData(0, 0, sampleSize, sampleSize);
        const data = imageData.data;

        let minX = sampleSize;
        let minY = sampleSize;
        let maxX = -1;
        let maxY = -1;

        // Find bounding box of non-transparent pixels
        for (let y = 0; y < sampleSize; y++) {
            for (let x = 0; x < sampleSize; x++) {
                const idx = (y * sampleSize + x) * 4;
                const alpha = data[idx + 3];
                if (alpha > 80) { // Ignore soft transparent glow/shadows
                    if (x < minX) minX = x;
                    if (y < minY) minY = y;
                    if (x > maxX) maxX = x;
                    if (y > maxY) maxY = y;
                }
            }
        }

        // If we couldn't detect anything, fall back to full image
        if (maxX < 0 || maxY < 0) {
            minX = 0;
            minY = 0;
            maxX = sampleSize - 1;
            maxY = sampleSize - 1;
        }

        // Set negative padding to zoom closer and make the tab logo larger
        const pad = -Math.floor(sampleSize * 0.03);
        minX = Math.max(0, minX - pad);
        minY = Math.max(0, minY - pad);
        maxX = Math.min(sampleSize - 1, maxX + pad);
        maxY = Math.min(sampleSize - 1, maxY + pad);

        const cropW = Math.max(1, maxX - minX + 1);
        const cropH = Math.max(1, maxY - minY + 1);

        const outCanvas = document.createElement('canvas');
        outCanvas.width = size;
        outCanvas.height = size;
        const outCtx = outCanvas.getContext('2d');
        if (!outCtx) {
            return null;
        }

        outCtx.clearRect(0, 0, size, size);
        // Scale crop to fit output square while preserving aspect ratio
        const outScale = Math.min(size / cropW, size / cropH);
        const outW = Math.max(1, Math.floor(cropW * outScale));
        const outH = Math.max(1, Math.floor(cropH * outScale));
        const outX = Math.floor((size - outW) / 2);
        const outY = Math.floor((size - outH) / 2);

        outCtx.imageSmoothingEnabled = true;
        outCtx.imageSmoothingQuality = 'high';
        outCtx.drawImage(sampleCanvas, minX, minY, cropW, cropH, outX, outY, outW, outH);

        return outCanvas.toDataURL('image/png');
    }

    function initFaviconCropper() {
        const link = ensureIconLink();
        const href = link.getAttribute('href');
        if (!href) return;

        const img = new Image();
        // Same-origin, but keep this safe if the app ever changes hosting.
        img.crossOrigin = 'anonymous';
        img.onload = function () {
            const dataUrl = drawAndCropToFavicon(img, 128);
            if (!dataUrl) return;

            link.type = 'image/png';
            link.rel = 'icon';
            link.setAttribute('sizes', '128x128');
            link.href = dataUrl;
        };
        img.onerror = function () {
            // If anything goes wrong, keep the original favicon.
        };
        img.src = href;
    }

    let lastNotifsHash = null;
    let lastStatsHash = null;

    async function checkAndRefreshNotifications() {
        const notifBtn = document.getElementById('headerBtnNotif');
        const notifPopup = document.getElementById('notifPopup');
        if (!notifBtn || !notifPopup) return;

        try {
            const res = await fetch('/api/notifications');
            if (res.status === 401) return;
            if (!res.ok) return;
            const data = await res.json();
            if (!data.success) return;

            const currentHash = JSON.stringify(data.notifications);
            if (currentHash === lastNotifsHash) return;
            lastNotifsHash = currentHash;

            const notifDot = notifBtn.querySelector('.header-notif-dot');
            if (data.notifications && data.notifications.length > 0) {
                notifBtn.classList.add('has-notif');
                if (notifDot) notifDot.style.display = 'block';

                let html = '<div style="display:flex; flex-direction:column; gap:8px; max-height:280px; overflow-y:auto; padding: 4px;">';
                data.notifications.slice(0, 3).forEach(n => {
                    html += `
                    <div class="notif-item" style="padding: 10px; border-bottom: 1px solid rgba(0,0,0,0.06); display: flex; flex-direction: column; gap: 4px; border-radius: 6px; transition: background 0.2s;">
                        <div class="notif-title" style="font-weight: 700; font-size: 13px; color: var(--notif-title-clr, #1a1a1a);">${n.title}</div>
                        <div style="font-size: 11.5px; color: var(--notif-desc-clr, #5a4a3a); line-height: 1.4;">${n.message}</div>
                        <div style="font-size: 10px; color: var(--notif-time-clr, #9a8a7a); text-align: right; margin-top: 2px;">${n.time}</div>
                    </div>`;
                });
                html += '</div>';
                notifPopup.innerHTML = html;

                const isDark = document.body.classList.contains('dark-mode');
                notifPopup.style.setProperty('--notif-title-clr', isDark ? '#ffffff' : '#1a1a1a');
                notifPopup.style.setProperty('--notif-desc-clr', isDark ? '#e2e8f8' : '#5a4a3a');
                notifPopup.style.setProperty('--notif-time-clr', isDark ? '#b8c5e6' : '#9a8a7a');
            } else {
                notifBtn.classList.remove('has-notif');
                if (notifDot) notifDot.style.display = 'none';
                notifPopup.innerHTML = `
                <div class="popup-empty">
                    <span class="popup-icon">🔔</span>
                    <span class="popup-msg">No notifications right now</span>
                </div>`;
            }
        } catch (e) {
            console.error('Error fetching notifications:', e);
        }
    }

    async function checkAndRefreshStats() {
        const notifBtn = document.getElementById('headerBtnNotif');
        if (!notifBtn) return;

        try {
            const res = await fetch('/api/attendance/stats');
            if (res.status === 401) return;
            if (!res.ok) return;
            const data = await res.json();
            if (!data.success) return;

            const currentHash = JSON.stringify(data);
            if (currentHash === lastStatsHash) return;
            lastStatsHash = currentHash;

            // 1. Update weekly charts
            const wInst = window.weeklyChartInst;
            const wzInst = window.weeklyChartZoomedInst;
            if (wInst && wInst.data && wInst.data.datasets && wInst.data.datasets[0]) {
                wInst.data.datasets[0].data = data.weekly_data;
                wInst.update();
            }
            if (wzInst && wzInst.data && wzInst.data.datasets && wzInst.data.datasets[0]) {
                wzInst.data.datasets[0].data = data.weekly_data;
                wzInst.update();
            }

            // 2. Update KPI Stats Rate
            const rateValEl = document.getElementById('val-attendance');
            if (rateValEl && data.attendance_rate !== undefined) {
                rateValEl.textContent = Math.round(data.attendance_rate) + '%';
                
                const rateBadgeEl = document.querySelector('#stat-attendance .stat-badge');
                if (rateBadgeEl) {
                    rateBadgeEl.textContent = 'Active';
                    rateBadgeEl.className = 'stat-badge';
                    rateBadgeEl.style.background = 'rgba(59, 130, 246, 0.12)';
                    rateBadgeEl.style.color = '#3b82f6';
                }
            }

            // Update Percentage and Academic Grade is managed by local GPA widgets updateGpaWidgets in dashboard.html.

            // 3. Update Course bars
            const courseBarsContainer = document.querySelector('.course-bars-area');
            if (courseBarsContainer && data.courses) {
                let html = '';
                data.courses.forEach(course => {
                    html += `
                    <div class="course-bar-row">
                        <span class="course-bar-label">${course.name}</span>
                        <div class="course-bar-track">
                            <div class="course-bar-fill" data-pct="${course.pct}" data-clr="${course.clr}" style="width: ${course.pct}%; background-color: ${course.clr};"></div>
                        </div>
                        <span class="course-bar-pct">${course.pct}%</span>
                    </div>`;
                });
                courseBarsContainer.innerHTML = html;
                
                if (typeof animateCourseBars === 'function') {
                    animateCourseBars(courseBarsContainer);
                }
            }

            // Update Course bars in modal
            const modalContent = document.querySelector('#courseAttendanceModal .custom-modal-content');
            if (modalContent && document.getElementById('courseAttendanceModal').classList.contains('open')) {
                const originalBars = document.querySelector('.course-bars-area');
                if (originalBars) {
                    modalContent.innerHTML = originalBars.innerHTML;
                    if (typeof animateCourseBars === 'function') {
                        animateCourseBars(document.getElementById('courseAttendanceModal'));
                    }
                }
            }
        } catch (e) {
            console.error('Error fetching stats:', e);
        }
    }

    function initRealtimeSync() {
        const notifBtn = document.getElementById('headerBtnNotif');
        if (!notifBtn) return;
        
        checkAndRefreshNotifications();
        checkAndRefreshStats();
        
        setInterval(() => {
            checkAndRefreshNotifications();
            checkAndRefreshStats();
        }, 5000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initFaviconCropper();
            initRealtimeSync();
        });
    } else {
        initFaviconCropper();
        initRealtimeSync();
    }
})();

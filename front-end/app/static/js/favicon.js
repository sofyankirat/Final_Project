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

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFaviconCropper);
    } else {
        initFaviconCropper();
    }
})();

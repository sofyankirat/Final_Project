(function () {
    const STRIP_IMAGES = [
        'image_1.jpg', 'image_2.jpg', 'image_3.jpg', 'image_4.jpg', 'image_5.jpg',
        'image_6.jpg', 'image_7.jpg', 'image_8.jpg', 'image_9.jpg', 'image_10.jpg',
        'image_11.jpg', 'image_12.jpg', 'image_13.jpg', 'image_14.jpg', 'image_15.jpg',
        'image_16.jpg', 'image_17.jpg', 'image_18.jpg', 'image_19.jpg', 'image_20.jpg',
        'image_21.jpg', 'image_22.jpg', 'image_23.jpg', 'image_24.jpg', 'image_25.jpg',
        'image_26.png', 'image_27.jpg'
    ];

    function shouldSkipContainer(container) {
        if (!container) return true;

        // Opt-out for pages where strips are authored in HTML and must not be replaced.
        // Use: <div class="login-illustration" data-strips-static="true"> ...
        if (container.dataset.stripsStatic === 'true') return true;
        if (container.dataset.stripsMode === 'static') return true;

        // Idempotency: never rebuild the same container twice.
        if (container.dataset.stripsInitialized === '1') return true;
        return false;
    }

    function shuffleArray(array) {
        const arr = [...array];
        for (let i = arr.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [arr[i], arr[j]] = [arr[j], arr[i]];
        }
        return arr;
    }

    function initStrips() {
        const container = document.querySelector('.login-illustration, .schedule-illustration');
        if (!container) return;
        if (shouldSkipContainer(container)) return;

        // Mark immediately to prevent any future re-entry.
        container.dataset.stripsInitialized = '1';

        const strips = container.querySelectorAll('.symbols-container');
        strips.forEach((strip) => {
            // Shuffle the image list
            const shuffled = shuffleArray(STRIP_IMAGES);
            // Slice the first 15 unique images
            const slice = shuffled.slice(0, 15);
            // Duplicate them to maintain seamless loop matching (15 + 15 = 30 symbols)
            const duplicated = [...slice, ...slice];

            // Rebuild the strip's contents
            const fragment = document.createDocumentFragment();
            duplicated.forEach((imgName, index) => {
                const symbolDiv = document.createElement('div');
                symbolDiv.className = 'symbol';

                const img = document.createElement('img');
                img.src = `/static/images/${imgName}`;
                img.alt = `Illustration Symbol ${index + 1}`;

                symbolDiv.appendChild(img);
                fragment.appendChild(symbolDiv);
            });

            strip.innerHTML = '';
            strip.appendChild(fragment);
        });
    }

    // Run immediately if container is already in DOM to prevent layout shift/flashing, otherwise fallback to DOMContentLoaded
    const container = document.querySelector('.login-illustration, .schedule-illustration');
    if (container) {
        initStrips();
    } else {
        document.addEventListener('DOMContentLoaded', initStrips);
    }
})();

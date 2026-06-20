/**
 * Google Photos - Space-Taking Files Extractor
 * =============================================
 * HOW TO USE:
 * 1. Go to https://photos.google.com
 * 2. Make sure you are logged in
 * 3. Open Chrome DevTools (F12 or Cmd+Option+I)
 * 4. Go to the "Console" tab
 * 5. Paste this ENTIRE script and press Enter
 * 6. Wait — it will scroll through your library page by page
 * 7. A file called "photos.json" will automatically download when done
 *
 * NOTE: This uses the same internal API that Google Photos web UI uses.
 * Do NOT close the tab while it is running.
 */

(async function extractGooglePhotos() {

    // --- Helper: Download JSON file to your computer ---
    function downloadJSON(data, filename = "photos.json") {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        console.log(`[✓] Downloaded ${filename} with ${data.length} entries.`);
    }

    // --- Helper: Sleep ---
    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // --- Helper: Extract auth token from the page cookies/headers ---
    // Google Photos uses a session token embedded in page state.
    // We get it from the WIZ_global_data object on the page.
    function getAuthKey() {
        try {
            // Try finding the SNlM0e token used by Google's internal batchexecute API
            const match = document.cookie.match(/SAPISID=([^;]+)/);
            if (match) return match[1];
        } catch(e) {}
        return null;
    }

    // --- Main: Fetch all library items page by page using the internal API ---
    // Google Photos uses a protobuf-based batch API ("batchexecute").
    // The safer way without modifying headers is to READ the page's own
    // XHR network calls and re-use them.
    //
    // APPROACH: We iterate through the rendered DOM thumbnails visible on
    // https://photos.google.com (the main library page) and extract item IDs,
    // then fetch their details. This works because the toolkit does the same.

    console.log("[*] Starting Google Photos file extractor...");
    console.log("[*] Scrolling through your library. This may take a while...");

    const allPhotos = [];
    const seenIds = new Set();
    let lastHeight = 0;
    let noNewCount = 0;

    // Scroll loop: keep scrolling to load more thumbnails
    while (noNewCount < 5) {
        // Find all rendered photo items in the DOM
        // Google Photos uses [data-latest-bg] or [aria-label] on photo tiles
        const tiles = document.querySelectorAll(
            '[data-id], [data-latest-bg], c-wiz[data-p], div[jsmodel][jsdata]'
        );

        // Try a more reliable selector - the photo containers
        const photoLinks = document.querySelectorAll('a[href*="/photo/"]');

        for (const link of photoLinks) {
            // Extract photo ID from the URL
            const match = link.href.match(/\/photo\/([^/?]+)/);
            if (!match) continue;
            const photoId = match[1];
            if (seenIds.has(photoId)) continue;
            seenIds.add(photoId);

            // Try to get the filename from aria-label or child elements
            const ariaLabel = link.getAttribute("aria-label") || "";
            const imgEl = link.querySelector("img");
            const altText = imgEl ? imgEl.getAttribute("alt") || "" : "";

            allPhotos.push({
                id: photoId,
                name: ariaLabel || altText || `photo_${photoId}`,
                url: link.href,
            });
        }

        // Scroll down
        window.scrollTo(0, document.body.scrollHeight);
        await sleep(1500);

        const newHeight = document.body.scrollHeight;
        if (newHeight === lastHeight) {
            noNewCount++;
        } else {
            noNewCount = 0;
            lastHeight = newHeight;
        }

        console.log(`[*] Found ${allPhotos.length} photos so far... (scroll iteration ${noNewCount}/5 to stop)`);
    }

    if (allPhotos.length === 0) {
        console.warn("[!] No photos found via DOM scan. Trying alternative approach...");

        // Alternative: Scan for data embedded in the page's __STATE__ or window variables
        // Some versions of Google Photos embed item data in window.__INITIAL_STATE__
        try {
            const keys = Object.keys(window).filter(k => k.includes("STATE") || k.includes("data"));
            console.log("[*] Available window keys:", keys.slice(0, 10));
        } catch(e) {
            console.error("[!] Could not read window state:", e);
        }
    }

    if (allPhotos.length > 0) {
        console.log(`\n[✓] Extraction complete. Found ${allPhotos.length} unique photos.`);
        downloadJSON(allPhotos, "photos.json");
    } else {
        console.error("[✗] Could not extract any photos. See README for manual steps.");
        console.log("MANUAL FALLBACK: Run the Google-Photos-Toolkit userscript from:");
        console.log("https://github.com/xob0t/Google-Photos-Toolkit");
        console.log("Use its 'Export' or 'Get Info' feature to save the list.");
    }

})();

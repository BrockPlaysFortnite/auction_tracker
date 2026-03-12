/**
 * Auction Tracker - Frontend Application
 *
 * Loads auction data from JSON, renders cards with countdown timers,
 * and provides source filtering + text search.
 */

(function () {
    "use strict";

    const DATA_URL = "data/auctions.json";
    const REFRESH_INTERVAL_MS = 60_000; // Recalculate countdowns every 60s

    let auctionData = [];
    let currentFilter = "all";
    let currentSearch = "";

    // --- DOM References ---
    const container = document.getElementById("auctions-container");
    const sourceFilter = document.getElementById("source-filter");
    const searchInput = document.getElementById("search-input");
    const lastUpdatedEl = document.getElementById("last-updated");
    const auctionCountEl = document.getElementById("auction-count");

    // --- Init ---
    async function init() {
        try {
            const resp = await fetch(DATA_URL);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const json = await resp.json();

            auctionData = json.auctions || [];
            updateLastUpdated(json.last_updated);
            render();
        } catch (err) {
            container.innerHTML =
                '<div class="error-state">Unable to load auction data. Please try again later.</div>';
            console.error("Failed to load auction data:", err);
        }

        // Event listeners
        sourceFilter.addEventListener("change", (e) => {
            currentFilter = e.target.value;
            render();
        });

        searchInput.addEventListener("input", (e) => {
            currentSearch = e.target.value.toLowerCase().trim();
            render();
        });

        // Auto-refresh countdowns
        setInterval(render, REFRESH_INTERVAL_MS);
    }

    // --- Countdown ---
    function getCountdown(isoDate) {
        const auctionDate = new Date(isoDate + "T00:00:00");
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const diffMs = auctionDate - today;
        const diffDays = Math.ceil(diffMs / 86_400_000);

        if (diffDays < -1) return { text: `${Math.abs(diffDays)} DAYS AGO`, cssClass: "past" };
        if (diffDays === -1) return { text: "YESTERDAY", cssClass: "past" };
        if (diffDays === 0) return { text: "TODAY", cssClass: "today" };
        if (diffDays === 1) return { text: "TOMORROW", cssClass: "tomorrow" };
        if (diffDays <= 7) return { text: `${diffDays} DAYS AWAY`, cssClass: "soon" };
        return { text: `${diffDays} DAYS AWAY`, cssClass: "later" };
    }

    // --- Filtering ---
    function getFilteredAuctions() {
        return auctionData.filter((a) => {
            // Source filter
            if (currentFilter !== "all" && a.source !== currentFilter) return false;

            // Text search
            if (currentSearch) {
                const haystack = [a.title, a.location, a.notes, a.source, a.auction_type]
                    .join(" ")
                    .toLowerCase();
                if (!haystack.includes(currentSearch)) return false;
            }

            return true;
        });
    }

    // --- Rendering ---
    function render() {
        const filtered = getFilteredAuctions();

        auctionCountEl.textContent = `${filtered.length} auction${filtered.length !== 1 ? "s" : ""}`;

        if (filtered.length === 0) {
            container.innerHTML = '<div class="empty-state">No upcoming auctions found.</div>';
            return;
        }

        container.innerHTML = filtered.map(renderCard).join("");
    }

    function renderCard(auction) {
        const countdown = getCountdown(auction.date);
        const itemCountText = auction.item_count != null ? `${auction.item_count} lots` : "";

        return `
        <article class="auction-card">
            <span class="countdown-badge ${countdown.cssClass}">${countdown.text}</span>
            <h2 class="card-title">
                <a href="${escapeHtml(auction.url)}" target="_blank" rel="noopener">${escapeHtml(auction.title)}</a>
            </h2>
            <div class="card-details">
                <div class="card-detail">
                    <span class="label">Date</span>
                    <span>${escapeHtml(auction.date_display)}</span>
                </div>
                <div class="card-detail">
                    <span class="label">Location</span>
                    <span>${escapeHtml(auction.location)}</span>
                </div>
                <div class="card-detail">
                    <span class="label">Type</span>
                    <span>${escapeHtml(auction.auction_type)}${itemCountText ? " &mdash; " + escapeHtml(itemCountText) : ""}</span>
                </div>
            </div>
            ${auction.notes ? `<p class="card-notes">${escapeHtml(auction.notes)}</p>` : ""}
            <div class="card-footer">
                <span class="source-badge" data-source="${escapeHtml(auction.source)}">${escapeHtml(auction.source)}</span>
                <a class="card-link" href="${escapeHtml(auction.url)}" target="_blank" rel="noopener">View Auction &rarr;</a>
            </div>
        </article>`;
    }

    // --- Helpers ---
    function escapeHtml(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function updateLastUpdated(isoTimestamp) {
        if (!isoTimestamp) return;
        try {
            const date = new Date(isoTimestamp);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHrs = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            let ago;
            if (diffMins < 1) ago = "just now";
            else if (diffMins < 60) ago = `${diffMins}m ago`;
            else if (diffHrs < 24) ago = `${diffHrs}h ago`;
            else if (diffDays === 1) ago = "1 day ago";
            else ago = `${diffDays} days ago`;

            lastUpdatedEl.textContent = `LAST SYNC: ${ago}`;
        } catch {
            lastUpdatedEl.textContent = `LAST SYNC: ${isoTimestamp}`;
        }
    }

    // --- Start ---
    document.addEventListener("DOMContentLoaded", init);
})();

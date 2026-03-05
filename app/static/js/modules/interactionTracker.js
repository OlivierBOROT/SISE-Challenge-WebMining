/**
 * EventTracker — Collecte d'événements produit, catégorie et pagination.
 *
 * Produit un objet structuré identique au modèle Pydantic
 * UserEvents (event_behavior_schema.py) pour alimenter le FeatureBuilder.
 *
 * Trois types d'événements :
 *   - ProductEvent  : hover / click / achat sur une fiche produit
 *   - CategoryEvent : hover / click sur une catégorie
 *   - PageEvent     : changement de page (pagination)
 *
 * Usage :
 *   tracker.start();
 *   // ... plus tard ...
 *   const payload = tracker.flush();   // { user_id, events }
 *   // envoyer payload au serveur
 */

"use strict";

/* ═══════════ Classe EventTracker ═══════════ */

export class EventTracker {
    /**
     * @param {object} [opts]
     */
    constructor(opts = {}) {

        /** @type {Array<object>} Liste des événements collectés */
        this.events = [];

        /* ── État interne pour le suivi du hover ── */
        /** @type {Map<string, {enterTime: number, element: Element}>} */
        this._productHovers = new Map();
        /** @type {Map<string, {enterTime: number, element: Element}>} */
        this._categoryHovers = new Map();

        /* ── Suivi interne ── */

        /* ── Bound handlers (pour pouvoir les détacher) ── */
        this._onProductEnter  = this._handleProductEnter.bind(this);
        this._onProductLeave  = this._handleProductLeave.bind(this);
        this._onProductClick  = this._handleProductClick.bind(this);
        this._onBuyClick      = this._handleBuyClick.bind(this);
        this._onCategoryEnter = this._handleCategoryEnter.bind(this);
        this._onCategoryLeave = this._handleCategoryLeave.bind(this);
        this._onCategoryClick = this._handleCategoryClick.bind(this);
        this._onPageClick     = this._handlePageClick.bind(this);
        this._onScroll        = this._handleScroll.bind(this);
        this._onWheel         = this._handleWheel.bind(this);
        this._lastScrollPos = 0;
        this._lastScrollTs = 0;
    }

    /* ══════════════════════════════════════════════
       Cycle de vie
       ══════════════════════════════════════════════ */

    /**
     * Attache les event listeners via délégation sur le document.
     * Utilise la délégation car les produits/catégories sont rendus
     * dynamiquement par layout.js.
     */
    start() {
        document.addEventListener("mouseenter", this._onProductEnter, true);
        document.addEventListener("mouseleave", this._onProductLeave, true);
        document.addEventListener("mouseenter", this._onCategoryEnter, true);
        document.addEventListener("mouseleave", this._onCategoryLeave, true);

        // Click handlers via délégation sur le document
        document.addEventListener("click", this._onProductClick);
        document.addEventListener("click", this._onBuyClick);
        document.addEventListener("click", this._onCategoryClick);
        document.addEventListener("click", this._onPageClick);
        document.addEventListener('wheel', this._onWheel, { passive: true });
    }

    stop() {
        document.removeEventListener("mouseenter", this._onProductEnter, true);
        document.removeEventListener("mouseleave", this._onProductLeave, true);
        document.removeEventListener("mouseenter", this._onCategoryEnter, true);
        document.removeEventListener("mouseleave", this._onCategoryLeave, true);

        document.removeEventListener("click", this._onProductClick);
        document.removeEventListener("click", this._onBuyClick);
        document.removeEventListener("click", this._onCategoryClick);
        document.removeEventListener("click", this._onPageClick);
        document.removeEventListener('wheel', this._onWheel, { passive: true });
    }

    /**
     * Retourne le payload UserEvents et vide le buffer.
     * @returns {{ user_id: string, events: Array<object> }}
     */
    flush() {
        const payload = {
            events: [...this.events],
        };
        this.events = [];
        return payload;
    }

    /**
     * Retourne le payload sans vider le buffer (lecture seule).
     * @returns {{ user_id: string, events: Array<object> }}
     */
    peek() {
        return {
            events: [...this.events],
        };
    }

    /* (No DOM extraction helpers needed for tracked events.) */

    /** Timestamp Unix courant en secondes. */
    _now() {
        return Date.now() / 1000;
    }

    /* ══════════════════════════════════════════════
       Handlers — Produits
       ══════════════════════════════════════════════ */

    _handleProductEnter(e) {
        const card = e.target.closest?.(".product-card");
        if (!card) return;
        // Ignore enter events when coming from an element inside the same card
        const from = e.relatedTarget;
        if (from && card.contains(from)) return;
        const id = card.dataset.id ?? card.querySelector("h3")?.textContent ?? "unknown";
        this._productHovers.set(id, { enterTime: performance.now(), element: card });
        
    }

    _handleProductLeave(e) {
        const card = e.target.closest?.(".product-card");
        if (!card) return;
        // Ignore leave events when moving to an element inside the same card
        const to = e.relatedTarget;
        if (to && card.contains(to)) return;

        const id = card.dataset.id ?? card.querySelector("h3")?.textContent ?? "unknown";
        const entry = this._productHovers.get(id);
        if (!entry) return;

        const timeSpent = (performance.now() - entry.enterTime) / 1000; // secondes
        const productId = card.dataset.id ?? id;
        this.events.push({
            batch_t:    Date.now() - this.sessionStart,
            timestamp: this._now(),
            object: "product",
            product_id: productId,
            time_spent: Math.round(timeSpent * 1000) / 1000,
            event_type: "hover",
        });

        this._productHovers.delete(id);
    }

    _handleProductClick(e) {
        const card = e.target.closest?.(".product-card");
        if (!card) return;
        // Ignorer si c'est le bouton Acheter (traité séparément)
        if (e.target.closest("button")) return;
        const productId = card.dataset.id ?? card.querySelector("h3")?.textContent ?? "unknown";
        this.events.push({
            batch_t:    Date.now() - this.sessionStart,
            timestamp: this._now(),
            object: "product",
            product_id: productId,
            time_spent: 0,
            event_type: "click",
        });
    }

    _handleBuyClick(e) {
        const btn = e.target.closest?.(".product-card button");
        if (!btn) return;

        const card = btn.closest(".product-card");
        const productId = card.dataset.id ?? card.querySelector("h3")?.textContent ?? "unknown";
        this.events.push({
            batch_t:    Date.now() - this.sessionStart,
            timestamp: this._now(),
            object: "product",
            product_id: productId,
            time_spent: 0,
            event_type: "achat",
        });
    }

    /* ══════════════════════════════════════════════
       Handlers — Catégories
       ══════════════════════════════════════════════ */

    _handleCategoryEnter(e) {
        const li = e.target.closest?.(".sidebar li, .categories li");
        if (!li) return;
        const from = e.relatedTarget;
        if (from && li.contains(from)) return;
        const name = li.dataset.id ?? li.textContent?.trim() ?? "unknown";
        this._categoryHovers.set(name, { enterTime: performance.now(), element: li });
    }

    _handleCategoryLeave(e) {
        const li = e.target.closest?.(".sidebar li, .categories li");
        if (!li) return;
        const to = e.relatedTarget;
        if (to && li.contains(to)) return;
        const name = li.dataset.id ?? li.textContent?.trim() ?? "unknown";
        const entry = this._categoryHovers.get(name);
        if (!entry) return;

        const timeSpent = (performance.now() - entry.enterTime) / 1000;

        this.events.push({
            batch_t:    Date.now() - this.sessionStart,
            timestamp: this._now(),
            object: "category",
            category_id: name,
            time_spent: Math.round(timeSpent * 1000) / 1000,
            event_type: "hover",
        });

        this._categoryHovers.delete(name);
    }

    _handleCategoryClick(e) {
        const li = e.target.closest?.(".sidebar li, .categories li");
        if (!li) return;
        const name = li.dataset.id ?? li.textContent?.trim() ?? "unknown";
        this.events.push({
            batch_t:    Date.now() - this.sessionStart,
            timestamp: this._now(),
            object: "category",
            category_id: name,
            time_spent: 0,
            event_type: "click",
        });
    }

    /* ══════════════════════════════════════════════
       Handlers — Pagination
       ══════════════════════════════════════════════ */

    _handlePageClick(e) {
        const btn = e.target.closest?.(".pagination button, .pagination-btn");
        if (!btn) return;

        const pageNum = parseInt(btn.value, 10);
        if (isNaN(pageNum) || pageNum < 1) return;

        this.events.push({
            batch_t:    Date.now() - this.sessionStart,
            timestamp: this._now(),
            object: "page",
            page_num: pageNum,
        });
    }

    /* ══════════════════════════════════════════════
       Handlers — Scroll
       ══════════════════════════════════════════════ */

    _handleScroll(e) {
        const now = performance.now();
        // throttle to ~100ms to avoid huge flood of events
        if (now - this._lastScrollTs < 50) return;
        const newPos = window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0;
        const delta = newPos - (this._lastScrollPos || 0);
        this._lastScrollPos = newPos;
        this._lastScrollTs = now;

        const maxScroll = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
        const ratio = Math.min(1, Math.max(0, newPos / maxScroll));

        this.events.push({
            batch_t:    Date.now() - this.sessionStart,
            timestamp: this._now(),
            object: 'scroll',
            delta_y: delta,
            scroll_position: Number(ratio.toFixed(4)),
        });
    }

    _handleWheel(e) {
        // Wheel events give immediate deltaY values (positive = down)
        const delta = e.deltaY || 0;
        const pos = window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0;
        const maxScroll = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
        const ratio = Math.min(1, Math.max(0, pos / maxScroll));
        // record with same shape as ScrollEvent
        this.events.push({
            batch_t:    Date.now() - this.sessionStart,
            timestamp: this._now(),
            object: 'scroll',
            delta_y: delta,
            scroll_position: Number(ratio.toFixed(4)),
        });
        this._lastScrollPos = pos;
        this._lastScrollTs = performance.now();
    }
}

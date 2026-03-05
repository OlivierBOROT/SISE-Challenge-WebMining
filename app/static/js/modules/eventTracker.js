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
 *   const tracker = new EventTracker({ userId: 'abc123' });
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
     * @param {string} [opts.userId]  Identifiant utilisateur (UUID ou autre).
     */
    constructor(opts = {}) {
        this.userId = opts.userId ?? crypto.randomUUID();

        /** @type {Array<object>} Liste des événements collectés */
        this.events = [];

        /* ── État interne pour le suivi du hover ── */
        /** @type {Map<string, {enterTime: number, element: Element}>} */
        this._productHovers = new Map();
        /** @type {Map<string, {enterTime: number, element: Element}>} */
        this._categoryHovers = new Map();

        /* ── Suivi de la catégorie active ── */
        this._activeCategory = "all";

        /* ── Bound handlers (pour pouvoir les détacher) ── */
        this._onProductEnter  = this._handleProductEnter.bind(this);
        this._onProductLeave  = this._handleProductLeave.bind(this);
        this._onProductClick  = this._handleProductClick.bind(this);
        this._onBuyClick      = this._handleBuyClick.bind(this);
        this._onCategoryEnter = this._handleCategoryEnter.bind(this);
        this._onCategoryLeave = this._handleCategoryLeave.bind(this);
        this._onCategoryClick = this._handleCategoryClick.bind(this);
        this._onPageClick     = this._handlePageClick.bind(this);
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
    }

    /**
     * Retourne le payload UserEvents et vide le buffer.
     * @returns {{ user_id: string, events: Array<object> }}
     */
    flush() {
        const payload = {
            user_id: this.userId,
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
            user_id: this.userId,
            events: [...this.events],
        };
    }

    /* ══════════════════════════════════════════════
       Helpers — extraction de données depuis le DOM
       ══════════════════════════════════════════════ */

    /**
     * Extrait les infos produit depuis un élément .product-card.
     * @param {Element} card
     * @returns {{ product_name: string, price: number, category: string } | null}
     */
    _extractProductInfo(card) {
        if (!card) return null;
        const name = card.querySelector("h3")?.textContent?.trim() ?? "unknown";
        const priceText = card.querySelector(".price")?.textContent?.trim() ?? "0";
        const price = parseFloat(priceText.replace(/[^0-9.,]/g, "").replace(",", ".")) || 0;
        const category = this._activeCategory;
        return { product_name: name, price, category };
    }

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
        const id = card.dataset.id ?? card.querySelector("h3")?.textContent ?? "unknown";
        this._productHovers.set(id, { enterTime: performance.now(), element: card });
    }

    _handleProductLeave(e) {
        const card = e.target.closest?.(".product-card");
        if (!card) return;
        const id = card.dataset.id ?? card.querySelector("h3")?.textContent ?? "unknown";
        const entry = this._productHovers.get(id);
        if (!entry) return;

        const timeSpent = (performance.now() - entry.enterTime) / 1000; // secondes
        const info = this._extractProductInfo(card);
        if (!info) return;

        this.events.push({
            timestamp: this._now(),
            object: "product",
            category: info.category,
            product_name: info.product_name,
            price: info.price,
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

        const info = this._extractProductInfo(card);
        if (!info) return;

        this.events.push({
            timestamp: this._now(),
            object: "product",
            category: info.category,
            product_name: info.product_name,
            price: info.price,
            time_spent: 0,
            event_type: "click",
        });
    }

    _handleBuyClick(e) {
        const btn = e.target.closest?.(".product-card button");
        if (!btn) return;

        const card = btn.closest(".product-card");
        const info = this._extractProductInfo(card);
        if (!info) return;

        this.events.push({
            timestamp: this._now(),
            object: "product",
            category: info.category,
            product_name: info.product_name,
            price: info.price,
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
        const name = li.dataset.id ?? li.textContent?.trim() ?? "unknown";
        this._categoryHovers.set(name, { enterTime: performance.now(), element: li });
    }

    _handleCategoryLeave(e) {
        const li = e.target.closest?.(".sidebar li, .categories li");
        if (!li) return;
        const name = li.dataset.id ?? li.textContent?.trim() ?? "unknown";
        const entry = this._categoryHovers.get(name);
        if (!entry) return;

        const timeSpent = (performance.now() - entry.enterTime) / 1000;

        this.events.push({
            timestamp: this._now(),
            object: "category",
            category_name: name,
            time_spent: Math.round(timeSpent * 1000) / 1000,
            event_type: "hover",
        });

        this._categoryHovers.delete(name);
    }

    _handleCategoryClick(e) {
        const li = e.target.closest?.(".sidebar li, .categories li");
        if (!li) return;
        const name = li.dataset.id ?? li.textContent?.trim() ?? "unknown";

        // Mettre à jour la catégorie active
        this._activeCategory = name;

        this.events.push({
            timestamp: this._now(),
            object: "category",
            category_name: name,
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
            timestamp: this._now(),
            object: "page",
            page_num: pageNum,
        });
    }
}

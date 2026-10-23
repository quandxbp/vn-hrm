/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.EduActivitySlideshow = publicWidget.Widget.extend({
    selector: ".edu-activity-slideshow",
    events: {
        "click .edu-activity-dot": "_choose",
        "click .edu-activity-slide": "_choosePhoto",
        keydown: "_onKeydown",
        focusin: "_onFocusIn",
        focusout: "_onFocusOut",
        "pointerdown .edu-activity-stage": "_onSwipeStart",
        "pointerup .edu-activity-stage": "_onSwipeEnd",
        "pointercancel .edu-activity-stage": "_onSwipeCancel",
    },

    start() {
        this.slides = [...this.el.querySelectorAll(".edu-activity-slide")];
        this.dots = [...this.el.querySelectorAll(".edu-activity-dot")];
        this.track = this.el.querySelector(".edu-activity-track");
        this.stage = this.el.querySelector(".edu-activity-stage");
        this.index = 0;
        this.ratios = [];
        this.slides.forEach((slide, index) => { slide.dataset.activityIndex = index; });
        this.clones = [];
        if (this.slides.length > 1) {
            const cloneSet = () => this.slides.map((slide) => {
                const clone = slide.cloneNode(true);
                clone.classList.remove("is-active");
                clone.setAttribute("aria-hidden", "true");
                // These are display copies, not additional editable records.
                [clone, ...clone.querySelectorAll("*")].forEach((el) => {
                    [...el.attributes].filter((attr) => attr.name.startsWith("data-oe-") || attr.name === "id")
                        .forEach((attr) => el.removeAttribute(attr.name));
                });
                return clone;
            });
            const before = cloneSet();
            const after = cloneSet();
            this.track.prepend(...before);
            this.track.append(...after);
            this.clones = [...before, ...after];
        }
        this.renderSlides = [...this.track.children];
        this.renderIndex = this.slides.length > 1 ? this.slides.length : 0;
        this.onImageLoad = (ev) => {
            if (ev.target.tagName !== "IMG" || !ev.target.naturalWidth) { return; }
            const index = Number(ev.target.closest(".edu-activity-slide").dataset.activityIndex);
            this.ratios[index] = ev.target.naturalWidth / ev.target.naturalHeight;
            this._queueLayout();
        };
        this.track.addEventListener("load", this.onImageLoad, true);
        this.renderSlides.forEach((slide) => {
            const img = slide.querySelector("img");
            if (img.complete && img.naturalWidth) {
                this.ratios[Number(slide.dataset.activityIndex)] = img.naturalWidth / img.naturalHeight;
            }
        });
        this.motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
        this.visible = !("IntersectionObserver" in window);
        this.onVisibility = () => this._schedule();
        this.onMotion = () => {
            this.animating = false;
            this._layout();
            this._schedule();
        };
        this.onTransitionEnd = (ev) => {
            if (ev.target !== this.track || ev.propertyName !== "transform") { return; }
            this.animating = false;
            this._layout();
        };
        this.track.addEventListener("transitionend", this.onTransitionEnd);
        this.resizeObserver = new ResizeObserver(() => this._queueLayout());
        this.resizeObserver.observe(this.stage);
        document.addEventListener("visibilitychange", this.onVisibility);
        this.motionQuery.addEventListener("change", this.onMotion);
        if ("IntersectionObserver" in window) {
            this.observer = new IntersectionObserver(([entry]) => {
                this.visible = entry.isIntersecting;
                this._schedule();
            }, { threshold: 0.15 });
            this.observer.observe(this.el);
        }
        this._prepareImages();
        this._layout();
        this.el.classList.add("is-ready");
        this._schedule();
        return this._super(...arguments);
    },

    destroy() {
        clearTimeout(this.timer);
        this.observer?.disconnect();
        this.resizeObserver?.disconnect();
        cancelAnimationFrame(this.layoutFrame);
        clearTimeout(this.transitionTimer);
        this.track?.removeEventListener("load", this.onImageLoad, true);
        this.track?.removeEventListener("transitionend", this.onTransitionEnd);
        this.clones?.forEach((clone) => clone.remove());
        if (this.track) {
            this.track.style.removeProperty("transform");
            this.track.style.removeProperty("transition");
        }
        this.slides?.forEach((slide, index) => {
            delete slide.dataset.activityIndex;
            slide.style.removeProperty("--activity-ratio");
            slide.classList.toggle("is-active", index === 0);
            slide.setAttribute("aria-hidden", String(index !== 0));
        });
        this.el.classList.remove("is-ready");
        document.removeEventListener("visibilitychange", this.onVisibility);
        this.motionQuery?.removeEventListener("change", this.onMotion);
        this._super(...arguments);
    },

    _schedule() {
        clearTimeout(this.timer);
        if (this.slides.length < 2 || this.motionQuery.matches || this.focused ||
            !this.visible || document.hidden) { return; }
        this.timer = setTimeout(() => this._show(this.index + 1), 5000);
    },

    _show(index) {
        if (this.animating) {
            this.animating = false;
            this._layout();
        }
        let delta = index - this.index;
        const count = this.slides.length;
        if (delta > count / 2) { delta -= count; }
        if (delta < -count / 2) { delta += count; }
        this.index = (index + count) % count;
        this.renderIndex += delta;
        this.slides.forEach((slide, i) => {
            slide.classList.toggle("is-active", i === this.index);
            slide.setAttribute("aria-hidden", String(i !== this.index));
        });
        this.dots.forEach((dot, i) => dot.setAttribute("aria-pressed", String(i === this.index)));
        this._prepareImages();
        this._move(delta !== 0 && !this.motionQuery.matches);
        this._schedule();
    },

    _prepareImages() {
        const count = this.slides.length;
        const adjacent = [this.index, (this.index + 1) % count, (this.index + count - 1) % count];
        this.renderSlides.forEach((slide) => {
            if (adjacent.includes(Number(slide.dataset.activityIndex))) {
                slide.querySelector("img").loading = "eager";
            }
        });
    },
    _queueLayout() {
        cancelAnimationFrame(this.layoutFrame);
        this.layoutFrame = requestAnimationFrame(() => {
            // Do not change card widths halfway through a slide transition.
            if (!this.animating) { this._layout(); }
        });
    },
    _layout() {
        clearTimeout(this.transitionTimer);
        this.renderSlides.forEach((slide) => {
            const ratio = this.ratios[Number(slide.dataset.activityIndex)];
            if (ratio) { slide.style.setProperty("--activity-ratio", ratio); }
        });
        this.renderIndex = this.slides.length > 1 ? this.slides.length + this.index : 0;
        this._move(false);
    },
    _move(animate) {
        const target = this.renderSlides[this.renderIndex];
        const offset = target.offsetLeft + target.offsetWidth / 2 - this.stage.clientWidth / 2;
        // Keep matching copies identical so normalizing the infinite track
        // cannot flash a dimmed version of the same photo at the loop boundary.
        this.renderSlides.forEach((slide) => slide.classList.toggle("is-active", Number(slide.dataset.activityIndex) === this.index));
        this.track.style.transition = animate ? "" : "none";
        this.track.style.transform = `translate3d(${-offset}px, 0, 0)`;
        this.animating = animate;
        clearTimeout(this.transitionTimer);
        if (animate) {
            // Also settle when a browser cancels a transition in a hidden tab.
            this.transitionTimer = setTimeout(() => {
                this.animating = false;
                this._layout();
            }, 950);
        }
    },

    _choose(ev) {
        // Pointer selection should resume autoplay; keyboard users can examine
        // the current slide while focus remains on the slideshow controls.
        if (ev.detail) { this.focused = false; }
        this._show(this.dots.indexOf(ev.currentTarget));
    },
    _choosePhoto(ev) {
        if (Date.now() < (this.swipeClickUntil || 0)) { return; }
        this.focused = false;
        this._show(Number(ev.currentTarget.dataset.activityIndex));
    },
    _onFocusIn(ev) {
        this.focused = ev.target.matches(':focus-visible');
        this._schedule();
    },
    _onFocusOut(ev) { this.focused = this.el.contains(ev.relatedTarget); this._schedule(); },
    _onKeydown(ev) {
        if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") { return; }
        ev.preventDefault();
        this.focused = true;
        this._show(this.index + (ev.key === "ArrowRight" ? 1 : -1));
    },
    _onSwipeStart(ev) {
        if (ev.pointerType === "mouse") { return; }
        this.swipe = { x: ev.clientX, y: ev.clientY };
    },
    _onSwipeEnd(ev) {
        if (!this.swipe) { return; }
        const dx = ev.clientX - this.swipe.x;
        const dy = ev.clientY - this.swipe.y;
        this.swipe = null;
        if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
            this.swipeClickUntil = Date.now() + 350;
            this._show(this.index + (dx < 0 ? 1 : -1));
        }
    },
    _onSwipeCancel() { this.swipe = null; },
});

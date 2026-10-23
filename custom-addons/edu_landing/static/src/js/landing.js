/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import "@website/js/content/menu";

// The homepage already owns a fixed overlay header. Running Odoo's standard
// affix loop as well causes inline style writes and synchronous layout reads
// at its 87/300px thresholds, even when CSS cancels their visible effects.
publicWidget.registry.StandardAffixedHeader.include({
    _updateHeaderOnScroll() {
        if (!this.editableMode && this.el.closest("#wrapwrap")?.querySelector(".edu-home")) {
            return;
        }
        return this._super(...arguments);
    },
});

// Odoo cuộn tới neo nhưng giữ offcanvas mở; đóng menu khi đã chọn nội dung.
publicWidget.registry.EduLandingNavbar = publicWidget.Widget.extend({
    selector: "#wrapwrap > header",
    start() {
        // Bắt sự kiện trước handler cuộn của Odoo (handler đó chặn bubbling).
        this.onAnchorClick = this._onAnchorClick.bind(this);
        this.el.addEventListener("click", this.onAnchorClick, true);
        this.scrollRoot = this.el.closest("#wrapwrap");
        this.onScroll = () => {
            if (this.scrollFrame) { return; }
            this.scrollFrame = requestAnimationFrame(() => {
                const scrolled = Math.max(window.scrollY, this.scrollRoot?.scrollTop || 0) > 32;
                if (scrolled !== this.navScrolled) {
                    this.el.classList.toggle("edu-nav-scrolled", scrolled);
                    this.navScrolled = scrolled;
                }
                this.scrollFrame = null;
            });
        };
        window.addEventListener("scroll", this.onScroll, { passive: true });
        this.scrollRoot?.addEventListener("scroll", this.onScroll, { passive: true });
        this.onScroll();
        return this._super(...arguments);
    },

    destroy() {
        this.el.removeEventListener("click", this.onAnchorClick, true);
        window.removeEventListener("scroll", this.onScroll);
        this.scrollRoot?.removeEventListener("scroll", this.onScroll);
        cancelAnimationFrame(this.scrollFrame);
        this._super(...arguments);
    },

    _onAnchorClick(ev) {
        const anchor = ev.target.closest('a[href^="/#"]');
        if (!anchor || anchor.classList.contains("dropdown-toggle")) {
            return;
        }
        const panel = anchor.closest(".offcanvas.show");
        if (panel) {
            setTimeout(() => panel.querySelector('[data-bs-dismiss="offcanvas"]')?.click(), 0);
        }
    },
});

/**
 * Hành vi của trang chủ trung tâm Anh ngữ:
 * - chọn độ tuổi để làm nổi bật chương trình phù hợp
 * - tab lọc thành tích học viên
 * - đếm số liệu khi cuộn tới
 * - điền sẵn chương trình vào form trên trang chi tiết khóa học
 * Trang vẫn đọc được đầy đủ khi tắt JS, vì số liệu và thẻ đã có sẵn trong HTML.
 */
publicWidget.registry.EduLanding = publicWidget.Widget.extend({
    selector: ".edu-landing",
    events: {
        "click .edu-chip": "_onChipClick",
        "click .edu-stu-tab": "_onStudentTab",
        "click .edu-smem-tab": "_onTeacherTab",
        "keydown .edu-smem-tab": "_onTeacherTabKeydown",
    },

    start() {
        this._setupCounters();
        this._setupHero();
        const programSelect = this.el.querySelector('select[name="Chương trình quan tâm"]');
        if (programSelect && this.el.dataset.program) {
            programSelect.value = this.el.dataset.program;
        }
        const teacherTab = this.el.querySelector('.edu-smem-tab[aria-selected="true"]');
        if (teacherTab) {
            this._selectTeacherTeam(teacherTab);
        }
        return this._super(...arguments);
    },

    destroy() {
        this.observer?.disconnect();
        this.heroObserver?.disconnect();
        this.hero?.removeEventListener("pointermove", this.onHeroPointer);
        this.hero?.removeEventListener("pointerleave", this.onHeroLeave);
        cancelAnimationFrame(this.heroFrame);
        this._super(...arguments);
    },

    _setupHero() {
        this.hero = this.el.querySelector(".edu-hero");
        if (!this.hero || window.matchMedia("(prefers-reduced-motion: reduce)").matches) { return; }
        if ("IntersectionObserver" in window) {
            this.heroObserver = new IntersectionObserver(([entry]) => {
                this.hero.classList.toggle("is-scene-paused", !entry.isIntersecting);
            });
            this.heroObserver.observe(this.hero);
        }
        if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) { return; }
        this.onHeroPointer = (ev) => {
            const rect = this.hero.getBoundingClientRect();
            this.heroPointer = [(ev.clientX - rect.left) / rect.width - 0.5,
                (ev.clientY - rect.top) / rect.height - 0.5];
            if (this.heroFrame) { return; }
            this.heroFrame = requestAnimationFrame(() => {
                this.hero.style.setProperty("--hero-x", `${this.heroPointer[0] * 22}px`);
                this.hero.style.setProperty("--hero-y", `${this.heroPointer[1] * 14}px`);
                this.heroFrame = null;
            });
        };
        this.onHeroLeave = () => {
            cancelAnimationFrame(this.heroFrame);
            this.heroFrame = null;
            this.hero.style.setProperty("--hero-x", "0px");
            this.hero.style.setProperty("--hero-y", "0px");
        };
        this.hero.addEventListener("pointermove", this.onHeroPointer, { passive: true });
        this.hero.addEventListener("pointerleave", this.onHeroLeave);
    },

    _onChipClick(ev) {
        const chip = ev.currentTarget;
        const alreadyActive = chip.classList.contains("is-active");
        this.el.querySelectorAll(".edu-chip").forEach((c) => {
            c.classList.remove("is-active");
            c.setAttribute("aria-pressed", "false");
        });
        const age = alreadyActive ? null : chip.dataset.age;
        if (age) {
            chip.classList.add("is-active");
            chip.setAttribute("aria-pressed", "true");
        }
        this.el.querySelectorAll(".edu-course-item").forEach((card) => {
            const matches = !age || card.dataset.ages.split(" ").includes(age);
            card.classList.toggle("is-match", Boolean(age) && matches);
            card.classList.toggle("is-dimmed", Boolean(age) && !matches);
        });
    },

    _onStudentTab(ev) {
        const tab = ev.currentTarget;
        const filter = tab.dataset.filter;
        this.el.querySelectorAll(".edu-stu-tab").forEach((t) => {
            const active = t === tab;
            t.classList.toggle("is-active", active);
            t.setAttribute("aria-selected", active ? "true" : "false");
        });
        let visible = 0;
        this.el.querySelectorAll(".edu-stu-col").forEach((col) => {
            const matches = filter === "all" || col.dataset.cat === filter;
            col.classList.toggle("is-hidden", !matches);
            if (matches) { visible++; }
        });
        const empty = this.el.querySelector(".edu-stu-empty");
        if (empty) { empty.hidden = visible > 0; }
    },

    _onTeacherTab(ev) {
        this._selectTeacherTeam(ev.currentTarget);
    },

    _selectTeacherTeam(tab) {
        const section = tab.closest(".edu-smem");
        section.querySelectorAll(".edu-smem-tab").forEach((button) => {
            const active = button === tab;
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-selected", String(active));
            button.tabIndex = active ? 0 : -1;
        });
        section.querySelectorAll(".edu-smem-panel").forEach((panel) => {
            panel.hidden = panel.dataset.team !== tab.dataset.team;
        });
    },

    _onTeacherTabKeydown(ev) {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(ev.key)) {
            return;
        }
        ev.preventDefault();
        const tabs = [...ev.currentTarget.closest(".edu-smem-tabs").querySelectorAll(".edu-smem-tab")];
        const index = tabs.indexOf(ev.currentTarget);
        const next = ev.key === "Home" ? 0 : ev.key === "End" ? tabs.length - 1 :
            (index + (ev.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
        this._selectTeacherTeam(tabs[next]);
        tabs[next].focus();
    },

    _setupCounters() {
        const counters = this.el.querySelectorAll(".edu-count[data-target]");
        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (!counters.length || reduceMotion || !("IntersectionObserver" in window)) {
            return;
        }
        this.observer = new IntersectionObserver(
            (entries) => {
                for (const entry of entries) {
                    if (entry.isIntersecting) {
                        this._animate(entry.target);
                        this.observer.unobserve(entry.target);
                    }
                }
            },
            { threshold: 0.4 }
        );
        counters.forEach((el) => this.observer.observe(el));
    },

    _animate(el) {
        const target = parseInt(el.dataset.target, 10);
        const suffix = el.dataset.suffix || "";
        const duration = 1200;
        const start = performance.now();
        const format = (n) => n.toLocaleString("vi-VN");
        const tick = (now) => {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = format(Math.round(target * eased)) + suffix;
            if (progress < 1) {
                requestAnimationFrame(tick);
            }
        };
        requestAnimationFrame(tick);
    },
});

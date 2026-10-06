/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Hành vi của trang chủ trung tâm Anh ngữ:
 * - chọn độ tuổi để làm nổi bật chương trình phù hợp
 * - tab lọc thành tích học viên
 * - đếm số liệu khi cuộn tới
 * - bấm thẻ chương trình thì điền sẵn chương trình vào form đăng ký
 * Trang vẫn đọc được đầy đủ khi tắt JS, vì số liệu và thẻ đã có sẵn trong HTML.
 */
publicWidget.registry.EduLanding = publicWidget.Widget.extend({
    selector: ".edu-landing",
    events: {
        "click .edu-chip": "_onChipClick",
        "click .edu-course-item[data-level]": "_onProgramClick",
        "click .edu-stu-tab": "_onStudentTab",
    },

    start() {
        this._setupCounters();
        return this._super(...arguments);
    },

    destroy() {
        this.observer?.disconnect();
        this._super(...arguments);
    },

    _onChipClick(ev) {
        const chip = ev.currentTarget;
        const alreadyActive = chip.classList.contains("is-active");
        this.el.querySelectorAll(".edu-chip").forEach((c) => c.classList.remove("is-active"));
        const age = alreadyActive ? null : chip.dataset.age;
        if (age) {
            chip.classList.add("is-active");
        }
        this.el.querySelectorAll(".edu-course-item").forEach((card) => {
            const matches = !age || card.dataset.ages.split(" ").includes(age);
            card.classList.toggle("is-match", Boolean(age) && matches);
            card.classList.toggle("is-dimmed", Boolean(age) && !matches);
        });
    },

    _onProgramClick(ev) {
        const select = this.el.querySelector('select[name="Chương trình quan tâm"]');
        if (select) {
            select.value = ev.currentTarget.dataset.level;
        }
    },

    _onStudentTab(ev) {
        const tab = ev.currentTarget;
        const filter = tab.dataset.filter;
        this.el.querySelectorAll(".edu-stu-tab").forEach((t) => {
            const active = t === tab;
            t.classList.toggle("is-active", active);
            t.setAttribute("aria-selected", active ? "true" : "false");
        });
        this.el.querySelectorAll(".edu-stu-col").forEach((col) => {
            col.classList.toggle("is-hidden", filter !== "all" && col.dataset.cat !== filter);
        });
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

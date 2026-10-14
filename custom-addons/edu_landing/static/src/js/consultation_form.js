/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import dom from "@web/legacy/js/core/dom";
import { jsonrpc } from "@web/core/network/rpc_service";
import "@website/snippets/s_website_form/000";

publicWidget.registry.s_website_form.include({
    async send(ev) {
        if (!this.el.hasAttribute("data-edu-database")) {
            return this._super(...arguments);
        }
        ev.preventDefault();
        if (this.eduSubmitting) {
            return;
        }
        const submit = this._super.bind(this);
        if (!this.check_error_fields({})) {
            return submit(ev);
        }
        this.eduSubmitting = true;
        const button = this.$el.find(".s_website_form_send");
        button.addClass("disabled").attr("disabled", "disabled");
        this.restoreBtnLoading = dom.addButtonLoadingEffect(button[0]);
        try {
            const session = await jsonrpc("/edu-landing/form-session", {});
            if (session.database !== this.el.dataset.eduDatabase) {
                this.update_status("error", "Phiên làm việc đã chuyển sang dữ liệu khác. Vui lòng mở lại website trước khi gửi thông tin.");
                return;
            }
            odoo.csrf_token = session.csrf_token;
        } catch {
            this.update_status("error", "Chưa kết nối được với trung tâm. Thông tin bạn nhập vẫn được giữ lại; vui lòng thử gửi lại.");
            return;
        } finally {
            this.eduSubmitting = false;
        }
        this.restoreBtnLoading();
        return submit(ev);
    },
});

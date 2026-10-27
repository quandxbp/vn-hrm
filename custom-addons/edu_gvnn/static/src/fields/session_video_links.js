/** @odoo-module **/

import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { UrlField } from "@web/views/fields/url/url_field";

class SessionVideoLinksField extends X2ManyField {
    static template = "edu_gvnn.SessionVideoLinksField";
    static components = { ...X2ManyField.components, UrlField };
    static props = { ...X2ManyField.props, linkField: String };

    onClick(event) {
        // Both columns use the same relation. The list renderer otherwise focuses
        // the first column with that field name, even when YouTube was clicked.
        if (!this.props.readonly) event.stopPropagation();
    }

    get parts() {
        return [...this.list.records].sort((a, b) => a.data.number - b.data.number);
    }

    async addPart() {
        if (this.props.readonly || !this.activeActions.create) return;
        const number = Math.max(1, ...this.list.records.map((part) => part.data.number || 1)) + 1;
        await this.onAdd({ context: { default_number: number }, editable: "bottom" });
    }
}

registry.category("fields").add("edu_session_video_links", {
    ...x2ManyField,
    component: SessionVideoLinksField,
    extractProps(fieldInfo, dynamicInfo) {
        return {
            ...x2ManyField.extractProps(fieldInfo, dynamicInfo),
            linkField: fieldInfo.options.link_field,
        };
    },
});

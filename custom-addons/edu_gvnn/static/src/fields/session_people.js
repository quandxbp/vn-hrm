/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class SessionStudentsField extends Component {
    static template = "edu_gvnn.SessionStudentsField";
    static props = { ...standardFieldProps };

    get students() {
        return this.props.record.data.student_badge_data || [];
    }
}

class SessionWeekField extends Component {
    static template = "edu_gvnn.SessionWeekField";
    static props = { ...standardFieldProps };

    get week() {
        const value = this.props.record.data[this.props.name];
        if (!value) return false;
        const label = value[1] || "";
        const split = label.indexOf(" (");
        return {
            color: value[0] % 5,
            title: split < 0 ? label : label.slice(0, split),
            dates: split < 0 ? "" : label.slice(split + 2).replace(/\)$/, ""),
        };
    }
}

registry.category("fields").add("edu_session_students", {
    component: SessionStudentsField,
    supportedTypes: ["char"],
});
registry.category("fields").add("edu_session_week", {
    component: SessionWeekField,
    supportedTypes: ["many2one"],
});

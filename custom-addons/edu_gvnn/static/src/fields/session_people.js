/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { CheckBox } from "@web/core/checkbox/checkbox";

class SessionStateToggleField extends Component {
    static template = "edu_gvnn.SessionStateToggleField";
    static props = { ...standardFieldProps };
    static components = { CheckBox };

    get isDone() {
        return this.props.record.data[this.props.name] === "done";
    }

    async onChange(isDone) {
        if (this.props.readonly) return;
        const original = this.props.record;
        const list = original.model.root;
        if (!original.isInEdition && !(await list.enterEditMode(original))) return;
        // Entering edit mode rebuilds record instances, so use the list's current record.
        const record = list.editedRecord;
        if (record && record.resId === original.resId) {
            await record.update({ [this.props.name]: isDone ? "done" : "cancel" });
        }
    }
}

class SessionStudentsField extends X2ManyField {
    static template = "edu_gvnn.SessionStudentsField";
    static components = { ...X2ManyField.components, Many2OneField };

    get students() {
        return this.props.record.data.student_badge_data || [];
    }

    get canEditStudents() {
        return !this.props.readonly && this.props.record.data.session_type !== "testing";
    }

    studentDomain(attendee) {
        const otherIds = this.list.records
            .filter((record) => record !== attendee && record.data.student_id)
            .map((record) => record.data.student_id[0]);
        return [["id", "not in", otherIds]];
    }

    async addStudent() {
        if (this.canEditStudents && this.activeActions.create && this.list.records.length < 2) {
            await this.onAdd({ editable: "bottom" });
        }
    }

    async removeStudent(attendee) {
        if (this.canEditStudents && this.activeActions.delete) {
            await this.list.delete(attendee);
        }
    }

    async setPresent(attendee, event) {
        if (this.canEditStudents) {
            await attendee.update({ present: event.target.checked });
        }
    }
}

class SessionStudentNamesField extends Component {
    static template = "edu_gvnn.SessionStudentsField";
    static props = { ...standardFieldProps };

    get canEditStudents() { return false; }
    get students() { return this.props.record.data.student_badge_data || []; }
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
    ...x2ManyField,
    component: SessionStudentsField,
    supportedTypes: ["one2many"],
});
registry.category("fields").add("edu_session_week", {
    component: SessionWeekField,
    supportedTypes: ["many2one"],
});
registry.category("fields").add("edu_session_student_names", {
    component: SessionStudentNamesField,
    supportedTypes: ["char"],
});

registry.category("fields").add("edu_session_state_toggle", {
    component: SessionStateToggleField,
    supportedTypes: ["selection"],
    extractProps: (fieldInfo, dynamicInfo) => ({ readonly: dynamicInfo.readonly }),
});

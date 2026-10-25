/** @odoo-module **/

import { registry } from "@web/core/registry";
import { BadgeField, badgeField } from "@web/views/fields/badge/badge_field";

class TeacherBadgeField extends BadgeField {
    get classFromDecoration() {
        const teacher = this.props.record.data[this.props.name];
        const color = teacher ? teacher[0] % 8 : 0;
        return `edu_teacher_badge edu_teacher_badge_${color}`;
    }
}

registry.category("fields").add("edu_teacher_badge", {
    ...badgeField,
    component: TeacherBadgeField,
    supportedTypes: ["many2one"],
});

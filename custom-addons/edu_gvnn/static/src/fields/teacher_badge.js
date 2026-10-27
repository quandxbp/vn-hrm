/** @odoo-module **/

import { registry } from "@web/core/registry";
import { BadgeField, badgeField } from "@web/views/fields/badge/badge_field";
import { Many2OneField, many2OneField } from "@web/views/fields/many2one/many2one_field";
import { xml } from "@odoo/owl";

class TeacherBadgeField extends BadgeField {
    static template = xml`
        <t t-if="props.readonly" t-call="web.BadgeField"/>
        <Many2OneField t-else="" t-props="props"/>
    `;
    static components = { Many2OneField };
    static props = Many2OneField.props;
    static defaultProps = Many2OneField.defaultProps;

    get classFromDecoration() {
        const teacher = this.props.record.data[this.props.name];
        const color = teacher ? teacher[0] % 8 : 0;
        return `edu_teacher_badge edu_teacher_badge_${color}`;
    }
}

registry.category("fields").add("edu_teacher_badge", {
    ...many2OneField,
    component: TeacherBadgeField,
    extractProps: (fieldInfo, dynamicInfo) => ({
        ...many2OneField.extractProps(fieldInfo, dynamicInfo),
        ...badgeField.extractProps(fieldInfo, dynamicInfo),
    }),
    supportedTypes: ["many2one"],
});

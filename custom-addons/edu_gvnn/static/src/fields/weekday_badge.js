/** @odoo-module **/

import { registry } from "@web/core/registry";
import { BadgeField, badgeField } from "@web/views/fields/badge/badge_field";

class WeekdayBadgeField extends BadgeField {
    get classFromDecoration() {
        const value = this.props.record.data[this.props.name];
        const isDate = this.props.record.fields[this.props.name].type === "date";
        const weekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
        const weekday = isDate ? weekdays[value?.weekday - 1] : value;
        const baseClass = isDate ? "edu_weekday_badge edu_date_badge" : "edu_weekday_badge";
        return weekdays.includes(weekday)
            ? `${baseClass} edu_weekday_badge_${weekday.toLowerCase()}`
            : baseClass;
    }
}

registry.category("fields").add("edu_weekday_badge", {
    ...badgeField,
    component: WeekdayBadgeField,
    supportedTypes: ["selection"],
});

registry.category("fields").add("edu_weekday_date_badge", {
    ...badgeField,
    component: WeekdayBadgeField,
    supportedTypes: ["date"],
});

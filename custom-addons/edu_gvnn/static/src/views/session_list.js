/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { listView } from "@web/views/list/list_view";

class SessionListController extends ListController {
    static template = "edu_gvnn.SessionListView";

    get actionBarButtons() {
        return this.archInfo.headerButtons.filter(
            (button) => button.display === "always" && !this.evalViewModifier(button.invisible)
        );
    }

    get actionBarGroups() {
        const buttons = this.actionBarButtons;
        const isFileAction = (button) => (button.className || "").split(/\s+/).includes("edu_session_action_file");
        return [
            { key: "main", buttons: buttons.filter((button) => !isFileAction(button)) },
            { key: "files", buttons: buttons.filter(isFileAction) },
        ];
    }
}

class SessionListRenderer extends ListRenderer {
    formatAggregateValue(group, column) {
        if (["time_start", "time_end"].includes(column.name)) {
            return "";
        }
        return super.formatAggregateValue(group, column);
    }
}

registry.category("views").add("edu_session_list", {
    ...listView,
    Controller: SessionListController,
    Renderer: SessionListRenderer,
});

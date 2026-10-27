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
    focusCell(column, forward = true) {
        if (column?.widget === "edu_session_video_links" && this.editedRecord &&
            !this.isCellReadonly(column, this.editedRecord)) {
            // Drive and YouTube are two occurrences of the same relation field.
            // Match the column occurrence instead of always choosing the first.
            const siblings = this.state.columns.filter((col) => col.name === column.name);
            const index = siblings.findIndex((col) => col.id === column.id);
            const cells = this.tableRef.el.querySelectorAll(
                `.o_selected_row td[name='${column.name}']`
            );
            const input = cells[index]?.querySelector("input:not(:disabled)");
            if (input) {
                this.focus(input);
                this.lastEditedCell = { column, record: this.editedRecord };
                return;
            }
        }
        return super.focusCell(column, forward);
    }

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

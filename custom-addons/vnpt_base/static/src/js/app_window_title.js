/** @odoo-module alias=web.window.title **/

import { WebClient } from "@web/webclient/webclient";
import {patch} from "@web/core/utils/patch";

patch(WebClient.prototype, {
    setup() {
        const title = document.title || "VNPT HRM";
        super.setup();
        this.title.setParts({ zopenerp: title });
    }
});

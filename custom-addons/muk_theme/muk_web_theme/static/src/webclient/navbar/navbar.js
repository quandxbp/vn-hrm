/** @odoo-module **/

import { patch } from '@web/core/utils/patch';
import { useService } from '@web/core/utils/hooks';

import { NavBar } from '@web/webclient/navbar/navbar';
import { AppsMenu } from "@muk_web_theme/webclient/appsmenu/appsmenu";

patch(NavBar.prototype, {
    setup() {
        super.setup();
        this.appMenuService = useService('app_menu');
        this.action = useService('action');
    },

    async onClickDashboard(ev) {
        ev.stopPropagation();
        ev.preventDefault();

        const app = this.appMenuService.getAppsMenuItems().find((app) => app.xmlid === "vnpt_hrm_dashboard.vnpt_hrm_dashboard_root_menu");

        if (app) {
            await app.action(); // Đây sẽ gọi chính xác action của app đó (mở module)
        } else {
            console.warn("App không tồn tại trong menu!");
        }
    }


});

patch(NavBar, {
    components: {
        ...NavBar.components,
        AppsMenu,
    },
});

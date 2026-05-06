/** @odoo-module **/

import { url } from '@web/core/utils/urls';
import { useService } from '@web/core/utils/hooks';

import { Component, onWillUnmount, useState } from '@odoo/owl';

export class AppsBar extends Component {
	static template = 'muk_web_appsbar.AppsBar';
    static props = {};
	setup() {
		this.companyService = useService('company');
        this.appMenuService = useService('app_menu');
        this.state = useState({ collapsed: false });

    	if (this.companyService.currentCompany.has_appsbar_image) {
            this.sidebarImageUrl = url('/web/image', {
                model: 'res.company',
                field: 'appbar_image',
                id: this.companyService.currentCompany.id,
            });
    	}
    	const renderAfterMenuChange = () => {
            this.render();
        };
        this.env.bus.addEventListener(
        	'MENUS:APP-CHANGED', renderAfterMenuChange
        );
        onWillUnmount(() => {
            this.env.bus.removeEventListener(
            	'MENUS:APP-CHANGED', renderAfterMenuChange
            );
        });

        this.toggleSidebar = () => {
            this.state.collapsed = !this.state.collapsed;
            document.body.classList.toggle('mk_sidebar_type_small', this.state.collapsed);
            document.body.classList.toggle('mk_sidebar_type_large', !this.state.collapsed);
        };
    }
}

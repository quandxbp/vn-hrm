from odoo import api, models, tools


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    @tools.ormcache('frozenset(self.env.user.groups_id.ids)', 'debug')
    def _visible_menu_ids(self, debug=False):
        visible = super()._visible_menu_ids(debug=debug)
        user = self.env.user
        if not user.has_group('edu_gvnn.group_edu_staff') or user.has_group('base.group_system'):
            return visible
        roots = self.browse()
        for xmlid in ('edu_gvnn.menu_edu_root',
                      'vnpt_hrm_dashboard.vnpt_hrm_dashboard_root_menu'):
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                roots |= menu
        # Bypass visibility filtering while finding descendants to avoid recursion.
        allowed = self.sudo().with_context(**{'ir.ui.menu.full_list': True}).search([
            ('id', 'child_of', roots.ids),
        ])
        return visible.intersection(allowed.ids)

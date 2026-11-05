from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEduMenuVisibility(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.extra = cls.env['ir.ui.menu'].create({
            'name': 'Other application',
            'action': 'ir.actions.client,%s' % cls.env['ir.actions.client'].create({
                'name': 'Other application', 'tag': 'menu_visibility_test',
            }).id,
        })

    def _user(self, group):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Menu test', 'login': 'menu-test-%s' % group,
            'groups_id': [Command.set([self.env.ref(group).id])],
        })

    def _assert_education_roots(self, group):
        menus = self.env['ir.ui.menu'].with_user(self._user(group))
        visible = menus._visible_menu_ids()
        self.assertNotIn(self.extra.id, visible)
        roots = menus.browse(visible).filtered(lambda menu: not menu.parent_id)
        allowed = {self.env.ref('edu_gvnn.menu_edu_root').id}
        home = self.env.ref('vnpt_hrm_dashboard.vnpt_hrm_dashboard_root_menu', False)
        if home:
            allowed.add(home.id)
            self.assertIn(home.id, visible)
        self.assertEqual(set(roots.ids), allowed)
        self.assertIn(self.env.ref('edu_gvnn.menu_edu_session').id, visible)
        self.assertNotIn(self.extra.id, menus._visible_menu_ids(debug=True))
        loaded = menus.load_menus(debug=False)
        self.assertEqual(set(loaded['root']['children']), allowed)

    def test_staff_sees_only_home_and_gvnn(self):
        self._assert_education_roots('edu_gvnn.group_edu_staff')

    def test_manager_sees_only_home_and_gvnn(self):
        self._assert_education_roots('edu_gvnn.group_edu_manager')

    def test_system_admin_retains_other_applications(self):
        menus = self.env['ir.ui.menu'].with_user(self._user('base.group_system'))
        self.assertIn(self.extra.id, menus._visible_menu_ids())

    def test_non_education_user_keeps_other_applications(self):
        menus = self.env['ir.ui.menu'].with_user(self._user('base.group_user'))
        self.assertIn(self.extra.id, menus._visible_menu_ids())

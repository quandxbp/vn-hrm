from odoo import models, api


class Menu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _visible_menu_ids(self, debug):
        visible_menu_ids = super()._visible_menu_ids(debug)
        user = self.env.user

        # Get menu IDs for hr_holidays and hr_attendance
        menu_hr_holidays = self.env.ref("hr_holidays.menu_hr_holidays_root").id
        menu_hr_attendance = self.env.ref("hr_attendance.menu_hr_attendance_root").id

        # Check if the user has the necessary access rights
        has_holidays_access = user.has_group("hr_holidays.group_hr_holidays_user")
        has_attendance_access = user.has_group("hr_attendance.group_hr_attendance_manager")

        # Hide menus if the user has no employee_id and lacks access rights
        if not user.employee_id:
            menus_to_hide = set()
            if not has_holidays_access:
                menus_to_hide.add(menu_hr_holidays)
            if not has_attendance_access:
                menus_to_hide.add(menu_hr_attendance)

            visible_menu_ids -= menus_to_hide

        return visible_menu_ids
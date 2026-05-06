from . import models
from . import controllers

# from odoo import api, SUPERUSER_ID
#
#
# def post_init_hook(cr):
#     env = api.Environment(cr, SUPERUSER_ID, {})
#     dashboard_action = env.ref('vnpt_hrm_dashboard.action_owl_hrm_dashboard', raise_if_not_found=False)
#
#     # Set the dashboard action for all users who have no home action set
#     env['res.users'].search([('action_id', '=', False)]).write({'action_id': dashboard_action.id})
# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    edu_block_minutes = fields.Integer(
        'Số phút mỗi buổi', config_parameter='edu_gvnn.block_minutes', default=30)
    edu_block_price = fields.Float(
        'Đơn giá mỗi buổi (đ)', config_parameter='edu_gvnn.block_price', default=100000)
    edu_default_blocks = fields.Integer(
        'Số buổi mặc định trên phiếu thu', config_parameter='edu_gvnn.default_blocks', default=20)
    edu_fee_out_threshold = fields.Float(
        'Ngưỡng hết học phí: số dư nhỏ hơn (đ)', config_parameter='edu_gvnn.fee_out_threshold', default=1)
    edu_fee_low_threshold = fields.Float(
        'Ngưỡng gần hết học phí: số dư nhỏ hơn (đ)', config_parameter='edu_gvnn.fee_low_threshold',
        default=300000)
    edu_absent_weeks = fields.Integer(
        'Số tuần nghỉ liên tiếp để cảnh báo đỏ', config_parameter='edu_gvnn.absent_weeks', default=3)
    edu_stop_suggest_weeks = fields.Integer(
        'Số tuần nghỉ để gợi ý ngưng học', config_parameter='edu_gvnn.stop_suggest_weeks', default=4)

    def set_values(self):
        super().set_values()
        students = self.env['edu.student'].search([])
        students.modified(['balance', 'state'])

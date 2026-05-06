# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

CONFIG_PARAM_WEB_WINDOW_TITLE = "web.base.title"

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    web_window_title = fields.Char('Tiêu đề của trang',default="VNPT HRM")
    login_system_title = fields.Char('Tên hệ thống khi đăng nhập',default="HỆ THỐNG QUẢN TRỊ NGUỒN NHÂN LỰC DOANH NGHIỆP")

    orientation = fields.Selection(selection=[('default', 'Mặc định'),
                                              ('left', 'Trái'),
                                              ('middle', 'Giữa'),
                                              ('right', 'Phải')],
                                   string="Hướng hiện thị",
                                   help="Loại hiển thị trang đăng nhập",
                                   config_parameter="vnpt_base.orientation")
    background = fields.Selection(selection=[('color', 'Chọn màu'),
                                             ('image', 'Hình ảnh'),
                                             ('url', 'Đường dẫn')],
                                  string="Hình nền",
                                  help="Hình nền của trang đăng nhập",
                                  config_parameter="vnpt_base.background")
    image = fields.Binary(string="Image", help="Chọn hình ảnh cho nền"
                                               "of login page")
    url = fields.Char(string="URL", help="Chọn đường dẫn cho hình ảnh",
                      config_parameter="vnpt_base.url")
    color = fields.Char(string="Color", help="Chọn màu cho nền của trang đăng nhập",
                        config_parameter="vnpt_base.color")

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ir_config = self.env['ir.config_parameter'].sudo()
        web_window_title = ir_config.get_param(CONFIG_PARAM_WEB_WINDOW_TITLE, default='')
        res.update(
            web_window_title=web_window_title
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ir_config = self.env['ir.config_parameter'].sudo()
        ir_config.set_param(CONFIG_PARAM_WEB_WINDOW_TITLE, self.web_window_title or "")

    @api.model
    def get_values(self):
        """Super the get_values function to get the field values."""
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(image=params.get_param('vnpt_base.image'))
        return res

    def set_values(self):
        """Super the set_values function to save the field values."""
        super(ResConfigSettings, self).set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('vnpt_base.image', self.image)

    @api.onchange('orientation')
    def onchange_orientation(self):
        """Set background field to false for hiding option to customize login
           page background """
        if self.orientation == 'default':
            self.background = False

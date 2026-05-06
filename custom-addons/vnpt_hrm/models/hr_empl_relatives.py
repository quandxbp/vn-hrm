from odoo import api, fields, models
from odoo.exceptions import ValidationError

class HrEmployeeRelativesShip(models.Model):
    _name = "hr.employee.relatives.relationship"

    code = fields.Char(string="Mã")
    name = fields.Char(string="Quan hệ", required=True)
    male_symmetrical_name = fields.Char(string="Quan hệ đối xứng (Nam)")
    female_symmetrical_name = fields.Char(string="Quan hệ đối xứng (Nữ)")
    active = fields.Boolean(default=True)

class HrEmployeeRelatives(models.Model):
    _name = "hr.employee.relatives"

    name = fields.Char(string="Họ và tên", required=True)
    relation_ship_id = fields.Many2one('hr.employee.relatives.relationship', string="Mối quan hệ", required=True)
    birth_year = fields.Char(string="Năm sinh")
    hometown = fields.Char(string="Quê quán")
    work_unit = fields.Char(string="Đơn vị công tác")
    is_dead = fields.Boolean(string="Đã mất?")
    is_dependent = fields.Boolean(string="Là người phụ thuộc?")
    address = fields.Char(string="Địa chỉ nơi ở")
    job_title = fields.Char(string="Nghề nghiệp")
    org_name = fields.Char(string="TV tổ chức CT&XH	")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên", readonly=True)

    attachment_id = fields.Many2one(
        "ir.attachment", string="File đính kèm", ondelete="cascade", auto_join=True, copy=False, index=True
    )
    note = fields.Text(string="Ghi chú")

    @api.constrains('is_dead', 'is_dependent')
    def _check_dependent_status(self):
        for record in self:
            if record.is_dead and record.is_dependent:
                raise ValidationError("Người đã mất không thể là người phụ thuộc!")

class HrEmployeePolicyRelatives(models.Model):
    _name = "hr.employee.policy.relatives"

    name = fields.Char(string="Họ và tên", required=True)
    relation_ship_id = fields.Many2one('hr.employee.relatives.relationship', string="Mối quan hệ", required=True)
    employee_id = fields.Many2one('hr.employee', string="Nhân viên", readonly=True)

    dead_year = fields.Char(string="Năm mất")
    fight_year = fields.Char(string="Năm chiến đấu")
    fight_place = fields.Text(string="Chiến trường")
    relatives_type = fields.Selection([
        ('cv_cao_cap', 'Thương binh'),
        ('cv_chinh', 'Bệnh binh'),
        ('cv', 'Liệt sĩ')], string="Đối tượng thân nhân")
    attachment_id = fields.Many2one(
        "ir.attachment", string="File đính kèm", ondelete="cascade", auto_join=True, copy=False, index=True
    )
    note = fields.Text(string="Ghi chú")

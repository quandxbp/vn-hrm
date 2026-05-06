from odoo import api, fields, models

class HrTrinhDoVanHoa(models.Model):
    _name = "hr.trinh.do.van.hoa"

    sequence = fields.Integer(string="Thứ tự", default=10)
    code = fields.Char(string="Mã")
    name = fields.Char(string="Tên", required=True)

class HrHocHam(models.Model):
    _name = "hr.hoc.ham"

    sequence = fields.Integer(string="Thứ tự", default=10)
    code = fields.Char(string="Mã")
    name = fields.Char(string="Tên", required=True)

class HrEmployeeEducationLevel(models.Model):
    _name = "hr.employee.education.level"

    code = fields.Char(string="Mã")
    name = fields.Char(string="Tên", required=True)

class HrEmployeeEducation(models.Model):
    _name = "hr.employee.education"

    employee_id = fields.Many2one('hr.employee', string="Nhân viên", readonly=True)
    type = fields.Selection([
        ('trong_nuoc', 'Trong nước'),
        ('nuoc_ngoai', 'Nước ngoài')], string="Loại đào tạo", required=True)
    major = fields.Char(string="Chuyên ngành đào tạo")
    school = fields.Char(string="Cơ sở đào tạo")
    level_id = fields.Many2one('hr.employee.education.level',
                               string="Trình độ đào tạo", required=True)
    date_start = fields.Date(string="Ngày bắt đầu", required=True)
    date_end = fields.Date(string="Ngày kết thúc")

    note = fields.Text(string="Ghi chú")
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string="Files đính kèm",
    )

    _sql_constraints = [
        ('date_check', "CHECK ((date_start <= date_end OR date_end IS NULL))",
         "Ngày bắt đầu phải trước ngày kết thúc!"),
    ]

# class HrEmployeeCertificateType(models.Model):
#     _name = "hr.employee.certificate.type"
#
#     code = fields.Char(string="Mã")
#     name = fields.Char(string="Tên", required=True)
#     type = fields.Char(string="Loại chứng chỉ")
#     is_international = fields.Boolean(default=False)

class HrEmployeeCertificate(models.Model):
    _name = "hr.employee.certificate"

    employee_id = fields.Many2one('hr.employee', string="Nhân viên", readonly=True)
    name = fields.Char(string="Văn bằng chứng chỉ", required=True)
    type = fields.Char(String="Loại chứng chỉ")
    major = fields.Char(string="Chuyên ngành đào tạo")
    school = fields.Char(string="Cơ sở đào tạo")
    location = fields.Char(string="Địa điểm đào tạo")

    date = fields.Date(string="Ngày cấp chứng chỉ", required=True)
    date_start = fields.Date(string="Ngày bắt đầu")
    date_end = fields.Date(string="Ngày kết thúc")

    note = fields.Text(string="Ghi chú")
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string="Files đính kèm",
    )

    _sql_constraints = [
        ('date_check', "CHECK ((date_start <= date_end OR date_end IS NULL))",
         "Ngày bắt đầu phải trước ngày kết thúc!"),
    ]
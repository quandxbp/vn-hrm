from odoo import api, fields, models


class HrWorkProcess(models.Model):
    _name = "hr.work.process"

    employee_id = fields.Many2one('hr.employee', string="Nhân viên", readonly=True)
    work_unit = fields.Char(string="Đơn vị công tác", required=True)
    job_title = fields.Char(string="Chức danh công việc")
    job_position = fields.Char(string="Vị trí công việc")
    job_type = fields.Selection([
        ('chuyen_vien', 'Chuyên viên'),
        ('quan_ly', 'Quản lý'),
        ('kiem_soat_vien', 'Kiểm soát viên')], string="Phân loại chức danh")
    date_start = fields.Date(string="Ngày bắt đầu", required=True)
    date_end = fields.Date(string="Ngày kết thúc")

    note = fields.Text(string="Ghi chú")
    description = fields.Text(string="Mô tả")
    leave_job_reason = fields.Char(string="Lý do nghỉ việc")
    salary = fields.Float(string="Mức thu nhập", digits=(16, 2))

    _sql_constraints = [
        ('date_check', "CHECK ((date_start <= date_end OR date_end IS NULL))",
         "Ngày bắt đầu phải trước ngày kết thúc!"),
    ]
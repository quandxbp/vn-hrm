from odoo import api, fields, models

from odoo import api, fields, models


class HrInsuranceRegistPlace(models.Model):
    _name = "hr.insurance.regist.place"
    _description = "Nơi khám chữa bệnh"

    code = fields.Char(string="Mã")
    name = fields.Char(string="Tên", required=True)
    address = fields.Char(string="Địa chỉ")

class HrInsuranceSalary(models.Model):
    _name = "hr.insurance.salary"
    _description = "Lương bảo hiểm"

    insurance_id = fields.Many2one('hr.insurance', string="Hồ sơ bảo hiểm", required=True, ondelete='cascade')

    state = fields.Selection([
        ('not_paid', 'Chưa đóng'),
        ('paid', 'Đóng bảo hiểm')
    ], string="Trạng thái đóng bảo hiểm", required=True, default='not_paid')

    position = fields.Char(string="Chức danh bảo hiểm")
    salary_level = fields.Integer(string="Bậc lương BHXH")
    department_id = fields.Many2one('hr.department', string="Đơn vị")

    date_salary = fields.Date(string="Từ ngày", required=True)
    salary_coefficient = fields.Float(string="Hệ số lương đóng BHXH", default=0.0)
    allowance_coefficient = fields.Float(string="Hệ số phụ cấp đóng BHXH", default=0.0)
    insurance_salary = fields.Monetary(string="Mức đóng bảo hiểm xã hội", currency_field='currency_id')

    description = fields.Text(string="Diễn giải")

    currency_id = fields.Many2one('res.currency', string="Loại tiền tệ",
                                  default=lambda self: self.env.company.currency_id)

class HrInsurance(models.Model):
    _name = "hr.insurance"
    _description = "Quản lý bảo hiểm"
    _inherit = ['mail.thread.main.attachment', 'mail.activity.mixin']

    employee_id = fields.Many2one('hr.employee', string="Nhân viên", required=True, unique=True, ondelete="cascade")
    department_id = fields.Many2one(related="employee_id.department_id", store=True)
    regist_place_id = fields.Many2one('hr.insurance.regist.place',
                                      string="Nơi đăng ký khám chữa bệnh")
    image_1024 = fields.Image(related='employee_id.image_1024', string="Ảnh nhân viên", max_width=1024, max_height=1024)
    image_128 = fields.Image(related='employee_id.image_128', string="Ảnh nhân viên", max_width=128, max_height=128)
    employee_name = fields.Char(related='employee_id.name')
    employee_code = fields.Char(related='employee_id.code')
    department_name = fields.Char(related='employee_id.department_id.name')
    identification_id = fields.Char(related='employee_id.identification_id')
    identification_date = fields.Date(related='employee_id.identification_date')
    identification_place = fields.Char(related='employee_id.identification_place')
    gender = fields.Selection(related='employee_id.gender')
    birthday = fields.Date(related='employee_id.birthday')

    # Information
    so_so = fields.Char(string="Số sổ BHXH")
    ma_don_vi_quan_ly_bhxh = fields.Char(string="Mã đơn vị quản lý BHXH")
    co_quan_quan_ly_bhxh = fields.Char(string="Cơ quan quản lý BHXH")


    start_date_bhxh = fields.Date(string="Ngày bắt đầu đóng BHXH")
    end_date_bhxh = fields.Date(string="Ngày bắt đầu đóng BHXH")
    start_date_bhtn = fields.Date(string="Ngày bắt đầu đóng BHTN")

    so_the_bhyt = fields.Char(string="Số thẻ BHYT")
    giao_the_date = fields.Date(string="Ngày giao thẻ")
    tra_the_date = fields.Date(string="Ngày trả thẻ")

    so_status = fields.Selection([
        ('chua_nhan_so', 'Chưa nhận sổ'),
        ('da_nhan_so', 'Đã nhận sổ'),
        ('da_tra_so', 'Đã trả sổ')], string="Trạng thái sổ")

    # Lương bảo hiểm
    salary_ids = fields.One2many('hr.insurance.salary', 'insurance_id', string="Lương bảo hiểm")

    latest_salary_id = fields.Many2one(
        'hr.insurance.salary',
        string="Lương bảo hiểm hiện tại",
        compute="_compute_latest_salary",
        store=True,  # Ensures the field is stored in the database
        search="_search_latest_salary",  # Custom search function
    )

    @api.model
    def _search_latest_salary(self, operator, value):
        """Custom search function for latest_salary_id"""
        # Find records that match the latest salary criteria
        salaries = self.env['hr.insurance.salary'].search([])  # Adjust search criteria as needed
        insurance_ids = salaries.mapped('insurance_id').ids  # Adjust based on your logic

        return [('id', 'in', insurance_ids)]

    salary_date = fields.Date(string="Ngày hưởng lương theo bảo hiểm", related="latest_salary_id.date_salary",
                              store=True)
    position = fields.Char(string="Chức danh bảo hiểm", related="latest_salary_id.position", store=True)
    salary_level = fields.Integer(string="Bậc lương BHXH", related="latest_salary_id.salary_level", store=True)
    salary_coefficient = fields.Float(string="Hệ số lương BHXH", related="latest_salary_id.salary_coefficient",
                                      store=True)
    allowance_coefficient = fields.Float(string="Hệ số phụ cấp BHXH", related="latest_salary_id.allowance_coefficient",
                                         store=True)
    insurance_salary = fields.Monetary(string="Lương đóng BHXH", related="latest_salary_id.insurance_salary",
                                       store=True, currency_field='currency_id')

    currency_id = fields.Many2one('res.currency', string="Loại tiền tệ",
                                  default=lambda self: self.env.company.currency_id)

    @api.depends('salary_ids')
    def _compute_latest_salary(self):
        for record in self:
            record.latest_salary_id = record.salary_ids.sorted(lambda s: s.date_salary, reverse=True)[:1].id

    @api.depends("employee_id")
    def _compute_display_name(self):
        super()._compute_display_name()
        for rec in self:
            if rec.employee_id:
                rec.display_name = f"Hồ sơ - {rec.employee_id.name}"
            else:
                rec.display_name = "Hồ sơ bảo hiểm mới"

    _sql_constraints = [
        ('employee_id_unique', 'unique(employee_id)', 'Mỗi nhân viên chỉ được tạo một hồ sơ bảo hiểm.')
    ]
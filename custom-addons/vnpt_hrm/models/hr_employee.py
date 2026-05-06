from odoo import api, fields, models

class HrEmployeeBase(models.AbstractModel):
    _inherit = "hr.employee.base"

    department_name = fields.Char(related='department_id.name', string="Tên phòng/Ban")
    code = fields.Char(string="Mã nhân viên", copy=False, tracking=True, index='trigram', readonly=True)

    different_name = fields.Char(string="Tên khác", tracking = True)
    employee_relatives_ids = fields.One2many(
        'hr.employee.relatives', 'employee_id', string="Thân nhân", tracking = True)

    employee_policy_relatives_ids = fields.One2many(
        'hr.employee.policy.relatives', 'employee_id', string="Thân nhân chính sách", tracking = True)
    employee_education_ids = fields.One2many(
        'hr.employee.education', 'employee_id', string="Trình độ học vấn")
    employee_work_process_ids = fields.One2many('hr.work.process', 'employee_id', string="Quá trình công tác"
                                                , tracking = True)
    employee_certificate_ids = fields.One2many(
        'hr.employee.certificate', 'employee_id', string="Chứng chỉ/Chứng nhận", tracking = True)

    # VNPT EXTRA FIELDS

    # Thông tin chung
    identification_date = fields.Date(string="Ngày cấp CMND/CCCD", tracking = True)
    identification_place = fields.Char(string="Nơi cấp CMND/CCCD", default="Cục Cảnh sát QLHC&TTXH", tracking = True)
    passport_date = fields.Date(string="Ngày cấp Passport", tracking = True)
    passport_place = fields.Char(string="Nơi cấp Passport", tracking = True)
    nguyen_quan = fields.Char(string="Nguyên quán", tracking = True)
    ethnicity_id = fields.Many2one('hr.ethnicity', string="Dân tộc", tracking = True)
    religion_id = fields.Many2one('hr.religion', string="Tôn giáo", tracking = True)

    trinh_do_van_hoa_id = fields.Many2one('hr.trinh.do.van.hoa', string="Trình độ văn hóa", tracking = True)
    thuoc_he = fields.Char(string="Thuộc hệ", tracking = True)
    hoc_ham_id = fields.Many2one('hr.hoc.ham', string="Học hàm", tracking = True)
    ly_luan_chinh_tri = fields.Selection([
        ('cu_nhan', 'Cử nhân'),
        ('so_cap', 'Sơ cấp'),
        ('trung_cap', 'Trung cấp'),
        ('cao_cap', 'Cao cấp')], string="Lý luận chính trị", tracking = True)
    quan_ly_nha_nuoc = fields.Selection([
        ('cv_cao_cap', 'Chuyên viên cao cấp'),
        ('cv_chinh', 'chuyên viên chính'),
        ('cv', 'Chuyên viên'),
        ('qlnn', 'Kiến thức quản lý nhà nước'),
        ('llcchc', 'Lý luận Chính trị - Hành chính')], string="Quản lý nhà nước", tracking = True)
    ky_nang_mem = fields.Char(string="Kỹ năng mềm", tracking = True)

    # Thông tin tuyển dụng
    ngay_td = fields.Date(string="Ngày tuyển dụng", tracking = True)
    quyet_dinh_td = fields.Char(string="Số QĐ tuyển dụng", tracking = True)
    don_vi_tuyen_dung = fields.Char(string="Đơn vị TD", tracking = True)
    vi_tri_tuyen_dung = fields.Char(string="Vị trí TD", tracking = True)
    ngay_vao_don_vi = fields.Date(string="Ngày vào đơn vị", tracking = True)
    ngay_vao_don_vi_ct = fields.Date(string="Ngày vào đơn vị CT", tracking = True)

    # Thông tin sức khoẻ
    tinh_trang_suc_khoe = fields.Char(string="Tình trạng", tracking = True)
    chieu_cao = fields.Float(string="Chiều cao", tracking = True)
    can_nang = fields.Float(string="Cân nặng", tracking = True)
    nhom_mau = fields.Selection([
        ('O', 'O'), ('A', 'A'), ('B', 'B'), ('AB', 'AB'), ('Rh', 'Rh')], string="Nhóm máu", tracking = True)

    # Thông tin ngân hàng/thuế
    ma_so_thue = fields.Char(string="Mã số thuế", tracking = True)
    bank_id = fields.Many2one('res.bank', string="Ngân hàng", tracking = True)
    bank_branch = fields.Char(string="Chi nhánh ngân hàng", tracking = True)
    bank_account = fields.Char(string="Số tài khoản", tracking = True)

    # Thông tin đảng
    is_dang_vien = fields.Boolean(string="Là đảng viên", tracking = True)
    ngay_vao_dang = fields.Date(string="Ngày vào đảng", tracking = True)
    chi_bo_dang = fields.Char(string="Tại chi bộ Đảng", tracking = True)
    ngay_vao_dang_chinh_thuc = fields.Date(string="Ngày vào đảng chính thức", tracking = True)
    chi_bo_dang_chinh_thuc = fields.Char(string="Tại chi bộ Đảng", tracking = True)
    chuc_vu_dang = fields.Char(string="Chức vụ Đảng", tracking = True)

    # Thông tin đoàn
    is_doan_vien = fields.Boolean(string="Là đoàn viên", tracking = True)
    ngay_vao_doan = fields.Date(string="Ngày vào đoàn", tracking = True)
    noi_ket_nap_doan = fields.Date(string="Nơi kết nạp", tracking = True)
    chuc_vu_doan = fields.Char(string="Chức vụ Đoàn", tracking = True)

    total_dependant = fields.Integer(string="Số người phụ thuộc", compute="compute_total_dependant", store=True)

    @api.depends('employee_relatives_ids')
    def compute_total_dependant(self):
        for record in self:
            record.total_dependant = len(record.employee_relatives_ids.filtered(lambda e: e.is_dependent))

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    insurance_count = fields.Integer(compute='_compute_insurance_count')
    insurance_id = fields.One2many('hr.insurance', 'employee_id', string='Bảo hiểm', ondelete="cascade")

    # Thông tin công việc
    so_bhxh = fields.Char(string="Số BHXH", related='insurance_id.so_so', readonly=True)
    full_address = fields.Char("Địa chỉ", compute="_compute_full_address", store=True)
    # full_address = fields.Char("Địa chỉ")
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string="Thêm tài liệu",
        tracking = True
    )

    @api.depends("private_street", "private_street2", "private_city", "private_state_id", "private_country_id")
    def _compute_full_address(self):
        for rec in self:
            address_parts = [
                rec.private_street,
                rec.private_street2,
                rec.private_city,
                rec.private_state_id.name if rec.private_state_id else None,
                rec.private_country_id.name if rec.private_country_id else None,
            ]
            # Lọc bỏ các phần None hoặc rỗng, rồi nối bằng dấu phẩy
            rec.full_address = ", ".join(part for part in address_parts if part)

    @api.depends('insurance_id')
    def _compute_insurance_count(self):
        for rec in self:
            rec.insurance_count = len(rec.insurance_id)

    def action_open_insurance(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('vnpt_hrm.hr_insurance_action')
        action['context'] = {
            'default_employee_id': self.id,
        }
        action['views'] = [(self.env.ref('vnpt_hrm.hr_insurance_view_form').id, 'form')]
        action['target'] = 'new'

        if self.insurance_id:
            action['res_id'] = self.insurance_id.id
        else:
            action['res_id'] = False

        return action

    @api.depends("code")
    def _compute_display_name(self):
        super()._compute_display_name()
        for rec in self:
            if rec.code:
                rec.display_name = f"{rec.code} - {rec.name}"
            else:
                rec.display_name = rec.name

    @api.model
    def create(self, vals):
        if not vals.get('code'):
            prefix = self.env['ir.config_parameter'].sudo().get_param('vnpt_hrm.employee_code_prefix', default="BPC")
            last_employee = self.search([], order="id desc", limit=1)
            last_number = int(last_employee.code[-3:]) if last_employee and last_employee.code and last_employee.code[
                                                                                                   -3:].isdigit() else 0
            vals['code'] = f"{prefix}{last_number + 1:03d}"

        employee = super(HrEmployee, self).create(vals)

        # Auto-create insurance_id
        self.env['hr.insurance'].create({
            'employee_id': employee.id,
        })

        return employee



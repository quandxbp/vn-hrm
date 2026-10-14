# -*- coding: utf-8 -*-

# (tên, neo, submenu). Menu Odoo hỗ trợ bàn phím và menu mobile.
LANDING_MENUS = [
    ('Về Kim Academy', '/#gioi-thieu', [
        ('Giới thiệu trung tâm', '/gioi-thieu'),
        ('Phương pháp & Lộ trình', '/#phuong-phap'),
        ('Đội ngũ giáo viên', '/#giao-vien'),
        ('Chứng nhận & Đối tác', '/#uy-tin'),
        ('Tuyển dụng', '/tuyen-dung'),
    ]),
    ('Chương trình học', '/#chuong-trinh', []),
    ('Học viên & Hoạt động', '/#hoc-vien', [
        ('Thành tích học viên', '/#hoc-vien'),
        ('Cảm nhận phụ huynh', '/#cam-nhan'),
        ('Hoạt động lớp học', '/#hoat-dong'),
    ]),
    ('Liên hệ', '/lien-he', []),
    ('Nhận tư vấn', '/#dang-ky', []),
]


def sync_landing_menus(env):
    """Cập nhật cây menu khi cài hoặc nâng cấp, không tạo bản sao."""
    Menu = env['website.menu']
    for website in env['website'].search([]):
        if not website.menu_id:
            continue
        root = website.menu_id

        def upsert(name, url, parent, sequence, aliases=()):
            menu = Menu.search([
                ('website_id', '=', website.id), ('parent_id', '=', parent.id),
                ('name', '=', name),
            ], limit=1)
            if not menu:
                menu = Menu.search([
                    ('website_id', '=', website.id), ('parent_id', '=', parent.id),
                    ('url', 'in', [url, *aliases]),
                ], limit=1)
            vals = {'name': name, 'url': url, 'page_id': False, 'parent_id': parent.id,
                    'website_id': website.id, 'sequence': sequence}
            if menu:
                menu.write(vals)
            else:
                menu = Menu.create(vals)
            return menu

        for sequence, (name, url, children) in enumerate(LANDING_MENUS, start=1):
            aliases = ('/#thanh-tich',) if name == 'Học viên & Hoạt động' else ()
            if name == 'Liên hệ':
                aliases = ('/contactus', '/#lien-he')
            parent = upsert(name, url, root, sequence * 10, aliases)
            for child_sequence, (child_name, child_url) in enumerate(children, start=1):
                if child_url == '/#giao-vien':
                    old = Menu.search([
                        ('parent_id', '=', root.id), ('url', '=', child_url),
                        ('website_id', '=', website.id),
                    ], limit=1)
                    if old:
                        old.write({'parent_id': parent.id})
                upsert(child_name, child_url, parent, child_sequence * 10)

        # Logo dẫn về trang chủ; chỉ bỏ mục Home mặc định không có submenu.
        home = Menu.search([
            ('parent_id', '=', root.id), ('website_id', '=', website.id),
            ('url', '=', '/'), ('name', 'in', ['Home', 'Trang chủ']),
        ])
        home.filtered(lambda menu: not menu.child_id).unlink()


def post_init_hook(env):
    sync_landing_menus(env)

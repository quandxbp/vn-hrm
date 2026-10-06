# -*- coding: utf-8 -*-

# (tên, neo trong trang chủ, thứ tự). Sửa hoặc xoá trong Website > Site > Menu Editor.
LANDING_MENUS = [
    ('Chương trình', '/#chuong-trinh', 20),
    ('Giáo viên', '/#giao-vien', 30),
    ('Thành tích', '/#thanh-tich', 40),
    ('Đăng ký tư vấn', '/#dang-ky', 50),
]


def post_init_hook(env):
    """Thêm menu neo vào cây menu của từng website.

    Mỗi website có cây menu riêng (website.menu_id). website.main_menu chỉ là menu mẫu
    dùng để sao chép khi tạo website mới, nên không gắn vào đó.
    """
    Menu = env['website.menu']
    for website in env['website'].search([]):
        if not website.menu_id:
            continue
        existing = set(Menu.search([('parent_id', '=', website.menu_id.id)]).mapped('url'))
        for name, url, sequence in LANDING_MENUS:
            if url in existing:
                continue
            Menu.create({
                'name': name,
                'url': url,
                'parent_id': website.menu_id.id,
                'website_id': website.id,
                'sequence': sequence,
            })

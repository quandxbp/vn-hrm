# -*- coding: utf-8 -*-


def normalize_name(name):
    """Bỏ khoảng trắng thừa và viết hoa, để khớp tên khi import và điểm danh."""
    return ' '.join(name.split()).upper() if name else name


def get_param(env, key, default=0.0):
    """Giá trị số của tham số `edu_gvnn.<key>` trong Thiết lập."""
    value = env['ir.config_parameter'].sudo().get_param('edu_gvnn.' + key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def amount_in_words(amount):
    """Số tiền bằng chữ tiếng Việt, ví dụ "Hai triệu đồng". Trả về chuỗi rỗng nếu thiếu thư viện."""
    try:
        from num2words import num2words
        words = num2words(int(round(abs(amount))), lang='vi_VN')
    except Exception:
        return ''
    return words[:1].upper() + words[1:] + ' đồng'

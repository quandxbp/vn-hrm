# -*- coding: utf-8 -*-
from urllib.parse import urlparse


def youtube_recording_url(value):
    """Recognize old YouTube recording links without treating arbitrary URLs as videos."""
    try:
        value = (value or '').strip()
        url = urlparse(value)
        if (url.scheme in ('http', 'https') and not url.username and not url.password
                and url.port in (None, 80, 443)
                and url.hostname in ('youtu.be', 'www.youtu.be', 'youtube.com', 'www.youtube.com', 'm.youtube.com')):
            return value
    except ValueError:
        pass
    return False


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

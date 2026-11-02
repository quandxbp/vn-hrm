/** @odoo-module **/

function setupLogin() {
    const root = document.querySelector('.ka-login');
    const password = root?.querySelector('#password');
    const toggle = root?.querySelector('.ka-login-password-toggle');
    if (!password || !toggle || toggle.dataset.ready) return;
    toggle.dataset.ready = 'true';
    toggle.hidden = false;
    toggle.addEventListener('click', () => {
        const visible = password.type === 'password';
        password.type = visible ? 'text' : 'password';
        toggle.setAttribute('aria-pressed', String(visible));
        toggle.setAttribute('aria-label', visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
        toggle.querySelector('i').className = visible ? 'fa fa-eye-slash' : 'fa fa-eye';
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupLogin, { once: true });
} else {
    setupLogin();
}

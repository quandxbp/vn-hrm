/* Standalone teacher schedule: save one form without navigating or replacing the page. */
(() => {
    'use strict';
    const notifications = document.getElementById('schedule-notifications');
    function bindToast(toast) {
        toast.querySelector('.toast-close').addEventListener('click', () => toast.remove());
        if (!toast.classList.contains('toast-error')) {
            setTimeout(() => toast.remove(), 5000);
        }
    }
    function notify(message, error = false) {
        const toast = document.createElement('div');
        toast.className = `schedule-toast ${error ? 'toast-error' : 'toast-success'}`;
        toast.setAttribute('role', error ? 'alert' : 'status');
        const text = document.createElement('span');
        text.textContent = message;
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'toast-close';
        close.setAttribute('aria-label', 'Dismiss notification');
        close.textContent = '×';
        toast.append(text, close);
        notifications.append(toast);
        bindToast(toast);
        while (notifications.children.length > 3) notifications.firstElementChild.remove();
    }
    notifications.querySelectorAll('.schedule-toast').forEach(bindToast);
    for (const form of document.querySelectorAll('.recording-form')) {
        form.addEventListener('click', event => {
            const add = event.target.closest('.add-recording-part');
            const remove = event.target.closest('.remove-recording-part');
            if ((!add && !remove) || form.hasAttribute('aria-busy')) return;
            if (remove) { remove.closest('.recording-part').remove(); return; }
            const fields = form.querySelector('.recording-fields');
            const rows = [...fields.children];
            if (rows.length >= 10) { notify('A lesson supports up to 10 recording parts.', true); return; }
            const number = Math.max(...rows.map(row => Number(row.dataset.number))) + 1;
            const row = document.createElement('div');
            row.className = 'recording-part';
            row.dataset.number = String(number);
            const id = document.createElement('input');
            id.type = 'hidden'; id.name = 'part_id'; id.value = '';
            const label = document.createElement('label');
            label.textContent = `Part ${number}`;
            const input = document.createElement('input');
            input.type = 'url'; input.name = 'part_url'; input.required = true;
            input.maxLength = 2048; input.autocomplete = 'off'; input.placeholder = 'Paste Google Drive link';
            input.setAttribute('aria-label', `Part ${number} Google Drive recording`);
            const button = document.createElement('button');
            button.type = 'button'; button.className = 'remove-recording-part'; button.textContent = '\u00d7';
            button.setAttribute('aria-label', `Remove Part ${number}`);
            row.append(id, label, input, button); fields.append(row);
            input.focus({preventScroll: true});
        });
    }
    for (const form of document.querySelectorAll('.attendance-form, .recording-form')) {
        let saving = false;
        form.addEventListener('submit', async event => {
            event.preventDefault();
            if (saving) return;
            saving = true;
            const data = new FormData(form);
            const button = form.querySelector('button[type="submit"]');
            const label = [...button.childNodes].map(node => node.cloneNode(true));
            const minimumWidth = button.style.minWidth;
            button.style.minWidth = `${button.getBoundingClientRect().width}px`;
            const controls = [...form.querySelectorAll('button, input:not([type="hidden"])')];
            const states = controls.map(control => ({disabled: control.disabled, readOnly: control.readOnly,
                ariaDisabled: control.getAttribute('aria-disabled')}));
            controls.forEach(control => {
                // Keep the focused button/input focusable to avoid viewport jumps on mobile.
                if (control.tagName === 'BUTTON') control.setAttribute('aria-disabled', 'true');
                else if (control.type === 'url') control.readOnly = true;
                else control.disabled = true;
            });
            button.textContent = 'Saving…';
            form.setAttribute('aria-busy', 'true');
            try {
                const response = await fetch(form.action, {
                    method: 'POST', body: data, credentials: 'same-origin',
                    headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
                });
                if (!response.headers.get('content-type')?.includes('application/json')) {
                    throw new Error('Your page may have expired. Reload before trying again.');
                }
                const result = await response.json();
                if (!response.ok || !result.success) {
                    notify(result.message || 'Unable to save. Please try again.', true);
                    return;
                }
                if (form.classList.contains('attendance-form')) {
                    form.elements.original_attendance.value = result.original_attendance;
                } else {
                    form.elements.original_recording.value = result.recording;
                    form.elements.recording.value = result.recording;
                    const section = form.closest('.lesson-recording');
                    form.elements.original_recordings.value = result.recording_version;
                    const links = section.querySelector('.recording-links');
                    links.replaceChildren();
                    const saved = result.recording_parts.filter(part => part.url);
                    for (const part of saved) {
                        const link = document.createElement('a');
                        link.className = 'recording-link'; link.target = '_blank'; link.rel = 'noopener noreferrer';
                        link.href = part.url;
                        link.textContent = saved.length > 1 ? `Part ${part.number} \u2197` : 'View recording \u2197';
                        links.append(link);
                    }
                    const rows = [...form.querySelectorAll('.recording-part')];
                    result.recording_parts.forEach((part, index) => {
                        const row = rows[index];
                        if (!row) return;
                        row.dataset.number = String(part.number);
                        row.querySelector('label').textContent = `Part ${part.number}`;
                        row.querySelector('input[type="url"]').value = part.url;
                        const id = row.querySelector('input[name="part_id"]');
                        if (id) id.value = part.id;
                    });
                    section.querySelector('summary').textContent = saved.length ? 'Edit links' : 'Add recording';
                    section.querySelector('summary').dataset.hasRecording = saved.length ? 'true' : 'false';
                    // Keep the editor open: collapsing it would shift the lessons below it.
                }
                notify(result.message);
            } catch (error) {
                notify(error instanceof TypeError
                    ? 'Connection interrupted. Your changes are still here. Reload to check whether they were saved.'
                    : error.message, true);
            } finally {
                controls.forEach((control, index) => {
                    control.disabled = states[index].disabled;
                    if (control.tagName === 'INPUT') control.readOnly = states[index].readOnly;
                    if (states[index].ariaDisabled === null) control.removeAttribute('aria-disabled');
                    else control.setAttribute('aria-disabled', states[index].ariaDisabled);
                });
                button.replaceChildren(...label);
                button.style.minWidth = minimumWidth;
                form.removeAttribute('aria-busy');
                saving = false;
            }
        });
    }
})();

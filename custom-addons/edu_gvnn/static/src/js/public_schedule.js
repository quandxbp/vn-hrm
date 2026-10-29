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
    const reviewDialog = document.getElementById('session-review-dialog');
    if (reviewDialog) {
        const body = document.getElementById('session-review-body');
        const subtitle = document.getElementById('session-review-lesson');
        const auth = document.getElementById('session-review-auth');
        let activeRequest = null;
        let trigger = null;
        function element(tag, className, text) {
            const node = document.createElement(tag);
            if (className) node.className = className;
            if (text !== undefined) node.textContent = text;
            return node;
        }
        function message(text, error = false) {
            body.replaceChildren(element('p', `review-message${error ? ' review-error' : ''}`, text));
        }
        function section(title, text) {
            if (!text) return null;
            const node = element('section', 'review-section');
            node.append(element('h3', '', title), element('div', 'review-prose', text));
            return node;
        }
        function render(payload) {
            const lesson = payload.lesson;
            subtitle.textContent = lesson ? `${lesson.teacher} · ${lesson.date} · ${lesson.time}${lesson.week ? ` · Week ${lesson.week}` : ''}` : '';
            const states = {
                missing: 'No AI review has been created for this lesson yet.',
                queued: 'The review is queued. Please come back later.',
                processing: 'The lesson video is being processed. Please come back later.',
                analyzing: 'AI is analysing this lesson. Please come back later.',
                failed: 'The latest analysis did not complete. Please contact Kim Academy.',
                cancelled: 'The latest analysis was cancelled.',
            };
            if (payload.state !== 'done' || !payload.report) {
                message(states[payload.state] || 'The review is not available yet.');
                return;
            }
            const report = payload.report;
            body.replaceChildren();
            if (payload.stale) body.append(element('p', 'review-message review-warning',
                'The recording links have changed. This review refers to the previous video version.'));
            const metrics = element('div', 'review-metrics');
            for (const [label, value, detail] of [
                ['Teaching / total video', report.time_display, [report.ratio_display, report.teaching_started_at ? `Teaching starts: ${report.teaching_started_at}` : ''].filter(Boolean).join(' · ')],
                ['Lesson quality / 10', report.score_display, 'Content · Instruction · Interaction · Organisation'],
            ]) {
                const card = element('div', 'review-metric');
                card.append(element('span', 'review-metric-label', label), element('strong', '', value), element('small', '', detail));
                metrics.append(card);
            }
            body.append(metrics);
            for (const [title, key] of [['Overall review', 'summary'], ['Content taught', 'lesson_content']]) {
                const node = section(title, report[key]);
                if (node) body.append(node);
            }
            const feedback = element('div', 'review-feedback');
            for (const [title, key] of [['Strengths', 'strengths'], ['Areas for improvement', 'improvements']]) {
                const node = section(title, report[key]);
                if (node) feedback.append(node);
            }
            if (feedback.children.length) body.append(feedback);
            if (report.scores?.length) {
                const scores = element('div', 'review-scores');
                for (const score of report.scores) {
                    const card = element('div', 'review-score');
                    card.append(element('span', '', score.label), element('strong', '', `${score.score} / ${score.maximum}`));
                    scores.append(card);
                }
                body.append(scores);
            }
            for (const [title, key] of [
                ['Scoring evidence', 'score_details'], ['Teaching time and exclusions', 'timing_note'],
                ['Teaching segments', 'timing_details'], [`Student interaction${({low: ' · Low', medium: ' · Medium', good: ' · Good', insufficient: ' · Insufficient data'})[report.interaction_level] || ''}`, 'interaction_comment'],
                ['Recording quality and limitations', 'quality_note'],
            ]) {
                const node = section(title, report[key]);
                if (node) body.append(node);
            }
            if (report.sources?.length) {
                const sources = element('section', 'review-section');
                sources.append(element('h3', '', 'Video sources'));
                const links = element('div', 'recording-links');
                for (const part of report.sources) {
                    if (!part.url) continue;
                    const seconds = Math.round(Number(part.duration_seconds) || 0);
                    const duration = seconds > 0 ? ` · ${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}` : '';
                    const link = element('a', 'recording-link', `Part ${part.number}${duration} ↗`);
                    link.href = part.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
                    links.append(link);
                }
                sources.append(links); body.append(sources);
            }
            const completed = report.completed_at ? new Date(report.completed_at) : null;
            if (completed && !Number.isNaN(completed.getTime())) body.append(element('p', 'review-completed',
                `Completed: ${new Intl.DateTimeFormat('en-GB', {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Ho_Chi_Minh'}).format(completed)} (Vietnam time)`));
            body.append(element('p', 'review-footnote', 'AI-assisted review. Teaching time and scores are estimates; check the video evidence alongside the assessment.'));
        }
        for (const button of document.querySelectorAll('.session-review-button:not(:disabled)')) {
            button.addEventListener('click', async () => {
                if (!reviewDialog.showModal) { notify('Please use a browser that supports dialogs.', true); return; }
                activeRequest?.abort();
                const controller = new AbortController();
                activeRequest = controller;
                trigger = button;
                subtitle.textContent = '';
                message('Loading Session Review…');
                body.setAttribute('aria-busy', 'true');
                if (!reviewDialog.open) reviewDialog.showModal();
                document.body.classList.add('review-modal-open');
                const timeout = setTimeout(() => controller.abort('timeout'), 20000);
                try {
                    const data = new FormData(auth);
                    data.set('session_id', button.dataset.sessionId);
                    const response = await fetch('/weekly-schedule/session-review', {
                        method: 'POST', body: data, credentials: 'same-origin', signal: controller.signal,
                        headers: {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
                    });
                    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Your page may have expired. Reload and try again.');
                    const payload = await response.json();
                    if (!response.ok) throw new Error(payload.message || 'Unable to load the review.');
                    if (activeRequest === controller && reviewDialog.open) render(payload);
                } catch (error) {
                    if (activeRequest === controller && reviewDialog.open && (!controller.signal.aborted || controller.signal.reason === 'timeout')) {
                        message(controller.signal.reason === 'timeout' ? 'The request timed out. Close this window and try again.' : error.message, true);
                    }
                } finally {
                    clearTimeout(timeout);
                    if (activeRequest === controller) body.removeAttribute('aria-busy');
                }
            });
        }
        reviewDialog.addEventListener('close', () => {
            activeRequest?.abort();
            document.body.classList.remove('review-modal-open');
            trigger?.focus({preventScroll: true});
        });
        reviewDialog.addEventListener('click', event => {
            const rect = reviewDialog.getBoundingClientRect();
            if (event.target === reviewDialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) reviewDialog.close();
        });
    }
})();

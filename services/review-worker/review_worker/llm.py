"""JSON-constrained chat backends. `local` keeps all data on the VPS; `api` receives only
pseudonymized transcript/visual notes (never video, audio, names or Odoo identifiers besides student_<id>)."""
import json


class LLMError(Exception):
    pass


class LocalLLM:
    def __init__(self, settings):
        from llama_cpp import Llama

        self.model = Llama(model_path=settings.llm_model_path, n_ctx=settings.llm_ctx,
                           n_threads=settings.threads, n_batch=256, verbose=False)
        self.ctx = settings.llm_ctx

    def complete(self, system, user, schema, max_tokens):
        tokens = len(self.model.tokenize((system + user).encode('utf-8')))
        if tokens + max_tokens > self.ctx:
            raise LLMError('context_overflow:%s' % tokens)
        last = None
        # Same prompt + same sampling gives the same broken output, so the job-level retry never
        # helps (session 27 failed 3x identically). Retry once here with different sampling.
        for temperature, seed in ((0.2, 42), (0.5, 7)):
            out = self.model.create_chat_completion(
                messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                response_format={'type': 'json_object', 'schema': schema},
                temperature=temperature, top_p=0.9, max_tokens=max_tokens, seed=seed)
            choice = out['choices'][0]
            usage = out.get('usage') or {}
            used = {'prompt_tokens': usage.get('prompt_tokens', tokens),
                    'completion_tokens': usage.get('completion_tokens', 0)}
            try:
                if choice.get('finish_reason') != 'stop':
                    raise LLMError('truncated')
                return _parse(choice['message']['content']), used
            except LLMError as exc:
                last = exc
        raise last


class ApiLLM:
    """Any OpenAI-compatible endpoint with json_schema response_format."""

    def __init__(self, settings):
        if not (settings.api_base.startswith('https://') and settings.api_key and settings.api_model):
            raise LLMError('api_not_configured')
        self.settings = settings

    def complete(self, system, user, schema, max_tokens):
        import requests

        s = self.settings
        try:
            response = requests.post(s.api_base.rstrip('/') + '/chat/completions', timeout=(10, 300),
                headers={'Authorization': 'Bearer ' + s.api_key}, allow_redirects=False, json={
                    'model': s.api_model, 'temperature': 0.2, 'max_tokens': max_tokens,
                    'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                    'response_format': {'type': 'json_schema',
                                        'json_schema': {'name': 'result', 'schema': schema, 'strict': True}}})
        except requests.RequestException as exc:
            raise LLMError('transport:%s' % type(exc).__name__) from exc
        if response.status_code != 200:
            raise LLMError('http_%s' % response.status_code)  # never log the provider body
        out = response.json()
        choice = out['choices'][0]
        if choice.get('finish_reason') not in ('stop', None):
            raise LLMError('truncated')
        return _parse(choice['message']['content']), out.get('usage') or {}


QUOTA_FILE = 'gemini-quota.json'


def next_quota_reset(now, reset_hour_utc=8):
    """Free Tier daily quotas reset at midnight Pacific time: 08:00 UTC in winter (07:00 in summer,
    so 08:00 is always safe). A 5-minute margin avoids hitting the boundary."""
    import datetime as dt

    moment = dt.datetime.fromtimestamp(now, dt.timezone.utc)
    reset = moment.replace(hour=reset_hour_utc, minute=5, second=0, microsecond=0)
    if reset <= moment:
        reset += dt.timedelta(days=1)
    return reset.timestamp()


class Quota:
    """Per-model 'blocked until' timestamps, shared by the runner and the LLM child process."""

    def __init__(self, data_dir=None, clock=None):
        import time
        from pathlib import Path

        self.path = Path(data_dir) / QUOTA_FILE if data_dir else None
        self.memory = {}
        self.clock = clock or time.time

    def _load(self):
        data = self.memory
        if self.path and self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
            except ValueError:
                data = {}
        now = self.clock()
        return {m: float(u) for m, u in data.items() if isinstance(u, (int, float)) and u > now}

    def block(self, model, until):
        data = self._load()
        data[model] = max(until, data.get(model, 0))
        self.memory = data
        if self.path:
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(data), encoding='utf-8')
            tmp.replace(self.path)

    def available(self, models):
        blocked = self._load()
        return [m for m in models if m not in blocked]

    def until(self, models):
        """0 when at least one model is usable, else the earliest time one becomes usable again."""
        blocked = self._load()
        return 0 if any(m not in blocked for m in models) else min(blocked[m] for m in models)


def quota_details(response):
    """(daily, retry_seconds) from a 429 body. Reads only quota ids/delay; never logs the body."""
    import re

    daily, delay = False, 0
    try:
        details = (response.json() or {}).get('error', {}).get('details') or []
    except (ValueError, AttributeError, TypeError):
        details = []
    for item in details if isinstance(details, list) else []:
        if not isinstance(item, dict):
            continue
        for violation in item.get('violations') or []:
            if isinstance(violation, dict) and 'PerDay' in str(violation.get('quotaId', '')):
                daily = True
        match = re.fullmatch(r'([0-9]+)(?:\.[0-9]+)?s', str(item.get('retryDelay', '')))
        if match:
            delay = int(match.group(1))
    try:
        delay = max(delay, int(response.headers.get('Retry-After') or 0))
    except (ValueError, AttributeError, TypeError):
        pass
    return daily, delay


def gemini_models(settings):
    return [settings.gemini_model] + [m for m in getattr(settings, 'gemini_fallback_models', ())
                                      if m != settings.gemini_model]


class GeminiLLM:
    """Gemini generateContent, text only (same request shape as edu_session_review).

    Free Tier: Google may use the input to improve its models, so callers send only the
    pseudonymized transcript. Errors carry only status codes, never the provider body.

    Quota (decision 2026-11-25): GEMINI_MODEL first, then GEMINI_FALLBACK_MODELS (each model has its
    own Free Tier bucket). A daily-quota 429 blocks that model until the next reset; a per-minute 429
    is retried briefly. When every model is blocked the call raises `gemini_quota` and the runner
    parks the job (transcript cached) instead of failing it."""
    API = 'https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent'
    RETRY = (500, 503, 504)

    def __init__(self, settings, sleep=None, clock=None):
        import re
        import time

        models = gemini_models(settings)
        if not (settings.gemini_key and all(re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', m or '') for m in models)):
            raise LLMError('gemini_not_configured')
        self.settings, self.models = settings, models
        self.sleep = sleep or time.sleep
        self.clock = clock or time.time
        self.quota = Quota(getattr(settings, 'data_dir', None), self.clock)
        self.reset_hour = getattr(settings, 'quota_reset_utc_hour', 8)

    def complete(self, system, user, schema, max_tokens):
        for model in self.quota.available(self.models):
            out = self._call(model, system, user, schema, max_tokens)
            if out is not None:
                return out
        raise LLMError('gemini_quota')

    def _call(self, model, system, user, schema, max_tokens):
        """(result, usage), or None when this model's quota is exhausted (then blocked in the quota file)."""
        import requests

        generation = {'temperature': 0.2, 'maxOutputTokens': max(max_tokens, 8192),
                      'responseMimeType': 'application/json', 'responseJsonSchema': schema}
        if model.startswith('gemini-3'):
            generation['thinkingConfig'] = {'thinkingLevel': 'low'}
        body = {'systemInstruction': {'parts': [{'text': system}]},
                'contents': [{'role': 'user', 'parts': [{'text': user}]}], 'generationConfig': generation}
        delays, minute_waits = [20, 60, 150], 2
        while True:
            code = None
            try:
                response = requests.post(self.API % model, json=body, timeout=(10, 300),
                                         headers={'x-goog-api-key': self.settings.gemini_key}, allow_redirects=False)
                code = response.status_code
            except requests.Timeout:
                code = 'timeout'
            except requests.RequestException as exc:
                raise LLMError('transport:%s' % type(exc).__name__) from exc
            if code == 200:
                break
            if code == 429:
                daily, delay = quota_details(response)
                if daily:
                    self.quota.block(model, next_quota_reset(self.clock(), self.reset_hour))
                    return None
                if not minute_waits:      # per-minute limit that does not clear: rest this model a while
                    self.quota.block(model, self.clock() + max(600, delay))
                    return None
                minute_waits -= 1
                self.sleep(min(240, max(30, delay)))
                continue
            if code not in self.RETRY and code != 'timeout' or not delays:
                raise LLMError('gemini_http_%s' % code)  # never log the provider body
            self.sleep(delays.pop(0))
        out = response.json()
        candidates = out.get('candidates') or []
        if len(candidates) != 1:
            raise LLMError('gemini_candidates')
        if candidates[0].get('finishReason') != 'STOP':
            raise LLMError('truncated' if candidates[0].get('finishReason') == 'MAX_TOKENS' else
                           'gemini_finish:%s' % str(candidates[0].get('finishReason'))[:40])
        text = ''.join(p.get('text', '') for p in candidates[0].get('content', {}).get('parts', [])
                       if not p.get('thought'))
        meta = out.get('usageMetadata') or {}
        return _parse(text), {'prompt_tokens': meta.get('promptTokenCount', 0),
                              'completion_tokens': meta.get('candidatesTokenCount', 0), 'model': model}


def _parse(text):
    """Accept raw control characters inside strings (newline/tab from the local model) and
    trailing text after the object. The error carries only positions, never content."""
    text = (text or '').strip()
    try:
        data, _ = json.JSONDecoder(strict=False).raw_decode(text[text.index('{'):] if '{' in text else text)
    except (TypeError, ValueError) as exc:
        raise LLMError('json:pos=%s/len=%s' % (getattr(exc, 'pos', '?'), len(text))) from exc
    if not isinstance(data, dict):
        raise LLMError('json')
    return data


def backend(settings, name=None):
    name = name or settings.synth_backend
    if name == 'local':
        return LocalLLM(settings)
    if name == 'api':
        return ApiLLM(settings)
    if name == 'gemini':
        return GeminiLLM(settings)
    raise LLMError('backend')

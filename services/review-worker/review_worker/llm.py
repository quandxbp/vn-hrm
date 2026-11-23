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


class GeminiLLM:
    """Gemini generateContent, text only (same request shape as edu_session_review).

    Free Tier: Google may use the input to improve its models, so callers send only the
    pseudonymized transcript. Retries 429/5xx/timeouts here (Retry-After, max ~4 min) because
    a job-level retry would redo nothing useful; errors carry only status codes."""
    API = 'https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent'
    RETRY = (429, 500, 503, 504)

    def __init__(self, settings, sleep=None):
        import re
        import time

        if not (settings.gemini_key and re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', settings.gemini_model or '')):
            raise LLMError('gemini_not_configured')
        self.settings = settings
        self.sleep = sleep or time.sleep

    def complete(self, system, user, schema, max_tokens):
        import requests

        s = self.settings
        generation = {'temperature': 0.2, 'maxOutputTokens': max(max_tokens, 8192),
                      'responseMimeType': 'application/json', 'responseJsonSchema': schema}
        if s.gemini_model.startswith('gemini-3'):
            generation['thinkingConfig'] = {'thinkingLevel': 'low'}
        body = {'systemInstruction': {'parts': [{'text': system}]},
                'contents': [{'role': 'user', 'parts': [{'text': user}]}], 'generationConfig': generation}
        delays = [20, 60, 150]
        while True:
            code = None
            try:
                response = requests.post(self.API % s.gemini_model, json=body, timeout=(10, 300),
                                         headers={'x-goog-api-key': s.gemini_key}, allow_redirects=False)
                code = response.status_code
            except requests.Timeout:
                code = 'timeout'
            except requests.RequestException as exc:
                raise LLMError('transport:%s' % type(exc).__name__) from exc
            if code == 200:
                break
            if code not in self.RETRY and code != 'timeout' or not delays:
                raise LLMError('gemini_http_%s' % code)  # never log the provider body
            wait = delays.pop(0)
            if code == 429:
                try:
                    wait = max(wait, min(240, int(response.headers.get('Retry-After') or 0)))
                except ValueError:
                    pass
            self.sleep(wait)
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
                              'completion_tokens': meta.get('candidatesTokenCount', 0)}


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

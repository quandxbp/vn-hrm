"""Roster name matching for OCR text and transcript pseudonymization (pure Python)."""
import difflib
import re
import unicodedata

# Single-word aliases that collide with common English words are never matched.
STOP = {'and', 'the', 'you', 'are', 'can', 'for', 'not', 'but', 'yes', 'how', 'who', 'why', 'she',
        'her', 'his', 'one', 'two', 'six', 'ten', 'may', 'will', 'good', 'well', 'nice', 'look',
        'read', 'say', 'see', 'now', 'new', 'next', 'teacher', 'class', 'host', 'meeting'}
WORD = re.compile(r'[^\W\d_]+', re.UNICODE)


def fold(text):
    text = unicodedata.normalize('NFD', text or '').replace('đ', 'd').replace('Đ', 'D')
    return ''.join(c for c in text if unicodedata.category(c) != 'Mn').casefold()


def tokens(text):
    return [(m.start(), m.end(), m.group(0)) for m in WORD.finditer(text or '')]


class Matcher:
    def __init__(self, roster):
        patterns = {}
        for row in roster or []:
            for alias in row.get('aliases') or []:
                words = tuple(fold(w) for _, _, w in tokens(alias))
                if not words:
                    continue
                patterns.setdefault(words, set()).add(row['key'])
                # Teachers usually call Vietnamese students by the given (last) name.
                if len(words) > 1:
                    patterns.setdefault((words[-1],), set()).add(row['key'])
        # OCR presence needs precision (3+ letters). Pseudonymization prefers privacy: short
        # capitalized names such as "An" or "Vy" are replaced even if that over-redacts a word.
        self.patterns = {p: keys for p, keys in patterns.items()
                         if not (len(p) == 1 and (len(p[0]) < 3 or p[0] in STOP))}
        self.redact = {p: keys for p, keys in patterns.items()
                       if not (len(p) == 1 and (len(p[0]) < 2 or p[0] in STOP))}
        self.max_len = max((len(p) for p in self.redact), default=0)

    def find(self, text, strict_case=False):
        """Return non-overlapping (start, end, keys), longest alias first."""
        toks = tokens(text)
        folded = [fold(t[2]) for t in toks]
        table = self.redact if strict_case else self.patterns
        out, i = [], 0
        while i < len(toks):
            hit = None
            for n in range(min(self.max_len, len(toks) - i), 0, -1):
                keys = table.get(tuple(folded[i:i + n]))
                if not keys or n == 1 and strict_case and not toks[i][2][:1].isupper():
                    continue
                hit = (toks[i][0], toks[i + n - 1][1], frozenset(keys), n)
                break
            if hit:
                out.append(hit[:3])
                i += hit[3]
            else:
                i += 1
        return out

    def keys_in(self, text):
        """Unambiguous keys and ambiguous keys seen in OCR text."""
        sure, ambiguous = set(), set()
        for _, _, keys in self.find(text):
            (sure if len(keys) == 1 else ambiguous).update(keys)
        return sure - ambiguous, ambiguous

    def pseudonymize(self, text, fuzzy=False):
        """fuzzy=True is for text leaving the VPS: ASR spells names loosely ("Ellie" for ELLY),
        so capitalized words that sound like a roster name are also replaced (over-redaction is
        preferred to leaking a name)."""
        hits = self.find(text, strict_case=True)
        if fuzzy:
            taken = [(s, e) for s, e, _ in hits]
            for start, end, word in tokens(text):
                if any(s < end and start < e for s, e in taken) or not word[:1].isupper():
                    continue
                keys = self._sounds_like(word, sentence_start=not text[:start].strip()
                                         or text[:start].rstrip()[-1:] in '.?!')
                if keys:
                    hits.append((start, end, frozenset(keys)))
            hits.sort()
        out, last = [], 0
        for start, end, keys in hits:
            out.append(text[last:start])
            out.append('[%s]' % next(iter(keys)) if len(keys) == 1 else '[học sinh chưa rõ]')
            last = end
        out.append(text[last:])
        return ''.join(out)

    def _sounds_like(self, word, sentence_start):
        folded = fold(word)
        if len(folded) < 3 or folded in STOP:
            return set()
        skel = skeleton(folded)
        keys = set()
        for pattern, pattern_keys in self.redact.items():
            if len(pattern) != 1 or len(pattern[0]) < 3:
                continue
            other = skeleton(pattern[0])
            if skel == other or (not sentence_start and skel[:1] == other[:1] and len(other) >= 4
                                 and difflib.SequenceMatcher(None, skel, other).ratio() >= 0.85):
                keys |= pattern_keys
        return keys


def skeleton(word):
    """Rough spelling-insensitive form: Ellie/Elly -> eli, Phuong/Fuong -> fuong."""
    word = re.sub(r'ph', 'f', word)
    word = re.sub(r'(ck|c|q)', 'k', word)
    word = re.sub(r'(ie|ee|ey|y)', 'i', word)
    word = re.sub(r'(.)\1+', r'\1', word)
    return re.sub(r'(?<=..)[eh]$', '', word)

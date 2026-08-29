from __future__ import annotations
import re
from dataclasses import dataclass
from statistics import median
from typing import Iterable
from core.text_fragment import TextFragment

@dataclass(frozen=True)
class NormalizedText:
    text: str
    quality_score: float
    method: str

class ContentNormalizer:
    """Deterministic reconstruction of readable page text from native/OCR fragments."""
    _SPACE_BEFORE = re.compile(r"\s+([,.;:!?%)\]\}])")
    _SPACE_AFTER_OPEN = re.compile(r"([\(\[\{])\s+")
    _PAGE_NUMBER = re.compile(r"^\s*(?:\d{1,4}|[ivxlcdm]{1,8})\s*$", re.I)

    def normalize(self, raw_text: str, fragments: list[TextFragment] | None = None, *, source: str = "pdf_text") -> NormalizedText:
        raw_text = raw_text or ""
        fragments = fragments or []
        # For native PDFs, pypdf's extraction order is generally safer than
        # rebuilding columns from visitor coordinates. Use layout fragments
        # only for scanned/OCR pages, where coordinates are the source of
        # reading order.
        if source.startswith("pdf") and raw_text.strip():
            text = self._from_raw_text(raw_text)
            method = "pdf_text_normalized"
        elif fragments:
            text = self._from_fragments(fragments, source=source)
            method = f"{source}_layout"
        else:
            text = self._from_raw_text(raw_text)
            method = f"{source}_text"
        text = self._cleanup(text)
        return NormalizedText(text, self._quality(text, fragments), method)

    def _from_fragments(self, fragments: list[TextFragment], *, source: str) -> str:
        usable = [f for f in fragments if f.text.strip() and f.x is not None and f.y is not None]
        if not usable:
            return self._from_raw_text(" ".join(f.text for f in fragments))
        heights = [abs(f.height) for f in usable if f.height and abs(f.height) > .1]
        sizes = [abs(f.font_size) for f in usable if f.font_size and abs(f.font_size) > .1]
        scale = median(heights or sizes or [8.0])
        tolerance = max(1.5, scale * .45)
        groups = []
        reverse = source.startswith("pdf")
        for f in sorted(usable, key=lambda x: self._y(x), reverse=reverse):
            y = self._y(f)
            best = None
            best_delta = None
            for g in groups:
                gy = median(self._y(v) for v in g)
                d = abs(y-gy)
                if d <= tolerance and (best_delta is None or d < best_delta):
                    best, best_delta = g, d
            if best is None: groups.append([f])
            else: best.append(f)
        groups.sort(key=lambda g: median(self._y(v) for v in g), reverse=reverse)
        gaps = []
        prev = None
        for g in groups:
            y = median(self._y(v) for v in g)
            if prev is not None and y != prev: gaps.append(abs(y-prev))
            prev = y
        typical = median(gaps or [scale])
        paragraph_gap = max(scale * 1.8, typical * 0.9)
        paras, current, prev = [], [], None
        for g in groups:
            g = sorted(g, key=lambda x: x.x if x.x is not None else 0)
            line = self._join(g)
            if not line: continue
            y = median(self._y(v) for v in g)
            if current and prev is not None and abs(y-prev) > paragraph_gap:
                paras.append(" ".join(current)); current=[]
            current.append(line); prev=y
        if current: paras.append(" ".join(current))
        return "\n\n".join(paras)

    @staticmethod
    def _y(f: TextFragment) -> float:
        return f.y + abs(f.height)/2 if f.height is not None else f.y

    def _join(self, fragments: Iterable[TextFragment]) -> str:
        out=""
        for f in fragments:
            token=f.text.strip()
            if not token: continue
            if not out: out=token
            elif out.endswith("-") and token[:1].islower(): out = out[:-1] + token
            elif token[:1] in ",.;:!?%)]}": out += token
            elif out[-1:] in "([{": out += token
            elif out.endswith(("—","–","/")): out += token
            else: out += " " + token
        return out

    def _from_raw_text(self, raw_text: str) -> str:
        lines=[x.strip() for x in raw_text.splitlines()]
        if not any(lines): return ""
        paras=[]; cur=[]
        for line in lines:
            if not line: 
                if cur: paras.append(" ".join(cur)); cur=[]
                continue
            if not cur and self._PAGE_NUMBER.fullmatch(line): continue
            cur.append(line)
        if cur: paras.append(" ".join(cur))
        return "\n\n".join(paras)

    def _cleanup(self, text: str) -> str:
        text=text.replace("\u00ad","")
        text=re.sub(r"(?<=\w)-\s*\n\s*(?=[a-z])","",text)
        text=self._SPACE_BEFORE.sub(r"\1",text)
        text=self._SPACE_AFTER_OPEN.sub(r"\1",text)
        return "\n\n".join(re.sub(r"\s*\n\s*"," ",p).strip() for p in re.split(r"\n\s*\n+",text) if p.strip())

    def _quality(self, text: str, fragments: list[TextFragment]) -> float:
        if not text: return 0.0
        alpha=sum(c.isalpha() for c in text)/max(len(text),1)
        score=.45 + .25*min(len(text)/1000,1) + .30*alpha
        conf=[f.confidence for f in fragments if f.confidence is not None]
        if conf: score=.8*score+.2*max(0,min(1,median(conf)))
        return round(max(0,min(1,score)),3)

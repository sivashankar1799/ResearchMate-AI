"""
notes_generator.py
Generates topic-grouped study notes and condensed revision notes
using NLTK-based sentence/keyword extraction. No external model required,
so this is fully offline-capable.
"""

import re
from collections import Counter

import nltk


def _ensure_nltk():
    for resource, path in [("punkt", "tokenizers/punkt"),
                           ("punkt_tab", "tokenizers/punkt_tab"),
                           ("stopwords", "corpora/stopwords")]:
        try:
            nltk.data.find(path)
        except LookupError:
            try:
                nltk.download(resource, quiet=True)
            except Exception:
                pass


_ensure_nltk()

from nltk.tokenize import sent_tokenize  # noqa: E402
from nltk.corpus import stopwords  # noqa: E402


def _clean(text):
    return re.sub(r"\s+", " ", text).strip()


def _sentences(text):
    try:
        return sent_tokenize(text)
    except Exception:
        return [s for s in re.split(r"(?<=[.!?])\s+", text) if s]


def _keywords(text, top_n=8):
    """Return the most frequent meaningful keywords in the document."""
    try:
        stop = set(stopwords.words("english"))
    except Exception:
        stop = set()
    words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", text)
             if w.lower() not in stop]
    return [w for w, _ in Counter(words).most_common(top_n)]


def generate_study_notes(text):
    """
    Produce topic-grouped study notes.
    Topics are derived from the document's top keywords; each topic groups
    the most relevant sentences as bullet points.

    Returns: list of {"topic": str, "points": [str, ...]}
    """
    text = _clean(text)
    sentences = _sentences(text)
    keywords = _keywords(text, top_n=6)

    notes = []
    used = set()  # avoid repeating the same sentence across topics

    for kw in keywords:
        points = []
        for i, sent in enumerate(sentences):
            if i in used:
                continue
            if kw in sent.lower() and 5 <= len(sent.split()) <= 40:
                points.append(sent.strip())
                used.add(i)
            if len(points) >= 4:
                break
        if points:
            notes.append({"topic": kw.capitalize(), "points": points})

    # Fallback: if no keyword grouping produced notes, chunk top sentences
    if not notes:
        chunk = sentences[:12]
        notes.append({"topic": "Key Points",
                      "points": [s.strip() for s in chunk if s.strip()]})
    return notes


def generate_revision_notes(text, max_points=10):
    """
    Produce condensed revision notes: short, high-signal bullet points
    capturing key concepts. Uses sentence scoring by keyword density.

    Returns: list of strings.
    """
    text = _clean(text)
    sentences = _sentences(text)
    keywords = set(_keywords(text, top_n=12))

    scored = []
    for sent in sentences:
        tokens = [w.lower() for w in re.findall(r"[A-Za-z]+", sent)]
        if not tokens:
            continue
        # Density = fraction of keyword tokens, rewards concise informative lines
        score = sum(1 for t in tokens if t in keywords) / len(tokens)
        if 5 <= len(tokens) <= 30:
            scored.append((score, sent.strip()))

    scored.sort(key=lambda x: x[0], reverse=True)
    revision = [s for _, s in scored[:max_points]]

    if not revision:
        revision = [s.strip() for s in sentences[:max_points] if s.strip()]
    return revision
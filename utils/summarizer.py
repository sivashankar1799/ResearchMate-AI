"""
summarizer.py
Abstractive summarization via HuggingFace Transformers with a robust
extractive fallback (NLTK frequency-based) when models are unavailable.
"""

import re
from collections import Counter

# NLTK for sentence tokenization and stopwords (extractive fallback)
import nltk

# Ensure required NLTK data is present (download once, gracefully)
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

from nltk.tokenize import sent_tokenize, word_tokenize  # noqa: E402
from nltk.corpus import stopwords  # noqa: E402

# ---------------------------------------------------------------------------
# Lazy-loaded HuggingFace summarization pipeline (loaded once on demand)
# ---------------------------------------------------------------------------
_SUMMARIZER = None
_SUMMARIZER_FAILED = False


def _get_summarizer():
    """
    Lazily instantiate the HuggingFace summarization pipeline.
    Returns None if loading fails (so callers can fall back to extractive).
    """
    global _SUMMARIZER, _SUMMARIZER_FAILED
    if _SUMMARIZER is not None:
        return _SUMMARIZER
    if _SUMMARIZER_FAILED:
        return None
    try:
        from transformers import pipeline
        # distilbart is small and fast; good default for summarization
        _SUMMARIZER = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
        return _SUMMARIZER
    except Exception:
        _SUMMARIZER_FAILED = True
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clean_text(text):
    """Collapse whitespace and strip noise for cleaner model input."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _chunk_text(text, max_words=600):
    """
    Split text into word-bounded chunks suitable for the summarizer's
    token limit. Long documents are summarized chunk-by-chunk.
    """
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunks.append(" ".join(words[i:i + max_words]))
    return chunks


def _extractive_summary(text, num_sentences=4):
    """
    Frequency-based extractive summarizer (fallback).
    Scores sentences by normalized word frequency and returns the top ones
    in their original order.
    """
    try:
        sentences = sent_tokenize(text)
    except Exception:
        sentences = re.split(r"(?<=[.!?])\s+", text)

    if len(sentences) <= num_sentences:
        return " ".join(sentences)

    try:
        stop = set(stopwords.words("english"))
    except Exception:
        stop = set()

    words = [w.lower() for w in re.findall(r"[A-Za-z]+", text) if w.lower() not in stop]
    freq = Counter(words)
    if not freq:
        return " ".join(sentences[:num_sentences])

    max_freq = max(freq.values())
    for w in freq:
        freq[w] /= max_freq  # normalize

    # Score each sentence
    scores = {}
    for idx, sent in enumerate(sentences):
        for w in re.findall(r"[A-Za-z]+", sent.lower()):
            if w in freq:
                scores[idx] = scores.get(idx, 0) + freq[w]

    # Pick top-N sentence indices, then restore original order
    top_idx = sorted(sorted(scores, key=scores.get, reverse=True)[:num_sentences])
    return " ".join(sentences[i] for i in top_idx)


def _abstractive(text, max_length=130, min_length=30):
    """
    Run the abstractive summarizer on a single chunk.
    Raises on failure so callers can decide on fallback.
    """
    summarizer = _get_summarizer()
    if summarizer is None:
        raise RuntimeError("Summarizer unavailable")
    result = summarizer(text, max_length=max_length, min_length=min_length,
                        do_sample=False, truncation=True)
    return result[0]["summary_text"].strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_short_summary(text):
    """
    Produce a concise summary of <= ~150 words.
    Tries abstractive first; falls back to extractive.
    """
    text = _clean_text(text)
    # Limit input size for the short summary
    snippet = " ".join(text.split()[:700])
    try:
        summary = _abstractive(snippet, max_length=150, min_length=40)
    except Exception:
        summary = _extractive_summary(snippet, num_sentences=5)
    # Enforce 150-word ceiling
    words = summary.split()
    if len(words) > 150:
        summary = " ".join(words[:150]) + "..."
    return summary


def generate_detailed_summary(text):
    """
    Produce a longer summary for long documents by chunking and summarizing
    each chunk, then concatenating the partial summaries.
    """
    text = _clean_text(text)
    chunks = _chunk_text(text, max_words=600)
    # Cap number of chunks to keep latency reasonable
    chunks = chunks[:6]

    partials = []
    for chunk in chunks:
        try:
            partials.append(_abstractive(chunk, max_length=140, min_length=40))
        except Exception:
            partials.append(_extractive_summary(chunk, num_sentences=3))

    detailed = " ".join(partials).strip()
    if not detailed:
        detailed = _extractive_summary(text, num_sentences=8)
    return detailed


def extract_key_findings(text, max_points=6):
    """
    Extract bullet-point key findings by selecting sentences containing
    result/finding cue words, with an extractive fallback.
    """
    text = _clean_text(text)
    try:
        sentences = sent_tokenize(text)
    except Exception:
        sentences = re.split(r"(?<=[.!?])\s+", text)

    cues = ("result", "found", "show", "demonstrat", "reveal", "observ",
            "indicate", "suggest", "significant", "increase", "decrease",
            "improve", "achieve", "performance", "accuracy")

    findings = []
    for sent in sentences:
        low = sent.lower()
        if any(c in low for c in cues) and 6 <= len(sent.split()) <= 45:
            findings.append(sent.strip())
        if len(findings) >= max_points:
            break

    # Fallback: top extractive sentences if no cue-based matches found
    if not findings:
        extractive = _extractive_summary(text, num_sentences=max_points)
        findings = [s.strip() for s in re.split(r"(?<=[.!?])\s+", extractive) if s.strip()]

    return findings[:max_points]


def extract_conclusions(text):
    """
    Extract conclusion-oriented content. Prefers a 'Conclusion' section if
    detected; otherwise summarizes the final portion of the document.
    """
    text = _clean_text(text)

    # Try to locate a conclusion section heading
    match = re.search(r"(conclusion[s]?|in summary|to conclude|in conclusion)",
                      text, flags=re.IGNORECASE)
    if match:
        tail = text[match.start():match.start() + 1500]
        try:
            return _abstractive(tail, max_length=130, min_length=30)
        except Exception:
            return _extractive_summary(tail, num_sentences=4)

    # Otherwise summarize the last ~600 words of the document
    last_part = " ".join(text.split()[-600:])
    try:
        return _abstractive(last_part, max_length=130, min_length=30)
    except Exception:
        return _extractive_summary(last_part, num_sentences=4)
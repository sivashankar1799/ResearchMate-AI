"""
chatbot.py
Answers user questions strictly from the uploaded document.
Primary path: HuggingFace extractive QA pipeline.
Fallback: TF-style keyword/sentence matching (offline-capable).
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

# ---------------------------------------------------------------------------
# Lazy QA pipeline
# ---------------------------------------------------------------------------
_QA = None
_QA_FAILED = False


def _get_qa():
    """Lazily load the extractive QA pipeline; None on failure."""
    global _QA, _QA_FAILED
    if _QA is not None:
        return _QA
    if _QA_FAILED:
        return None
    try:
        from transformers import pipeline
        _QA = pipeline("question-answering",
                       model="distilbert-base-cased-distilled-squad")
        return _QA
    except Exception:
        _QA_FAILED = True
        return None


def _clean(text):
    return re.sub(r"\s+", " ", text).strip()


def _stopwords():
    try:
        return set(stopwords.words("english"))
    except Exception:
        return set()


def _keyword_match(text, question, top_k=3):
    """
    Fallback retrieval: rank document sentences by keyword overlap with the
    question and return the best-matching sentence(s) as the answer.
    """
    try:
        sentences = sent_tokenize(text)
    except Exception:
        sentences = re.split(r"(?<=[.!?])\s+", text)

    stop = _stopwords()
    q_words = {w.lower() for w in re.findall(r"[A-Za-z]+", question)
               if w.lower() not in stop}
    if not q_words:
        return "Could you please rephrase your question with more detail?"

    scored = []
    for sent in sentences:
        s_words = {w.lower() for w in re.findall(r"[A-Za-z]+", sent)}
        overlap = len(q_words & s_words)
        if overlap:
            # Normalize slightly by sentence length to avoid favoring long ones
            scored.append((overlap / (1 + 0.01 * len(s_words)), sent.strip()))

    if not scored:
        return ("I couldn't find information about that in the uploaded "
                "document. Please ask something covered by the paper.")

    scored.sort(key=lambda x: x[0], reverse=True)
    best = [s for _, s in scored[:top_k]]
    return " ".join(best)


def _select_context(text, question, window_chars=3000):
    """
    For long documents, narrow the QA context to the most relevant region
    around the highest keyword-overlap sentence to fit model token limits.
    """
    try:
        sentences = sent_tokenize(text)
    except Exception:
        sentences = re.split(r"(?<=[.!?])\s+", text)

    stop = _stopwords()
    q_words = {w.lower() for w in re.findall(r"[A-Za-z]+", question)
               if w.lower() not in stop}

    best_idx, best_score = 0, -1
    for i, sent in enumerate(sentences):
        s_words = {w.lower() for w in re.findall(r"[A-Za-z]+", sent)}
        score = len(q_words & s_words)
        if score > best_score:
            best_score, best_idx = score, i

    # Build a context window of sentences around the best match
    context_parts, length = [], 0
    i, j = best_idx, best_idx
    context_parts.append(sentences[best_idx])
    length += len(sentences[best_idx])
    while length < window_chars and (i > 0 or j < len(sentences) - 1):
        if i > 0:
            i -= 1
            context_parts.insert(0, sentences[i])
            length += len(sentences[i])
        if j < len(sentences) - 1 and length < window_chars:
            j += 1
            context_parts.append(sentences[j])
            length += len(sentences[j])
    return " ".join(context_parts)


def answer_question(text, question):
    """
    Answer `question` using the document `text`.
    Tries the QA model on a focused context; falls back to keyword matching.
    """
    text = _clean(text)
    question = question.strip()
    if not text:
        return "No document is loaded. Please upload a PDF first."

    qa = _get_qa()
    if qa is not None:
        try:
            context = _select_context(text, question)
            result = qa(question=question, context=context)
            answer = (result.get("answer") or "").strip()
            score = result.get("score", 0)
            # If model is confident enough, return its answer; else fall back
            if answer and score >= 0.05:
                # Provide a fuller sentence-level answer for readability
                supporting = _keyword_match(context, question, top_k=1)
                if answer.lower() in supporting.lower():
                    return supporting
                return f"{answer}. {supporting}"
        except Exception:
            pass  # fall through to keyword matching

    # Fallback path
    return _keyword_match(text, question, top_k=2)
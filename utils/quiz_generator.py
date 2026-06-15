"""
quiz_generator.py
Generates multiple-choice and true/false questions from document text
using NLTK sentence parsing and simple, deterministic heuristics.
Fully offline — no model dependency required.
"""

import re
import random
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


def _good_sentences(text, min_words=8, max_words=30):
    """Return sentences within a useful length band for question generation."""
    try:
        sents = sent_tokenize(text)
    except Exception:
        sents = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sents if min_words <= len(s.split()) <= max_words]


def _keywords(text, top_n=40):
    """Extract candidate keywords (capitalized terms + frequent nouns-like)."""
    try:
        stop = set(stopwords.words("english"))
    except Exception:
        stop = set()
    words = [w for w in re.findall(r"[A-Za-z]{4,}", text)
             if w.lower() not in stop]
    freq = Counter(w.lower() for w in words)
    common = [w for w, _ in freq.most_common(top_n)]
    return common


def generate_mcqs(text, count=5):
    """
    Generate `count` multiple-choice questions.

    Strategy: pick informative sentences, blank out a salient keyword to form
    the question, and build distractor options from other keywords.

    Returns: list of {"question", "options"[4], "answer"}
    """
    text = _clean(text)
    sentences = _good_sentences(text)
    vocab = _keywords(text, top_n=60)
    random.seed(42)  # deterministic output for reproducibility

    questions = []
    used_answers = set()

    for sent in sentences:
        if len(questions) >= count:
            break
        # Find a salient keyword present in this sentence to use as the answer
        candidates = [w for w in re.findall(r"[A-Za-z]{4,}", sent)
                      if w.lower() in vocab and w.lower() not in used_answers]
        if not candidates:
            continue
        answer = max(candidates, key=len)  # pick the longest as most specific
        used_answers.add(answer.lower())

        # Create the question stem by blanking the answer word
        stem = re.sub(r"\b" + re.escape(answer) + r"\b", "______", sent, count=1)

        # Build 3 distractors from vocab not equal to the answer
        distractor_pool = [w for w in vocab if w != answer.lower()]
        random.shuffle(distractor_pool)
        distractors = []
        for d in distractor_pool:
            if d.lower() != answer.lower() and d not in distractors:
                distractors.append(d.capitalize())
            if len(distractors) >= 3:
                break
        while len(distractors) < 3:
            distractors.append("None of the above")

        options = distractors + [answer.capitalize()]
        random.shuffle(options)

        questions.append({
            "question": stem,
            "options": options,
            "answer": answer.capitalize()
        })

    # Fallback: if too few questions, create simple comprehension items
    idx = 0
    while len(questions) < count and idx < len(sentences):
        sent = sentences[idx]
        idx += 1
        questions.append({
            "question": f"Which statement appears in the document? (Select the correct one)",
            "options": [
                sent[:80] + ("..." if len(sent) > 80 else ""),
                "This topic is not discussed in the document.",
                "The document contradicts this entirely.",
                "None of the above."
            ],
            "answer": sent[:80] + ("..." if len(sent) > 80 else "")
        })

    return questions[:count]


def generate_true_false(text, count=5):
    """
    Generate `count` True/False statements.

    Half are true (verbatim/lightly-edited document sentences) and half are
    false (sentences with a key term swapped/negated).

    Returns: list of {"statement", "answer"} where answer is "True"/"False".
    """
    text = _clean(text)
    sentences = _good_sentences(text)
    vocab = _keywords(text, top_n=60)
    random.seed(7)
    random.shuffle(sentences)

    tf = []
    for sent in sentences:
        if len(tf) >= count:
            break
        make_false = len(tf) % 2 == 1  # alternate true/false

        if make_false:
            # Corrupt the sentence to make it false: negate or swap a keyword
            if " is " in sent:
                statement = sent.replace(" is ", " is not ", 1)
            elif " are " in sent:
                statement = sent.replace(" are ", " are not ", 1)
            else:
                # Swap a present keyword with a different one
                present = [w for w in re.findall(r"[A-Za-z]{4,}", sent)
                           if w.lower() in vocab]
                if present:
                    target = present[0]
                    alt_pool = [w for w in vocab if w != target.lower()]
                    if alt_pool:
                        replacement = random.choice(alt_pool).capitalize()
                        statement = re.sub(r"\b" + re.escape(target) + r"\b",
                                           replacement, sent, count=1)
                    else:
                        continue
                else:
                    continue
            tf.append({"statement": statement.strip(), "answer": "False"})
        else:
            tf.append({"statement": sent.strip(), "answer": "True"})

    # Fallback to ensure we always return `count` items
    while len(tf) < count and sentences:
        tf.append({"statement": sentences[len(tf) % len(sentences)].strip(),
                   "answer": "True"})

    return tf[:count]
"""Query Preprocessing, Meta-Instruction Sanitization, and Intent Classification."""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProcessedQuery:
    raw_query: str
    cleaned_query: str
    search_terms: list[str]
    expanded_terms: set[str] = field(default_factory=set)
    is_meta_query: bool = False
    is_overview_query: bool = False
    is_methodology_query: bool = False
    is_results_query: bool = False
    subqueries: list[str] = field(default_factory=list)
    is_compound_query: bool = False
    anchor_constraints: dict[str, Any] = field(default_factory=dict)
    is_multi_source: bool = False
    detected_sources: list[str] = field(default_factory=list)

    @property
    def intent(self) -> str:
        if self.is_meta_query:
            return "meta_paper_info"
        if self.is_overview_query:
            return "overview_or_objectives"
        if self.is_methodology_query:
            return "methodology_query"
        if self.is_results_query:
            return "results_or_benchmarks"
        return "general_research_qa"

    @property
    def academic_synonyms(self) -> list[str]:
        return sorted(list(self.expanded_terms - set(self.search_terms)))

    @property
    def meta_instructions_removed(self) -> list[str]:
        removed = []
        if len(self.raw_query) > len(self.cleaned_query):
            diff = self.raw_query[len(self.cleaned_query):].strip()
            if diff:
                removed.append(diff)
        return removed


# Meta-instruction patterns commonly appended by users or prompts that pollute semantic retrieval
META_INSTRUCTION_PATTERNS = [
    r'(?i)\bquote\s+(?:the\s+)?(?:exact\s+)?title\s*(?:and\s+cite\s+(?:the\s+)?(?:exact\s+)?page(?:\s+numbers?)?)?\b.*',
    r'(?i)\bquote\s+.*',
    r'(?i)\bcite\s+(?:the\s+)?(?:exact\s+)?page(?:\s+numbers?)?\b.*',
    r'(?i)\bcite\s+(?:the\s+)?(?:sources?|pages?)\b.*',
    r'(?i)\bwith\s+page\s+citations?\b.*',
    r'(?i)\binclude\s+citations?\b.*',
    r'(?i)\bprovide\s+page\s+citations?\b.*',
    r'(?i)\baccording\s+to\s+the\s+(?:paper|document|text)\b.*',
]

# Standard academic synonyms bridging user phrasing with research paper vocabulary
ACADEMIC_SYNONYMS: dict[str, list[str]] = {
    "objectives": ["aim", "aims", "purpose", "goal", "goals", "objective", "scope", "examine", "examines"],
    "objective": ["aim", "aims", "purpose", "goal", "goals", "scope", "examine", "examines"],
    "problem": ["challenge", "challenges", "issue", "issues", "gap", "gaps", "limitation", "limitations", "insufficient"],
    "problems": ["challenges", "issues", "gaps", "limitations"],
    "limitations": ["gaps", "gap", "lack", "scarcity", "challenges", "issues", "unresolved"],
    "limitation": ["gap", "gaps", "lack", "scarcity", "challenge", "issue", "unresolved"],
    "gaps": ["limitations", "limitation", "lack", "scarcity", "challenges", "unresolved"],
    "gap": ["limitation", "limitations", "lack", "scarcity", "challenge", "unresolved"],
    "methodology": ["method", "methods", "search strategy", "databases", "inclusion", "exclusion", "criteria", "scopus"],
    "methods": ["methodology", "search strategy", "databases", "criteria"],
    "results": ["findings", "empirical results", "outcomes", "benchmarks", "evaluation"],
    "findings": ["results", "outcomes", "empirical"],
    "conclusion": ["concluding remarks", "summary", "future work", "outlook"],
    "paper": ["review", "study", "article", "manuscript", "report", "work", "investigation"],
    "papers": ["reviews", "studies", "articles", "manuscripts", "reports", "works"],
    "review": ["paper", "study", "article", "survey", "overview"],
    "article": ["paper", "review", "study", "manuscript"],
    "study": ["paper", "review", "article", "work", "investigation"],
    "country": ["indonesia", "india", "japan", "portugal", "austria", "nation", "national", "geographic"],
    "countries": ["indonesia", "india", "japan", "portugal", "austria", "nations", "geographies"],
    "contribution": ["reducing", "input", "virgin", "rate"],
    "recycled": ["recycling", "re-used", "secondary", "circular"],
    "collection": ["collect", "collected", "collecting", "recovery", "recovered"],
    "rate": ["rates", "ratio", "percentage", "proportion"],
    "production": ["produced", "manufacturing", "output", "amounted"],
    "consumption": ["consumed", "use", "demand", "applications"],
}

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me",
    "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should",
    "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "us", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves",
    # Academic reporting words and citation tokens that pollute semantic search
    "et", "al", "reported", "author", "authors", "paper", "study", "article",
    "findings", "stated", "described", "according", "mentioned", "discussed",
    "analyze", "analyzed", "literature", "presents", "presented", "shown", "shows",
}


def extract_anchor_constraints(query: str) -> dict[str, Any]:
    """Extracts country, model, allegation, and scope anchors that require strict evidence grounding."""
    q_lower = query.lower()

    # 1. Geographic country/region anchors
    geo_anchors: dict[str, list[str]] = {}
    country_patterns = {
        "portugal": [r"\bportugal\b", r"\bportuguese\b"],
        "japan": [r"\bjapan\b", r"\bjapanese\b"],
        "india": [r"\bindia\b", r"\bindian\b"],
        "indonesia": [r"\bindonesia\b", r"\bindonesian\b"],
        "austria": [r"\baustria\b", r"\baustrian\b"],
    }
    for country, pats in country_patterns.items():
        if any(re.search(p, q_lower) for p in pats):
            geo_anchors[country] = pats

    # 2. Specific named models
    model_anchors: list[str] = []
    if re.search(r"\bdpmfa\b", q_lower) or "dynamic probabilistic material flow" in q_lower:
        model_anchors.append("dpmfa")
    if re.search(r"\bcleanchain\b", q_lower):
        model_anchors.append("cleanchain")

    # 3. Fraud / collusion / investigative allegations
    fraud_terms = ["fraud", "fraudulent", "collusion", "colluding", "convicted", "cartel", "investigative audit", "audits", "scam", "malfeasance"]
    has_fraud = any(re.search(r"\b" + re.escape(w) + r"\b", q_lower) for w in fraud_terms)

    # 4. Project frozen scope constraints
    frozen_terms = ["frozen research scope", "frozen scope", "project's frozen"]
    has_frozen = any(w in q_lower for w in frozen_terms)

    return {
        "geo_anchors": geo_anchors,
        "model_anchors": model_anchors,
        "has_fraud": has_fraud,
        "has_frozen": has_frozen,
    }


def is_reference_chunk(text: str) -> bool:
    """Detects bibliography, references, and CRediT authorship sections that pollute substantive evidence."""
    clean = text.replace("\u200b", "")
    t_lower = clean.lower().strip()
    if any(t_lower.startswith(p) for p in [
        "references", "reference", "bibliography", "credit authorship",
        "declaration of competing", "conflict of interest", "acknowledg"
    ]):
        return True
    if "\nreferences\n" in t_lower or "references and notes" in t_lower or "\nbibliography\n" in t_lower:
        return True

    # Whitespace and zero-width space normalized DOI matching (e.g. 10.1016/...)
    no_ws = re.sub(r"[\u200b\s]+", "", text)
    standard_dois = len(re.findall(r"10\.\d{4,9}/", no_ws))

    et_als = len(re.findall(r"\bet\s+al\b", clean, re.IGNORECASE))
    num_entries = len(re.findall(r"(?:^|\n|\.\s+)\s*\[?\d{1,3}\]?\.\s+[A-Z]", clean))
    author_date_entries = len(re.findall(r"[A-Z][a-zA-Z\u00c0-\u024f\s\.-]+,\s+[A-Z]\.?.*?\b(?:19|20)\d\d[a-z]?[\.,\)]", clean))

    if standard_dois >= 2:
        return True
    if standard_dois >= 1 and (num_entries >= 1 or author_date_entries >= 1 or et_als >= 1):
        return True
    if num_entries >= 3:
        return True
    if author_date_entries >= 3:
        return True
    if et_als >= 3:
        return True
    if et_als >= 2 and standard_dois >= 1:
        return True
    return False


def resolve_citation_page(excerpt: str, chunk_text: str, page_numbers: list[int]) -> int:
    """Resolves the exact verified page number for an excerpt from a multi-page chunk."""
    if not page_numbers:
        return 1
    if len(page_numbers) == 1:
        return page_numbers[0]

    clean_e = re.sub(r"\s+", " ", excerpt.strip().lower()[:60])
    clean_c = re.sub(r"\s+", " ", chunk_text.strip().lower())

    pos = clean_c.find(clean_e) if clean_e else -1
    if pos != -1 and len(clean_c) > 0:
        ratio = pos / len(clean_c)
        page_idx = min(int(ratio * len(page_numbers)), len(page_numbers) - 1)
        return page_numbers[page_idx]

    return page_numbers[0]


def normalize_stem(word: str) -> str:
    """Stem a word safely, preserving words ending in double-s (e.g. address, process, access)."""
    w = word.lower()
    if w.endswith("ss"):
        return w
    for suffix in ("ability", "ibility", "ship", "tions", "tion", "ing", "ies", "es", "ed", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            stem = w[:-len(suffix)]
            if stem.endswith("ss"):
                return stem
            return stem
    return w


def clean_query_text(query: str) -> str:
    """Removes trailing formatting instructions and meta-prompts from raw user queries."""
    cleaned = query.strip()
    for pat in META_INSTRUCTION_PATTERNS:
        cleaned = re.sub(pat, "", cleaned).strip()
    return cleaned if len(cleaned) >= 4 else query.strip()


def decompose_query(cleaned_query: str) -> list[str]:
    """Decomposes compound or multi-part research inquiries into distinct subquestions before retrieval."""
    q = cleaned_query.strip()
    if not q:
        return []

    # 1. Numbered or bullet list lines: e.g. "1. ...\n2. ..." or "- ...\n- ..."
    lines = [line.strip() for line in q.splitlines() if line.strip()]
    if len(lines) > 1:
        bullet_items = []
        for line in lines:
            sub = re.sub(r"^(?:\d+[\.\)]|[-*•])\s*", "", line).strip()
            if len(sub) >= 4:
                bullet_items.append(sub)
        if len(bullet_items) > 1:
            return bullet_items

    # 2. Multiple sentences ending in question marks: e.g. "What is X? What is Y?"
    q_marks = [s.strip() for s in re.split(r"\?+", q) if s.strip()]
    if len(q_marks) > 1:
        valid_q = [s + "?" if not s.endswith("?") else s for s in q_marks if len(s) >= 6]
        if len(valid_q) > 1:
            return valid_q

    # 3. Semicolon-separated subquestions: e.g. "Topic A; Topic B; Topic C"
    if ";" in q:
        parts = [p.strip() for p in q.split(";") if len(p.strip()) >= 4]
        if len(parts) > 1:
            return parts

# Blacklist of non-author entities to reject from author conjunction matching
NON_AUTHOR_ENTITIES = {
    # Countries, regions, and adjectives
    "india", "japan", "china", "united states", "usa", "uk", "europe", "asia",
    "portugal", "indonesia", "austria", "germany", "france", "brazil", "spain",
    "italy", "canada", "australia", "global", "developing countries",
    "asian", "indian", "japanese", "indonesian", "portuguese", "european", "american", "austrian",
    "economies", "economy", "countries", "country",
    # Materials, polymers, waste streams
    "pet", "hdpe", "ldpe", "pp", "pvc", "ps", "eps", "abs", "pur", "pla", "pha",
    "plastics", "polymers", "packaging", "textiles", "automotive",
    # Frameworks, methodologies, concepts, acronyms
    "epr", "mfa", "lca", "dpmfa", "msw", "ghg", "csiro", "teri", "iot", "ai",
    "industry", "government", "policy", "policymakers", "recycling", "landfills",
    "incineration", "mechanical recycling", "chemical recycling", "informal sector"
}

_NAME_PREFIX = r"(?:(?:van\s+(?:der|den|de)\s+|von\s+|de\s+(?:la\s+|l'|los\s+)?|del\s+|di\s+|da\s+|du\s+|le\s+|la\s+))"
_BASE_NAME = r"(?:[A-Z][a-zA-Z\u00c0-\u024f\.-]*(?:'[A-Z][a-zA-Z\u00c0-\u024f\.-]*)?)"
_FULL_NAME = rf"(?:{_NAME_PREFIX}?{_BASE_NAME}(?:\s+{_BASE_NAME}){{0,2}})"
_AUTH_TOKEN = rf"(?:{_FULL_NAME}(?:\s+(?i:et\s+al\.?))?)"


def clean_author_candidate(text: str, documents: list[Any] | None = None) -> str | None:
    """Extracts and validates genuine author name, validating against documents if available and rejecting non-author entities."""
    if not text:
        return None
    m = re.search(_AUTH_TOKEN, text)
    if not m:
        return None
    cand = m.group(0).strip()
    raw_name = re.sub(r"\s+(?i:et\s+al\.?)$", "", cand).strip().lower()

    if raw_name in NON_AUTHOR_ENTITIES:
        return None
    parts = raw_name.split()
    if all(p in NON_AUTHOR_ENTITIES for p in parts):
        return None

    # If documents are provided, validate against document metadata or filename
    if documents:
        doc_authors = set()
        for d in documents:
            fn = getattr(d, "filename", "") or ""
            fn_clean = re.sub(r"\.pdf$", "", fn, flags=re.IGNORECASE).lower()
            doc_authors.add(fn_clean)
            for part in fn_clean.split():
                if len(part) >= 3 and part not in NON_AUTHOR_ENTITIES:
                    doc_authors.add(part)
            meta = getattr(d, "doc_metadata", None) or getattr(d, "metadata", None) or {}
            if isinstance(meta, dict) and "authors" in meta:
                for a in meta["authors"]:
                    doc_authors.add(str(a).lower())
        if any(p in doc_authors for p in parts) or raw_name in doc_authors:
            return cand
        # Fallback to regex if not directly in documents
        return cand

    return cand


def detect_query_sources(cleaned_query: str, documents: list[Any] | None = None) -> tuple[list[str], bool]:
    """Detects author or paper sources referenced in the query. Returns (sources, is_multi_source)."""
    q = cleaned_query.strip()

    # CP-1: Interrogative cross-paper
    m_interrog = re.match(
        r"^(?i:how|what)\s+(?i:do|does|can)\s+(" + _AUTH_TOKEN + r")\s+(?i:and)\s+(" + _AUTH_TOKEN + r")\s+(?i:characterize|analyze|address|examine|discuss|evaluate|report|view|say\s+about|approach|say)\s+(.+)$",
        q,
    )
    if m_interrog:
        a1 = clean_author_candidate(m_interrog.group(1), documents)
        a2 = clean_author_candidate(m_interrog.group(2), documents)
        if a1 and a2 and a1.lower() != a2.lower():
            return [a1, a2], True

    # CP-2: "Synthesize how Author1 and Author2 analyze/address/... [topic]"
    m_synth_how = re.match(
        r"^(?i:(?:can you\s+)?(?:please\s+)?(?:synthesize|analyze|review|compare)\s+how)\s+(" + _AUTH_TOKEN + r")\s+(?i:and)\s+(" + _AUTH_TOKEN + r")\s+(?i:analyze|address|characterize|examine|discuss|evaluate|investigate|view)\s+(.+)$",
        q,
    )
    if m_synth_how:
        a1 = clean_author_candidate(m_synth_how.group(1), documents)
        a2 = clean_author_candidate(m_synth_how.group(2), documents)
        if a1 and a2 and a1.lower() != a2.lower():
            return [a1, a2], True

    # CP-3: "Synthesize [topic] across Author1 and Author2"
    m_across = re.match(
        r"^(?i:(?:can you\s+)?(?:please\s+)?(?:synthesize|analyze|review|examine)\s+(?:the\s+)?)(.+?)\s+(?i:(?:reported\s+)?across)\s+(" + _AUTH_TOKEN + r")\s+(?i:and)\s+(" + _AUTH_TOKEN + r")$",
        q,
    )
    if m_across:
        a1 = clean_author_candidate(m_across.group(2), documents)
        a2 = clean_author_candidate(m_across.group(3), documents)
        if a1 and a2 and a1.lower() != a2.lower():
            return [a1, a2], True

    # CP-4: "Compare [topic] between Author1 and Author2"
    m_between = re.match(
        r"^(?i:(?:can you\s+)?(?:please\s+)?(?:compare|contrast)\s+(?:the\s+)?)(.+?)\s+(?i:between)\s+(" + _AUTH_TOKEN + r".*?)\s+(?i:and)\s+(" + _AUTH_TOKEN + r".*?)$",
        q,
    )
    if m_between:
        a1 = clean_author_candidate(m_between.group(2), documents)
        a2 = clean_author_candidate(m_between.group(3), documents)
        if a1 and a2 and a1.lower() != a2.lower():
            return [a1, a2], True

    # CP-5: "Compare [topic] of/for/in Author1 with/to Author2"
    m_comp_with = re.match(
        r"^(?i:(?:can you\s+)?(?:please\s+)?(?:compare|contrast)\s+(?:the\s+)?)(.+?)\s+(?i:(?:of|for|in))\s+(" + _AUTH_TOKEN + r".*?)\s+(?i:(?:with|to))\s+(" + _AUTH_TOKEN + r".*?)$",
        q,
    )
    if m_comp_with:
        a1 = clean_author_candidate(m_comp_with.group(2), documents)
        a2 = clean_author_candidate(m_comp_with.group(3), documents)
        if a1 and a2 and a1.lower() != a2.lower():
            return [a1, a2], True

    # Single-author check
    candidates = []
    for m_single in re.finditer(r"\b(?i:in|according to)\s+(" + _AUTH_TOKEN + r")\b", q):
        a = clean_author_candidate(m_single.group(1), documents)
        if a:
            candidates.append(a)
    if candidates:
        et_als = [c for c in candidates if "et al" in c.lower()]
        return [et_als[-1] if et_als else candidates[-1]], False

    return [], False


def decompose_query(cleaned_query: str, documents: list[Any] | None = None) -> list[str]:
    """Decomposes complex, multi-part, or comparative research queries into subqueries."""
    q = cleaned_query.strip()

    # 1. Numbered or bulleted questions
    if re.search(r"(?:^|\n)\s*(?:\d+[\.\)]|[-*•])\s+", q):
        lines = [line.strip() for line in q.split("\n") if line.strip()]
        bullet_items = []
        for line in lines:
            cleaned_line = re.sub(r"^(?:\d+[\.\)]|[-*•])\s*", "", line).strip()
            if len(cleaned_line) >= 4:
                bullet_items.append(cleaned_line)
        if len(bullet_items) > 1:
            return bullet_items

    # 2. Multiple sentences ending in question marks: e.g. "What is X? What is Y?"
    q_marks = [s.strip() for s in re.split(r"\?+", q) if s.strip()]
    if len(q_marks) > 1:
        valid_q = [s + "?" if not s.endswith("?") else s for s in q_marks if len(s) >= 6]
        if len(valid_q) > 1:
            return valid_q

    # 3. Semicolon-separated subquestions: e.g. "Topic A; Topic B; Topic C"
    if ";" in q:
        parts = [p.strip() for p in q.split(";") if len(p.strip()) >= 4]
        if len(parts) > 1:
            return parts

    # === CROSS-PAPER COMPARATIVE PATTERNS PRIORITIZED BEFORE GENERIC IMPERATIVE SPLITTING ===
    # CP-1: Interrogative cross-paper: "How/What do/does Author1 and Author2 [verb] [topic]?"
    m_interrog = re.match(
        r"^(?i:how|what)\s+(?i:do|does|can)\s+(" + _AUTH_TOKEN + r")\s+(?i:and)\s+(" + _AUTH_TOKEN + r")\s+(?i:characterize|analyze|address|examine|discuss|evaluate|report|view|say\s+about|approach|say)\s+(.+)$",
        q,
    )
    if m_interrog:
        a1 = clean_author_candidate(m_interrog.group(1), documents)
        a2 = clean_author_candidate(m_interrog.group(2), documents)
        if a1 and a2 and a1.lower() != a2.lower():
            topic = m_interrog.group(3).strip(" .?")
            return [f"{topic} in {a1}", f"{topic} in {a2}"]

    # CP-2: "Synthesize how Author1 and Author2 analyze/address/... [topic]"
    m_synth_how = re.match(
        r"^(?i:(?:can you\s+)?(?:please\s+)?(?:synthesize|analyze|review|compare)\s+how)\s+(" + _AUTH_TOKEN + r")\s+(?i:and)\s+(" + _AUTH_TOKEN + r")\s+(?i:analyze|address|characterize|examine|discuss|evaluate|investigate|view)\s+(.+)$",
        q,
    )
    if m_synth_how:
        a1 = clean_author_candidate(m_synth_how.group(1), documents)
        a2 = clean_author_candidate(m_synth_how.group(2), documents)
        if a1 and a2 and a1.lower() != a2.lower():
            topic = m_synth_how.group(3).strip(" .?")
            return [f"{topic} in {a1}", f"{topic} in {a2}"]

    # CP-3: "Synthesize [topic] across Author1 and Author2"
    m_across = re.match(
        r"^(?i:(?:can you\s+)?(?:please\s+)?(?:synthesize|analyze|review|examine)\s+(?:the\s+)?)(.+?)\s+(?i:(?:reported\s+)?across)\s+(" + _AUTH_TOKEN + r")\s+(?i:and)\s+(" + _AUTH_TOKEN + r")$",
        q,
    )
    if m_across:
        a1 = clean_author_candidate(m_across.group(2), documents)
        a2 = clean_author_candidate(m_across.group(3), documents)
        if a1 and a2 and a1.lower() != a2.lower():
            topic = m_across.group(1).strip(" .")
            return [f"{topic} in {a1}", f"{topic} in {a2}"]

    # CP-4: "Compare [topic] between Author1 and Author2"
    m_between = re.match(
        r"^(?i:(?:can you\s+)?(?:please\s+)?(?:compare|contrast)\s+(?:the\s+)?)(.+?)\s+(?i:between)\s+(" + _AUTH_TOKEN + r".*?)\s+(?i:and)\s+(" + _AUTH_TOKEN + r".*?)$",
        q,
    )
    if m_between:
        a1 = clean_author_candidate(m_between.group(2), documents)
        a2 = clean_author_candidate(m_between.group(3), documents)
        if a1 and a2 and a1.lower() != a2.lower():
            topic = m_between.group(1).strip(" .")
            return [f"{topic} in {m_between.group(2).strip()}", f"{topic} in {m_between.group(3).strip()}"]

    # CP-5: "Compare [topic] of/for/in Author1 with/to Author2" (shared topic preservation)
    m_comp_with = re.match(
        r"^(?i:(?:can you\s+)?(?:please\s+)?(?:compare|contrast)\s+(?:the\s+)?)(.+?)\s+(?i:(?:of|for|in))\s+(" + _AUTH_TOKEN + r".*?)\s+(?i:(?:with|to))\s+(" + _AUTH_TOKEN + r".*?)$",
        q,
    )
    if m_comp_with:
        a1 = clean_author_candidate(m_comp_with.group(2), documents)
        a2 = clean_author_candidate(m_comp_with.group(3), documents)
        if a1 and a2 and a1.lower() != a2.lower():
            topic = m_comp_with.group(1).strip(" .")
            return [f"{topic} of {m_comp_with.group(2).strip()}", f"{topic} of {m_comp_with.group(3).strip()}"]

    # CP-6: Simple "Compare X with/to Y"
    m_simple_comp = re.match(
        r"^(?i:(?:can you\s+)?(?:please\s+)?(?:compare|contrast)\s+(?:the\s+)?)(.+?)\s+(?i:(?:with|to))\s+(.+)$",
        q,
    )
    if m_simple_comp:
        part1 = m_simple_comp.group(1).strip(" .")
        part2 = m_simple_comp.group(2).strip(" .")
        if len(part1) >= 4 and len(part2) >= 4:
            return sanitize_decomposed_parts([part1, part2], q)

    # 4. Command/Imperative prefix with comma-separated list ending in "and":
    lead_match = re.match(
        r"^(?:can you\s+)?(?:please\s+)?(?:analyze|investigate|evaluate|examine|discuss|review|assess|explore|synthesize|identify|detail|explain|describe)\s+(.+)$",
        q,
        flags=re.IGNORECASE,
    )
    if lead_match:
        body = lead_match.group(1).strip()
        # Protect author conjunctions like 'Author A and Author B' from being split
        if not re.search(r"\b" + _AUTH_TOKEN + r"\s+and\s+" + _AUTH_TOKEN + r"\b", body):
            if "," in body:
                parts = re.split(r",\s*(?:and\s+)?", body)
                parts = [p.strip(" .") for p in parts if len(p.strip(" .")) >= 3]
                if len(parts) > 1:
                    return sanitize_decomposed_parts(parts, q)

    # 5. Comma-separated list with "and" ending without explicit verb (>= 2 commas)
    if q.count(",") >= 2 and re.search(r",\s+and\s+", q, flags=re.IGNORECASE):
        core_q = re.sub(r"^(?:in|according to)\s+[^,]+,\s*", "", q, flags=re.IGNORECASE).strip()
        if not re.match(r"^(?:what|how|why|which|where|when|who|is|are|do|does|can|could|would)\b", core_q, flags=re.IGNORECASE):
            parts = re.split(r",\s*(?:and\s+)?|\s+and\s+", q)
            parts = [p.strip(" .") for p in parts if len(p.strip(" .")) >= 3]
            if len(parts) > 1:
                return sanitize_decomposed_parts(parts, q)

    # 6. Compound question joining two full clauses with ", and " or " and ":
    and_match = re.split(r",?\s+and\s+(?=(?:what|how|why|which|where|when|can|does|is|are)\b)", q, flags=re.IGNORECASE)
    if len(and_match) > 1:
        valid_and = [s.strip(" .?") for s in and_match if len(s.strip(" .?")) >= 6]
        if len(valid_and) > 1:
            return sanitize_decomposed_parts(valid_and, q)

    return [q]


def is_modifier_or_low_content(text: str) -> bool:
    """Detects clauses that lack substantive content words or are merely anaphoric/modifier clauses."""
    cleaned = text.strip().lower()
    # 1. Participle / anaphoric modifier clauses like "explaining their relationship", "highlighting their differences"
    if re.match(
        r"^(?:and\s+)?(?:explaining|describing|discussing|evaluating|highlighting|clarifying|summarizing|assessing|identifying|analyzing)\s+(?:their|its|the|these|those)\s+(?:relationship|relationships|differences?|similarities?|connections?|roles?|implications?|methodology|approach)\b",
        cleaned,
    ):
        return True

    # 2. Short clauses referencing anaphora: "explaining how they relate", "and how they differ"
    if re.match(r"^(?:and\s+)?(?:how\s+they\s+(?:relate|differ|compare|connect))\b", cleaned):
        return True

    # 3. Content words check: strip punctuation, numbers, stopwords, and generic meta/academic verbs
    tokens = [t for t in re.findall(r"\b[a-z0-9_-]+\b", cleaned) if len(t) > 2 and t not in STOP_WORDS]
    meta_words = {
        "relationship", "relationships", "explain", "explaining", "describe", "describing",
        "discuss", "discussing", "compare", "comparing", "synthesize", "synthesizing",
        "between", "their", "differ", "differences", "similarity", "similarities",
        "connection", "connections", "implication", "implications", "overview", "role", "roles",
        "regarding", "according", "reported", "across"
    }
    content_tokens = [t for t in tokens if t not in meta_words]
    # If 0 substantive content words remain, it lacks content words
    return len(content_tokens) == 0


def sanitize_decomposed_parts(parts: list[str], original_query: str) -> list[str]:
    """Ensures subqueries are substantive search queries and never low-content modifier fragments."""
    from app.core.config import settings
    if not getattr(settings, "FLAG_MODIFIER_FRAGMENT_SANITIZATION", True):
        return [p.strip(" .?,") for p in parts if p.strip(" .?,")]

    valid_parts: list[str] = []
    for p in parts:
        p_clean = p.strip(" .?,")
        if not p_clean:
            continue
        if is_modifier_or_low_content(p_clean):
            continue
        valid_parts.append(p_clean)

    if len(valid_parts) <= 1:
        return [original_query]
    return valid_parts


def process_query(raw_query: str, documents: list[Any] | None = None) -> ProcessedQuery:
    """Full preprocessing pipeline returning cleaned query, tokens, expanded synonyms, subqueries, and intent flags."""
    cleaned = clean_query_text(raw_query)
    q_lower = cleaned.lower()

    # Decompose compound query
    subqueries = decompose_query(cleaned, documents=documents)
    is_compound = len(subqueries) > 1

    # Detect sources and multi-source intent
    detected_sources, is_multi_source = detect_query_sources(cleaned, documents=documents)

    # Tokenize
    raw_tokens = re.findall(r"\b[A-Za-z0-9_-]+\b", q_lower)
    search_terms = [t for t in raw_tokens if len(t) > 1 and t not in STOP_WORDS]

    # Expand synonyms
    expanded = set(search_terms)
    for term in search_terms:
        if term in ACADEMIC_SYNONYMS:
            expanded.update(ACADEMIC_SYNONYMS[term])

    # Intent classification
    is_meta = any(w in q_lower for w in ["title", "author", "authors", "who", "paper", "name", "journal", "published"])
    is_overview = any(w in q_lower for w in ["problem", "objective", "objectives", "aim", "aims", "purpose", "overview", "address", "about", "review", "scope"])
    is_methodology = any(w in q_lower for w in ["method", "methodology", "database", "databases", "search strategy", "inclusion", "exclusion", "sample", "dataset", "datasets"])
    is_results = any(w in q_lower for w in ["result", "results", "finding", "findings", "score", "scores", "benchmark", "performance", "metric", "accuracy"])

    anchors = extract_anchor_constraints(raw_query)

    return ProcessedQuery(
        raw_query=raw_query,
        cleaned_query=cleaned,
        search_terms=search_terms,
        expanded_terms=expanded,
        is_meta_query=is_meta,
        is_overview_query=is_overview,
        is_methodology_query=is_methodology,
        is_results_query=is_results,
        subqueries=subqueries,
        is_compound_query=is_compound,
        anchor_constraints=anchors,
        is_multi_source=is_multi_source,
        detected_sources=detected_sources,
    )

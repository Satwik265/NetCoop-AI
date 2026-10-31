"""Character n-gram and token-aware TF-IDF field-name matcher with cosine similarity and LLM fallback."""

import re
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class FieldNameMatcher:
    """Matches arbitrary or mutated field names to canonical telemetry schema names."""

    CANONICAL_NAMES = [
        "device_id",
        "device_type",
        "device_status",
        "timestamp",
        "latency_ms",
        "jitter_ms",
        "packet_loss_pct",
        "throughput_mbps",
        "bandwidth_mbps",
        "link_utilization_pct",
        "cpu_pct",
        "memory_pct",
        "queue_drops",
        "interface_errors",
        "link_flaps",
        "wifi_rssi_dbm",
        "wifi_retransmission_pct",
        "dns_resolution_ms",
        "dns_failure_pct",
        "dhcp_failure_pct",
    ]

    # Domain entities that distinguish orthogonal subsystems
    DOMAIN_ENTITIES = {
        "cpu",
        "link",
        "wifi",
        "dns",
        "dhcp",
        "memory",
        "mem",
        "jitter",
        "latency",
        "queue",
        "interface",
    }

    def __init__(self, threshold: float = 0.50) -> None:
        self.threshold = threshold
        canon_preprocessed = [self._preprocess(c) for c in self.CANONICAL_NAMES]
        self.vectorizer_char = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), lowercase=True)
        self.vectorizer_word = TfidfVectorizer(analyzer="word", lowercase=True)

        self.vectorizer_char.fit(canon_preprocessed)
        self.vectorizer_word.fit(canon_preprocessed)

        self.canonical_char_vecs = self.vectorizer_char.transform(canon_preprocessed)
        self.canonical_word_vecs = self.vectorizer_word.transform(canon_preprocessed)

    @classmethod
    def _tokenize(cls, s: str) -> List[str]:
        return [t for t in re.split(r"[_\s\-]+", str(s).lower()) if t]

    @classmethod
    def _preprocess(cls, s: str) -> str:
        return " ".join(cls._tokenize(s))

    def match_field(self, field_name: str) -> Tuple[Optional[str], float, bool]:
        """Match unknown field name to closest canonical target using n-gram cosine similarity and token coverage.

        Returns:
            (best_canonical_or_none, similarity_score, is_confident)
        """
        clean_name = str(field_name).lower().strip()
        if clean_name in self.CANONICAL_NAMES:
            return clean_name, 1.0, True

        query_tokens = self._tokenize(clean_name)
        query_prep = " ".join(query_tokens)

        qc = self.vectorizer_char.transform([query_prep])
        qw = self.vectorizer_word.transform([query_prep])

        sims_char = cosine_similarity(qc, self.canonical_char_vecs)[0]
        sims_word = cosine_similarity(qw, self.canonical_word_vecs)[0]

        scores: List[float] = []
        for idx, canon_name in enumerate(self.CANONICAL_NAMES):
            c_tokens = self._tokenize(canon_name)

            # Token overlap coverage (supports prefix matching like mem -> memory)
            matches = 0
            for ct in c_tokens:
                if any(
                    ct == qt or (len(qt) >= 3 and ct.startswith(qt)) or (len(ct) >= 3 and qt.startswith(ct))
                    for qt in query_tokens
                ):
                    matches += 1
            cov = matches / max(1, len(c_tokens))

            # Domain entity conflict penalty (e.g. cpu vs link)
            q_dom = {qt for qt in query_tokens if any(d.startswith(qt) or qt.startswith(d) for d in self.DOMAIN_ENTITIES)}
            c_dom = {ct for ct in c_tokens if any(d.startswith(ct) or ct.startswith(d) for d in self.DOMAIN_ENTITIES)}
            dom_penalty = 0.0
            if q_dom and c_dom and not (q_dom & c_dom):
                dom_penalty = 0.40

            # Composite similarity
            score = 0.35 * sims_char[idx] + 0.35 * sims_word[idx] + 0.30 * cov - dom_penalty
            scores.append(float(score))

        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])
        best_match = self.CANONICAL_NAMES[best_idx]

        if best_score >= self.threshold:
            return best_match, round(best_score, 3), True

        # Below threshold: check if LLM fallback can propose a mapping
        proposed_mapping = self._propose_llm_mapping(clean_name)
        if proposed_mapping:
            return proposed_mapping, round(best_score, 3), False

        return None, round(best_score, 3), False

    def _propose_llm_mapping(self, field_name: str) -> Optional[str]:
        """Propose mapping using GeminiBridge if configured; otherwise unmapped."""
        try:
            from netcoop.llm.gemini_bridge import GeminiBridge
            bridge = GeminiBridge()
            prompt = (
                f"You are a network telemetry normalizer. Map this telemetry field '{field_name}' "
                f"to exactly one of these canonical fields or 'UNKNOWN': {', '.join(self.CANONICAL_NAMES)}. "
                "Respond with only the canonical field name."
            )
            resp = bridge.query(prompt)
            if resp and resp.strip() in self.CANONICAL_NAMES:
                return resp.strip()
        except Exception:
            pass
        return None

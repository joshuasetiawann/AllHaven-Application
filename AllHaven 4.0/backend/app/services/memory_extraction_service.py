# backend/app/services/memory_extraction_service.py
"""Hybrid memory extraction: rule-based (inline) + LLM (daemon thread, non-blocking).

Rule-based extraction fires synchronously with zero latency.
LLM extraction runs in a daemon thread only when rule-based finds ambiguous patterns.
Secret patterns are detected and NEVER saved — they're silently dropped.
"""
from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.principal import Principal

# --------------------------------------------------------------------------- #
# Secret detection — ALWAYS run before saving anything
# --------------------------------------------------------------------------- #

_SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r'\bsk-[A-Za-z0-9_-]{12,}\b'),            # OpenAI-style keys
    re.compile(r'\b(?:gsk|pk|rk|xoxb|xoxp|ghp|gho|github_pat)_[A-Za-z0-9_-]{8,}\b'),
    re.compile(r'\bAKIA[0-9A-Z]{16}\b'),                  # AWS access key
    re.compile(r'\bBearer\s+[A-Za-z0-9._-]{12,}\b', re.IGNORECASE),
    re.compile(r'\beyJ[A-Za-z0-9._-]{20,}\b'),            # JWT
    re.compile(r'\b[A-Za-z0-9_-]{40,}\b'),                # long opaque tokens
    re.compile(
        r'\b(api[_-]?key|secret|token|password|passwd|pwd|authorization)\b\s*[:=]\s*\S+',
        re.IGNORECASE,
    ),
]


def _contains_secret(text: str) -> bool:
    for pat in _SECRET_PATTERNS:
        if pat.search(text):
            return True
    return False


# --------------------------------------------------------------------------- #
# Memory candidate
# --------------------------------------------------------------------------- #

@dataclass
class MemoryCandidate:
    category: str       # "Profile" | "Preferences" | "Projects" | ...
    title: str
    content: str
    confidence: float   # 0.0–1.0
    sensitivity: str    # "LOW" | "MEDIUM" | "HIGH"
    snippet: str        # the raw phrase that triggered this
    explicit: bool = False  # user explicitly said "ingat/remember" → may auto-save


# Pure greetings / acks should never become memories.
_GREETING_RE = re.compile(
    r"^\s*(halo|hai|hi|hello|hey|p|pagi|siang|sore|malam|selamat\s+\w+|thanks?|thank\s+you|"
    r"makasih|terima\s+kasih|ok(?:e|ay|sip)?|sip|mantap|noted|test|tes|coba)\b[\s!.?]*$",
    re.IGNORECASE,
)


def _should_skip_memory(user_msg: str) -> bool:
    """3.9 gate: never extract memory from finance/task/note commands, greetings, or
    trivially short messages — those belong to their own systems, not memory."""
    text = (user_msg or "").strip()
    if len(text) < 6:
        return True
    if _GREETING_RE.match(text):
        return True
    from app.services import ai_intent_router

    intent = ai_intent_router.classify(text).intent
    return intent in (ai_intent_router.FINANCE, ai_intent_router.TASK, ai_intent_router.NOTE)


# --------------------------------------------------------------------------- #
# Rule-based extraction patterns
# --------------------------------------------------------------------------- #

# Each entry: (compiled_regex, category, title_template, content_template, confidence, sensitivity)
# Capture group 1 is always the extracted value.
_RULES: list[tuple] = [
    # Explicit memory commands
    (re.compile(r'(?:tolong\s+)?(?:ingat|simpan|catat)\s+(?:bahwa\s+)?(.{4,180}?)(?:[.!?]|$)', re.IGNORECASE),
     "Other", "User-provided memory", "User explicitly asked the AI to remember: {value}.", 0.95, "LOW"),
    (re.compile(r'(?:remember|save|note)\s+(?:that\s+)?(.{4,180}?)(?:[.!?]|$)', re.IGNORECASE),
     "Other", "User-provided memory", "User explicitly asked the AI to remember: {value}.", 0.92, "LOW"),

    # Name
    (re.compile(r'nama\s+saya\s+(?:adalah\s+)?([A-Za-z][A-Za-z\s]{1,40}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User name", "User's name is {value}.", 0.95, "LOW"),
    (re.compile(r'saya\s+bernama\s+([A-Za-z][A-Za-z\s]{1,40}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User name", "User's name is {value}.", 0.95, "LOW"),
    (re.compile(r'panggil\s+(?:saya|aku)\s+([A-Za-z][A-Za-z\s]{1,30}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User name", "User prefers to be called {value}.", 0.9, "LOW"),
    (re.compile(r'my\s+name\s+is\s+([A-Za-z][A-Za-z\s]{1,40}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User name", "User's name is {value}.", 0.95, "LOW"),

    # Education / location
    (re.compile(r'saya\s+(?:sekolah|belajar|kuliah)\s+di\s+([A-Za-z0-9][A-Za-z0-9\s&._-]{1,60}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "School", "User studies at {value}.", 0.92, "LOW"),
    (re.compile(r'(?:saya\s+)?(?:tinggal|berdomisili)\s+di\s+([A-Za-z0-9][A-Za-z0-9\s,._-]{1,80}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "Location", "User lives in {value}.", 0.88, "LOW"),
    (re.compile(r'i\s+(?:study|go\s+to\s+school)\s+at\s+([A-Za-z0-9][A-Za-z0-9\s&._-]{1,60}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "School", "User studies at {value}.", 0.9, "LOW"),

    # Role / job
    (re.compile(r'saya\s+(?:adalah\s+)?(?:seorang\s+)?([A-Za-z][A-Za-z\s]{1,50}?)\s+\b(?:di|pada|yang|bekerja)\b', re.IGNORECASE),
     "Profile", "User role", "User's role is {value}.", 0.75, "LOW"),
    (re.compile(r'(?:jabatan|posisi|pekerjaan)\s+saya\s+(?:adalah\s+)?([A-Za-z][A-Za-z\s]{1,50}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User role", "User's role is {value}.", 0.85, "LOW"),
    (re.compile(r'bekerja\s+sebagai\s+([A-Za-z][A-Za-z\s]{1,50}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User role", "User's role is {value}.", 0.85, "LOW"),
    (re.compile(r'i\s+(?:am|work\s+as)\s+(?:a\s+|an\s+)?([A-Za-z][A-Za-z\s]{1,50}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Profile", "User role", "User's role is {value}.", 0.8, "LOW"),

    # Project
    (re.compile(r'project\s+(?:saya|kami|ini|utama\s+saya)\s+(?:adalah\s+|bernama\s+)?([A-Za-z0-9][A-Za-z0-9\s/_-]{1,60}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Projects", "Current project name", "User's current project is {value}.", 0.9, "LOW"),
    (re.compile(r'(?:sedang\s+)?(?:mengerjakan|membangun|membuat|develop)\s+(?:project\s+)?(?:bernama\s+|yang\s+namanya\s+)?([A-Za-z0-9][A-Za-z0-9\s/_-]{1,60}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Projects", "Current project name", "User is building a project called {value}.", 0.8, "LOW"),
    (re.compile(r'(?:this\s+)?project\s+(?:is\s+called\s+|named\s+|name\s+is\s+)([A-Za-z0-9][A-Za-z0-9\s/_-]{1,60}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Projects", "Current project name", "User's current project is {value}.", 0.9, "LOW"),

    (re.compile(r'untuk\s+project\s+([A-Za-z0-9][A-Za-z0-9\s/_-]{1,60}?),?\s+saya\s+mau\s+(.{8,160}?)(?:[.!?]|$)', re.IGNORECASE),
     "Decisions", "Project decision", "For project {value}, the user made a decision recorded in chat.", 0.75, "LOW"),

    # Response preferences
    (re.compile(r'(?:mau|ingin|prefer|suka|tolong|jawab|jawabannya|ai(?:nya)?)\s+.{0,50}?((?:tanpa|ga|gak|nggak|tidak)\s+basa\s+basi|langsung\s*(?:sat\s*set)?|sat\s*set)', re.IGNORECASE),
     "Writing style", "Direct response style", "User prefers direct, concise responses without small talk.", 0.92, "LOW"),
    (re.compile(r'((?:no\s+small\s+talk|skip\s+the\s+preamble|be\s+direct|concise\s+answers?))', re.IGNORECASE),
     "Writing style", "Direct response style", "User prefers direct, concise responses without small talk.", 0.9, "LOW"),
    (re.compile(r'saya\s+suka\s+jawaban\s+(?:yang\s+)?([A-Za-z][A-Za-z\s,]{2,80}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Preferences", "Response style preference", "User prefers {value} responses.", 0.9, "LOW"),
    (re.compile(r'(?:tolong\s+)?jawab\s+(?:dengan\s+)?(?:cara\s+)?(?:yang\s+)?([A-Za-z][A-Za-z\s,]{2,60}?)(?:\s+ya)?(?:[.,!?]|$)', re.IGNORECASE),
     "Preferences", "Response style preference", "User prefers {value} responses.", 0.75, "LOW"),
    (re.compile(r'jangan\s+(?:pernah\s+)?([A-Za-z][A-Za-z\s]{2,60}?)\s+(?:dalam\s+jawaban|ketika\s+menjawab)', re.IGNORECASE),
     "Preferences", "Response style - avoid", "User dislikes {value} in responses.", 0.85, "LOW"),
    (re.compile(r'i\s+(?:prefer|like|want)\s+(?:responses?\s+(?:that\s+are\s+|to\s+be\s+))?([A-Za-z][A-Za-z\s,]{2,80}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Preferences", "Response style preference", "User prefers {value} responses.", 0.85, "LOW"),
    (re.compile(r'kebutuhan\s+saya\s+untuk\s+ai\s+ini\s+(?:adalah\s+)?(.{5,160}?)(?:[.!?]|$)', re.IGNORECASE),
     "Preferences", "AI usage needs", "User wants the AI to help with {value}.", 0.92, "LOW"),
    (re.compile(r'ai(?:nya)?\s+.*?(ngoding|coding|programming|jadwal|schedule).{0,120}', re.IGNORECASE),
     "Work context", "AI work focus", "User wants the AI to help with coding and schedule management.", 0.86, "LOW"),
    (re.compile(r'saya\s+(?:suka|senang)\s+(.{3,120}?)(?:[.!?]|$)', re.IGNORECASE),
     "Preferences", "User likes", "User likes {value}.", 0.82, "LOW"),
    (re.compile(r'saya\s+(?:tidak\s+suka|ga\s+suka|gak\s+suka|nggak\s+suka|benci)\s+(.{3,120}?)(?:[.!?]|$)', re.IGNORECASE),
     "Preferences", "User dislikes", "User dislikes {value}.", 0.82, "LOW"),
    (re.compile(r'(?:i\s+)?(?:like|love)\s+(.{3,120}?)(?:[.!?]|$)', re.IGNORECASE),
     "Preferences", "User likes", "User likes {value}.", 0.8, "LOW"),
    (re.compile(r'(?:i\s+)?(?:dislike|hate|do\s+not\s+like|don\'t\s+like)\s+(.{3,120}?)(?:[.!?]|$)', re.IGNORECASE),
     "Preferences", "User dislikes", "User dislikes {value}.", 0.8, "LOW"),
    (re.compile(r'saya\s+(?:mau|ingin|pengen|butuh)\s+(.{5,160}?)(?:[.!?]|$)', re.IGNORECASE),
     "Goals", "User intent", "User wants {value}.", 0.74, "LOW"),
    (re.compile(r'i\s+(?:want|need|would\s+like)\s+(.{5,160}?)(?:[.!?]|$)', re.IGNORECASE),
     "Goals", "User intent", "User wants {value}.", 0.74, "LOW"),
    (re.compile(r'(?:jadwal|schedule)\s+saya\s+(.{5,160}?)(?:[.!?]|$)', re.IGNORECASE),
     "Tasks context", "Schedule context", "User's schedule context: {value}.", 0.8, "LOW"),
    (re.compile(r'(?:repo|repository|github)\s+saya\s+(.{5,160}?)(?:[.!?]|$)', re.IGNORECASE),
     "Work context", "Repository context", "User's repository context: {value}.", 0.82, "LOW"),

    # Tech stack
    (re.compile(r'(?:saya\s+)?(?:menggunakan|pakai|pake)\s+([A-Za-z0-9][A-Za-z0-9\s+_/-]{1,60}?)\s+(?:sebagai\s+)?(?:untuk|framework|library|tech\s+stack)', re.IGNORECASE),
     "Technical", "Tech stack", "User uses {value}.", 0.8, "LOW"),
    (re.compile(r'tech\s+stack\s+(?:saya\s+)?(?:adalah\s+|:\s*)?([A-Za-z0-9][A-Za-z0-9\s+,_/-]{2,100}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Technical", "Tech stack", "User's tech stack: {value}.", 0.9, "LOW"),

    # Language preference
    (re.compile(r'(?:bahasa\s+)?(?:pemrograman\s+)?(?:yang\s+saya\s+)?(?:pakai|gunakan|suka)\s+(?:adalah\s+)?([A-Za-z0-9#++\s]{2,40}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Technical", "Programming language", "User uses {value}.", 0.8, "LOW"),

    # Goals
    (re.compile(r'(?:goal|target|tujuan)\s+saya\s+(?:adalah\s+)?([A-Za-z][A-Za-z\s,.]{2,120}?)(?:[.,!?]|$)', re.IGNORECASE),
     "Goals", "User goal", "User's goal: {value}.", 0.8, "LOW"),
]


def rule_based_extract(text: str) -> List[MemoryCandidate]:
    """Extract memory candidates from text using rule-based patterns. Fast, no I/O."""
    if _contains_secret(text):
        return []  # entire message has a secret — skip to be safe

    candidates: List[MemoryCandidate] = []
    seen_titles: set[str] = set()

    for pattern, category, title, content_tpl, confidence, sensitivity in _RULES:
        for m in pattern.finditer(text):
            value = m.group(1).strip().rstrip(".,!?").strip()
            if not value or len(value) < 2:
                continue
            if _contains_secret(value):
                continue
            c = MemoryCandidate(
                category=category,
                title=title,
                content=content_tpl.format(value=value),
                confidence=confidence,
                sensitivity=sensitivity,
                snippet=m.group(0)[:200],
                # Only the explicit "ingat/simpan/catat/remember/save/note that ..."
                # rules may auto-save; everything else must go to review.
                explicit=(title == "User-provided memory"),
            )
            key = f"{category}:{title}"
            if key not in seen_titles:
                seen_titles.add(key)
                candidates.append(c)

    return candidates


# --------------------------------------------------------------------------- #
# Auto-save vs suggest decision
# --------------------------------------------------------------------------- #

def _auto_save_or_suggest(
    db: Session,
    principal: Principal,
    candidate: MemoryCandidate,
    session_id: Optional[uuid.UUID],
    extraction_method: str = "rule_based",
) -> None:
    from app.services import ai_settings_service, memory_service

    require_approval_sensitive = ai_settings_service.is_memory_require_approval_sensitive(
        db, principal
    )

    # 3.9 policy: only auto-save EXPLICIT "ingat/remember" facts or HIGH-confidence
    # (>=0.85) stable facts (names, school, role, tech stack, durable preferences).
    # The noisy mid-confidence rules ("saya suka X" 0.82, "saya mau X" 0.74) and all
    # transient Goals/wants are demoted to Memory Review instead of silently saving.
    # Sensitive items still require approval when that setting is on.
    may_auto_save = candidate.explicit or (
        candidate.confidence >= 0.85 and candidate.category != "Goals"
    )
    needs_approval = (not may_auto_save) or (
        require_approval_sensitive and candidate.sensitivity in ("MEDIUM", "HIGH")
    )
    if needs_approval:
        memory_service.create_suggestion(
            db, principal,
            category=candidate.category,
            title=candidate.title,
            content=candidate.content,
            source_session_id=session_id,
            source_snippet=candidate.snippet,
            confidence=candidate.confidence,
            sensitivity=candidate.sensitivity,
            extraction_method=extraction_method,
        )
        return

    # Setting OFF (or LOW sensitivity) + HIGH confidence → upsert directly (auto-save).
    memory_service.upsert_memory(
        db, principal,
        category=candidate.category,
        title=candidate.title,
        content=candidate.content,
        source="chat_extracted",
        sensitivity=candidate.sensitivity,
        confidence=candidate.confidence,
        source_session_id=session_id,
    )


# --------------------------------------------------------------------------- #
# Background LLM extraction (daemon thread, never blocks response)
# --------------------------------------------------------------------------- #

def _llm_extract_thread(
    workspace_id_str: str,
    user_id_str: str,
    email_str: str,
    user_msg: str,
    assistant_msg: str,
    session_id_str: str,
) -> None:
    """Runs in a daemon thread. Creates its own DB session. Never raises."""
    from app.core.database import SessionLocal
    from app.core.principal import Principal as _Principal

    db = SessionLocal()
    try:
        principal = _Principal(
            workspace_id=uuid.UUID(workspace_id_str),
            user_id=uuid.UUID(user_id_str),
            email=email_str,
        )
        session_id = uuid.UUID(session_id_str) if session_id_str else None
        candidates = _llm_extract_candidates(user_msg, assistant_msg, principal, db)
        for c in candidates:
            _auto_save_or_suggest(db, principal, c, session_id, extraction_method="llm")
        db.commit()
    except Exception:  # noqa: BLE001 - background thread must never raise
        pass
    finally:
        db.close()


def _llm_extract_candidates(
    user_msg: str, assistant_msg: str, principal: Principal, db: Session
) -> List[MemoryCandidate]:
    """Use the workspace's default provider to extract memory candidates from a turn.
    Returns empty list if no provider configured or on any error."""
    from app.domain.ai_memory import MEMORY_CATEGORIES, SENSITIVITY_LEVELS
    from app.services import ai_provider_router, ai_settings_service

    if not ai_settings_service.is_memory_auto_learning_enabled(db, principal):
        return []

    plan = ai_provider_router.plan_chat(db, principal, None)
    if not plan.runnable:
        return []

    prompt = (
        "You are a memory extractor. Identify ONLY stable, long-term facts or preferences worth "
        "remembering about the user. Return a JSON array of objects with keys: "
        "category (Profile|Preferences|Projects|Decisions|Writing style|Work context|UI/UX preferences|Technical|Technical preferences|Tasks context|Goals|Other), "
        "title (short, max 50 chars), content (complete sentence), confidence (0.0-1.0), sensitivity (LOW|MEDIUM|HIGH). "
        "STRICT EXCLUSIONS — return [] rather than include any of these: one-time income/expense or ANY finance "
        "transaction or amount; tasks, to-dos, or notes; greetings or small talk; transient wants/plans for today; "
        "anything the user did not state as a durable fact. Only stable preferences, identity, projects, and "
        "long-term context qualify. Do NOT include secrets, passwords, or API keys.\n\n"
        f"User: {user_msg[:800]}\nAssistant: {assistant_msg[:800]}"
    )
    try:
        result = plan.execute([{"role": "user", "content": prompt}])
        if not result.ok or not result.content:
            return []
        import json
        content = result.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        raw = json.loads(content.strip())
        if not isinstance(raw, list):
            return []
        candidates = []
        for item in raw[:10]:
            if not isinstance(item, dict):
                continue
            cat = str(item.get("category", "Profile"))
            # 3.9: finance/transaction context is never a memory — drop it outright.
            if cat == "Finance context":
                continue
            # Validate category: bogus or >50-char value would break String(50) column.
            if cat not in MEMORY_CATEGORIES:
                cat = "Profile"
            title = str(item.get("title", ""))[:200]
            content_str = str(item.get("content", ""))
            conf = float(item.get("confidence", 0.7))
            sens = str(item.get("sensitivity", "MEDIUM"))
            # Validate sensitivity: unknown value → fail-safe MEDIUM (requires approval).
            if sens not in SENSITIVITY_LEVELS:
                sens = "MEDIUM"
            # Drop candidates whose title or content contains secrets.
            if not title or not content_str or _contains_secret(content_str) or _contains_secret(title):
                continue
            candidates.append(MemoryCandidate(
                category=cat, title=title, content=content_str,
                confidence=conf, sensitivity=sens, snippet=user_msg[:200],
            ))
        return candidates
    except Exception:  # noqa: BLE001
        return []


# --------------------------------------------------------------------------- #
# Public entry point (called from chat services after each response)
# --------------------------------------------------------------------------- #

def schedule_extraction(
    db: Session,
    principal: Principal,
    user_msg: str,
    assistant_msg: str,
    session_id: Optional[uuid.UUID],
) -> int:
    """Synchronously run rule-based extraction and optionally start LLM thread.

    Returns the number of memories created/suggested synchronously.
    Never raises — errors are swallowed so they don't affect the main response.
    """
    from app.services import ai_settings_service

    try:
        if not ai_settings_service.is_memory_auto_learning_enabled(db, principal):
            return 0

        # 3.9 gate: finance/task/note commands, greetings, and trivially short
        # messages never become memory — they are owned by their own systems.
        if _should_skip_memory(user_msg):
            return 0

        candidates = rule_based_extract(user_msg)
        for c in candidates:
            _auto_save_or_suggest(db, principal, c, session_id)
        db.flush()

        # Start LLM background extraction for informative turns. Even when the
        # rules catch a few explicit facts, the LLM can still find softer context
        # (project names, working style, schedule needs) without blocking chat.
        if len(user_msg) > 20 and len(candidates) < 4:
            t = threading.Thread(
                target=_llm_extract_thread,
                args=(
                    str(principal.workspace_id),
                    str(principal.user_id),
                    principal.email,
                    user_msg,
                    assistant_msg,
                    str(session_id) if session_id else "",
                ),
                daemon=True,
            )
            t.start()

        return len(candidates)
    except Exception:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return 0


def extract_and_commit(
    db: Session,
    principal: Principal,
    *,
    user_msg: str,
    assistant_msg: str,
    session_id: Optional[uuid.UUID],
) -> None:
    """Run ``schedule_extraction`` for a finished turn and commit its memories.

    Shared post-response hook for every chat service (single, multi, debate,
    reasoning). Extraction must never break the main chat response.

    NOTE: ``schedule_extraction`` itself never raises (it swallows errors and
    rolls back internally); the try/except here exists to protect the follow-up
    ``db.commit()`` — do not "simplify" it away.
    """
    try:
        schedule_extraction(db, principal, user_msg, assistant_msg, session_id)
        db.commit()  # commit any memories created synchronously
    except Exception:  # noqa: BLE001
        db.rollback()

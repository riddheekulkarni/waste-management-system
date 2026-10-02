"""
Canonical Complaint Lifecycle & State Machine for EcoClean Civic.

Defines:
1. Core Lifecycle States:
   SUBMITTED -> AI_PROCESSING -> VERIFIED -> ASSIGNED -> IN_PROGRESS -> RESOLUTION_SUBMITTED -> RESOLVED

2. Exceptional States:
   PROCESSING_FAILED
   DUPLICATE
   REJECTED
   NEEDS_INFORMATION

3. Background Job Processing Stages:
   QUEUED -> ANALYZING_IMAGE -> CALCULATING_SEVERITY -> CHECKING_DUPLICATES -> ASSIGNING_DEPARTMENT -> COMPLETED / FAILED
"""

from typing import Optional, Set

# ── Canonical Lifecycle Statuses ──────────────────────────────────────────
STATUS_SUBMITTED = "SUBMITTED"
STATUS_AI_PROCESSING = "AI_PROCESSING"
STATUS_VERIFIED = "VERIFIED"
STATUS_ASSIGNED = "ASSIGNED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_RESOLUTION_SUBMITTED = "RESOLUTION_SUBMITTED"
STATUS_RESOLVED = "RESOLVED"

# Exceptional Statuses
STATUS_PROCESSING_FAILED = "PROCESSING_FAILED"
STATUS_DUPLICATE = "DUPLICATE"
STATUS_REJECTED = "REJECTED"
STATUS_NEEDS_INFORMATION = "NEEDS_INFORMATION"

ALL_CANONICAL_STATUSES: Set[str] = {
    STATUS_SUBMITTED,
    STATUS_AI_PROCESSING,
    STATUS_VERIFIED,
    STATUS_ASSIGNED,
    STATUS_IN_PROGRESS,
    STATUS_RESOLUTION_SUBMITTED,
    STATUS_RESOLVED,
    STATUS_PROCESSING_FAILED,
    STATUS_DUPLICATE,
    STATUS_REJECTED,
    STATUS_NEEDS_INFORMATION,
}

# Mapping legacy status strings to canonical states for backward compatibility
LEGACY_STATUS_MAP = {
    "open": STATUS_VERIFIED,
    "submitted": STATUS_SUBMITTED,
    "in progress": STATUS_IN_PROGRESS,
    "inprogress": STATUS_IN_PROGRESS,
    "resolved": STATUS_RESOLVED,
    "closed": STATUS_RESOLVED,
}

# Valid forward & branching state transitions
TRANSITION_GRAPH = {
    STATUS_SUBMITTED: {STATUS_AI_PROCESSING, STATUS_REJECTED},
    STATUS_AI_PROCESSING: {STATUS_VERIFIED, STATUS_PROCESSING_FAILED, STATUS_DUPLICATE},
    STATUS_PROCESSING_FAILED: {STATUS_AI_PROCESSING, STATUS_REJECTED},  # Retry re-enters AI_PROCESSING
    STATUS_VERIFIED: {STATUS_ASSIGNED, STATUS_DUPLICATE, STATUS_REJECTED, STATUS_NEEDS_INFORMATION},
    STATUS_ASSIGNED: {STATUS_IN_PROGRESS, STATUS_REJECTED, STATUS_NEEDS_INFORMATION},
    STATUS_IN_PROGRESS: {STATUS_RESOLUTION_SUBMITTED, STATUS_RESOLVED, STATUS_NEEDS_INFORMATION},
    STATUS_RESOLUTION_SUBMITTED: {STATUS_RESOLVED, STATUS_IN_PROGRESS, STATUS_REJECTED},
    STATUS_NEEDS_INFORMATION: {STATUS_IN_PROGRESS, STATUS_VERIFIED, STATUS_REJECTED},
    STATUS_DUPLICATE: {STATUS_VERIFIED, STATUS_REJECTED},
    STATUS_RESOLVED: set(),
    STATUS_REJECTED: set(),
}

# ── Processing Job Stages ──────────────────────────────────────────────────
STAGE_QUEUED = "QUEUED"
STAGE_ANALYZING_IMAGE = "ANALYZING_IMAGE"
STAGE_CALCULATING_SEVERITY = "CALCULATING_SEVERITY"
STAGE_CHECKING_DUPLICATES = "CHECKING_DUPLICATES"
STAGE_ASSIGNING_DEPARTMENT = "ASSIGNING_DEPARTMENT"
STAGE_COMPLETED = "COMPLETED"
STAGE_FAILED = "FAILED"

ALL_PROCESSING_STAGES: Set[str] = {
    STAGE_QUEUED,
    STAGE_ANALYZING_IMAGE,
    STAGE_CALCULATING_SEVERITY,
    STAGE_CHECKING_DUPLICATES,
    STAGE_ASSIGNING_DEPARTMENT,
    STAGE_COMPLETED,
    STAGE_FAILED,
}

ACTIVE_PROCESSING_STAGES: Set[str] = {
    STAGE_QUEUED,
    STAGE_ANALYZING_IMAGE,
    STAGE_CALCULATING_SEVERITY,
    STAGE_CHECKING_DUPLICATES,
    STAGE_ASSIGNING_DEPARTMENT,
}


def normalize_status(status_str: Optional[str]) -> Optional[str]:
    """
    Normalizes any status representation (canonical uppercase or legacy casing)
    to its canonical uppercase representation.
    """
    if not status_str:
        return None
    cleaned = status_str.strip()
    upper = cleaned.upper()
    if upper in ALL_CANONICAL_STATUSES:
        return upper
    lower = cleaned.lower()
    if lower in LEGACY_STATUS_MAP:
        return LEGACY_STATUS_MAP[lower]
    return upper


def can_transition(current: str, target: str) -> bool:
    """Validate if current state can legally transition to target state."""
    curr_norm = normalize_status(current)
    target_norm = normalize_status(target)
    if not curr_norm or not target_norm:
        return False
    if curr_norm == target_norm:
        return True
    allowed = TRANSITION_GRAPH.get(curr_norm, set())
    return target_norm in allowed

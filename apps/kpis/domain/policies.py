from .entities import LifecycleState
from .exceptions import InvalidLifecycleTransition


_ALLOWED_TRANSITIONS: dict[LifecycleState, set[LifecycleState]] = {
    LifecycleState.DRAFT: {LifecycleState.APPROVED, LifecycleState.ARCHIVED},
    LifecycleState.APPROVED: {LifecycleState.PUBLISHED, LifecycleState.ARCHIVED},
    LifecycleState.PUBLISHED: {LifecycleState.ARCHIVED},
    LifecycleState.ARCHIVED: set(),
}


def ensure_lifecycle_transition(current: LifecycleState, target: LifecycleState) -> None:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidLifecycleTransition(
            f"Invalid KPI version transition from '{current}' to '{target}'."
        )

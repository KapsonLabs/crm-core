from django.test import SimpleTestCase

from apps.kpis.domain.entities import LifecycleState
from apps.kpis.domain.exceptions import InvalidLifecycleTransition
from apps.kpis.domain.policies import ensure_lifecycle_transition


class LifecyclePolicyTests(SimpleTestCase):
    def test_allows_draft_to_approved(self):
        ensure_lifecycle_transition(LifecycleState.DRAFT, LifecycleState.APPROVED)

    def test_rejects_draft_to_published(self):
        with self.assertRaises(InvalidLifecycleTransition):
            ensure_lifecycle_transition(LifecycleState.DRAFT, LifecycleState.PUBLISHED)

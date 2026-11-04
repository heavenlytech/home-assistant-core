"""System policies."""

from .const import CAT_ENTITIES, POLICY_READ, SUBCAT_ALL
from .types import PolicyType

ADMIN_POLICY = {CAT_ENTITIES: True}

USER_POLICY = {CAT_ENTITIES: True}

READ_ONLY_POLICY = {CAT_ENTITIES: {SUBCAT_ALL: {POLICY_READ: True}}}

LEAST_PRIVILEGED_POLICY: PolicyType = {}

ACCESS_MODE_OPEN = "open"
ACCESS_MODE_READ_ONLY = "read_only"
ACCESS_MODE_LEAST_PRIVILEGED = "least_privileged"
ACCESS_MODE_OPEN_UNLESS_SPECIFIED = "open_unless_specified"

ACCESS_MODES = (
    ACCESS_MODE_OPEN,
    ACCESS_MODE_READ_ONLY,
    ACCESS_MODE_LEAST_PRIVILEGED,
    ACCESS_MODE_OPEN_UNLESS_SPECIFIED,
)

_ACCESS_MODE_POLICIES: dict[str, PolicyType] = {
    ACCESS_MODE_OPEN: USER_POLICY,
    ACCESS_MODE_READ_ONLY: READ_ONLY_POLICY,
    ACCESS_MODE_LEAST_PRIVILEGED: LEAST_PRIVILEGED_POLICY,
    # The group stays open; users holding direct rules are limited to
    # those rules instead when their permissions are resolved.
    ACCESS_MODE_OPEN_UNLESS_SPECIFIED: USER_POLICY,
}


def policy_for_access_mode(mode: str) -> PolicyType:
    """Return the default user-group policy for an access mode."""
    return _ACCESS_MODE_POLICIES[mode]

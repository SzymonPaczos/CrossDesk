"""crossdesk doctor — pre-flight checks before install/launch."""

from crossdesk_host.doctor.checks import (
    CheckResult,
    DEFAULT_CHECKS,
    Status,
    has_failures,
    run_all,
)

__all__ = ["DEFAULT_CHECKS", "CheckResult", "Status", "has_failures", "run_all"]

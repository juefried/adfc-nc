"""Gemeinsame Filter für Benutzer- und Gruppenauswertungen."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from adfc_nc.nextcloud.users import AgeBasis, User


class UserStatus(StrEnum):
    """Statusfilter für Benutzerauswertungen."""

    ALL = "all"
    ACTIVE = "active"
    DISABLED = "disabled"


class UserType(StrEnum):
    """Unterscheidung zwischen normalen Benutzern und Ressourcenbenutzern."""

    ALL = "all"
    USER = "user"
    RESOURCE = "resource"


@dataclass(frozen=True)
class StaleCriteria:
    """Schwellwerte für Deaktivierungs-Kandidaten."""

    min_age_days: int = 60
    inactive_days: int = 60
    include_unknown_age: bool = False
    status: UserStatus = UserStatus.ALL


def matches_status(user: User, status: UserStatus) -> bool:
    """Prüft den Aktivierungsstatus eines Benutzers."""
    if status is UserStatus.ACTIVE:
        return user.enabled
    if status is UserStatus.DISABLED:
        return not user.enabled
    return True


def matches_type(user: User, user_type: UserType) -> bool:
    """Prüft, ob ein Benutzer dem gewünschten Benutzertyp entspricht."""
    if user_type is UserType.USER:
        return not user.is_resource
    if user_type is UserType.RESOURCE:
        return user.is_resource
    return True


def matches_inactive(user: User, inactive_days: int) -> bool:
    """Prüft, ob ein Benutzer lange genug inaktiv ist."""
    if user.never_logged_in:
        return True
    return user.inactive_days is not None and user.inactive_days >= inactive_days


def matches_stale(
    user: User,
    *,
    min_age_days: int,
    inactive_days: int,
    include_unknown_age: bool,
) -> bool:
    """Prüft Alter und Inaktivität nach der Stale-Logik."""
    if not matches_inactive(user, inactive_days):
        return False
    if user.age_days is not None and user.age_days >= min_age_days:
        return True
    if user.age_basis is AgeBasis.PRE_NC31:
        return True
    return include_unknown_age and user.age_basis is AgeBasis.UNKNOWN


def is_stale_candidate(user: User, criteria: StaleCriteria) -> bool:
    """Prüft, ob ein Benutzer ein Deaktivierungs-Kandidat ist."""
    return matches_status(user, criteria.status) and matches_stale(
        user,
        min_age_days=criteria.min_age_days,
        inactive_days=criteria.inactive_days,
        include_unknown_age=criteria.include_unknown_age,
    )

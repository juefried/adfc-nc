"""Gruppensuche und Auswertung der Mitglieder über die OCS-Provisioning-API."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from adfc_nc.config import Settings
from adfc_nc.nextcloud.users import User, load_users_with_group_names
from adfc_nc.stale import (
    StaleCriteria,
    UserType,
    is_stale_candidate,
    matches_type,
)


@dataclass(frozen=True)
class GroupSummary:
    """Eine gefundene Gruppe."""

    id: str
    display_name: str


@dataclass(frozen=True)
class GroupReport:
    """Auswertung eines Suchbegriffs über Gruppen und ihre Mitglieder."""

    query: str
    groups: tuple[GroupSummary, ...]
    users: tuple[User, ...]
    user_type: UserType = UserType.USER
    criteria: StaleCriteria | None = None

    def matching_groups(self, user: User) -> tuple[GroupSummary, ...]:
        """Liefert die gefundenen Gruppen, denen der Benutzer angehört."""
        return tuple(group for group in self.groups if group.id in user.group_ids)


def load_group_reports(
    settings: Settings,
    queries: Sequence[str],
    *,
    user_type: UserType = UserType.USER,
    now: datetime | None = None,
) -> list[GroupReport]:
    """Lädt Gruppen und Benutzer einmalig und erstellt je Suchbegriff einen Report."""
    group_names, users = load_users_with_group_names(settings, now=now)
    return [build_group_report(query, group_names, users, user_type=user_type) for query in queries]


def load_stale_group_reports(
    settings: Settings,
    queries: Sequence[str],
    *,
    user_type: UserType = UserType.USER,
    criteria: StaleCriteria | None = None,
    now: datetime | None = None,
) -> list[GroupReport]:
    """Erstellt je Suchbegriff einen Report mit Deaktivierungs-Kandidaten."""
    effective_criteria = criteria or StaleCriteria()
    group_names, users = load_users_with_group_names(
        settings,
        track_inventory=True,
        now=now,
    )
    candidates = [user for user in users if is_stale_candidate(user, effective_criteria)]
    return [
        build_group_report(
            query,
            group_names,
            candidates,
            user_type=user_type,
            include_empty_groups=False,
            criteria=effective_criteria,
        )
        for query in queries
    ]


def build_group_report(
    query: str,
    group_names: Mapping[str, str],
    users: Sequence[User],
    *,
    user_type: UserType = UserType.USER,
    include_empty_groups: bool = True,
    criteria: StaleCriteria | None = None,
) -> GroupReport:
    """Findet Gruppen zu einem Suchbegriff und alle zugehörigen Benutzer."""
    needle = _normalize(query)
    groups = tuple(
        sorted(
            (
                GroupSummary(id=group_id, display_name=display_name)
                for group_id, display_name in group_names.items()
                if _matches(needle, group_id, display_name)
            ),
            key=lambda group: (group.id.casefold(), group.display_name.casefold()),
        )
    )
    if not groups:
        return GroupReport(
            query=query,
            groups=(),
            users=(),
            user_type=user_type,
            criteria=criteria,
        )

    group_ids = {group.id for group in groups}
    eligible_users = [user for user in users if matches_type(user, user_type)]
    matched_users = tuple(
        sorted(
            (user for user in eligible_users if group_ids.intersection(user.group_ids)),
            key=lambda user: (user.display_name.casefold(), user.id.casefold()),
        )
    )
    if not include_empty_groups:
        used_group_ids = {group_id for user in matched_users for group_id in user.group_ids}
        groups = tuple(group for group in groups if group.id in used_group_ids)
    return GroupReport(
        query=query,
        groups=groups,
        users=matched_users,
        user_type=user_type,
        criteria=criteria,
    )


def _matches(needle: str, group_id: str, display_name: str) -> bool:
    if not needle:
        return False
    return needle in _normalize(group_id) or needle in _normalize(display_name)


def _normalize(value: str) -> str:
    return " ".join(value.replace("_", " ").casefold().split())

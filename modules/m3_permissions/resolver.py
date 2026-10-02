"""Hierarchical permission resolution: inheritance down a resource tree, with overrides.

Rules:
1. Walk from the resource up to the root; the nearest node with an applicable grant wins.
   A child grant replaces what the parent gives, so it can downgrade or deny (Role.NONE).
2. On the same node, a direct user grant beats group grants; among groups, the highest role wins.
3. No applicable grant anywhere on the path -> Role.NONE.
"""

from dataclasses import dataclass
from enum import Enum, IntEnum


class Role(IntEnum):
    NONE = 0
    VIEWER = 1
    EDITOR = 2
    ADMIN = 3


class PrincipalKind(Enum):
    USER = "user"
    GROUP = "group"


ACTION_MIN_ROLE = {
    "read": Role.VIEWER,
    "write": Role.EDITOR,
    "share": Role.ADMIN,
    "delete": Role.ADMIN,
}


@dataclass(frozen=True)
class Resource:
    id: str
    parent_id: str | None = None


@dataclass(frozen=True)
class Grant:
    kind: PrincipalKind
    principal_id: str
    resource_id: str
    role: Role


class Resolver:
    def __init__(self, resources: list[Resource], grants: list[Grant]):
        self._parents: dict[str, str | None] = {}
        for r in resources:
            if r.id in self._parents:
                raise ValueError(f"duplicate resource: {r.id}")
            self._parents[r.id] = r.parent_id

        for rid, parent in self._parents.items():
            if parent is not None and parent not in self._parents:
                raise ValueError(f"resource {rid} has unknown parent {parent}")
        self._check_no_cycles()

        self._grants: dict[str, list[Grant]] = {}
        for g in grants:
            if g.resource_id not in self._parents:
                raise ValueError(f"grant on unknown resource: {g.resource_id}")
            self._grants.setdefault(g.resource_id, []).append(g)

    def _check_no_cycles(self) -> None:
        reaches_root: set[str] = set()
        for start in self._parents:
            path: list[str] = []
            node: str | None = start
            while node is not None and node not in reaches_root:
                if node in path:
                    raise ValueError(f"cycle in resource tree at {node}")
                path.append(node)
                node = self._parents[node]
            reaches_root.update(path)

    def _role_at(self, resource_id: str, user_id: str, group_ids: set[str]) -> Role | None:
        grants = self._grants.get(resource_id, [])
        user_roles = [
            g.role for g in grants
            if g.kind is PrincipalKind.USER and g.principal_id == user_id
        ]
        if user_roles:
            return max(user_roles)
        group_roles = [
            g.role for g in grants
            if g.kind is PrincipalKind.GROUP and g.principal_id in group_ids
        ]
        return max(group_roles) if group_roles else None

    def effective_role(self, user_id: str, group_ids: list[str], resource_id: str) -> Role:
        if resource_id not in self._parents:
            raise ValueError(f"unknown resource: {resource_id}")
        groups = set(group_ids)
        node: str | None = resource_id
        while node is not None:
            role = self._role_at(node, user_id, groups)
            if role is not None:
                return role
            node = self._parents[node]
        return Role.NONE

    def can(self, user_id: str, group_ids: list[str], resource_id: str, action: str) -> bool:
        required = ACTION_MIN_ROLE[action]
        return self.effective_role(user_id, group_ids, resource_id) >= required

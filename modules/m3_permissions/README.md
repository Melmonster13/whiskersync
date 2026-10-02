# m3 — Hierarchical permissions

**Problem:** resources live in a tree (workspace → folder → project → clip). Access granted high up should flow down, but a team must be able to restrict or deny access to one branch without restructuring the tree. **Approach:** walk from the resource up to the root and stop at the first node that has a grant for this user or their groups; on that node a direct user grant beats group grants, and among groups the highest role wins. Bad trees (duplicates, unknown parents, cycles) are rejected when the resolver is built, not at query time. **Result:** 26 table-driven tests cover inheritance, downgrades, explicit deny, user-vs-group precedence, and every invalid-tree case; a lookup visits at most one node per tree level.

## Usage

```python
from modules.m3_permissions.resolver import Grant, PrincipalKind, Resolver, Resource, Role

resolver = Resolver(
    resources=[Resource("ws"), Resource("folder_a", "ws"), Resource("clip_x", "folder_a")],
    grants=[
        Grant(PrincipalKind.USER, "alice", "ws", Role.ADMIN),
        Grant(PrincipalKind.USER, "alice", "folder_a", Role.VIEWER),   # downgrade
    ],
)
resolver.effective_role("alice", [], "clip_x")        # Role.VIEWER
resolver.can("alice", [], "clip_x", "write")          # False
```

Roles: `NONE < VIEWER < EDITOR < ADMIN`. Actions: `read` → viewer, `write` → editor, `share` / `delete` → admin.

## Rules

1. The nearest node (walking up) with an applicable grant wins, so a child grant can downgrade or deny (`Role.NONE`) what a parent gives.
2. On the same node, a user grant beats group grants; among several groups, the highest role wins.
3. No applicable grant anywhere on the path → `Role.NONE`.

## Edge cases

| Case | Behaviour | Test |
|---|---|---|
| Grant only at the root | Inherited by every descendant | `test_effective_role` |
| Child downgrade (admin → viewer) | Child grant wins, and is inherited further down | `test_effective_role` |
| Explicit deny on a child | `Role.NONE`, even if a group grants more on that node | `test_effective_role` |
| User and group grant on the same node | User grant wins, even if lower | `test_effective_role` |
| User in several groups on one node | Highest group role | `test_effective_role` |
| Nearer group grant vs. farther user grant | Nearer wins (nearest-node rule comes first) | `test_effective_role` |
| No grants for the user anywhere | `Role.NONE` | `test_effective_role` |
| Unknown resource in a query | `ValueError` | `test_unknown_resource_raises` |
| Unknown action | `KeyError` | `test_unknown_action_raises` |
| Duplicate resource id | `ValueError` at construction | `test_invalid_construction_raises` |
| Parent id that doesn't exist | `ValueError` at construction | `test_invalid_construction_raises` |
| Self-parent or longer cycle | `ValueError` at construction | `test_invalid_construction_raises` |
| Grant on an unknown resource | `ValueError` at construction | `test_invalid_construction_raises` |

## Trade-offs

See `DECISIONS.md`: nearest-grant-wins over highest-role-on-path; user grant over group grants on one node.

## Run

```bash
.venv/bin/pytest modules/m3_permissions
```

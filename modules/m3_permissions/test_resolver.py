import pytest

from modules.m3_permissions.resolver import Grant, PrincipalKind, Resolver, Resource, Role

USER, GROUP = PrincipalKind.USER, PrincipalKind.GROUP

# ws
# ├── folder_a
# │   └── project_1
# │       └── clip_x
# └── folder_b
#     └── project_2
RESOURCES = [
    Resource("ws"),
    Resource("folder_a", "ws"),
    Resource("project_1", "folder_a"),
    Resource("clip_x", "project_1"),
    Resource("folder_b", "ws"),
    Resource("project_2", "folder_b"),
]

GRANTS = [
    Grant(USER, "alice", "ws", Role.ADMIN),
    Grant(USER, "alice", "folder_a", Role.VIEWER),
    Grant(USER, "alice", "project_2", Role.NONE),
    Grant(USER, "carol", "ws", Role.ADMIN),
    Grant(GROUP, "eng", "folder_b", Role.EDITOR),
    Grant(GROUP, "design", "folder_b", Role.VIEWER),
    Grant(GROUP, "eng", "project_2", Role.ADMIN),
    Grant(USER, "bob", "project_2", Role.VIEWER),
]


@pytest.fixture
def resolver():
    return Resolver(RESOURCES, GRANTS)


@pytest.mark.parametrize(
    "user, groups, resource, expected",
    [
        ("alice", [], "ws", Role.ADMIN),                  # direct grant
        ("alice", [], "folder_b", Role.ADMIN),            # inherited from root
        ("alice", [], "folder_a", Role.VIEWER),           # child downgrade
        ("alice", [], "clip_x", Role.VIEWER),             # downgrade inherited down a deep chain
        ("alice", ["eng"], "project_2", Role.NONE),       # explicit deny; user beats group
        ("bob", ["eng"], "project_2", Role.VIEWER),       # user grant beats group grant on same node
        ("dave", ["eng"], "project_2", Role.ADMIN),       # group grant
        ("dave", ["eng", "design"], "folder_b", Role.EDITOR),  # several groups: highest wins
        ("erin", ["design"], "folder_b", Role.VIEWER),
        ("carol", ["design"], "folder_b", Role.VIEWER),   # nearer group grant beats farther user grant
        ("carol", ["design"], "folder_a", Role.ADMIN),
        ("frank", [], "clip_x", Role.NONE),               # no grants anywhere
        ("frank", ["design"], "ws", Role.NONE),
    ],
)
def test_effective_role(resolver, user, groups, resource, expected):
    assert resolver.effective_role(user, groups, resource) == expected


@pytest.mark.parametrize(
    "user, groups, resource, action, expected",
    [
        ("alice", [], "clip_x", "read", True),
        ("alice", [], "clip_x", "write", False),
        ("alice", [], "project_2", "read", False),
        ("dave", ["eng"], "project_2", "delete", True),
        ("dave", ["eng"], "folder_b", "write", True),
        ("dave", ["eng"], "folder_b", "share", False),
    ],
)
def test_can(resolver, user, groups, resource, action, expected):
    assert resolver.can(user, groups, resource, action) is expected


def test_unknown_resource_raises(resolver):
    with pytest.raises(ValueError):
        resolver.effective_role("alice", [], "nope")


def test_unknown_action_raises(resolver):
    with pytest.raises(KeyError):
        resolver.can("alice", [], "ws", "teleport")


@pytest.mark.parametrize(
    "resources, grants",
    [
        ([Resource("a"), Resource("a")], []),                               # duplicate id
        ([Resource("a", "missing")], []),                                   # unknown parent
        ([Resource("a", "a")], []),                                         # self-cycle
        ([Resource("r"), Resource("a", "b"), Resource("b", "a")], []),      # two-node cycle
        ([Resource("a")], [Grant(USER, "alice", "nope", Role.VIEWER)]),     # grant on unknown resource
    ],
)
def test_invalid_construction_raises(resources, grants):
    with pytest.raises(ValueError):
        Resolver(resources, grants)

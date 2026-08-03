"""app/admin/rbac.py — Role-Based Access Control (RBAC) for Admin Panel.

Role hierarchy (highest → lowest):
    OWNER  >  SUPER_ADMIN  >  ADMIN  >  SUPPORT

Section permission map — minimum role required to access each section/action:

    Section               | SUPPORT | ADMIN | SUPER_ADMIN | OWNER
    ──────────────────────┼─────────┼───────┼─────────────┼──────
    📊 Stats              |   ✅    |  ✅   |     ✅      |  ✅
    👥 View Users         |   ✅    |  ✅   |     ✅      |  ✅
    📩 Send Message       |   ✅    |  ✅   |     ✅      |  ✅
    🚫 Ban / Unban        |   ❌    |  ✅   |     ✅      |  ✅
    💎 Grant / Remove VIP |   ❌    |  ✅   |     ✅      |  ✅
    📢 Broadcast          |   ❌    |  ✅   |     ✅      |  ✅
    🎧 Support Settings   |   ❌    |  ✅   |     ✅      |  ✅
    💳 VIP & Payments     |   ❌    |  ✅   |     ✅      |  ✅
    📌 Force Join         |   ❌    |  ❌   |     ✅      |  ✅
    👮 Admin Management   |   ❌    |  ❌   |     ✅      |  ✅
"""

from __future__ import annotations

# ─── Role Hierarchy ──────────────────────────────────────────────────────────

ROLE_LEVEL: dict[str, int] = {
    "OWNER":       100,
    "SUPER_ADMIN": 30,
    "ADMIN":       20,
    "SUPPORT":     10,
}

# ─── Section / Action → Minimum Required Role ────────────────────────────────

# AdminNav action → minimum role string
NAV_PERMISSIONS: dict[str, str] = {
    "home":       "SUPPORT",
    "stats":      "SUPPORT",
    "users":      "SUPPORT",
    "broadcast":  "ADMIN",
    "support":    "ADMIN",
    "vip":        "ADMIN",
    "force_join": "SUPER_ADMIN",
    "admins":     "SUPER_ADMIN",
    "language":   "SUPPORT",
    "close":      "SUPPORT",
}

# Fine-grained UserAction → minimum role
USER_ACTION_PERMISSIONS: dict[str, str] = {
    "view":       "SUPPORT",
    "msg":        "SUPPORT",
    "ban":        "ADMIN",
    "unban":      "ADMIN",
    "give_vip":   "ADMIN",
    "remove_vip": "ADMIN",
}

# Admin Management actions → minimum role
ADMIN_MGMT_PERMISSIONS: dict[str, str] = {
    "view":           "SUPER_ADMIN",
    "add_start":      "SUPER_ADMIN",
    "confirm_remove": "SUPER_ADMIN",
    "do_remove":      "SUPER_ADMIN",
    "role_menu":      "SUPER_ADMIN",
    "set_role":       "SUPER_ADMIN",
}

# Sections visible in the main menu per role
MENU_SECTIONS: list[tuple[str, str, str]] = [
    # (action, label_key, min_role)
    ("stats",      "btn_stats",      "SUPPORT"),
    ("users",      "btn_users",      "SUPPORT"),
    ("broadcast",  "btn_broadcast",  "ADMIN"),
    ("support",    "btn_support",    "ADMIN"),
    ("vip",        "btn_vip",        "ADMIN"),
    ("force_join", "btn_force_join", "SUPER_ADMIN"),
    ("admins",     "btn_admins",     "SUPER_ADMIN"),
]


# ─── Helper Functions ─────────────────────────────────────────────────────────

def role_level(role: str) -> int:
    """Return numeric level for a role string. Unknown roles → 0 (no access)."""
    return ROLE_LEVEL.get(role, 0)


def has_permission(user_role: str, required_role: str) -> bool:
    """Return True if user_role meets or exceeds required_role in the hierarchy."""
    return role_level(user_role) >= role_level(required_role)


def check_nav_permission(user_role: str, nav_action: str) -> bool:
    """Check if the user role can access a given AdminNav action."""
    required = NAV_PERMISSIONS.get(nav_action, "OWNER")  # unknown → max required
    return has_permission(user_role, required)


def check_user_action_permission(user_role: str, action: str) -> bool:
    """Check if the user role can execute a given UserAction."""
    required = USER_ACTION_PERMISSIONS.get(action, "OWNER")
    return has_permission(user_role, required)


def check_admin_mgmt_permission(user_role: str, action: str) -> bool:
    """Check if the user role can execute a given AdminMgmtAction."""
    required = ADMIN_MGMT_PERMISSIONS.get(action, "OWNER")
    return has_permission(user_role, required)


def visible_sections(user_role: str) -> list[tuple[str, str]]:
    """Return (action, label_key) tuples for sections visible to user_role."""
    return [
        (action, label_key)
        for action, label_key, min_role in MENU_SECTIONS
        if has_permission(user_role, min_role)
    ]

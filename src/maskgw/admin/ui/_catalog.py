"""Generated closed private catalog; checked against HTTP sources by tests."""

CALLS: tuple[tuple[str, str, str | None, str, str, str | None, str], ...] = (
    ("GET", "/admin/v1/status", None, "m50", "read", None, "m44"),
    ("GET", "/admin/v1/config", None, "m66", "read", None, "m44"),
    ("GET", "/admin/v1/rules", None, "m69", "read", None, "m44"),
    ("GET", "/admin/v1/rules/{rule_id}", None, "m70", "read", "rule_id", "m44"),
    ("GET", "/admin/v1/exceptions", None, "m73", "read", None, "m44"),
    ("GET", "/admin/v1/exceptions/{exception_id}", None, "m74", "read", "exception_id", "m44"),
    ("GET", "/admin/v1/transformers", None, "m77", "read", None, "m44"),
    ("GET", "/admin/v1/protected", None, "m79", "read", None, "m44"),
    ("POST", "/admin/v1/config:validate", "m89", "m90", "check", None, "m44"),
    ("POST", "/admin/v1/config:adopt", "m91", "m92", "confirm", None, "m44"),
    ("POST", "/admin/v1/rules:reorder", "m94", "m92", "move", None, "m44"),
    ("POST", "/admin/v1/rules", "m97", "m92", "create", None, "m44"),
    ("PUT", "/admin/v1/rules/{rule_id}", "m98", "m92", "replace", "rule_id", "m44"),
    ("DELETE", "/admin/v1/rules/{rule_id}", "m99", "m92", "delete", "rule_id", "m44"),
    ("POST", "/admin/v1/exceptions", "m101", "m92", "create", None, "m44"),
    ("PUT", "/admin/v1/exceptions/{exception_id}", "m101", "m92", "replace", "exception_id", "m44"),
    (
        "DELETE",
        "/admin/v1/exceptions/{exception_id}",
        "m99",
        "m92",
        "delete",
        "exception_id",
        "m44",
    ),
    ("PUT", "/admin/v1/database", "m102", "m92", "replace", None, "m44"),
    ("PUT", "/admin/v1/sql", "m103", "m92", "append", None, "m44"),
)
MODEL_SHA256 = "eef802f4ea9c779c498f2a6a934f6f6f99f1e924e7017f02f5410c40a2eef5a3"

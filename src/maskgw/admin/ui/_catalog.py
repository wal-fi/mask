"""Generated closed private catalog; checked against HTTP sources by tests."""

CALLS: tuple[tuple[str, str, str | None, str, str, str | None, str], ...] = (
    ("GET", "/admin/v1/status", None, "m50", "read", None, "m44"),
    ("GET", "/admin/v1/config", None, "m63", "read", None, "m44"),
    ("GET", "/admin/v1/rules", None, "m66", "read", None, "m44"),
    ("GET", "/admin/v1/rules/{rule_id}", None, "m67", "read", "rule_id", "m44"),
    ("GET", "/admin/v1/exceptions", None, "m70", "read", None, "m44"),
    ("GET", "/admin/v1/exceptions/{exception_id}", None, "m71", "read", "exception_id", "m44"),
    ("GET", "/admin/v1/transformers", None, "m74", "read", None, "m44"),
    ("GET", "/admin/v1/protected", None, "m76", "read", None, "m44"),
    ("POST", "/admin/v1/config:validate", "m90", "m91", "check", None, "m44"),
    ("POST", "/admin/v1/config:adopt", "m92", "m93", "confirm", None, "m44"),
    ("POST", "/admin/v1/rules:reorder", "m95", "m93", "move", None, "m44"),
    ("POST", "/admin/v1/rules", "m98", "m93", "create", None, "m44"),
    ("PUT", "/admin/v1/rules/{rule_id}", "m99", "m93", "replace", "rule_id", "m44"),
    ("DELETE", "/admin/v1/rules/{rule_id}", "m100", "m93", "delete", "rule_id", "m44"),
    ("POST", "/admin/v1/exceptions", "m102", "m93", "create", None, "m44"),
    ("PUT", "/admin/v1/exceptions/{exception_id}", "m102", "m93", "replace", "exception_id", "m44"),
    (
        "DELETE",
        "/admin/v1/exceptions/{exception_id}",
        "m100",
        "m93",
        "delete",
        "exception_id",
        "m44",
    ),
    ("PUT", "/admin/v1/database", "m103", "m93", "replace", None, "m44"),
    ("PUT", "/admin/v1/sql", "m104", "m93", "append", None, "m44"),
)
MODEL_SHA256 = "80444bacfb0850d7d7a161fcee3b13caa47f36c41fb238153bb93624c0d5ef77"

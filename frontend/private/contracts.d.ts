// Generated from the eleven existing HTTP contracts. Never shipped.
export type AdminConfigResponse = { readonly "revision": number; readonly "adopted": boolean; readonly "config": ConfigDocument };
export type AdminCounters = { readonly "queries_total": number; readonly "admin_operations_total": number };
export type AdminExceptionResponse = { readonly "revision": number; readonly "adopted": boolean; readonly "exception": ExceptionView };
export type AdminExceptionsResponse = { readonly "revision": number; readonly "adopted": boolean; readonly "exceptions": ReadonlyArray<ExceptionView> };
export type AdminProtectedResponse = { readonly "revision": number; readonly "denied_relations": ReadonlyArray<string>; readonly "pg_namespace_default": string; readonly "allowed_pg_functions": ReadonlyArray<string>; readonly "denied_functions": ReadonlyArray<string>; readonly "denied_function_prefixes": ReadonlyArray<string>; readonly "validator_rules": ReadonlyArray<string>; readonly "session": ProtectedSession; readonly "pipeline": ReadonlyArray<string>; readonly "unmatched_policy": string; readonly "editable": boolean };
export type AdminRuleResponse = { readonly "revision": number; readonly "adopted": boolean; readonly "rule": RuleView };
export type AdminRulesResponse = { readonly "revision": number; readonly "adopted": boolean; readonly "rules": ReadonlyArray<RuleView> };
export type AdminRuntimeState = { readonly "revision": number; readonly "retired_runtimes_open": number };
export type AdminSecrets = { readonly "hmac_sha256_key": SecretState; readonly "admin_token": SecretState; readonly "database_dsn": SecretState };
export type AdminStatusResponse = { readonly "revision": number; readonly "adopted": boolean; readonly "runtime": AdminRuntimeState; readonly "counters": AdminCounters; readonly "secrets": AdminSecrets };
export type AdminTransformersResponse = { readonly "revision": number; readonly "transformers": ReadonlyArray<TransformerView> };
export type AdoptRequest = { readonly "expected_revision": number; readonly "confirm_comment_loss": true };
export type ConfigDocument = { readonly "revision": number; readonly "masking": ReadonlyArray<RuleDocument>; readonly "exceptions": ReadonlyArray<ExceptionDocument>; readonly "database": DatabaseDocument; readonly "sql": SqlDocument };
export type ConfigReplaceDatabase = { readonly "statement_timeout_ms": number; readonly "max_rows": number };
export type ConfigReplaceException = { readonly "match": string; readonly "mode"?: MatchMode; readonly "case_sensitive"?: boolean; readonly "id"?: string | null };
export type ConfigReplaceRequest = { readonly "expected_revision": number; readonly "masking": ReadonlyArray<ConfigReplaceRule>; readonly "exceptions": ReadonlyArray<ConfigReplaceException>; readonly "database": ConfigReplaceDatabase; readonly "sql": ConfigReplaceSql };
export type ConfigReplaceRule = { readonly "match": string; readonly "mode"?: MatchMode; readonly "case_sensitive"?: boolean; readonly "transformer": string; readonly "config"?: Readonly<Record<string, unknown>>; readonly "id"?: string | null };
export type ConfigReplaceSql = { readonly "denied_functions": ReadonlyArray<string>; readonly "allowed_pg_functions"?: JsonValue | null };
export type ConfigValidateRequest = { readonly "revision"?: number; readonly "masking"?: ReadonlyArray<ValidateRuleRequest>; readonly "exceptions"?: ReadonlyArray<ValidateExceptionRequest>; readonly "database"?: ValidateDatabaseRequest; readonly "sql"?: ValidateSqlRequest };
export type ConfigValidateResponse = { readonly "valid": boolean; readonly "schema_validated": boolean; readonly "policy_compiled": boolean; readonly "database_checks_performed": boolean };
export type DatabaseDocument = { readonly "statement_timeout_ms": number; readonly "max_rows": number };
export type DatabaseWriteRequest = { readonly "expected_revision": number; readonly "statement_timeout_ms": number; readonly "max_rows": number };
export type DeleteRequest = { readonly "expected_revision": number };
export type ExceptionContent = { readonly "match": string; readonly "mode"?: MatchMode; readonly "case_sensitive"?: boolean };
export type ExceptionCreateRequest = { readonly "expected_revision": number; readonly "exception": ExceptionContent };
export type ExceptionDocument = { readonly "id": string | null; readonly "match": string; readonly "mode": MatchMode; readonly "case_sensitive": boolean };
export type ExceptionReplaceRequest = { readonly "expected_revision": number; readonly "exception": ExceptionContent };
export type ExceptionView = { readonly "id": string | null; readonly "match": string; readonly "mode": MatchMode; readonly "case_sensitive": boolean; readonly "position": number };
export type JsonValue = unknown;
export type MatchMode = "contains" | "exact";
export type ProtectedSession = { readonly "read_only": boolean; readonly "statement_timeout_enforced_by": string; readonly "provenance_capability_required": boolean };
export type RuleContent = { readonly "match": string; readonly "mode"?: MatchMode; readonly "case_sensitive"?: boolean; readonly "transformer": string; readonly "config"?: Readonly<Record<string, unknown>> };
export type RuleCreateRequest = { readonly "expected_revision": number; readonly "rule": RuleContent; readonly "position"?: number | null };
export type RuleDocument = { readonly "id": string | null; readonly "match": string; readonly "mode": MatchMode; readonly "case_sensitive": boolean; readonly "transformer": string; readonly "config": Readonly<Record<string, unknown>> };
export type RuleReorderRequest = { readonly "expected_revision": number; readonly "rule_ids"?: ReadonlyArray<string> };
export type RuleReplaceRequest = { readonly "expected_revision": number; readonly "rule": RuleContent };
export type RuleView = { readonly "id": string | null; readonly "match": string; readonly "mode": MatchMode; readonly "case_sensitive": boolean; readonly "transformer": string; readonly "config": Readonly<Record<string, unknown>>; readonly "position": number };
export type SecretState = "configured" | "missing";
export type SqlDocument = { readonly "allowed_pg_functions": ReadonlyArray<string>; readonly "denied_functions": ReadonlyArray<string> };
export type SqlWriteRequest = { readonly "expected_revision": number; readonly "denied_functions"?: ReadonlyArray<string>; readonly "allowed_pg_functions"?: JsonValue | null };
export type TransformerView = { readonly "name": string; readonly "required_parameters": ReadonlyArray<string>; readonly "optional_parameters": ReadonlyArray<string> };
export type ValidateDatabaseRequest = { readonly "statement_timeout_ms"?: number; readonly "max_rows"?: number };
export type ValidateExceptionRequest = { readonly "match": string; readonly "case_sensitive"?: boolean; readonly "mode"?: MatchMode; readonly "id"?: string | null };
export type ValidateMatchRequest = { readonly "match": string; readonly "case_sensitive"?: boolean };
export type ValidateRuleRequest = { readonly "match": string; readonly "case_sensitive"?: boolean; readonly "mode"?: MatchMode; readonly "transformer": string; readonly "config"?: Readonly<Record<string, unknown>>; readonly "id"?: string | null };
export type ValidateSqlRequest = { readonly "allowed_pg_functions"?: ReadonlyArray<string>; readonly "denied_functions"?: ReadonlyArray<string> };
export type WriteResponse = { readonly "revision": number; readonly "applied": true };
export type WriteContract =
{ readonly method: "POST"; readonly path: "/admin/v1/config:adopt"; readonly request: AdoptRequest; readonly response: WriteResponse } |
{ readonly method: "PUT"; readonly path: "/admin/v1/config"; readonly request: ConfigReplaceRequest; readonly response: WriteResponse } |
{ readonly method: "POST"; readonly path: "/admin/v1/rules:reorder"; readonly request: RuleReorderRequest; readonly response: WriteResponse } |
{ readonly method: "POST"; readonly path: "/admin/v1/rules"; readonly request: RuleCreateRequest; readonly response: WriteResponse } |
{ readonly method: "PUT"; readonly path: "/admin/v1/rules/{rule_id}"; readonly request: RuleReplaceRequest; readonly response: WriteResponse } |
{ readonly method: "DELETE"; readonly path: "/admin/v1/rules/{rule_id}"; readonly request: DeleteRequest; readonly response: WriteResponse } |
{ readonly method: "POST"; readonly path: "/admin/v1/exceptions"; readonly request: ExceptionCreateRequest; readonly response: WriteResponse } |
{ readonly method: "PUT"; readonly path: "/admin/v1/exceptions/{exception_id}"; readonly request: ExceptionReplaceRequest; readonly response: WriteResponse } |
{ readonly method: "DELETE"; readonly path: "/admin/v1/exceptions/{exception_id}"; readonly request: DeleteRequest; readonly response: WriteResponse } |
{ readonly method: "PUT"; readonly path: "/admin/v1/database"; readonly request: DatabaseWriteRequest; readonly response: WriteResponse } |
{ readonly method: "PUT"; readonly path: "/admin/v1/sql"; readonly request: SqlWriteRequest; readonly response: WriteResponse };
export type TransformerInput = { readonly transformer: "md5" | "sha256" | "sha512" | "hmac_sha256"; readonly config?: Readonly<Record<string, never>> } | { readonly transformer: "fixed"; readonly config: { readonly value: string } } | { readonly transformer: "truncate"; readonly config: { readonly length: number } } | { readonly transformer: "regex"; readonly config: { readonly pattern: string; readonly replacement: string } } | { readonly transformer: "random"; readonly config: { readonly strategy: "digits" | "alphanumeric" } & ({ readonly preserve_length?: true; readonly length?: never } | { readonly preserve_length: false; readonly length: number }) };
export type UiRuleContent = Omit<RuleContent, "transformer" | "config"> & TransformerInput;
export type UiRuleCreateRequest = Omit<RuleCreateRequest, "rule"> & { readonly rule: UiRuleContent };
export type UiRuleReplaceRequest = Omit<RuleReplaceRequest, "rule"> & { readonly rule: UiRuleContent };
export type UiWriteContract =
{ readonly method: "POST"; readonly path: "/admin/v1/config:adopt"; readonly request: AdoptRequest; readonly response: WriteResponse } |
{ readonly method: "POST"; readonly path: "/admin/v1/rules:reorder"; readonly request: RuleReorderRequest; readonly response: WriteResponse } |
{ readonly method: "POST"; readonly path: "/admin/v1/rules"; readonly request: UiRuleCreateRequest; readonly response: WriteResponse } |
{ readonly method: "PUT"; readonly path: "/admin/v1/rules/{rule_id}"; readonly request: UiRuleReplaceRequest; readonly response: WriteResponse } |
{ readonly method: "DELETE"; readonly path: "/admin/v1/rules/{rule_id}"; readonly request: DeleteRequest; readonly response: WriteResponse } |
{ readonly method: "POST"; readonly path: "/admin/v1/exceptions"; readonly request: ExceptionCreateRequest; readonly response: WriteResponse } |
{ readonly method: "PUT"; readonly path: "/admin/v1/exceptions/{exception_id}"; readonly request: ExceptionReplaceRequest; readonly response: WriteResponse } |
{ readonly method: "DELETE"; readonly path: "/admin/v1/exceptions/{exception_id}"; readonly request: DeleteRequest; readonly response: WriteResponse } |
{ readonly method: "PUT"; readonly path: "/admin/v1/database"; readonly request: DatabaseWriteRequest; readonly response: WriteResponse } |
{ readonly method: "PUT"; readonly path: "/admin/v1/sql"; readonly request: UiSqlRequest; readonly response: WriteResponse };
export type UiSqlRequest = Omit<SqlWriteRequest, "allowed_pg_functions"> & { readonly allowed_pg_functions?: never };
export type ErrorCategory = "CONFIG_INVALID" | "CONFIG_RELOAD_ERROR" | "CONFIG_WRITE_ERROR" | "CONFIG_DURABILITY_ERROR" | "CONFIG_OUT_OF_SYNC" | "CONFIG_NOT_ADOPTED" | "CONFIG_ALREADY_ADOPTED" | "REVISION_CONFLICT" | "RELOAD_BUSY" | "IMMUTABLE_FIELD" | "INTERNAL_ERROR" | "UNAUTHORIZED" | "NOT_FOUND" | "SCHEMA_INVALID" | "METHOD_NOT_ALLOWED" | "HOST_NOT_ALLOWED" | "CROSS_ORIGIN_REJECTED" | "UNSUPPORTED_MEDIA_TYPE" | "PAYLOAD_TOO_LARGE";
export type ReasonCode = "immutable" | "missing" | "out_of_range" | "too_short" | "unknown_field" | "wrong_type";
export type AdminErrorResponse = { readonly detail: string; readonly current_revision?: number; readonly fields?: ReadonlyArray<{ readonly path: string; readonly reason: ReasonCode }> } & ({ readonly error: "CONFIG_DURABILITY_ERROR"; readonly applied: true } | { readonly error: Exclude<ErrorCategory, "CONFIG_DURABILITY_ERROR">; readonly applied?: never });
export type DurabilityResponse = Extract<AdminErrorResponse, { readonly error: "CONFIG_DURABILITY_ERROR" }>;
export type UiCommand<C = UiWriteContract> = C extends UiWriteContract ? Omit<C, "response"> : never;
export type EditState = { readonly base: AdminConfigResponse; readonly command: UiCommand };
export type WriteOutcome = { readonly type: "success"; readonly value: WriteResponse } | { readonly type: "rejected"; readonly value: Exclude<AdminErrorResponse, DurabilityResponse> } | { readonly type: "unknown" } | { readonly type: "uncertain"; readonly value: DurabilityResponse };
export type ViewState = { readonly type: "loading" | "authentication" } | ({ readonly type: "draft" | "pending" | "conflict" | "busy" } & EditState) | { readonly type: "success"; readonly value: AdminConfigResponse } | { readonly type: "incompatible"; readonly value: AdminErrorResponse } | { readonly type: "unknown" } | { readonly type: "uncertain"; readonly value: DurabilityResponse };

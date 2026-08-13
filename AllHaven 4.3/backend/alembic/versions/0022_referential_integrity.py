"""Enforce referential integrity for core application relationships.

Revision ID: 0022_referential_integrity
Revises: 0021_secret_aead_envelopes
Create Date: 2026-08-13

Required relationships fail closed when legacy orphan rows exist. Nullable
references use SET NULL semantics and legacy orphan values are normalized to
NULL before the constraint is installed. PostgreSQL constraints are added NOT
VALID first, then validated, which keeps the validation step explicit and makes
failures attributable to one named relationship.
"""

from collections import defaultdict
from dataclasses import dataclass
import hashlib
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_referential_integrity"
down_revision: Union[str, None] = "0021_secret_aead_envelopes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _safe_constraint_name(base: str) -> str:
    """Return a deterministic PostgreSQL-safe identifier (max 63 bytes)."""
    if len(base.encode("ascii")) <= 63:
        return base
    digest = hashlib.sha1(base.encode("ascii")).hexdigest()[:8]
    return f"{base[:54]}_{digest}"


@dataclass(frozen=True)
class ForeignKeySpec:
    child: str
    column: str
    parent: str
    ondelete: str
    nullable: bool = False

    @property
    def name(self) -> str:
        return _safe_constraint_name(f"fk_{self.child}_{self.column}_{self.parent}")


@dataclass(frozen=True)
class CompositeForeignKeySpec:
    """A tenant-bound parent reference.

    The single-column FK is intentionally retained as well: it owns the legacy
    SET NULL/CASCADE action, while this constraint proves that the referenced
    parent belongs to the same workspace as the child.
    """

    child: str
    column: str
    parent: str
    ondelete: str = "NO ACTION"
    nullable: bool = False

    @property
    def name(self) -> str:
        return _safe_constraint_name(
            f"fk_{self.child}_workspace_{self.column}_{self.parent}"
        )


@dataclass(frozen=True)
class WorkspaceUniqueSpec:
    table: str

    @property
    def name(self) -> str:
        return _safe_constraint_name(f"uq_{self.table}_workspace_id_id")


@dataclass(frozen=True)
class NamedUniqueSpec:
    table: str
    columns: tuple[str, ...]
    name: str


def _ws(table: str) -> ForeignKeySpec:
    return ForeignKeySpec(table, "workspace_id", "workspaces", "CASCADE")


def _creator(table: str) -> ForeignKeySpec:
    return ForeignKeySpec(table, "created_by", "profiles", "RESTRICT")


def _updater(table: str) -> ForeignKeySpec:
    return ForeignKeySpec(table, "updated_by", "profiles", "SET NULL", True)


FK_SPECS = [
    ForeignKeySpec("workspaces", "owner_id", "profiles", "RESTRICT"),
    _ws("workspace_members"),
    ForeignKeySpec("workspace_members", "user_id", "profiles", "CASCADE"),
    ForeignKeySpec("user_sessions", "user_id", "local_users", "CASCADE"),
    *[_ws(t) for t in (
        "tasks", "task_checklist_items", "notes", "finance_categories", "transactions",
        "calendar_events", "drive_files", "automations", "weather_locations",
        "integration_configs", "ai_agent_configs", "chat_groups", "chat_sessions",
        "chat_messages", "ai_tool_proposals", "ai_tool_calls", "ai_multi_agent_runs",
        "ai_agent_responses", "ai_memories", "ai_memory_suggestions",
        "ai_conversation_summaries", "ai_knowledge_documents", "ai_knowledge_chunks",
        "sync_state",
    )],
    *[_creator(t) for t in (
        "tasks", "task_checklist_items", "notes", "finance_categories", "transactions",
        "calendar_events", "drive_files", "automations", "weather_locations",
        "integration_configs", "ai_agent_configs", "chat_groups", "chat_sessions",
        "ai_tool_proposals", "ai_multi_agent_runs", "ai_knowledge_documents",
    )],
    *[_updater(t) for t in ("tasks", "notes", "transactions", "integration_configs", "ai_agent_configs")],
    ForeignKeySpec("transactions", "category_id", "finance_categories", "SET NULL", True),
    ForeignKeySpec("chat_sessions", "group_id", "chat_groups", "SET NULL", True),
    ForeignKeySpec("chat_messages", "session_id", "chat_sessions", "CASCADE", True),
    ForeignKeySpec("ai_tool_calls", "user_id", "profiles", "RESTRICT"),
    ForeignKeySpec("ai_tool_calls", "session_id", "chat_sessions", "SET NULL", True),
    ForeignKeySpec("ai_tool_calls", "message_id", "chat_messages", "SET NULL", True),
    ForeignKeySpec("ai_tool_calls", "proposal_id", "ai_tool_proposals", "SET NULL", True),
    ForeignKeySpec("ai_multi_agent_runs", "session_id", "chat_sessions", "CASCADE", True),
    ForeignKeySpec("ai_multi_agent_runs", "user_message_id", "chat_messages", "SET NULL", True),
    ForeignKeySpec("ai_agent_responses", "run_id", "ai_multi_agent_runs", "CASCADE"),
    ForeignKeySpec("ai_tool_proposals", "executed_by", "profiles", "SET NULL", True),
    ForeignKeySpec("audit_logs", "workspace_id", "workspaces", "SET NULL", True),
    ForeignKeySpec("audit_logs", "user_id", "profiles", "SET NULL", True),
    ForeignKeySpec("ai_memories", "source_session_id", "chat_sessions", "SET NULL", True),
    ForeignKeySpec("ai_memory_suggestions", "memory_id", "ai_memories", "SET NULL", True),
    ForeignKeySpec("ai_memory_suggestions", "source_session_id", "chat_sessions", "SET NULL", True),
    ForeignKeySpec("ai_conversation_summaries", "session_id", "chat_sessions", "CASCADE"),
    ForeignKeySpec("ai_knowledge_documents", "source_drive_file_id", "drive_files", "SET NULL", True),
    ForeignKeySpec("ai_knowledge_chunks", "document_id", "ai_knowledge_documents", "CASCADE"),
]


# A UUID by itself identifies a row, but it does not prove tenant ownership.
# These candidate keys make `(workspace_id, id)` a valid composite FK target.
WORKSPACE_UNIQUES = [
    WorkspaceUniqueSpec(table) for table in (
        "tasks", "finance_categories", "chat_groups", "chat_sessions",
        "chat_messages", "ai_tool_proposals", "ai_multi_agent_runs",
        "ai_memories", "drive_files", "ai_knowledge_documents",
    )
]
OTHER_UNIQUES = [
    NamedUniqueSpec(
        "workspace_members",
        ("workspace_id", "user_id"),
        "uq_workspace_members_workspace_user",
    ),
]


COMPOSITE_FK_SPECS = [
    CompositeForeignKeySpec(
        "task_checklist_items", "task_id", "tasks", "CASCADE"
    ),
    CompositeForeignKeySpec(
        "transactions", "category_id", "finance_categories", nullable=True
    ),
    CompositeForeignKeySpec(
        "chat_sessions", "group_id", "chat_groups", nullable=True
    ),
    CompositeForeignKeySpec(
        "chat_messages", "session_id", "chat_sessions", "CASCADE", True
    ),
    CompositeForeignKeySpec(
        "ai_tool_calls", "session_id", "chat_sessions", nullable=True
    ),
    CompositeForeignKeySpec(
        "ai_tool_calls", "message_id", "chat_messages", nullable=True
    ),
    CompositeForeignKeySpec(
        "ai_tool_calls", "proposal_id", "ai_tool_proposals", nullable=True
    ),
    CompositeForeignKeySpec(
        "ai_multi_agent_runs", "session_id", "chat_sessions", "CASCADE", True
    ),
    CompositeForeignKeySpec(
        "ai_multi_agent_runs", "user_message_id", "chat_messages", nullable=True
    ),
    CompositeForeignKeySpec(
        "ai_agent_responses", "run_id", "ai_multi_agent_runs", "CASCADE"
    ),
    CompositeForeignKeySpec(
        "ai_memories", "source_session_id", "chat_sessions", nullable=True
    ),
    CompositeForeignKeySpec(
        "ai_memory_suggestions", "memory_id", "ai_memories", nullable=True
    ),
    CompositeForeignKeySpec(
        "ai_memory_suggestions", "source_session_id", "chat_sessions", nullable=True
    ),
    CompositeForeignKeySpec(
        "ai_conversation_summaries", "session_id", "chat_sessions", "CASCADE"
    ),
    CompositeForeignKeySpec(
        "ai_knowledge_documents", "source_drive_file_id", "drive_files", nullable=True
    ),
    CompositeForeignKeySpec(
        "ai_knowledge_chunks", "document_id", "ai_knowledge_documents", "CASCADE"
    ),
]


def _quote(identifier: str) -> str:
    return op.get_bind().dialect.identifier_preparer.quote(identifier)


def _existing_names(table: str) -> set[str]:
    return {
        fk.get("name")
        for fk in sa.inspect(op.get_bind()).get_foreign_keys(table)
        if fk.get("name")
    }


def _existing_unique_names(table: str) -> set[str]:
    return {
        constraint.get("name")
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table)
        if constraint.get("name")
    }


def _fail_on_duplicate_memberships() -> None:
    if "workspace_members" not in sa.inspect(op.get_bind()).get_table_names():
        return
    q = _quote
    duplicate_groups = int(op.get_bind().execute(sa.text(
        f"SELECT count(*) FROM ("
        f"SELECT {q('workspace_id')}, {q('user_id')} "
        f"FROM {q('workspace_members')} "
        f"GROUP BY {q('workspace_id')}, {q('user_id')} HAVING count(*) > 1"
        f") AS duplicate_memberships"
    )).scalar_one())
    if duplicate_groups:
        raise RuntimeError(
            "Referential-integrity preflight failed: workspace_members contains "
            f"{duplicate_groups} duplicate workspace/user membership group(s). "
            "Merge duplicate rows, then rerun the migration. No rows were deleted."
        )


def _orphan_count(spec: ForeignKeySpec) -> int:
    c, p, col = map(_quote, (spec.child, spec.parent, spec.column))
    stmt = sa.text(
        f"SELECT count(*) FROM {c} AS child "
        f"LEFT JOIN {p} AS parent ON parent.id = child.{col} "
        f"WHERE child.{col} IS NOT NULL AND parent.id IS NULL"
    )
    return int(op.get_bind().execute(stmt).scalar_one())


def _normalize_or_fail(spec: ForeignKeySpec) -> None:
    count = _orphan_count(spec)
    if count == 0:
        return
    if spec.nullable:
        c, p, col = map(_quote, (spec.child, spec.parent, spec.column))
        op.execute(sa.text(
            f"UPDATE {c} AS child SET {col} = NULL "
            f"WHERE child.{col} IS NOT NULL AND NOT EXISTS "
            f"(SELECT 1 FROM {p} AS parent WHERE parent.id = child.{col})"
        ))
        return
    raise RuntimeError(
        f"Referential-integrity preflight failed: {spec.child}.{spec.column} has "
        f"{count} row(s) without a matching {spec.parent}.id. Repair or restore "
        "those parent rows, then rerun the migration. No rows were deleted."
    )


def _create_postgresql(spec: ForeignKeySpec) -> None:
    q = _quote
    op.execute(sa.text(
        f"ALTER TABLE {q(spec.child)} ADD CONSTRAINT {q(spec.name)} "
        f"FOREIGN KEY ({q(spec.column)}) REFERENCES {q(spec.parent)} (id) "
        f"ON DELETE {spec.ondelete} NOT VALID"
    ))
    op.execute(sa.text(
        f"ALTER TABLE {q(spec.child)} VALIDATE CONSTRAINT {q(spec.name)}"
    ))


def _composite_orphan_count(spec: CompositeForeignKeySpec) -> int:
    c, p, col = map(_quote, (spec.child, spec.parent, spec.column))
    workspace = _quote("workspace_id")
    stmt = sa.text(
        f"SELECT count(*) FROM {c} AS child "
        f"LEFT JOIN {p} AS parent ON parent.id = child.{col} "
        f"AND parent.{workspace} = child.{workspace} "
        f"WHERE child.{col} IS NOT NULL AND parent.id IS NULL"
    )
    return int(op.get_bind().execute(stmt).scalar_one())


def _normalize_composite_or_fail(spec: CompositeForeignKeySpec) -> None:
    count = _composite_orphan_count(spec)
    if count == 0:
        return
    if spec.nullable:
        c, p, col = map(_quote, (spec.child, spec.parent, spec.column))
        workspace = _quote("workspace_id")
        op.execute(sa.text(
            f"UPDATE {c} AS child SET {col} = NULL "
            f"WHERE child.{col} IS NOT NULL AND NOT EXISTS ("
            f"SELECT 1 FROM {p} AS parent WHERE parent.id = child.{col} "
            f"AND parent.{workspace} = child.{workspace})"
        ))
        return
    raise RuntimeError(
        f"Tenant-integrity preflight failed: {spec.child}.{spec.column} has "
        f"{count} row(s) whose {spec.parent} belongs to another workspace (or "
        "does not exist). Repair the rows, then rerun the migration. No rows "
        "were deleted."
    )


def _create_composite_postgresql(spec: CompositeForeignKeySpec) -> None:
    q = _quote
    op.execute(sa.text(
        f"ALTER TABLE {q(spec.child)} ADD CONSTRAINT {q(spec.name)} "
        f"FOREIGN KEY ({q('workspace_id')}, {q(spec.column)}) "
        f"REFERENCES {q(spec.parent)} ({q('workspace_id')}, {q('id')}) "
        f"ON DELETE {spec.ondelete} NOT VALID"
    ))
    op.execute(sa.text(
        f"ALTER TABLE {q(spec.child)} VALIDATE CONSTRAINT {q(spec.name)}"
    ))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    applicable = [s for s in FK_SPECS if s.child in tables and s.parent in tables]
    existing = {table: _existing_names(table) for table in {s.child for s in applicable}}

    composite = [
        s for s in COMPOSITE_FK_SPECS
        if s.child in tables and s.parent in tables
    ]
    uniques = [s for s in WORKSPACE_UNIQUES if s.table in tables]
    other_uniques = [s for s in OTHER_UNIQUES if s.table in tables]

    if any(s.table == "workspace_members" for s in other_uniques):
        _fail_on_duplicate_memberships()

    # Validate the full legacy data set before changing required relationships.
    for spec in applicable:
        if spec.name not in existing[spec.child]:
            _normalize_or_fail(spec)
    for spec in composite:
        if spec.name not in existing.get(spec.child, set()):
            _normalize_composite_or_fail(spec)

    if op.get_bind().dialect.name == "sqlite":
        for unique in other_uniques:
            if unique.name in _existing_unique_names(unique.table):
                continue
            with op.batch_alter_table(unique.table, recreate="always") as batch:
                batch.create_unique_constraint(unique.name, list(unique.columns))
        for unique in uniques:
            if unique.name in _existing_unique_names(unique.table):
                continue
            with op.batch_alter_table(unique.table, recreate="always") as batch:
                batch.create_unique_constraint(unique.name, ["workspace_id", "id"])
        grouped: dict[str, list[ForeignKeySpec]] = defaultdict(list)
        for spec in applicable:
            if spec.name not in existing[spec.child]:
                grouped[spec.child].append(spec)
        for table, specs in grouped.items():
            with op.batch_alter_table(table, recreate="always") as batch:
                for spec in specs:
                    batch.create_foreign_key(
                        spec.name, spec.parent, [spec.column], ["id"], ondelete=spec.ondelete
                    )
        composite_grouped: dict[str, list[CompositeForeignKeySpec]] = defaultdict(list)
        for spec in composite:
            if spec.name not in _existing_names(spec.child):
                composite_grouped[spec.child].append(spec)
        for table, specs in composite_grouped.items():
            with op.batch_alter_table(table, recreate="always") as batch:
                for spec in specs:
                    batch.create_foreign_key(
                        spec.name,
                        spec.parent,
                        ["workspace_id", spec.column],
                        ["workspace_id", "id"],
                        ondelete=spec.ondelete,
                    )
        return

    for unique in other_uniques:
        if unique.name not in _existing_unique_names(unique.table):
            op.create_unique_constraint(unique.name, unique.table, list(unique.columns))
    for unique in uniques:
        if unique.name not in _existing_unique_names(unique.table):
            op.create_unique_constraint(
                unique.name, unique.table, ["workspace_id", "id"]
            )

    for spec in applicable:
        if spec.name in existing[spec.child]:
            continue
        if op.get_bind().dialect.name == "postgresql":
            _create_postgresql(spec)
        else:
            op.create_foreign_key(
                spec.name, spec.child, spec.parent, [spec.column], ["id"], ondelete=spec.ondelete
            )

    for spec in composite:
        if spec.name in _existing_names(spec.child):
            continue
        if op.get_bind().dialect.name == "postgresql":
            _create_composite_postgresql(spec)
        else:
            op.create_foreign_key(
                spec.name,
                spec.child,
                spec.parent,
                ["workspace_id", spec.column],
                ["workspace_id", "id"],
                ondelete=spec.ondelete,
            )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    composite = [
        s for s in reversed(COMPOSITE_FK_SPECS)
        if s.child in tables and s.parent in tables
    ]
    applicable = [s for s in reversed(FK_SPECS) if s.child in tables and s.parent in tables]
    if op.get_bind().dialect.name == "sqlite":
        composite_grouped: dict[str, list[CompositeForeignKeySpec]] = defaultdict(list)
        for spec in composite:
            composite_grouped[spec.child].append(spec)
        for table, specs in composite_grouped.items():
            existing = _existing_names(table)
            with op.batch_alter_table(table, recreate="always") as batch:
                for spec in specs:
                    if spec.name in existing:
                        batch.drop_constraint(spec.name, type_="foreignkey")
        grouped: dict[str, list[ForeignKeySpec]] = defaultdict(list)
        for spec in applicable:
            grouped[spec.child].append(spec)
        for table, specs in grouped.items():
            existing = _existing_names(table)
            with op.batch_alter_table(table, recreate="always") as batch:
                for spec in specs:
                    if spec.name in existing:
                        batch.drop_constraint(spec.name, type_="foreignkey")
        for unique in reversed(WORKSPACE_UNIQUES):
            if unique.table in tables and unique.name in _existing_unique_names(unique.table):
                with op.batch_alter_table(unique.table, recreate="always") as batch:
                    batch.drop_constraint(unique.name, type_="unique")
        for unique in reversed(OTHER_UNIQUES):
            if unique.table in tables and unique.name in _existing_unique_names(unique.table):
                with op.batch_alter_table(unique.table, recreate="always") as batch:
                    batch.drop_constraint(unique.name, type_="unique")
        return
    for spec in composite:
        if spec.name in _existing_names(spec.child):
            op.drop_constraint(spec.name, spec.child, type_="foreignkey")
    for spec in applicable:
        if spec.name in _existing_names(spec.child):
            op.drop_constraint(spec.name, spec.child, type_="foreignkey")
    for unique in reversed(WORKSPACE_UNIQUES):
        if unique.table in tables and unique.name in _existing_unique_names(unique.table):
            op.drop_constraint(unique.name, unique.table, type_="unique")
    for unique in reversed(OTHER_UNIQUES):
        if unique.table in tables and unique.name in _existing_unique_names(unique.table):
            op.drop_constraint(unique.name, unique.table, type_="unique")

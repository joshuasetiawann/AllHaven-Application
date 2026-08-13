"""Idempotently reconcile tenant-bound parent keys and foreign keys.

Revision ID: 0025_tenant_fk_reconcile
Revises: 0024_secret_context
Create Date: 2026-08-13

This head repairs installations that may already have recorded an early form of
0022 which contained only independent UUID foreign keys. Independent keys prove
that both rows exist; these composite keys additionally prove they belong to
the same workspace.
"""

from collections import defaultdict
from dataclasses import dataclass
import hashlib
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_tenant_fk_reconcile"
down_revision: Union[str, None] = "0024_secret_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _safe_constraint_name(base: str) -> str:
    if len(base.encode("ascii")) <= 63:
        return base
    digest = hashlib.sha1(base.encode("ascii")).hexdigest()[:8]
    return f"{base[:54]}_{digest}"


@dataclass(frozen=True)
class Link:
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


PARENTS = (
    "tasks", "finance_categories", "chat_groups", "chat_sessions",
    "chat_messages", "ai_tool_proposals", "ai_multi_agent_runs",
    "ai_memories", "drive_files", "ai_knowledge_documents",
)

LINKS = (
    Link("task_checklist_items", "task_id", "tasks", "CASCADE"),
    Link("transactions", "category_id", "finance_categories", nullable=True),
    Link("chat_sessions", "group_id", "chat_groups", nullable=True),
    Link("chat_messages", "session_id", "chat_sessions", "CASCADE", True),
    Link("ai_tool_calls", "session_id", "chat_sessions", nullable=True),
    Link("ai_tool_calls", "message_id", "chat_messages", nullable=True),
    Link("ai_tool_calls", "proposal_id", "ai_tool_proposals", nullable=True),
    Link("ai_multi_agent_runs", "session_id", "chat_sessions", "CASCADE", True),
    Link("ai_multi_agent_runs", "user_message_id", "chat_messages", nullable=True),
    Link("ai_agent_responses", "run_id", "ai_multi_agent_runs", "CASCADE"),
    Link("ai_memories", "source_session_id", "chat_sessions", nullable=True),
    Link("ai_memory_suggestions", "memory_id", "ai_memories", nullable=True),
    Link(
        "ai_memory_suggestions", "source_session_id", "chat_sessions", nullable=True
    ),
    Link("ai_conversation_summaries", "session_id", "chat_sessions", "CASCADE"),
    Link(
        "ai_knowledge_documents", "source_drive_file_id", "drive_files", nullable=True
    ),
    Link(
        "ai_knowledge_chunks", "document_id", "ai_knowledge_documents", "CASCADE"
    ),
)


def _quote(identifier: str) -> str:
    return op.get_bind().dialect.identifier_preparer.quote(identifier)


def _foreign_key_names(table: str) -> set[str]:
    return {
        fk.get("name")
        for fk in sa.inspect(op.get_bind()).get_foreign_keys(table)
        if fk.get("name")
    }


def _equivalent_foreign_key(link: Link) -> dict | None:
    for fk in sa.inspect(op.get_bind()).get_foreign_keys(link.child):
        if (
            fk.get("referred_table") == link.parent
            and list(fk.get("constrained_columns") or [])
            == ["workspace_id", link.column]
            and list(fk.get("referred_columns") or []) == ["workspace_id", "id"]
        ):
            return fk
    return None


def _unique_names(table: str) -> set[str]:
    return {
        item.get("name")
        for item in sa.inspect(op.get_bind()).get_unique_constraints(table)
        if item.get("name")
    }


def _preflight_membership_unique(tables: set[str]) -> None:
    if "workspace_members" not in tables:
        return
    q = _quote
    count = int(op.get_bind().execute(sa.text(
        f"SELECT count(*) FROM (SELECT {q('workspace_id')}, {q('user_id')} "
        f"FROM {q('workspace_members')} GROUP BY {q('workspace_id')}, {q('user_id')} "
        "HAVING count(*) > 1) AS duplicates"
    )).scalar_one())
    if count:
        raise RuntimeError(
            f"Tenant-integrity preflight found {count} duplicate workspace/user "
            "membership group(s). Merge them and retry; no rows were deleted."
        )


def _preflight_link(link: Link) -> None:
    q = _quote
    count = int(op.get_bind().execute(sa.text(
        f"SELECT count(*) FROM {q(link.child)} child "
        f"LEFT JOIN {q(link.parent)} parent "
        f"ON parent.{q('id')} = child.{q(link.column)} "
        f"AND parent.{q('workspace_id')} = child.{q('workspace_id')} "
        f"WHERE child.{q(link.column)} IS NOT NULL AND parent.{q('id')} IS NULL"
    )).scalar_one())
    if not count:
        return
    if link.nullable:
        op.execute(sa.text(
            f"UPDATE {q(link.child)} AS child SET {q(link.column)} = NULL "
            f"WHERE child.{q(link.column)} IS NOT NULL AND NOT EXISTS ("
            f"SELECT 1 FROM {q(link.parent)} parent "
            f"WHERE parent.{q('id')} = child.{q(link.column)} "
            f"AND parent.{q('workspace_id')} = child.{q('workspace_id')})"
        ))
        return
    raise RuntimeError(
        f"Tenant-integrity preflight found {count} invalid {link.child}."
        f"{link.column} reference(s). Repair them and retry; no rows were deleted."
    )


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    parents = [table for table in PARENTS if table in tables]
    links = [link for link in LINKS if link.child in tables and link.parent in tables]

    _preflight_membership_unique(tables)
    for link in links:
        if _equivalent_foreign_key(link) is None:
            _preflight_link(link)

    unique_specs = [
        (
            table,
            _safe_constraint_name(f"uq_{table}_workspace_id_id"),
            ["workspace_id", "id"],
        )
        for table in parents
    ]
    if "workspace_members" in tables:
        unique_specs.append((
            "workspace_members",
            "uq_workspace_members_workspace_user",
            ["workspace_id", "user_id"],
        ))

    if bind.dialect.name == "sqlite":
        for table, name, columns in unique_specs:
            if name not in _unique_names(table):
                with op.batch_alter_table(table, recreate="always") as batch:
                    batch.create_unique_constraint(name, columns)
        grouped: dict[str, list[Link]] = defaultdict(list)
        for link in links:
            if _equivalent_foreign_key(link) is None:
                grouped[link.child].append(link)
        for table, table_links in grouped.items():
            with op.batch_alter_table(table, recreate="always") as batch:
                for link in table_links:
                    batch.create_foreign_key(
                        link.name,
                        link.parent,
                        ["workspace_id", link.column],
                        ["workspace_id", "id"],
                        ondelete=link.ondelete,
                    )
        return

    for table, name, columns in unique_specs:
        if name not in _unique_names(table):
            op.create_unique_constraint(name, table, columns)

    q = _quote
    for link in links:
        equivalent = _equivalent_foreign_key(link)
        if equivalent is not None:
            old_name = equivalent.get("name")
            # Early 0022 builds let PostgreSQL silently truncate long names.
            # Normalize those names so future idempotency and downgrades are exact.
            if (
                bind.dialect.name == "postgresql"
                and old_name
                and old_name != link.name
                and link.name not in _foreign_key_names(link.child)
            ):
                op.execute(sa.text(
                    f"ALTER TABLE {q(link.child)} RENAME CONSTRAINT "
                    f"{q(old_name)} TO {q(link.name)}"
                ))
            continue
        if bind.dialect.name == "postgresql":
            op.execute(sa.text(
                f"ALTER TABLE {q(link.child)} ADD CONSTRAINT {q(link.name)} "
                f"FOREIGN KEY ({q('workspace_id')}, {q(link.column)}) "
                f"REFERENCES {q(link.parent)} ({q('workspace_id')}, {q('id')}) "
                f"ON DELETE {link.ondelete} NOT VALID"
            ))
            op.execute(sa.text(
                f"ALTER TABLE {q(link.child)} VALIDATE CONSTRAINT {q(link.name)}"
            ))
        else:
            op.create_foreign_key(
                link.name,
                link.child,
                link.parent,
                ["workspace_id", link.column],
                ["workspace_id", "id"],
                ondelete=link.ondelete,
            )


def downgrade() -> None:
    # 0025 repairs databases that may have run an early, incomplete copy of 0022.
    # On a fresh/current chain these exact constraints are already owned by 0022,
    # so their provenance cannot be inferred from the catalog.  Dropping by name
    # would remove 0022's tenant boundary during a one-step downgrade.  Keep the
    # additive integrity constraints; they are compatible with revision 0024 and
    # safer than weakening an older installation.
    pass

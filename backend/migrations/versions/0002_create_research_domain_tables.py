"""Create research domain tables with pgvector, tenant isolation, and cascades

Revision ID: 0002_research_domain
Revises: 0001_auth_tables
Create Date: 2026-11-01 13:35:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_research_domain"
down_revision: str | None = "0001_auth_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0. Enable pgvector extension on PostgreSQL
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector;"))

    # 1. Create documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "owner_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="uploaded"),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("extraction_warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"], unique=False)
    op.create_index("ix_documents_owner_status", "documents", ["owner_id", "status"], unique=False)
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"], unique=False)
    op.create_index("ix_documents_status", "documents", ["status"], unique=False)

    # 2. Create chunks table with pgvector(384)
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.String(length=64),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("page_numbers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("character_start", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("character_end", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("embedding_model", sa.String(length=64), nullable=False, server_default="BAAI/bge-small-en-v1.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"], unique=False)
    op.create_index("ix_chunks_doc_index", "chunks", ["document_id", "chunk_index"], unique=False)
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # 3. Create collections table
    op.create_table(
        "collections",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "owner_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_collections_owner_id", "collections", ["owner_id"], unique=False)

    # 4. Create document_collections junction table
    op.create_table(
        "document_collections",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.String(length=64),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "collection_id",
            sa.String(length=64),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "collection_id", name="uq_document_collection"),
    )
    op.create_index("ix_doc_coll_pair", "document_collections", ["document_id", "collection_id"], unique=False)

    # Database-level tenant isolation trigger for document_collections (single statements)
    op.execute(sa.text("""
    CREATE OR REPLACE FUNCTION check_document_collection_same_owner()
    RETURNS TRIGGER AS $$
    DECLARE
        doc_owner VARCHAR(64);
        coll_owner VARCHAR(64);
    BEGIN
        SELECT owner_id INTO doc_owner FROM documents WHERE id = NEW.document_id;
        SELECT owner_id INTO coll_owner FROM collections WHERE id = NEW.collection_id;
        IF doc_owner IS NOT NULL AND coll_owner IS NOT NULL AND doc_owner <> coll_owner THEN
            RAISE EXCEPTION 'Tenant ownership mismatch: document and collection belong to different users';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """))

    op.execute(sa.text("""
    CREATE CONSTRAINT TRIGGER trg_check_document_collection_owner
    AFTER INSERT OR UPDATE ON document_collections
    FOR EACH ROW EXECUTE FUNCTION check_document_collection_same_owner();
    """))

    # 5. Create research_sessions table
    op.create_table(
        "research_sessions",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "owner_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_research_sessions_owner_id", "research_sessions", ["owner_id"], unique=False)

    # 6. Create chat_messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            sa.String(length=64),
            sa.ForeignKey("research_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("claims", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("insufficient_evidence", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_ms", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"], unique=False)

    # 7. Create research_notes table
    op.create_table(
        "research_notes",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "owner_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.String(length=64),
            sa.ForeignKey("research_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_citations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_research_notes_owner_id", "research_notes", ["owner_id"], unique=False)
    op.create_index("ix_research_notes_session_id", "research_notes", ["session_id"], unique=False)

    # Database-level tenant isolation trigger for research_notes (single statements)
    op.execute(sa.text("""
    CREATE OR REPLACE FUNCTION check_research_note_same_owner()
    RETURNS TRIGGER AS $$
    DECLARE
        sess_owner VARCHAR(64);
    BEGIN
        IF NEW.session_id IS NOT NULL THEN
            SELECT owner_id INTO sess_owner FROM research_sessions WHERE id = NEW.session_id;
            IF sess_owner IS NOT NULL AND sess_owner <> NEW.owner_id THEN
                RAISE EXCEPTION 'Tenant ownership mismatch: research note cannot link to session belonging to another user';
            END IF;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """))

    op.execute(sa.text("""
    CREATE CONSTRAINT TRIGGER trg_check_research_note_owner
    AFTER INSERT OR UPDATE ON research_notes
    FOR EACH ROW EXECUTE FUNCTION check_research_note_same_owner();
    """))

    # 8. Create answer_feedback table
    op.create_table(
        "answer_feedback",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "message_id",
            sa.String(length=64),
            sa.ForeignKey("chat_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_answer_feedback_message_id", "answer_feedback", ["message_id"], unique=False)

    # 9. Create llm_quota_configs table
    op.create_table(
        "llm_quota_configs",
        sa.Column("model_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("rpm_limit", sa.Integer(), nullable=False),
        sa.Column("tpm_limit", sa.Integer(), nullable=False),
        sa.Column("rpd_limit", sa.Integer(), nullable=False),
        sa.Column("quota_timezone", sa.String(length=64), nullable=False, server_default="America/Los_Angeles"),
        sa.Column("warning_threshold_percent", sa.Float(), nullable=False, server_default="0.80"),
        sa.Column("safety_margin_percent", sa.Float(), nullable=False, server_default="0.10"),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Seed approved initial quota configuration for gemini-3.5-flash-lite
    op.execute(sa.text("""
    INSERT INTO llm_quota_configs (
        model_id, rpm_limit, tpm_limit, rpd_limit, quota_timezone,
        warning_threshold_percent, safety_margin_percent, notes, updated_at
    ) VALUES (
        'gemini-3.5-flash-lite', 15, 250000, 500, 'America/Los_Angeles',
        0.80, 0.10, 'Reference limits based on Google AI Studio tier for gemini-3.5-flash-lite.', NOW()
    ) ON CONFLICT (model_id) DO NOTHING;
    """))

    # 10. Create llm_usage_records table
    op.create_table(
        "llm_usage_records",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "session_id",
            sa.String(length=64),
            sa.ForeignKey("research_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("call_type", sa.String(length=32), nullable=False, server_default="research_qa"),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("is_provider_call", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("has_usage_metadata", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_llm_usage_records_trace_id", "llm_usage_records", ["trace_id"], unique=False)
    op.create_index("ix_llm_usage_records_request_id", "llm_usage_records", ["request_id"], unique=False)
    op.create_index("ix_llm_usage_records_session_id", "llm_usage_records", ["session_id"], unique=False)
    op.create_index("ix_llm_usage_records_user_id", "llm_usage_records", ["user_id"], unique=False)
    op.create_index("ix_llm_usage_records_model", "llm_usage_records", ["model"], unique=False)
    op.create_index("ix_llm_usage_records_is_provider_call", "llm_usage_records", ["is_provider_call"], unique=False)
    op.create_index("ix_llm_usage_records_status", "llm_usage_records", ["status"], unique=False)
    op.create_index("ix_llm_usage_records_created_at", "llm_usage_records", ["created_at"], unique=False)

    # Database-level tenant isolation trigger for llm_usage_records (single statements)
    op.execute(sa.text("""
    CREATE OR REPLACE FUNCTION check_llm_usage_same_owner()
    RETURNS TRIGGER AS $$
    DECLARE
        sess_owner VARCHAR(64);
    BEGIN
        IF NEW.session_id IS NOT NULL AND NEW.user_id IS NOT NULL THEN
            SELECT owner_id INTO sess_owner FROM research_sessions WHERE id = NEW.session_id;
            IF sess_owner IS NOT NULL AND sess_owner <> NEW.user_id THEN
                RAISE EXCEPTION 'Tenant ownership mismatch: llm_usage_record cannot link to session belonging to another user';
            END IF;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """))

    op.execute(sa.text("""
    CREATE CONSTRAINT TRIGGER trg_check_llm_usage_owner
    AFTER INSERT OR UPDATE ON llm_usage_records
    FOR EACH ROW EXECUTE FUNCTION check_llm_usage_same_owner();
    """))


def downgrade() -> None:
    # Drop triggers and functions (single statements)
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_check_llm_usage_owner ON llm_usage_records;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS check_llm_usage_same_owner();"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_check_research_note_owner ON research_notes;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS check_research_note_same_owner();"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_check_document_collection_owner ON document_collections;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS check_document_collection_same_owner();"))

    # Drop tables in reverse order
    op.drop_table("llm_usage_records")
    op.drop_table("llm_quota_configs")
    op.drop_table("answer_feedback")
    op.drop_table("research_notes")
    op.drop_table("chat_messages")
    op.drop_table("research_sessions")
    op.drop_table("document_collections")
    op.drop_table("collections")
    op.drop_table("chunks")
    op.drop_table("documents")

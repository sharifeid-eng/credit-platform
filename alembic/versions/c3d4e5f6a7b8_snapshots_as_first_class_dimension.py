"""snapshots as first-class dimension

Revision ID: c3d4e5f6a7b8
Revises: b2f3a8c91d45
Create Date: 2026-04-21

Session 31 (D1a approved). Per the user's decision on 2026-04-21:
    "create a plan for the best long term solution and lets implement"
    D1a — drop existing DB invoice/payment rows + clean re-seed from tape files.

What this migration does:
1. Creates `snapshots` table — point-in-time views of a product's book.
2. Deletes all rows from `invoices` and `payments` (per D1a). The 7,697 Klaim
   rows were one-off-seeded from an older Mar 3 tape and carry no unique
   information not present in the source tapes. Re-seeding via
   `scripts/seed_db.py` after this migration restores every tape as its own
   snapshot with full `extra_data` JSONB payload.
3. Adds `snapshot_id` FK on `invoices` (NOT NULL), `payments` (NOT NULL), and
   `bank_statements` (nullable — time-series, not strictly snapshot-scoped).
4. Adds composite uniqueness `(snapshot_id, invoice_number)` — the same
   invoice can exist in multiple snapshots, each carrying its state at that
   point in time.
5. New indexes for snapshot-filtered reads.

After this migration the application CANNOT read invoice/payment data until
`seed_db.py` (or `ingest_tape.py`) has been run. This is intentional — the
tape-fallback code path is removed in Phase 3 of the same session, so DB is
the only runtime source.

Downgrade preserves the table shape but data lost in step 2 is not recovered.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2f3a8c91d45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Create snapshots table ─────────────────────────────────────────
    op.create_table(
        'snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('taken_at', sa.Date(), nullable=False),
        sa.Column('ingested_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.UniqueConstraint('product_id', 'name', name='uq_snapshots_product_name'),
    )
    op.create_index('ix_snapshots_product_taken_at', 'snapshots',
                    ['product_id', 'taken_at'], unique=False)
    op.create_index('ix_snapshots_source', 'snapshots', ['source'], unique=False)

    # ── 2. Drop existing invoice/payment rows (per D1a) ───────────────────
    # Payments cascade from invoices; delete in FK-safe order.
    op.execute("DELETE FROM payments")
    op.execute("DELETE FROM invoices")
    # bank_statements retained but will have NULL snapshot_id until re-tagged.

    # ── 3. Add snapshot_id columns ────────────────────────────────────────
    # Tables `invoices` and `payments` are now empty, so NOT NULL is safe.
    op.add_column('invoices',
                  sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), nullable=False))
    op.create_foreign_key('fk_invoices_snapshot_id', 'invoices', 'snapshots',
                          ['snapshot_id'], ['id'])

    op.add_column('payments',
                  sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), nullable=False))
    op.create_foreign_key('fk_payments_snapshot_id', 'payments', 'snapshots',
                          ['snapshot_id'], ['id'])

    op.add_column('bank_statements',
                  sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_bank_statements_snapshot_id', 'bank_statements', 'snapshots',
                          ['snapshot_id'], ['id'])

    # ── 4. Indexes & unique constraints ───────────────────────────────────
    op.create_index('ix_invoices_snapshot_id', 'invoices', ['snapshot_id'], unique=False)
    op.create_unique_constraint('uq_invoices_snapshot_invoice_number', 'invoices',
                                ['snapshot_id', 'invoice_number'])

    op.create_index('ix_payments_snapshot_id', 'payments', ['snapshot_id'], unique=False)

    op.create_index('ix_bank_statements_org', 'bank_statements', ['org_id'], unique=False)
    op.create_index('ix_bank_statements_snapshot_id', 'bank_statements', ['snapshot_id'], unique=False)
    op.create_index('ix_bank_statements_statement_date', 'bank_statements',
                    ['statement_date'], unique=False)


def downgrade() -> None:
    # Drop indexes & constraints in reverse order
    op.drop_index('ix_bank_statements_statement_date', table_name='bank_statements')
    op.drop_index('ix_bank_statements_snapshot_id', table_name='bank_statements')
    op.drop_index('ix_bank_statements_org', table_name='bank_statements')

    op.drop_index('ix_payments_snapshot_id', table_name='payments')

    op.drop_constraint('uq_invoices_snapshot_invoice_number', 'invoices', type_='unique')
    op.drop_index('ix_invoices_snapshot_id', table_name='invoices')

    # Drop FK constraints
    op.drop_constraint('fk_bank_statements_snapshot_id', 'bank_statements', type_='foreignkey')
    op.drop_constraint('fk_payments_snapshot_id', 'payments', type_='foreignkey')
    op.drop_constraint('fk_invoices_snapshot_id', 'invoices', type_='foreignkey')

    # Drop snapshot_id columns
    op.drop_column('bank_statements', 'snapshot_id')
    op.drop_column('payments', 'snapshot_id')
    op.drop_column('invoices', 'snapshot_id')

    # Drop snapshots table
    op.drop_index('ix_snapshots_source', table_name='snapshots')
    op.drop_index('ix_snapshots_product_taken_at', table_name='snapshots')
    op.drop_table('snapshots')

    # Note: data deleted in upgrade step 2 (invoices, payments) is not recovered.
    # Re-populate from tape files via scripts/seed_db.py if needed.

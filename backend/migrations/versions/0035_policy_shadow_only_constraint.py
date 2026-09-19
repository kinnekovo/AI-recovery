"""enforce Policy V2 shadow-only mode
Revision ID: 0035_policy_shadow_guard
Revises: 0034_policy_v2_shadow
"""
from alembic import op
import sqlalchemy as sa
revision="0035_policy_shadow_guard";down_revision="0034_policy_v2_shadow";branch_labels=None;depends_on=None
def _exists():
    return any(item.get("name")=="ck_policy_decisions_shadow_only" for item in sa.inspect(op.get_bind()).get_check_constraints("policy_decisions"))
def upgrade():
    # Supports the developer DB where this guard was created while 0034 was being authored.
    if not _exists(): op.create_check_constraint("ck_policy_decisions_shadow_only","policy_decisions","mode = 'shadow'")
def downgrade():
    if _exists(): op.drop_constraint("ck_policy_decisions_shadow_only","policy_decisions",type_="check")

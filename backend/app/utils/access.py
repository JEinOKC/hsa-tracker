# TODO(bilateral-roles): The _bilateral_* helpers below are dormant — no frontend
# UI currently creates AccountRole/AccountAccess records, so bilateral grants are
# never in use. They remain here for when the external-access feature (accountants,
# advisors) is built out. The household path is the only active access route.
"""Permission helpers for role-based account access."""

from uuid import UUID
from sqlalchemy.orm import Session

from app.models.access import AccountAccess, AccountRole
from app.models.household import HouseholdMembership


def get_readable_owner_ids(user, db: Session, resource: str = None) -> list[UUID]:
    """Returns the user's own ID plus all owner IDs where the user has read access.

    If resource is given (e.g. "transactions"), only include owners where that
    specific resource's read permission is granted. Checks both bilateral grants
    and household membership.
    """
    owner_ids = {user.id}

    # Bilateral path
    query = (
        db.query(AccountAccess)
        .join(AccountRole, AccountAccess.role_id == AccountRole.id)
        .filter(AccountAccess.sub_user_id == user.id)
    )
    if resource:
        field = f"can_read_{resource}"
        query = query.filter(getattr(AccountRole, field) == True)
    else:
        query = query.filter(
            AccountRole.can_read_transactions
            | AccountRole.can_read_bank_accounts
            | AccountRole.can_read_documents
            | AccountRole.can_read_family_members
        )
    for a in query.all():
        owner_ids.add(a.owner_user_id)

    # Household path
    for uid in _household_owner_ids(user, db, resource):
        owner_ids.add(uid)

    return list(owner_ids)


def check_permission(user, target_user_id: UUID, resource: str, operation: str, db: Session) -> bool:
    """
    Returns True if `user` can perform `operation` on `target_user_id`'s `resource`.

    operation: "read" | "write" | "delete"
    resource:  "transactions" | "bank_accounts" | "documents" | "family_members"

    Own data always passes. Shared data is checked against bilateral grants and
    household membership.
    """
    if user.id == target_user_id:
        return True

    # Bilateral check
    access = (
        db.query(AccountAccess)
        .join(AccountRole, AccountAccess.role_id == AccountRole.id)
        .filter(
            AccountAccess.owner_user_id == target_user_id,
            AccountAccess.sub_user_id == user.id,
        )
        .first()
    )
    if access:
        field = f"can_{operation}_{resource}"
        if bool(getattr(access.role, field, False)):
            return True

    # Household check
    return _household_check(user, target_user_id, resource, operation, db)


def _household_owner_ids(user, db: Session, resource: str = None) -> list[UUID]:
    """Return IDs of other household members whose data the user can read."""
    membership = db.query(HouseholdMembership).filter(
        HouseholdMembership.user_id == user.id
    ).first()
    if not membership:
        return []
    if resource and not getattr(membership.role, f"can_read_{resource}", False):
        return []
    others = db.query(HouseholdMembership).filter(
        HouseholdMembership.household_id == membership.household_id,
        HouseholdMembership.user_id != user.id,
    ).all()
    return [m.user_id for m in others]


def _household_check(user, target_user_id: UUID, resource: str, operation: str, db: Session) -> bool:
    user_mem = db.query(HouseholdMembership).filter(
        HouseholdMembership.user_id == user.id
    ).first()
    target_mem = db.query(HouseholdMembership).filter(
        HouseholdMembership.user_id == target_user_id
    ).first()
    if not user_mem or not target_mem:
        return False
    if user_mem.household_id != target_mem.household_id:
        return False
    field = f"can_{operation}_{resource}"
    return bool(getattr(user_mem.role, field, False))

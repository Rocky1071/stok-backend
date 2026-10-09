"""Role-based authorization — single shared company, so roles only (no tenancy, no ownership).

One decision point: `has_perm()`. Routes declare the action they need via `require_perm(...)`.
Deny-by-default: a role missing from PERMS, or an action missing from its set, is denied.
The principal is always re-read from Mongo per request (lib.security.require_user), so a role
revoked in the admin panel stops working immediately rather than at token expiry.
"""

from fastapi import Depends, HTTPException

from lib.security import require_user

# Roles
ANA = "ana_yonetici"  # Ana Yönetici — full access
YARDIMCI = "yardimci_yonetici"  # Yardımcı Yönetici — stock/product/movement entry only
UYE = "uye"  # Üye — read only

ROLE_LABELS = {
    ANA: "Ana Yönetici",
    YARDIMCI: "Yardımcı Yönetici",
    UYE: "Üye",
}

# Actions
PRODUCT_CREATE = "product:create"
PRODUCT_UPDATE = "product:update"
PRODUCT_DELETE = "product:delete"
MOVEMENT_CREATE = "movement:create"
MOVEMENT_DELETE = "movement:delete"
FIELD_MANAGE = "field:manage"
USER_MANAGE = "user:manage"
UPLOAD = "upload"

# Yardımcı Yönetici: ürün ekler, stok günceller, satış/düşüm yapar — silemez,
# özel alan ve üye yönetimine erişemez.
PERMS: dict[str, set[str]] = {
    ANA: {
        PRODUCT_CREATE,
        PRODUCT_UPDATE,
        PRODUCT_DELETE,
        MOVEMENT_CREATE,
        MOVEMENT_DELETE,
        FIELD_MANAGE,
        USER_MANAGE,
        UPLOAD,
    },
    YARDIMCI: {PRODUCT_CREATE, PRODUCT_UPDATE, MOVEMENT_CREATE, UPLOAD},
    UYE: set(),
}


def role_of(user: dict) -> str:
    return user.get("role") or UYE


def has_perm(user: dict, action: str) -> bool:
    return action in PERMS.get(role_of(user), set())


def require_perm(action: str):
    """Route dependency: `dependencies=[Depends(require_perm(PRODUCT_DELETE))]` or
    `user: dict = Depends(require_perm(...))` when the handler needs the principal."""

    async def dependency(user: dict = Depends(require_user)) -> dict:
        if not has_perm(user, action):
            raise HTTPException(
                status_code=403,
                detail=f"Bu işlem için yetkiniz yok ({ROLE_LABELS.get(role_of(user), 'Üye')})",
            )
        return user

    return dependency

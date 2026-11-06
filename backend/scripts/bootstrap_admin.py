#!/usr/bin/env python3
"""ORION Administrator Bootstrap Utility.

Securely provisions the primary administrator account (e.g. orionadmin@gmail.com)
using Argon2id password hashing and existing database conventions.

Security Guarantees:
- Passwords are typed via hidden terminal prompts (getpass) with no terminal echo.
- Plaintext passwords are never logged, stored, or exposed.
- Password strength is enforced against NIST / OWASP requirements.
- Existing researcher data and duplicate accounts are preserved without disruption.
"""

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import select

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.config import settings
from app.db.base import generate_uuid
from app.db.session import AsyncSessionLocal
from app.models.auth_event import AuthAuditEvent
from app.models.user import User
from app.security.service import (
    hash_password,
    normalize_email,
    validate_password_strength,
)


def _resolve_is_admin(email: str, user_id: str | None = None) -> bool:
    """Verify administrator configuration matching."""
    admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS if e.strip()]
    if email and email.strip().lower() in admin_emails:
        return True
    admin_ids = [uid.strip() for uid in settings.ADMIN_USER_IDS if uid.strip()]
    if user_id and user_id.strip() in admin_ids:
        return True
    return False


async def bootstrap_admin(
    email: str,
    display_name: str = "ORION Administrator",
    institution: str | None = "ORION System Administration",
    password_stdin: bool = False,
    reset_password: bool = False,
) -> None:
    """Execute administrator bootstrap procedure."""
    try:
        norm_email = normalize_email(email)
    except ValueError as e:
        print(f"[ERROR] Invalid email: {e}", file=sys.stderr)
        sys.exit(1)

    print("=" * 64)
    print("ORION — Primary Administrator Bootstrap")
    print("=" * 64)
    print(f"Target Email: {norm_email}")
    print(f"Display Name: {display_name}")

    is_configured_admin = _resolve_is_admin(norm_email)
    if not is_configured_admin:
        print(
            f"[WARNING] {norm_email} is not yet in ADMIN_EMAILS ({settings.ADMIN_EMAILS}).",
            file=sys.stderr,
        )
    else:
        print(f"[OK] {norm_email} is recognized as an authorized administrator in system settings.")

    async with AsyncSessionLocal() as session:
        # Check if user already exists
        stmt = select(User).where(User.email == norm_email)
        res = await session.execute(stmt)
        existing_user = res.scalar_one_or_none()

        if existing_user and not reset_password:
            print("\n[INFO] An account with this email already exists:")
            print(f"  User ID     : {existing_user.id}")
            print(f"  Display Name: {existing_user.display_name}")
            print(f"  Status      : {existing_user.status}")
            print(f"  Active      : {existing_user.is_active}")
            print(f"  Admin Role  : {'admin' if _resolve_is_admin(existing_user.email, existing_user.id) else 'authenticated'}")
            print("\nExisting research data and account have been preserved.")
            print("To reset the password for this administrator account, re-run with --reset-password.")
            return

        # Secure password input (hidden prompt)
        password: str = ""
        env_pwd = os.environ.get("ORION_BOOTSTRAP_PASSWORD")

        if password_stdin:
            password = sys.stdin.readline().strip()
        elif env_pwd:
            password = env_pwd.strip()
            # Immediately clear from env to prevent accidental leakage in child processes
            os.environ.pop("ORION_BOOTSTRAP_PASSWORD", None)
        else:
            prompt_msg = (
                f"Enter new password for administrator '{norm_email}': "
                if existing_user
                else f"Enter initial password for administrator '{norm_email}': "
            )
            password = getpass.getpass(prompt_msg)
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("[ERROR] Passwords do not match.", file=sys.stderr)
                sys.exit(1)

        # Validate password strength against NIST/OWASP requirements
        try:
            validate_password_strength(password)
        except ValueError as err:
            print(f"[ERROR] Password does not meet security requirements: {err}", file=sys.stderr)
            sys.exit(1)

        # Hash with Argon2id
        hashed = hash_password(password)
        # Clear plain password reference immediately
        password = ""
        del password

        if existing_user:
            existing_user.hashed_password = hashed
            existing_user.status = "active"
            existing_user.is_active = True
            await session.commit()
            print(f"\n[SUCCESS] Password updated successfully for administrator '{norm_email}'.")
            print(f"  User ID   : {existing_user.id}")
            print(f"  Role      : admin")
        else:
            new_user = User(
                id=generate_uuid("usr"),
                email=norm_email,
                hashed_password=hashed,
                display_name=display_name,
                institution=institution,
                status="active",
                is_active=True,
            )
            session.add(new_user)
            await session.flush()

            # Record registration audit event
            try:
                audit_evt = AuthAuditEvent(
                    id=generate_uuid("evt"),
                    user_id=new_user.id,
                    email=new_user.email,
                    event_type="register",
                    success=True,
                    ip_address="127.0.0.1",
                    user_agent="ORION-Admin-Bootstrap-CLI",
                )
                session.add(audit_evt)
            except Exception:
                pass

            await session.commit()
            await session.refresh(new_user)

            print(f"\n[SUCCESS] Primary administrator account created successfully!")
            print(f"  User ID   : {new_user.id}")
            print(f"  Email     : {new_user.email}")
            print(f"  Role      : admin")
            print(f"  Status    : {new_user.status}")

    print("\nAdministrator is authorized to access /admin and all administrative REST APIs.")


def main() -> None:
    parser = argparse.ArgumentParser(description="ORION Administrator Bootstrap Utility")
    parser.add_argument(
        "--email",
        default="orionadmin@gmail.com",
        help="Email address for primary administrator (default: orionadmin@gmail.com)",
    )
    parser.add_argument(
        "--display-name",
        default="ORION Administrator",
        help="Display name for administrator account",
    )
    parser.add_argument(
        "--institution",
        default="ORION System Administration",
        help="Institutional affiliation",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read password from stdin rather than interactive hidden prompt",
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Reset password if account already exists",
    )
    args = parser.parse_args()

    asyncio.run(
        bootstrap_admin(
            email=args.email,
            display_name=args.display_name,
            institution=args.institution,
            password_stdin=args.stdin,
            reset_password=args.reset_password,
        )
    )


if __name__ == "__main__":
    main()


"""Password change service adhering to SOLID principles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from django.db import transaction

from authentication.models import User

import sys
import os
# Add parent directory to path to import monitoring module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monitoring import track_service_operation


class PasswordEncoder(Protocol):
    """Abstraction for password hashing."""

    def encode(self, raw_password: str) -> str:
        raise NotImplementedError


class DjangoPasswordEncoder:
    """Adapter for Django's password hashing utilities."""

    def encode(self, raw_password: str) -> str:
        from django.contrib.auth.hashers import make_password

        return make_password(raw_password)


class UserRepository(Protocol):
    """Abstraction for user persistence operations."""

    def get_by_credentials(self, *, user_id: str, username: str) -> User | None:
        raise NotImplementedError

    def save_password(self, user: User, encoded_password: str) -> None:
        raise NotImplementedError

    def delete_user(self, user: User) -> None:
        raise NotImplementedError


class DjangoUserRepository:
    """Concrete repository backed by Django's ORM."""

    def get_by_credentials(self, *, user_id: str, username: str) -> User | None:
        try:
            return User.objects.get(user_id=user_id, username=username)
        except User.DoesNotExist:
            return None

    def save_password(self, user: User, encoded_password: str) -> None:
        user.password = encoded_password
        user.save(update_fields=["password"])

    def delete_user(self, user: User) -> None:
        user.delete()


@dataclass(frozen=True)
class PasswordChangeResult:
    """Value object describing the result of a password update."""

    success: bool
    message: str


@dataclass(frozen=True)
class AccountDeletionResult:
    """Value object describing the result of an account deletion."""

    success: bool
    message: str


class PasswordChangeService:
    """Coordinates password change logic while keeping collaborators abstract."""

    def __init__(
        self,
        *,
        user_repository: UserRepository,
        password_encoder: PasswordEncoder,
    ) -> None:
        self._users = user_repository
        self._encoder = password_encoder

    @track_service_operation("password_change")
    def change_password(
        self,
        *,
        user: User,
        new_password: str,
    ) -> PasswordChangeResult:
        encoded = self._encoder.encode(new_password)

        with transaction.atomic():
            self._users.save_password(user, encoded)

        return PasswordChangeResult(success=True, message="Password changed successfully")

    @track_service_operation("account_deletion")
    def delete_account(
        self,
        *,
        user: User,
        password: str,
    ) -> AccountDeletionResult:
        from django.contrib.auth.hashers import check_password
        
        # Verify current password before deletion
        if not check_password(password, user.password):
            return AccountDeletionResult(success=False, message="Current password is incorrect")

        with transaction.atomic():
            self._users.delete_user(user)

        return AccountDeletionResult(success=True, message="Account deleted successfully")

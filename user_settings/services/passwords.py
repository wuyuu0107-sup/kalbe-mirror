"""Password change service adhering to SOLID principles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

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
    """Concrete repository backed by Django's ORM with caching."""

    def __init__(self):
        # Simple in-memory cache to reduce repeated DB queries
        self._cache = {}
        self._cache_max_size = 100  # Prevent unlimited growth
    
    def _get_cache_key(self, user_id: str, username: str) -> str:
        """Generate cache key for user lookup."""
        return f"{user_id}:{username}"
    
    def _clear_cache_if_full(self) -> None:
        """Clear cache if it exceeds max size."""
        if len(self._cache) >= self._cache_max_size:
            # Clear half of the cache (simple LRU approximation)
            keys_to_remove = list(self._cache.keys())[: self._cache_max_size // 2]
            for key in keys_to_remove:
                del self._cache[key]

    def get_by_credentials(self, *, user_id: str, username: str) -> User | None:
        cache_key = self._get_cache_key(user_id, username)
        
        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Query database if not in cache
        try:
            user = User.objects.get(user_id=user_id, username=username)
            # Cache the result
            self._clear_cache_if_full()
            self._cache[cache_key] = user
            return user
        except User.DoesNotExist:
            # Cache negative results too (cache None)
            self._clear_cache_if_full()
            self._cache[cache_key] = None
            return None

    def save_password(self, user: User, encoded_password: str) -> None:
        # Use update() instead of save() for better performance
        # This bypasses model validation and signals but is much faster
        User.objects.filter(pk=user.pk).update(password=encoded_password)
        # Update the in-memory object to stay consistent
        user.password = encoded_password
        # Invalidate cache for this user
        cache_key = self._get_cache_key(user.user_id, user.username)
        if cache_key in self._cache:
            del self._cache[cache_key]

    def delete_user(self, user: User) -> None:
        # Invalidate cache before deletion
        cache_key = self._get_cache_key(user.user_id, user.username)
        if cache_key in self._cache:
            del self._cache[cache_key]
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
        # No need for transaction.atomic() for single update operation
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

        # No need for transaction.atomic() for single delete operation
        self._users.delete_user(user)
        return AccountDeletionResult(success=True, message="Account deleted successfully")

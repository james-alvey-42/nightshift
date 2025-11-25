"""
Authentication and Authorization Module
Handles user identity mapping and access control
"""

from .authenticator import Authenticator, AuthResult
from .user_mapper import UserMapper

__all__ = ['Authenticator', 'AuthResult', 'UserMapper']

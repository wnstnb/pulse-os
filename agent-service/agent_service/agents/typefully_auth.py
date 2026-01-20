"""
Typefully API Authentication Module

Handles secure authentication, API key management, and multi-account support
for Typefully API integration.
"""

import os
import json
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from pathlib import Path

logger = logging.getLogger(__name__)


class TypefullyAuthError(Exception):
    """Custom exception for Typefully authentication errors"""
    pass


class TypefullyAuth:
    """
    Secure authentication system for Typefully API
    
    Features:
    - Secure API key management with encryption
    - Multi-account Twitter/X support
    - Credential validation and health checks
    - Account switching capabilities
    - Rate limiting compliance
    """
    
    BASE_URL = "https://api.typefully.com/v1"
    CREDENTIALS_FILE = ".typefully_credentials.json"
    
    def __init__(self, credentials_dir: Optional[str] = None):
        """
        Initialize Typefully authentication system
        
        Args:
            credentials_dir: Directory to store encrypted credentials (default: project root)
        """
        load_dotenv()
        
        # Set up credentials directory
        self.credentials_dir = Path(credentials_dir) if credentials_dir else Path.cwd()
        self.credentials_path = self.credentials_dir / self.CREDENTIALS_FILE
        
        # Initialize encryption
        self._init_encryption()
        
        # Load API keys and account profiles
        self.api_keys = self._load_api_keys()
        self.account_profiles = self._load_account_profiles()
        self.current_account = self._get_default_account()
        
        logger.info(f"Typefully auth initialized with {len(self.account_profiles)} account(s)")
    
    def _init_encryption(self) -> None:
        """Initialize encryption for secure credential storage"""
        key_file = self.credentials_dir / ".typefully_key"
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                key = f.read()
        else:
            # Generate new encryption key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            # Set secure permissions
            key_file.chmod(0o600)
        
        self.cipher = Fernet(key)
    
    def _load_api_keys(self) -> Dict[str, str]:
        """Load API keys from environment variables"""
        api_keys = {}
        
        # Primary API key
        primary_key = os.getenv("TYPEFULLY_API_KEY")
        if primary_key:
            api_keys["primary"] = primary_key
        
        # Additional account keys (TYPEFULLY_API_KEY_ACCOUNT1, etc.)
        for key, value in os.environ.items():
            if key.startswith("TYPEFULLY_API_KEY_") and key != "TYPEFULLY_API_KEY":
                account_name = key.replace("TYPEFULLY_API_KEY_", "").lower()
                api_keys[account_name] = value
        
        if not api_keys:
            logger.warning("No Typefully API keys found in environment variables")
        
        return api_keys
    
    def _load_account_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Load account profiles from encrypted storage"""
        profiles = {}
        
        if self.credentials_path.exists():
            try:
                with open(self.credentials_path, 'rb') as f:
                    encrypted_data = f.read()
                
                decrypted_data = self.cipher.decrypt(encrypted_data)
                profiles = json.loads(decrypted_data.decode())
                
                logger.info(f"Loaded {len(profiles)} account profiles")
                
            except Exception as e:
                logger.error(f"Failed to load account profiles: {e}")
                profiles = {}
        
        # Create default profiles for available API keys
        for account_name, api_key in self.api_keys.items():
            if account_name not in profiles:
                profiles[account_name] = {
                    "account_id": account_name,
                    "api_key_hint": api_key[-8:],  # Last 8 characters for identification
                    "created_at": datetime.now().isoformat(),
                    "last_validated": None,
                    "is_active": True,
                    "twitter_username": None,
                    "account_metadata": {}
                }
        
        # Save updated profiles
        if profiles:
            self._save_account_profiles(profiles)
        
        return profiles
    
    def _save_account_profiles(self, profiles: Dict[str, Dict[str, Any]]) -> None:
        """Save account profiles to encrypted storage"""
        try:
            data = json.dumps(profiles, indent=2).encode()
            encrypted_data = self.cipher.encrypt(data)
            
            with open(self.credentials_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Set secure permissions
            self.credentials_path.chmod(0o600)
            
            logger.debug("Account profiles saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save account profiles: {e}")
            raise TypefullyAuthError(f"Could not save account profiles: {e}")
    
    def _get_default_account(self) -> Optional[str]:
        """Get the default account to use"""
        if not self.account_profiles:
            return None
        
        # Try primary first
        if "primary" in self.account_profiles:
            return "primary"
        
        # Return first available active account
        for account_id, profile in self.account_profiles.items():
            if profile.get("is_active", True):
                return account_id
        
        return list(self.account_profiles.keys())[0]
    
    def get_auth_headers(self, account_id: Optional[str] = None) -> Dict[str, str]:
        """
        Get authentication headers for Typefully API requests
        
        Args:
            account_id: Specific account to use (default: current account)
            
        Returns:
            Dictionary with authentication headers
            
        Raises:
            TypefullyAuthError: If no valid credentials available
        """
        target_account = account_id or self.current_account
        
        if not target_account or target_account not in self.api_keys:
            raise TypefullyAuthError(f"No API key available for account: {target_account}")
        
        api_key = self.api_keys[target_account]
        
        return {
            "X-API-KEY": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "x-agent-os/1.0"
        }
    
    def validate_credentials(self, account_id: Optional[str] = None) -> bool:
        """
        Validate API credentials by making a test request
        
        Args:
            account_id: Account to validate (default: current account)
            
        Returns:
            True if credentials are valid, False otherwise
        """
        target_account = account_id or self.current_account
        
        if not target_account:
            logger.error("No account specified for validation")
            return False
        
        try:
            headers = self.get_auth_headers(target_account)
            
            # Make a lightweight test request to notifications endpoint
            response = requests.get(
                f"{self.BASE_URL}/notifications/",
                headers=headers,
                timeout=10
            )
            
            is_valid = response.status_code in [200, 201]
            
            # Update validation timestamp
            if is_valid and target_account in self.account_profiles:
                self.account_profiles[target_account]["last_validated"] = datetime.now().isoformat()
                self._save_account_profiles(self.account_profiles)
            
            logger.info(f"Credential validation for {target_account}: {'SUCCESS' if is_valid else 'FAILED'}")
            return is_valid
            
        except requests.RequestException as e:
            logger.error(f"Network error during credential validation: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during credential validation: {e}")
            return False
    
    def switch_account(self, account_id: str) -> bool:
        """
        Switch to a different Twitter/X account
        
        Args:
            account_id: Account identifier to switch to
            
        Returns:
            True if switch successful, False otherwise
        """
        if account_id not in self.account_profiles:
            logger.error(f"Account {account_id} not found in profiles")
            return False
        
        if not self.account_profiles[account_id].get("is_active", True):
            logger.error(f"Account {account_id} is inactive")
            return False
        
        # Validate credentials before switching
        if not self.validate_credentials(account_id):
            logger.error(f"Invalid credentials for account {account_id}")
            return False
        
        self.current_account = account_id
        logger.info(f"Switched to account: {account_id}")
        return True
    
    def list_accounts(self) -> List[Dict[str, Any]]:
        """
        List all available accounts with their status
        
        Returns:
            List of account information dictionaries
        """
        accounts = []
        
        for account_id, profile in self.account_profiles.items():
            account_info = {
                "account_id": account_id,
                "is_current": account_id == self.current_account,
                "is_active": profile.get("is_active", True),
                "twitter_username": profile.get("twitter_username"),
                "last_validated": profile.get("last_validated"),
                "created_at": profile.get("created_at")
            }
            accounts.append(account_info)
        
        return accounts
    
    def add_account(self, account_id: str, api_key: str, twitter_username: Optional[str] = None) -> bool:
        """
        Add a new account with API key
        
        Args:
            account_id: Unique identifier for the account
            api_key: Typefully API key for the account
            twitter_username: Optional Twitter username
            
        Returns:
            True if account added successfully
        """
        # Store API key in memory
        self.api_keys[account_id] = api_key
        
        # Create account profile
        profile = {
            "account_id": account_id,
            "api_key_hint": api_key[-8:],
            "created_at": datetime.now().isoformat(),
            "last_validated": None,
            "is_active": True,
            "twitter_username": twitter_username,
            "account_metadata": {}
        }
        
        # Validate new credentials
        temp_headers = {"X-API-KEY": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            response = requests.get(f"{self.BASE_URL}/notifications/", headers=temp_headers, timeout=10)
            if response.status_code not in [200, 201]:
                logger.error(f"Invalid API key for account {account_id}")
                return False
            
            profile["last_validated"] = datetime.now().isoformat()
            
        except requests.RequestException as e:
            logger.error(f"Failed to validate new account credentials: {e}")
            return False
        
        # Save account profile
        self.account_profiles[account_id] = profile
        self._save_account_profiles(self.account_profiles)
        
        logger.info(f"Successfully added account: {account_id}")
        return True
    
    def remove_account(self, account_id: str) -> bool:
        """
        Remove an account from the system
        
        Args:
            account_id: Account to remove
            
        Returns:
            True if account removed successfully
        """
        if account_id not in self.account_profiles:
            logger.error(f"Account {account_id} not found")
            return False
        
        # Don't allow removing the current account if it's the only one
        if account_id == self.current_account and len(self.account_profiles) == 1:
            logger.error("Cannot remove the only available account")
            return False
        
        # Remove from profiles and API keys
        del self.account_profiles[account_id]
        if account_id in self.api_keys:
            del self.api_keys[account_id]
        
        # Switch to another account if removing current
        if account_id == self.current_account:
            self.current_account = self._get_default_account()
        
        # Save updated profiles
        self._save_account_profiles(self.account_profiles)
        
        logger.info(f"Removed account: {account_id}")
        return True
    
    def get_current_account_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the currently active account
        
        Returns:
            Account information dictionary or None
        """
        if not self.current_account or self.current_account not in self.account_profiles:
            return None
        
        profile = self.account_profiles[self.current_account].copy()
        profile["is_current"] = True
        return profile
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check on authentication system
        
        Returns:
            Health status dictionary
        """
        health_status = {
            "overall_status": "healthy",
            "total_accounts": len(self.account_profiles),
            "active_accounts": 0,
            "current_account": self.current_account,
            "account_statuses": {},
            "last_check": datetime.now().isoformat()
        }
        
        for account_id, profile in self.account_profiles.items():
            is_valid = self.validate_credentials(account_id)
            
            account_status = {
                "is_valid": is_valid,
                "is_active": profile.get("is_active", True),
                "last_validated": profile.get("last_validated"),
                "twitter_username": profile.get("twitter_username")
            }
            
            health_status["account_statuses"][account_id] = account_status
            
            if is_valid and account_status["is_active"]:
                health_status["active_accounts"] += 1
        
        # Determine overall status
        if health_status["active_accounts"] == 0:
            health_status["overall_status"] = "critical"
        elif health_status["active_accounts"] < health_status["total_accounts"]:
            health_status["overall_status"] = "warning"
        
        return health_status 
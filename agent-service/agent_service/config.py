import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional
import json

load_dotenv()

# Existing API Keys
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
RAPIDAPI_API_KEY = os.getenv("RAPIDAPI_API_KEY")

# Typefully API Configuration
TYPEFULLY_API_KEY_TUON = os.getenv("TYPEFULLY_API_KEY_TUON")

# Typefully Configuration Class
class TypefullyConfig:
    """Configuration management for Typefully API integration"""
    
    def __init__(self):
        load_dotenv()
        
        # API Configuration
        self.api_key = os.getenv("TYPEFULLY_API_KEY_TUON")
        self.base_url = "https://api.typefully.com/v1"
        
        # Request Configuration
        self.timeout_seconds = int(os.getenv("TYPEFULLY_TIMEOUT", "30"))
        self.max_retries = int(os.getenv("TYPEFULLY_MAX_RETRIES", "3"))
        self.retry_delay = float(os.getenv("TYPEFULLY_RETRY_DELAY", "1.5"))
        
        # Scheduling Preferences
        self.default_schedule_strategy = os.getenv("TYPEFULLY_SCHEDULE_STRATEGY", "next-free-slot")
        self.schedule_buffer_minutes = int(os.getenv("TYPEFULLY_SCHEDULE_BUFFER", "30"))
        
        # Content Preferences
        self.auto_retweet_enabled = os.getenv("TYPEFULLY_AUTO_RETWEET", "false").lower() == "true"
        self.auto_plug_enabled = os.getenv("TYPEFULLY_AUTO_PLUG", "false").lower() == "true"
        self.default_threadify = os.getenv("TYPEFULLY_DEFAULT_THREADIFY", "true").lower() == "true"
        
        # Rate Limiting
        self.rate_limit_per_minute = int(os.getenv("TYPEFULLY_RATE_LIMIT", "60"))
        self.rate_limit_per_hour = int(os.getenv("TYPEFULLY_RATE_LIMIT_HOUR", "300"))
        
        # Logging and Monitoring
        self.enable_detailed_logging = os.getenv("TYPEFULLY_DETAILED_LOGS", "false").lower() == "true"
        self.log_api_responses = os.getenv("TYPEFULLY_LOG_RESPONSES", "false").lower() == "true"
    
    def get_headers(self, api_key: Optional[str] = None) -> Dict[str, str]:
        """Get standard headers for Typefully API requests"""
        key = api_key or self.api_key
        if not key:
            raise ValueError("No Typefully API key available")
        
        return {
            "X-API-KEY": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "x-agent-os/1.0"
        }
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate current configuration and return status"""
        status = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "config_summary": {}
        }
        
        # Check required configuration
        if not self.api_key:
            status["errors"].append("TYPEFULLY_API_KEY is required")
            status["valid"] = False
        
        # Check rate limits
        if self.rate_limit_per_minute <= 0:
            status["warnings"].append("Rate limit per minute should be positive")
        
        if self.timeout_seconds <= 0:
            status["warnings"].append("Timeout should be positive")
        
        # Configuration summary
        status["config_summary"] = {
            "api_key_present": bool(self.api_key),
            "base_url": self.base_url,
            "timeout": self.timeout_seconds,
            "max_retries": self.max_retries,
            "auto_retweet": self.auto_retweet_enabled,
            "auto_plug": self.auto_plug_enabled,
            "default_threadify": self.default_threadify,
            "rate_limit_per_minute": self.rate_limit_per_minute
        }
        
        return status

# Initialize Typefully configuration
TYPEFULLY_CONFIG = TypefullyConfig()

# Validation warnings
if not PERPLEXITY_API_KEY:
    print("Warning: PERPLEXITY_API_KEY not found in .env file.")

if not GOOGLE_API_KEY:
    print("Warning: GOOGLE_API_KEY not found in .env file.")

if not RAPIDAPI_API_KEY:
    print("Warning: RAPIDAPI_API_KEY not found in .env file.")

if not TYPEFULLY_API_KEY_TUON:
    print("Warning: TYPEFULLY_API_KEY_TUON not found in .env file.")
    print("  → Get your API key from: https://typefully.com/settings/integrations")

# Validate Typefully configuration
typefully_status = TYPEFULLY_CONFIG.validate_config()
if not typefully_status["valid"]:
    for error in typefully_status["errors"]:
        print(f"Error: Typefully config - {error}")

if typefully_status["warnings"]:
    for warning in typefully_status["warnings"]:
        print(f"Warning: Typefully config - {warning}") 
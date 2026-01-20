"""
Typefully Agent

High-level agent interface for Typefully content publishing and management
that integrates with the existing agent architecture.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from .typefully_auth import TypefullyAuth, TypefullyAuthError
from .typefully_client import TypefullyClient, TypefullyAPIError, ValidationError

logger = logging.getLogger(__name__)


@dataclass
class PublishingResult:
    """Result of a publishing operation"""
    success: bool
    draft_id: Optional[str] = None
    share_url: Optional[str] = None
    tweet_url: Optional[str] = None
    error_message: Optional[str] = None
    content_type: str = "unknown"
    scheduled_date: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


@dataclass
class ContentRequest:
    """Request for content publishing"""
    content: str
    content_type: str = "auto"  # auto, single_tweet, thread
    schedule_date: Optional[Union[str, datetime]] = None
    auto_retweet: bool = False
    auto_plug: bool = False
    account_id: Optional[str] = None


class TypefullyAgent:
    """
    High-level Typefully agent for content publishing and management
    
    Features:
    - Content publishing with automatic optimization
    - Batch publishing operations
    - Content monitoring and analytics
    - Integration with existing agent architecture
    - Comprehensive error handling and logging
    """
    
    def __init__(self, account_id: Optional[str] = None):
        """
        Initialize Typefully agent
        
        Args:
            account_id: Specific Typefully account to use
        """
        self.account_id = account_id
        self.auth = None
        self.client = None
        self.initialized = False
        
        # Performance tracking
        self.stats = {
            "total_published": 0,
            "total_scheduled": 0,
            "total_errors": 0,
            "last_activity": None,
            "session_start": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Typefully agent initialized for account: {account_id or 'default'}")
    
    async def initialize(self) -> bool:
        """
        Initialize the agent and test connectivity
        
        Returns:
            True if initialization successful
        """
        try:
            # Initialize authentication
            self.auth = TypefullyAuth()
            
            # Initialize client
            self.client = TypefullyClient(self.auth)
            
            # Test connectivity
            health = self.client.health_check()
            
            if health["api_connectivity"]:
                self.initialized = True
                logger.info("Typefully agent initialized successfully")
                return True
            else:
                logger.error("Failed to connect to Typefully API")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize Typefully agent: {e}")
            return False
    
    def _ensure_initialized(self):
        """Ensure agent is initialized before operations"""
        if not self.initialized:
            raise RuntimeError("Typefully agent not initialized. Call initialize() first.")
    
    async def publish_content(self, request: ContentRequest) -> PublishingResult:
        """
        Publish content using optimized settings
        
        Args:
            request: Content publishing request
            
        Returns:
            Publishing result with details
        """
        self._ensure_initialized()
        
        try:
            # Prepare publishing options
            options = {
                "auto_retweet": request.auto_retweet,
                "auto_plug": request.auto_plug,
                "share": True  # Always generate share URL
            }
            
            if request.schedule_date:
                if isinstance(request.schedule_date, datetime):
                    options["schedule_date"] = request.schedule_date.isoformat()
                else:
                    options["schedule_date"] = request.schedule_date
            
            # Determine content type and publish
            content_length = len(request.content)
            
            if content_length <= 280 or request.content_type == "single_tweet":
                # Single tweet
                result = self.client.create_draft({
                    "content": request.content,
                    **options
                })
                pub_type = "single_tweet"
            else:
                # Thread
                result = self.client.create_thread({
                    "content": request.content,
                    **options
                })
                pub_type = "thread"
            
            # Update stats
            if request.schedule_date:
                self.stats["total_scheduled"] += 1
            else:
                self.stats["total_published"] += 1
            
            self.stats["last_activity"] = datetime.now(timezone.utc).isoformat()
            
            logger.info(f"Successfully published {pub_type}: {result.get('id', 'unknown')}")
            
            return PublishingResult(
                success=True,
                draft_id=result.get("id"),
                share_url=result.get("share_url"),
                tweet_url=result.get("tweet_url"),
                content_type=pub_type,
                scheduled_date=options.get("schedule_date"),
                metrics={"content_length": content_length}
            )
            
        except TypefullyAPIError as e:
            self.stats["total_errors"] += 1
            logger.error(f"Typefully API error: {e}")
            return PublishingResult(
                success=False,
                error_message=f"API error: {e}"
            )
            
        except Exception as e:
            self.stats["total_errors"] += 1
            logger.error(f"Unexpected error publishing content: {e}")
            return PublishingResult(
                success=False,
                error_message=f"Unexpected error: {e}"
            )
    
    async def get_recent_activity(self, limit: int = 10) -> Dict[str, Any]:
        """
        Get recent publishing activity
        
        Args:
            limit: Maximum number of items to return
            
        Returns:
            Recent activity data
        """
        self._ensure_initialized()
        
        try:
            scheduled = self.client.get_recently_scheduled_drafts()
            published = self.client.get_recently_published_drafts()
            
            return {
                "scheduled_drafts": scheduled[:limit],
                "published_drafts": published[:limit],
                "total_scheduled": len(scheduled),
                "total_published": len(published),
                "agent_stats": self.stats
            }
            
        except Exception as e:
            logger.error(f"Error getting recent activity: {e}")
            return {"error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current agent status
        
        Returns:
            Agent status information
        """
        return {
            "initialized": self.initialized,
            "account_id": self.account_id,
            "stats": self.stats,
            "last_check": datetime.now(timezone.utc).isoformat()
        }
    
    async def cleanup(self):
        """Clean up agent resources"""
        if self.client:
            self.client.close()
        
        logger.info("Typefully agent cleaned up")


# Convenience functions for common operations
async def quick_publish(content: str, schedule_date: Optional[Union[str, datetime]] = None, 
                       account_id: Optional[str] = None) -> PublishingResult:
    """
    Quick publish function for simple use cases
    
    Args:
        content: Content to publish
        schedule_date: When to schedule (optional)
        account_id: Account to use (optional)
        
    Returns:
        Publishing result
    """
    agent = TypefullyAgent(account_id)
    
    if not await agent.initialize():
        return PublishingResult(
            success=False,
            error_message="Failed to initialize Typefully agent"
        )
    
    try:
        request = ContentRequest(
            content=content,
            schedule_date=schedule_date
        )
        
        result = await agent.publish_content(request)
        return result
        
    finally:
        await agent.cleanup() 
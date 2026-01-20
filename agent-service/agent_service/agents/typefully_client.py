"""
Typefully API Client

Comprehensive client for Typefully API that handles all HTTP operations,
rate limiting, error handling, and response validation.
"""

import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json

from .typefully_auth import TypefullyAuth, TypefullyAuthError

logger = logging.getLogger(__name__)


class TypefullyAPIError(Exception):
    """Base exception for Typefully API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class RateLimitError(TypefullyAPIError):
    """Raised when rate limit is exceeded"""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class ValidationError(TypefullyAPIError):
    """Raised when request validation fails"""
    pass


class NotificationPayload:
    """Base class for notification payloads"""
    pass


class DraftPublishedPayload(NotificationPayload):
    """Payload for draft published notifications"""
    def __init__(self, data: Dict[str, Any]):
        self.action = data.get("action")
        self.draft_id = data.get("draft_id")
        self.success = data.get("success")
        self.tweet_url = data.get("tweet_url")
        self.linkedin_url = data.get("linkedin_url")
        self.error = data.get("error")
        self.platform = data.get("platform")
        self.first_tweet_text = data.get("first_tweet_text")
        self.num_tweets = data.get("num_tweets")


class TypefullyClient:
    """
    Comprehensive Typefully API client
    
    Features:
    - All Typefully API endpoints
    - Automatic retry logic with exponential backoff
    - Rate limiting compliance
    - Response validation and error handling
    - Connection pooling and session management
    """
    
    def __init__(self, auth: Optional[TypefullyAuth] = None, account_id: Optional[str] = None):
        """
        Initialize Typefully API client
        
        Args:
            auth: TypefullyAuth instance (will create if None)
            account_id: Specific account to use
        """
        self.auth = auth or TypefullyAuth()
        self.account_id = account_id
        
        # Set up session with connection pooling and retries
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
            backoff_factor=1
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 1.0  # 1 second between requests
        
        logger.info(f"Typefully client initialized for account: {self.account_id or 'default'}")
    
    def _wait_for_rate_limit(self) -> None:
        """Implement basic rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                     params: Optional[Dict] = None, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Make an API request with error handling and rate limiting
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., '/drafts/')
            data: Request body data
            params: Query parameters
            account_id: Specific account to use for this request
            
        Returns:
            Response data as dictionary
            
        Raises:
            TypefullyAPIError: For various API errors
            RateLimitError: When rate limited
        """
        # Apply rate limiting
        self._wait_for_rate_limit()
        
        # Build URL
        url = f"{self.auth.BASE_URL}{endpoint}"
        
        # Get authentication headers
        try:
            headers = self.auth.get_auth_headers(account_id or self.account_id)
        except TypefullyAuthError as e:
            raise TypefullyAPIError(f"Authentication failed: {e}")
        
        logger.debug(f"Making {method} request to {endpoint}", extra={
            "method": method,
            "endpoint": endpoint,
            "has_data": bool(data),
            "has_params": bool(params)
        })
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers,
                timeout=30
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limit exceeded, retry after {retry_after} seconds")
                raise RateLimitError(
                    f"Rate limit exceeded. Retry after {retry_after} seconds",
                    retry_after=retry_after
                )
            
            # Handle other HTTP errors
            if not response.ok:
                error_data = None
                try:
                    error_data = response.json()
                except:
                    pass
                
                error_msg = f"HTTP {response.status_code}: {response.reason}"
                if error_data:
                    error_msg += f" - {error_data}"
                
                logger.error(f"API request failed: {error_msg}")
                raise TypefullyAPIError(
                    error_msg,
                    status_code=response.status_code,
                    response_data=error_data
                )
            
            # Parse response
            try:
                result = response.json() if response.content else {}
                logger.debug(f"Request successful: {method} {endpoint}")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse response JSON: {e}")
                raise TypefullyAPIError(f"Invalid JSON response: {e}")
                
        except requests.RequestException as e:
            logger.error(f"Network error during API request: {e}")
            raise TypefullyAPIError(f"Network error: {e}")
    
    # ========================
    # DRAFT MANAGEMENT
    # ========================
    
    def create_draft(self, content: str, threadify: bool = True, share: bool = False,
                    schedule_date: Optional[Union[str, datetime]] = None,
                    auto_retweet_enabled: bool = False, auto_plug_enabled: bool = False,
                    account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a draft
        
        Args:
            content: Tweet content (use 4 consecutive newlines to split tweets)
            threadify: Automatically split content into multiple tweets
            share: If true, returned payload will include a share_url
            schedule_date: ISO formatted date or "next-free-slot"
            auto_retweet_enabled: Enable auto-retweet for this draft
            auto_plug_enabled: Enable auto-plug for this draft
            account_id: Specific account to use
            
        Returns:
            Created draft information
        """
        if not content.strip():
            raise ValidationError("Content cannot be empty")
        
        data = {
            "content": content,
            "threadify": threadify,
            "share": share,
            "auto_retweet_enabled": auto_retweet_enabled,
            "auto_plug_enabled": auto_plug_enabled
        }
        
        # Handle scheduling
        if schedule_date:
            if isinstance(schedule_date, datetime):
                data["schedule-date"] = schedule_date.isoformat()
            else:
                data["schedule-date"] = schedule_date
        
        logger.info(f"Creating draft with {len(content)} characters")
        return self._make_request("POST", "/drafts/", data=data, account_id=account_id)
    
    def get_recently_scheduled_drafts(self, content_filter: Optional[str] = None,
                                    account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recently scheduled drafts
        
        Args:
            content_filter: Filter by "threads" or "tweets"
            account_id: Specific account to use
            
        Returns:
            List of recently scheduled drafts
        """
        params = {}
        if content_filter:
            if content_filter not in ["threads", "tweets"]:
                raise ValidationError("content_filter must be 'threads' or 'tweets'")
            params["content_filter"] = content_filter
        
        logger.info("Fetching recently scheduled drafts")
        result = self._make_request("GET", "/drafts/recently-scheduled/", 
                                  params=params, account_id=account_id)
        return result if isinstance(result, list) else result.get("drafts", [])
    
    def get_recently_published_drafts(self, content_filter: Optional[str] = None,
                                    account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recently published drafts
        
        Args:
            content_filter: Filter by "threads" or "tweets"
            account_id: Specific account to use
            
        Returns:
            List of recently published drafts
        """
        params = {}
        if content_filter:
            if content_filter not in ["threads", "tweets"]:
                raise ValidationError("content_filter must be 'threads' or 'tweets'")
            params["content_filter"] = content_filter
        
        logger.info("Fetching recently published drafts")
        result = self._make_request("GET", "/drafts/recently-published/", 
                                  params=params, account_id=account_id)
        return result if isinstance(result, list) else result.get("drafts", [])
    
    # ========================
    # NOTIFICATIONS
    # ========================
    
    def get_notifications(self, kind: Optional[str] = None,
                         account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get latest notifications
        
        Args:
            kind: Filter by "inbox" or "activity"
            account_id: Specific account to use
            
        Returns:
            Notifications data with accounts and notifications
        """
        params = {}
        if kind:
            if kind not in ["inbox", "activity"]:
                raise ValidationError("kind must be 'inbox' or 'activity'")
            params["kind"] = kind
        
        logger.info(f"Fetching notifications" + (f" (kind: {kind})" if kind else ""))
        return self._make_request("GET", "/notifications/", params=params, account_id=account_id)
    
    def mark_notifications_read(self, kind: Optional[str] = None, username: Optional[str] = None,
                              account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Mark notifications as read
        
        Args:
            kind: Mark only "inbox" or "activity" notifications
            username: Mark notifications only for specific username
            account_id: Specific account to use
            
        Returns:
            Result of mark read operation
        """
        data = {}
        if kind:
            if kind not in ["inbox", "activity"]:
                raise ValidationError("kind must be 'inbox' or 'activity'")
            data["kind"] = kind
        
        if username:
            data["username"] = username
        
        logger.info(f"Marking notifications as read" + 
                   (f" (kind: {kind})" if kind else "") + 
                   (f" (username: {username})" if username else ""))
        
        return self._make_request("POST", "/notifications/mark-all-read/", 
                                data=data, account_id=account_id)
    
    # ========================
    # UTILITY METHODS
    # ========================
    
    def format_thread_content(self, tweets: List[str]) -> str:
        """
        Format a list of tweets into thread content using 4 consecutive newlines
        
        Args:
            tweets: List of individual tweet texts
            
        Returns:
            Formatted thread content
        """
        if not tweets:
            raise ValidationError("Tweet list cannot be empty")
        
        # Join tweets with 4 consecutive newlines
        thread_content = "\n\n\n\n".join(tweet.strip() for tweet in tweets if tweet.strip())
        
        logger.debug(f"Formatted {len(tweets)} tweets into thread content")
        return thread_content
    
    def validate_content_length(self, content: str, max_length: int = 280) -> bool:
        """
        Validate content length for individual tweets
        
        Args:
            content: Tweet content to validate
            max_length: Maximum allowed length (default: 280)
            
        Returns:
            True if valid, False otherwise
        """
        return len(content) <= max_length
    
    def split_long_content(self, content: str, max_length: int = 280) -> List[str]:
        """
        Split long content into multiple tweets
        
        Args:
            content: Long content to split
            max_length: Maximum length per tweet
            
        Returns:
            List of tweet-sized content pieces
        """
        if len(content) <= max_length:
            return [content]
        
        tweets = []
        words = content.split()
        current_tweet = ""
        
        for word in words:
            # Check if adding this word would exceed the limit
            test_tweet = current_tweet + (" " if current_tweet else "") + word
            
            if len(test_tweet) <= max_length:
                current_tweet = test_tweet
            else:
                # Start a new tweet
                if current_tweet:
                    tweets.append(current_tweet)
                current_tweet = word
                
                # Handle words longer than max_length
                if len(current_tweet) > max_length:
                    # Split the word itself
                    while len(current_tweet) > max_length:
                        tweets.append(current_tweet[:max_length])
                        current_tweet = current_tweet[max_length:]
        
        # Add the last tweet
        if current_tweet:
            tweets.append(current_tweet)
        
        logger.debug(f"Split content into {len(tweets)} tweets")
        return tweets
    
    def get_client_info(self) -> Dict[str, Any]:
        """
        Get client information and status
        
        Returns:
            Client information dictionary
        """
        return {
            "auth_account": self.account_id or "default",
            "base_url": self.auth.BASE_URL,
            "last_request_time": self._last_request_time,
            "min_request_interval": self._min_request_interval,
            "available_accounts": [acc["account_id"] for acc in self.auth.list_accounts()]
        }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the client and underlying auth
        
        Returns:
            Health status information
        """
        logger.info("Performing Typefully client health check")
        
        # Get auth health check
        auth_health = self.auth.health_check()
        
        # Test basic connectivity
        api_connectivity = False
        try:
            # Use a lightweight endpoint to test connectivity
            self.get_notifications()
            api_connectivity = True
        except Exception as e:
            logger.warning(f"API connectivity test failed: {e}")
        
        return {
            "client_status": "healthy" if api_connectivity else "degraded",
            "api_connectivity": api_connectivity,
            "auth_health": auth_health,
            "current_account": self.account_id,
            "session_active": bool(self.session),
            "last_check": datetime.now(timezone.utc).isoformat()
        }
    
    def close(self) -> None:
        """Close the client session"""
        if self.session:
            self.session.close()
            logger.info("Typefully client session closed") 
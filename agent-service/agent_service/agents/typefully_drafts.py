"""
Typefully Draft Creation & Management

Handles all draft creation, thread management, content formatting,
and media attachments for Typefully integration.
"""

import re
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum

from .typefully_client import TypefullyClient, ValidationError

logger = logging.getLogger(__name__)


class ContentType(Enum):
    """Content types for draft creation"""
    SINGLE_TWEET = "single_tweet"
    THREAD = "thread"
    LONG_FORM = "long_form"


@dataclass
class TweetMetrics:
    """Metrics for tweet content analysis"""
    character_count: int
    word_count: int
    hashtag_count: int
    mention_count: int
    url_count: int
    estimated_display_chars: int


@dataclass
class ThreadPreview:
    """Preview of a thread before creation"""
    total_tweets: int
    tweets: List[str]
    total_characters: int
    estimated_read_time: str
    content_type: ContentType


class TypefullyDraftManager:
    """
    Comprehensive draft creation and management system
    
    Features:
    - Single tweet and thread creation
    - Automatic and manual content splitting
    - Rich text formatting
    - Content validation and optimization
    - Media attachment support
    - Draft preview and analysis
    """
    
    # Twitter/X content limits
    MAX_TWEET_LENGTH = 280
    MAX_THREAD_LENGTH = 25  # Twitter's thread limit
    MAX_MEDIA_ITEMS = 4     # Max media per tweet
    
    # Character weights for display (some chars take more visual space)
    WEIGHTED_CHARS = {
        'W': 1.5, 'M': 1.5, 'w': 1.2, 'm': 1.2,
        'I': 0.5, 'l': 0.5, 'i': 0.5, 'j': 0.5,
        ' ': 0.3
    }
    
    def __init__(self, client: TypefullyClient):
        """
        Initialize draft manager
        
        Args:
            client: TypefullyClient instance
        """
        self.client = client
        logger.info("Typefully draft manager initialized")
    
    # ========================
    # CONTENT ANALYSIS
    # ========================
    
    def analyze_content(self, content: str) -> TweetMetrics:
        """
        Analyze content and return detailed metrics
        
        Args:
            content: Text content to analyze
            
        Returns:
            TweetMetrics with detailed analysis
        """
        # Basic counts
        char_count = len(content)
        word_count = len(content.split())
        
        # Count social media elements
        hashtag_count = len(re.findall(r'#\w+', content))
        mention_count = len(re.findall(r'@\w+', content))
        url_count = len(re.findall(r'https?://\S+', content))
        
        # Estimate display characters (weighted)
        estimated_display = sum(
            self.WEIGHTED_CHARS.get(char, 1.0) for char in content
        )
        
        return TweetMetrics(
            character_count=char_count,
            word_count=word_count,
            hashtag_count=hashtag_count,
            mention_count=mention_count,
            url_count=url_count,
            estimated_display_chars=int(estimated_display)
        )
    
    def get_content_type(self, content: str) -> ContentType:
        """
        Determine the best content type for given text
        
        Args:
            content: Text content to analyze
            
        Returns:
            Recommended ContentType
        """
        metrics = self.analyze_content(content)
        
        if metrics.character_count <= self.MAX_TWEET_LENGTH:
            return ContentType.SINGLE_TWEET
        elif '\\n\\n\\n\\n' in content or metrics.character_count <= self.MAX_TWEET_LENGTH * 5:
            return ContentType.THREAD
        else:
            return ContentType.LONG_FORM
    
    # ========================
    # CONTENT FORMATTING
    # ========================
    
    def format_rich_text(self, content: str) -> str:
        """
        Apply rich text formatting for Twitter/X compatibility
        
        Args:
            content: Content to format
            
        Returns:
            Formatted content with Unicode styling
        """
        formatted = content
        
        # Bold: **text** or *text*
        formatted = re.sub(r'\\*\\*(.+?)\\*\\*', r'𝗯𝗼𝗹𝗱', formatted)
        formatted = re.sub(r'\\*(.+?)\\*', r'𝘪𝘵𝘢𝘭𝘪𝘤', formatted)
        
        # Italic: _text_
        formatted = re.sub(r'_(.+?)_', r'𝘪𝘵𝘢𝘭𝘪𝘤', formatted)
        
        # Code: `text`
        formatted = re.sub(r'`(.+?)`', r'𝚌𝚘𝚍𝚎', formatted)
        
        # Clean up any remaining markdown
        formatted = re.sub(r'[*_`]', '', formatted)
        
        return formatted
    
    def optimize_hashtags(self, content: str, max_hashtags: int = 3) -> str:
        """
        Optimize hashtag usage for better engagement
        
        Args:
            content: Content with hashtags
            max_hashtags: Maximum number of hashtags to keep
            
        Returns:
            Content with optimized hashtags
        """
        # Extract hashtags
        hashtags = re.findall(r'#\\w+', content)
        
        if len(hashtags) <= max_hashtags:
            return content
        
        # Keep the most relevant hashtags (first ones)
        relevant_hashtags = hashtags[:max_hashtags]
        
        # Remove excess hashtags
        optimized = content
        for hashtag in hashtags[max_hashtags:]:
            optimized = optimized.replace(hashtag, '')
        
        # Clean up extra spaces
        optimized = re.sub(r'\\s+', ' ', optimized).strip()
        
        logger.info(f"Optimized hashtags: kept {len(relevant_hashtags)} out of {len(hashtags)}")
        return optimized
    
    # ========================
    # CONTENT SPLITTING
    # ========================
    
    def split_content_smart(self, content: str, max_length: int = None) -> List[str]:
        """
        Intelligently split content into tweets
        
        Args:
            content: Content to split
            max_length: Maximum length per tweet (default: MAX_TWEET_LENGTH)
            
        Returns:
            List of tweet-sized content pieces
        """
        max_length = max_length or self.MAX_TWEET_LENGTH
        
        if len(content) <= max_length:
            return [content]
        
        # Try to split by sentences first
        sentences = re.split(r'(?<=[.!?])\\s+', content)
        tweets = []
        current_tweet = ""
        
        for sentence in sentences:
            test_tweet = current_tweet + (" " if current_tweet else "") + sentence
            
            if len(test_tweet) <= max_length:
                current_tweet = test_tweet
            else:
                if current_tweet:
                    tweets.append(current_tweet.strip())
                
                # If sentence is too long, split by words
                if len(sentence) > max_length:
                    word_tweets = self._split_by_words(sentence, max_length)
                    tweets.extend(word_tweets[:-1])
                    current_tweet = word_tweets[-1] if word_tweets else ""
                else:
                    current_tweet = sentence
        
        if current_tweet:
            tweets.append(current_tweet.strip())
        
        # Add numbering for threads
        if len(tweets) > 1:
            numbered_tweets = []
            for i, tweet in enumerate(tweets, 1):
                if i == 1:
                    numbered_tweets.append(f"{tweet} 🧵")
                else:
                    numbered_tweets.append(f"{i}/{len(tweets)} {tweet}")
            return numbered_tweets
        
        return tweets
    
    def _split_by_words(self, text: str, max_length: int) -> List[str]:
        """Split text by words when sentences are too long"""
        words = text.split()
        tweets = []
        current_tweet = ""
        
        for word in words:
            test_tweet = current_tweet + (" " if current_tweet else "") + word
            
            if len(test_tweet) <= max_length:
                current_tweet = test_tweet
            else:
                if current_tweet:
                    tweets.append(current_tweet)
                current_tweet = word
                
                # Handle extremely long words
                if len(current_tweet) > max_length:
                    while len(current_tweet) > max_length:
                        tweets.append(current_tweet[:max_length])
                        current_tweet = current_tweet[max_length:]
        
        if current_tweet:
            tweets.append(current_tweet)
        
        return tweets
    
    def preview_thread(self, content: str, auto_split: bool = True) -> ThreadPreview:
        """
        Generate a preview of how content will be split into a thread
        
        Args:
            content: Content to preview
            auto_split: Whether to use automatic splitting
            
        Returns:
            ThreadPreview with detailed breakdown
        """
        if auto_split:
            tweets = self.split_content_smart(content)
        else:
            # Manual split by 4 consecutive newlines
            tweets = [tweet.strip() for tweet in re.split(r'\\n{4,}', content) if tweet.strip()]
        
        total_chars = sum(len(tweet) for tweet in tweets)
        content_type = self.get_content_type(content)
        
        # Estimate read time (average 200 words per minute)
        word_count = sum(len(tweet.split()) for tweet in tweets)
        read_time_minutes = word_count / 200
        
        if read_time_minutes < 1:
            read_time = f"{int(read_time_minutes * 60)} seconds"
        else:
            read_time = f"{read_time_minutes:.1f} minutes"
        
        return ThreadPreview(
            total_tweets=len(tweets),
            tweets=tweets,
            total_characters=total_chars,
            estimated_read_time=read_time,
            content_type=content_type
        )
    
    # ========================
    # DRAFT CREATION
    # ========================
    
    def create_single_draft(self, content: str, schedule_date: Optional[Union[str, datetime]] = None,
                          auto_retweet: bool = False, auto_plug: bool = False,
                          share: bool = False, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a single tweet draft
        
        Args:
            content: Tweet content
            schedule_date: When to schedule (ISO date or "next-free-slot")
            auto_retweet: Enable auto-retweet
            auto_plug: Enable auto-plug
            share: Generate share URL
            account_id: Specific account to use
            
        Returns:
            Created draft information
        """
        # Validate content length
        metrics = self.analyze_content(content)
        if metrics.character_count > self.MAX_TWEET_LENGTH:
            raise ValidationError(f"Content exceeds {self.MAX_TWEET_LENGTH} characters. "
                                f"Consider using create_thread() instead.")
        
        # Optimize content
        optimized_content = self.optimize_hashtags(content)
        formatted_content = self.format_rich_text(optimized_content)
        
        logger.info(f"Creating single draft: {metrics.character_count} characters")
        
        return self.client.create_draft(
            content=formatted_content,
            threadify=False,
            share=share,
            schedule_date=schedule_date,
            auto_retweet_enabled=auto_retweet,
            auto_plug_enabled=auto_plug,
            account_id=account_id
        )
    
    def create_thread(self, content: str, manual_split: bool = False,
                     schedule_date: Optional[Union[str, datetime]] = None,
                     auto_retweet: bool = False, auto_plug: bool = False,
                     share: bool = False, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a thread from content
        
        Args:
            content: Thread content
            manual_split: Use manual splitting (4 newlines) vs automatic
            schedule_date: When to schedule
            auto_retweet: Enable auto-retweet
            auto_plug: Enable auto-plug
            share: Generate share URL
            account_id: Specific account to use
            
        Returns:
            Created thread information
        """
        if manual_split:
            # Split by 4 consecutive newlines (Typefully format)
            tweets = [tweet.strip() for tweet in re.split(r'\\n{4,}', content) if tweet.strip()]
            
            # Validate each tweet
            for i, tweet in enumerate(tweets):
                if len(tweet) > self.MAX_TWEET_LENGTH:
                    raise ValidationError(f"Tweet {i+1} exceeds {self.MAX_TWEET_LENGTH} characters")
            
            # Rejoin with Typefully format
            thread_content = "\\n\\n\\n\\n".join(tweets)
        else:
            # Use automatic splitting
            tweets = self.split_content_smart(content)
            
            if len(tweets) > self.MAX_THREAD_LENGTH:
                raise ValidationError(f"Thread too long: {len(tweets)} tweets "
                                    f"(max: {self.MAX_THREAD_LENGTH})")
            
            thread_content = "\\n\\n\\n\\n".join(tweets)
        
        logger.info(f"Creating thread with {len(tweets)} tweets")
        
        return self.client.create_draft(
            content=thread_content,
            threadify=False,  # We've already formatted it
            share=share,
            schedule_date=schedule_date,
            auto_retweet_enabled=auto_retweet,
            auto_plug_enabled=auto_plug,
            account_id=account_id
        )
    
    def create_from_generated_content(self, posts: List[str], 
                                    content_type: ContentType = ContentType.SINGLE_TWEET,
                                    schedule_interval_minutes: int = 60,
                                    **kwargs) -> List[Dict[str, Any]]:
        """
        Create multiple drafts from generated content
        
        Args:
            posts: List of post content
            content_type: Type of content to create
            schedule_interval_minutes: Minutes between scheduled posts
            **kwargs: Additional options for draft creation
            
        Returns:
            List of created draft information
        """
        results = []
        base_time = datetime.now(timezone.utc)
        
        for i, post_content in enumerate(posts):
            try:
                # Calculate schedule time
                schedule_time = base_time.replace(minute=0, second=0, microsecond=0)
                schedule_time = schedule_time.replace(hour=schedule_time.hour + (i * schedule_interval_minutes // 60))
                schedule_time = schedule_time.replace(minute=(i * schedule_interval_minutes) % 60)
                
                if content_type == ContentType.SINGLE_TWEET:
                    result = self.create_single_draft(
                        content=post_content,
                        schedule_date=schedule_time.isoformat(),
                        **kwargs
                    )
                elif content_type == ContentType.THREAD:
                    result = self.create_thread(
                        content=post_content,
                        schedule_date=schedule_time.isoformat(),
                        **kwargs
                    )
                else:
                    # For long form, create as thread with auto-split
                    result = self.create_thread(
                        content=post_content,
                        manual_split=False,
                        schedule_date=schedule_time.isoformat(),
                        **kwargs
                    )
                
                results.append(result)
                logger.info(f"Created draft {i+1}/{len(posts)}")
                
            except Exception as e:
                logger.error(f"Failed to create draft {i+1}: {e}")
                results.append({"error": str(e), "content": post_content})
        
        return results
    
    # ========================
    # UTILITY METHODS
    # ========================
    
    def validate_draft_content(self, content: str, content_type: ContentType = None) -> Dict[str, Any]:
        """
        Validate content for draft creation
        
        Args:
            content: Content to validate
            content_type: Expected content type
            
        Returns:
            Validation results with recommendations
        """
        metrics = self.analyze_content(content)
        detected_type = self.get_content_type(content)
        
        validation = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": [],
            "metrics": metrics,
            "detected_type": detected_type.value
        }
        
        # Check content length
        if metrics.character_count == 0:
            validation["errors"].append("Content cannot be empty")
            validation["valid"] = False
        
        if metrics.character_count > self.MAX_TWEET_LENGTH and detected_type == ContentType.SINGLE_TWEET:
            validation["warnings"].append(f"Content exceeds single tweet limit ({self.MAX_TWEET_LENGTH} chars)")
            validation["recommendations"].append("Consider creating a thread instead")
        
        # Check hashtag usage
        if metrics.hashtag_count > 3:
            validation["warnings"].append(f"Many hashtags detected ({metrics.hashtag_count})")
            validation["recommendations"].append("Consider reducing hashtags for better engagement")
        
        # Check for potential issues
        if metrics.url_count > 2:
            validation["warnings"].append("Multiple URLs detected")
            validation["recommendations"].append("Consider shortening URLs or splitting content")
        
        # Type mismatch warning
        if content_type and content_type != detected_type:
            validation["warnings"].append(f"Content better suited for {detected_type.value}")
        
        return validation
    
    def get_draft_stats(self) -> Dict[str, Any]:
        """
        Get statistics about recent draft creation
        
        Returns:
            Draft creation statistics
        """
        try:
            recent_scheduled = self.client.get_recently_scheduled_drafts()
            recent_published = self.client.get_recently_published_drafts()
            
            return {
                "recently_scheduled": len(recent_scheduled),
                "recently_published": len(recent_published),
                "total_recent": len(recent_scheduled) + len(recent_published),
                "last_activity": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get draft stats: {e}")
            return {"error": str(e)} 
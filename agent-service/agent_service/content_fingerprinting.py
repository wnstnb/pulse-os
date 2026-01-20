import hashlib
import json
import re
from typing import Dict, Any, Optional
from datetime import datetime

class ContentFingerprinter:
    """Utility class for creating content fingerprints for deduplication."""
    
    @staticmethod
    def create_search_result_fingerprint(search_result: Dict, raw_response: str = "") -> Dict[str, Any]:
        """Create fingerprint for search results from Perplexity API."""
        url = search_result.get("url", "")
        snippet = search_result.get("snippet", "")
        
        # Generate content hash
        content_hash = hashlib.sha256(snippet.encode('utf-8')).hexdigest()
        
        # Create platform metadata
        platform_metadata = {
            "snippet": snippet,
            "raw_response_hash": hashlib.sha256(raw_response.encode('utf-8')).hexdigest() if raw_response else None,
            "fingerprint_created": datetime.now().isoformat()
        }
        
        return {
            "content_type": "search_result",
            "primary_identifier": url,
            "url": url,
            "content_hash": content_hash,
            "platform": "perplexity",
            "platform_metadata": platform_metadata
        }
    
    @staticmethod
    def create_twitter_fingerprint(tweet_result: Dict, raw_response: str = "") -> Dict[str, Any]:
        """Create fingerprint for Twitter results from RapidAPI."""
        url = tweet_result.get("url", "")
        snippet = tweet_result.get("snippet", "")
        
        # Extract tweet ID from URL
        tweet_id = ContentFingerprinter._extract_tweet_id_from_url(url)
        
        # Generate content hash from tweet text
        content_hash = hashlib.sha256(snippet.encode('utf-8')).hexdigest()
        
        # Create platform metadata with engagement data
        platform_metadata = {
            "snippet": snippet,
            "screen_name": tweet_result.get("screen_name", ""),
            "followers_count": tweet_result.get("followers_count", 0),
            "favorite_count": tweet_result.get("favorite_count", 0),
            "retweet_count": tweet_result.get("retweet_count", 0),
            "reply_count": tweet_result.get("reply_count", 0),
            "quote_count": tweet_result.get("quote_count", 0),
            "created_at": tweet_result.get("created_at", ""),
            "raw_response_hash": hashlib.sha256(raw_response.encode('utf-8')).hexdigest() if raw_response else None,
            "fingerprint_created": datetime.now().isoformat()
        }
        
        return {
            "content_type": "tweet",
            "primary_identifier": tweet_id,
            "url": url,
            "content_hash": content_hash,
            "platform": "twitter",
            "platform_metadata": platform_metadata
        }
    
    @staticmethod
    def _extract_tweet_id_from_url(url: str) -> str:
        """Extract tweet ID from Twitter URL."""
        # Pattern: https://twitter.com/username/status/1234567890
        match = re.search(r'/status/(\d+)', url)
        return match.group(1) if match else url  # Fallback to URL if no match
    
    @staticmethod
    def is_content_duplicate(fingerprint1: Dict, fingerprint2: Dict) -> bool:
        """Check if two content fingerprints represent duplicate content."""
        # Same content type and primary identifier = duplicate
        if (fingerprint1.get("content_type") == fingerprint2.get("content_type") and
            fingerprint1.get("primary_identifier") == fingerprint2.get("primary_identifier")):
            return True
        
        # Same content hash = duplicate (even across types)
        if fingerprint1.get("content_hash") == fingerprint2.get("content_hash"):
            return True
            
        return False


class IncrementalProcessingManager:
    """Manages incremental processing workflow."""
    
    def __init__(self, db_handler):
        self.db = db_handler
        self.fingerprinter = ContentFingerprinter()
    
    def process_search_results_incrementally(self, search_results: list, raw_response: str = "") -> Dict[str, Any]:
        """Process search results and return only new ones."""
        new_results = []
        duplicate_count = 0
        new_fingerprints = []
        
        for result in search_results:
            # Create fingerprint
            fingerprint = self.fingerprinter.create_search_result_fingerprint(result, raw_response)
            
            # Check if we've seen this content before
            existing = self.db.check_content_fingerprint(
                fingerprint["content_type"], 
                fingerprint["primary_identifier"]
            )
            
            if not existing:
                # Save new fingerprint
                fingerprint_id = self.db.save_content_fingerprint(**fingerprint)
                new_results.append(result)
                new_fingerprints.append(fingerprint_id)
                print(f"✅ NEW search result: {result.get('url', 'N/A')[:60]}...")
            else:
                duplicate_count += 1
                print(f"⏭️  DUPLICATE search result: {result.get('url', 'N/A')[:60]}...")
        
        return {
            "new_results": new_results,
            "duplicate_count": duplicate_count,
            "new_fingerprint_ids": new_fingerprints,
            "total_processed": len(search_results)
        }
    
    def process_twitter_results_incrementally(self, twitter_results: list, raw_response: str = "") -> Dict[str, Any]:
        """Process Twitter results and return only new ones."""
        new_results = []
        duplicate_count = 0
        new_fingerprints = []
        
        for result in twitter_results:
            # Create fingerprint
            fingerprint = self.fingerprinter.create_twitter_fingerprint(result, raw_response)
            
            # Check if we've seen this tweet before
            existing = self.db.check_content_fingerprint(
                fingerprint["content_type"], 
                fingerprint["primary_identifier"]
            )
            
            if not existing:
                # Save new fingerprint
                fingerprint_id = self.db.save_content_fingerprint(**fingerprint)
                new_results.append(result)
                new_fingerprints.append(fingerprint_id)
                print(f"✅ NEW tweet: @{result.get('screen_name', 'unknown')} - {result.get('snippet', '')[:40]}...")
            else:
                duplicate_count += 1
                print(f"⏭️  DUPLICATE tweet: @{result.get('screen_name', 'unknown')} - {result.get('snippet', '')[:40]}...")
        
        return {
            "new_results": new_results,
            "duplicate_count": duplicate_count,
            "new_fingerprint_ids": new_fingerprints,
            "total_processed": len(twitter_results)
        }
    
    def mark_content_as_processed(self, fingerprint_ids: list):
        """Mark content as processed after successful content generation."""
        for fingerprint_id in fingerprint_ids:
            self.db.update_fingerprint_status(fingerprint_id, "processed") 
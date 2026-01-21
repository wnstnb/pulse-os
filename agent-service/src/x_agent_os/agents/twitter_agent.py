import http.client
import json
import os
import urllib.parse # For URL encoding the query
from typing import Optional
from x_agent_os.config import RAPIDAPI_API_KEY
from x_agent_os.database import DatabaseHandler
from x_agent_os.content_fingerprinting import IncrementalProcessingManager

class TwitterAgent:
    def __init__(self):
        if not RAPIDAPI_API_KEY:
            raise ValueError("RAPIDAPI_API_KEY not configured.")
        self.api_key = RAPIDAPI_API_KEY
        self.db = DatabaseHandler()
        self.conn = http.client.HTTPSConnection("twitter241.p.rapidapi.com")
        print("TwitterAgent initialized with RapidAPI client.")

    def search_tweets(self, query: str, count: int = 20, search_type: str = "Top", session_id: Optional[int] = None) -> list:
        """Queries RapidAPI Twitter V2 to find tweets based on the query."""
        print(f"Searching for tweets matching query: '{query}' using RapidAPI (count: {count}, type: {search_type})")

        # Check database cache first
        if session_id and self.db.has_twitter_results(session_id):
            cached_results = self.db.get_twitter_results(session_id)
            print(f"💾 CACHE HIT: Loaded {len(cached_results)} tweet results from database for session {session_id}")
            print(f"   🚀 Skipping API call - using cached data")
            # Convert database results to expected format
            return [dict(result) for result in cached_results]
        
        if session_id:
            print(f"💿 CACHE MISS: No cached twitter results found for session {session_id}")
            print(f"   🌐 Making API call to RapidAPI...")
        else:
            print(f"❌ NO SESSION ID: Cannot use caching, making API call to RapidAPI...")

        headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': "twitter241.p.rapidapi.com"
        }
        
        # URL encode the query parameter
        encoded_query = urllib.parse.quote(query)
        endpoint = f"/search-v2?type={search_type}&count={count}&query={encoded_query}"

        try:
            self.conn.request("GET", endpoint, headers=headers)
            res = self.conn.getresponse()
            data = res.read()
            raw_response_text = data.decode("utf-8")

            # Prepare raw API response for database storage
            try:
                raw_api_response = json.dumps(json.loads(raw_response_text), indent=2)
            except json.JSONDecodeError:
                raw_api_response = raw_response_text
            
            # Store for incremental processing
            self._last_raw_response = raw_api_response

            if res.status != 200:
                print(f"Error from RapidAPI: {res.status} - {raw_response_text}")
                return []

            response_json = json.loads(raw_response_text)
            
            # Extract relevant data: tweet URL and text content as snippet
            # Based on sample_rapidapi_response.json, tweets are in response_json['data']['search_by_raw_query']['search_timeline']['timeline']['instructions'][0]['entries']
            # Each entry that is a tweet has an itemContent of type "tweet"
            # The tweet URL can be constructed: https://twitter.com/{user_screen_name}/status/{tweet_id}
            # The tweet text is in legacy.full_text
            
            tweet_results_data = []
            
            # Navigating the complex structure of the sample response
            raw_entries_or_items = [] # Will store items from either 'entries' or 'moduleItems'

            if response_json and \
                response_json.get('result','{}').get('timeline', {}).get('instructions'):
                
                for instruction in response_json['result']['timeline']['instructions']:
                    instruction_type = instruction.get('type')
                    if instruction_type == 'TimelineAddEntries':
                        raw_entries_or_items.extend(instruction.get('entries', []))
                    elif instruction_type == 'TimelineModule': # Check for TimelineModule
                        for module_item_container in instruction.get('items', []): # items in TimelineModule
                            # The actual tweet item is nested deeper
                            item = module_item_container.get('item')
                            if item and item.get('itemContent'):
                                raw_entries_or_items.append(item) # Add the item itself which contains itemContent
            
            # Fallback for globalObjects structure if the primary path yields nothing
            if not raw_entries_or_items and response_json.get('globalObjects', {}).get('tweets'):
                print("Processing tweets from 'globalObjects.tweets' structure.")
                for tweet_id, tweet_data in response_json['globalObjects']['tweets'].items():
                    user_id_str = tweet_data.get('user_id_str')
                    user_info = response_json.get('globalObjects', {}).get('users', {}).get(user_id_str, {})
                    
                    screen_name = user_info.get('screen_name', 'unknown_user')
                    followers_count = user_info.get('followers_count', 0)
                    text = tweet_data.get('full_text', tweet_data.get('text', 'No text available'))
                    url = f"https://twitter.com/{screen_name}/status/{tweet_id}"
                    
                    tweet_results_data.append({
                        "url": url,
                        "snippet": text,
                        "screen_name": screen_name,
                        "followers_count": followers_count,
                        "created_at": tweet_data.get('created_at', 'N/A'),
                        "favorite_count": tweet_data.get('favorite_count', 0),
                        "quote_count": tweet_data.get('quote_count', 0),
                        "reply_count": tweet_data.get('reply_count', 0),
                        "retweet_count": tweet_data.get('retweet_count', 0)
                    })
                if tweet_results_data:
                        print(f"Processed {len(tweet_results_data)} tweets from 'globalObjects'.")
            
            # Process the collected entries or items
            for item_like_entry in raw_entries_or_items:
                tweet_result = None
                item_content = item_like_entry.get('itemContent') # Used by TimelineModule items
                content = item_like_entry.get('content') # Used by TimelineAddEntries entries

                if item_content and item_content.get('tweet_results', {}).get('result'):
                    tweet_result = item_content['tweet_results']['result']
                elif content: # Fallback to original logic for TimelineAddEntries structure
                    if content.get('itemContent', {}).get('tweet_results', {}).get('result'):
                        tweet_result = content['itemContent']['tweet_results']['result']
                    elif content.get('tweet_results', {}).get('result'):
                        tweet_result = content['tweet_results']['result']
                    elif content.get('tweet', {}).get('tweet_results', {}).get('result'):
                        tweet_result = content['tweet']['tweet_results']['result']

                if tweet_result and tweet_result.get('__typename') == 'Tweet':
                    legacy_tweet_data = tweet_result.get('legacy', {})
                    
                    # Get user data - UPDATED for new API structure
                    core_user_data = {}
                    screen_name = 'unknown_user'
                    
                    # Try new API structure first (screen_name moved to core)
                    if tweet_result.get('core', {}).get('user_results', {}).get('result', {}).get('core'):
                        user_core = tweet_result['core']['user_results']['result']['core']
                        screen_name = user_core.get('screen_name', 'unknown_user')
                        # Get legacy data for followers count, etc.
                        user_legacy = tweet_result['core']['user_results']['result'].get('legacy', {})
                        core_user_data = user_legacy
                    
                    # Fallback to old structure
                    elif tweet_result.get('core', {}).get('user_results', {}).get('result', {}).get('legacy'):
                        core_user_data = tweet_result['core']['user_results']['result']['legacy']
                        screen_name = core_user_data.get('screen_name', 'unknown_user')
                    elif tweet_result.get('user', {}).get('result', {}).get('legacy'): # For some tweet types like community tweet
                        core_user_data = tweet_result['user']['result']['legacy']
                        screen_name = core_user_data.get('screen_name', 'unknown_user')
                    
                    tweet_id = legacy_tweet_data.get('id_str')
                    full_text = legacy_tweet_data.get('full_text', 'No text available')
                    
                    if tweet_id and screen_name != 'unknown_user':
                        url = f"https://twitter.com/{screen_name}/status/{tweet_id}"
                        
                        tweet_item = {
                            "url": url,
                            "snippet": full_text,
                            "screen_name": screen_name,
                            "followers_count": core_user_data.get('followers_count', 0),
                            "created_at": legacy_tweet_data.get('created_at', 'N/A'),
                            "favorite_count": legacy_tweet_data.get('favorite_count', 0),
                            "quote_count": legacy_tweet_data.get('quote_count', 0),
                            "reply_count": legacy_tweet_data.get('reply_count', 0),
                            "retweet_count": legacy_tweet_data.get('retweet_count', 0)
                        }
                        tweet_results_data.append(tweet_item)
            
            if not tweet_results_data:
                # Keep the warning if, after all attempts, no data is extracted
                # This also covers the case where globalObjects was processed but yielded no data.
                if not ('globalObjects' in response_json and 'tweets' in response_json['globalObjects'] and tweet_results_data): # only show warning if not already processed globalObjects
                    print(f"Warning: No tweets extracted from primary paths or globalObjects. Response structure might have changed or contained no tweets. Raw response snippet: {raw_response_text[:500]}")

            # Save to database if we have data and a session_id
            if tweet_results_data and session_id:
                try:
                    self.db.save_twitter_results(session_id, tweet_results_data, raw_api_response)
                    print(f"Saved {len(tweet_results_data)} tweet results to database for session {session_id}")
                except Exception as e:
                    print(f"Error saving tweet results to database: {e}")
            
            return tweet_results_data

        except http.client.HTTPException as e:
            print(f"HTTP client error connecting to RapidAPI: {e}")
            import traceback
            traceback.print_exc()
            return []
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response from RapidAPI: {e}. Response text: {raw_response_text[:500]}")
            import traceback
            traceback.print_exc()
            return []
        except Exception as e:
            print(f"An unexpected error occurred in TwitterAgent: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            # It's good practice to close the connection, 
            # but HTTPSConnection can be reused for multiple requests to the same host.
            # If you were done with this host, you'd close it: self.conn.close()
            # For now, assume it might be reused if multiple searches are done with one agent instance.
            pass 

    def search_user_tweets(self, username: str, count: int = 20, search_type: str = "Latest") -> list:
        """Fetch recent tweets from a specific username using search."""
        handle = username.lstrip("@")
        query = f"from:{handle}"
        return self.search_tweets(query, count=count, search_type=search_type, session_id=None)
    
    def search_tweets_incremental(self, query: str, count: int = 20, search_type: str = "Top", session_id: Optional[int] = None) -> dict:
        """
        Search for tweets and return only NEW ones not seen before.
        This is the main method for incremental content generation.
        """
        print(f"🔄 INCREMENTAL Twitter search for query: '{query}'")
        
        # Get all tweet results (both new and existing)
        all_results = self.search_tweets(query, count, search_type, session_id)
        
        if not all_results:
            print("❌ No tweets returned from API")
            return {
                "new_results": [],
                "duplicate_count": 0,
                "total_processed": 0,
                "fingerprint_ids": []
            }
        
        # Process incrementally using fingerprinting
        processor = IncrementalProcessingManager(self.db)
        
        # Get the raw response for fingerprinting
        raw_response = getattr(self, '_last_raw_response', "")
        
        result = processor.process_twitter_results_incrementally(all_results, raw_response)
        
        print(f"📊 Twitter processing summary:")
        print(f"   Total tweets: {result['total_processed']}")
        print(f"   New tweets: {len(result['new_results'])}")
        print(f"   Duplicates skipped: {result['duplicate_count']}")
        
        return result 
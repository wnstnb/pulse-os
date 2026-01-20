from agent_service.config import PERPLEXITY_API_KEY
from openai import OpenAI # Import OpenAI
import json # For parsing if sources are in a JSON string
import os
from typing import Optional
from agent_service.database import DatabaseHandler
from agent_service.content_fingerprinting import IncrementalProcessingManager

class SearchAgent:
    def __init__(self):
        if not PERPLEXITY_API_KEY:
            raise ValueError("PERPLEXITY_API_KEY not configured.")
        self.api_key = PERPLEXITY_API_KEY
        self.db = DatabaseHandler()
        try:
            self.client = OpenAI(api_key=self.api_key, base_url="https://api.perplexity.ai")
            print("SearchAgent initialized with Perplexity API client.")
        except Exception as e:
            print(f"Error initializing Perplexity API client: {e}")
            raise

    def search(self, topic: str, session_id: Optional[int] = None) -> list:
        """Queries Perplexity API to find relevant content based on the topic."""
        print(f"Searching for topic: '{topic}' using Perplexity API (model: sonar-pro)")
        
        # Check database cache first
        if session_id and self.db.has_search_results(session_id):
            cached_results = self.db.get_search_results(session_id)
            print(f"💾 CACHE HIT: Loaded {len(cached_results)} search results from database for session {session_id}")
            print(f"   🚀 Skipping API call - using cached data")
            # Convert database results to expected format
            return [{"url": result.get("url"), "snippet": result.get("snippet")} for result in cached_results]
        
        if session_id:
            print(f"💿 CACHE MISS: No cached search results found for session {session_id}")
            print(f"   🌐 Making API call to Perplexity...")
        else:
            print(f"❌ NO SESSION ID: Cannot use caching, making API call to Perplexity...")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that researches topics and provides concise, factual information, including sources and search results. "
                    "Focus on finding recent and relevant articles, blog posts, forum discussions, and social media threads related to the user's query."
                ),
            },
            {
                "role": "user",
                "content": topic,
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model="sonar-pro",
                messages=messages,
            )
            
            # Get the full dictionary representation of the response for raw caching
            full_response_dict = {}
            if hasattr(response, 'model_dump'):
                full_response_dict = response.model_dump()
            else:
                try:
                    full_response_dict = json.loads(response.json()) # For some SDK versions
                except AttributeError: # If .json() doesn't exist
                    try:
                        full_response_dict = vars(response) # General fallback
                    except TypeError: # If vars() is not applicable (e.g. for pydantic models directly)
                        # This might be a scenario where response itself is already dict-like or needs specific handling
                        # For now, we'll try to force it to a string and log a warning if it's not a dict
                        print(f"Warning: Could not easily convert response to dict. Saving string representation for raw cache.")
                        full_response_dict = {"raw_string_representation": str(response)}
                except json.JSONDecodeError:
                    print(f"Warning: response.json() did not return valid JSON. Trying vars() for raw cache.")
                    full_response_dict = vars(response)
            
            # Prepare raw API response for database storage
            raw_api_response = json.dumps(full_response_dict, indent=2)
            
            # Store for incremental processing
            self._last_raw_response = raw_api_response

            search_results_data = []
            
            # Prioritize the structured "search_results" field if available
            if "search_results" in full_response_dict and isinstance(full_response_dict.get("search_results"), list):
                for item in full_response_dict["search_results"]:
                    url = item.get("url")
                    title = item.get("title", "No title provided")
                    # Using title as snippet for now, as per PRD requirement for URL and snippet
                    # Could also use a portion of message.content if more detail per source is needed
                    # and can be mapped, but title is directly associated with the URL here.
                    if url:
                        search_results_data.append({"url": url, "snippet": title})
                if search_results_data:
                    print(f"Processed {len(search_results_data)} items from API's 'search_results' field.")

            # Fallback or augmentation: if no structured search_results, or if we also want the main content
            # For now, the PRD implies distinct URL/snippet pairs, so structured search_results are preferred.
            # If search_results_data is still empty, but we have main content, use that.
            # Adjusting to use full_response_dict for consistency in accessing choices
            choices = full_response_dict.get('choices', [])
            if not search_results_data and choices and isinstance(choices, list) and len(choices) > 0 \
               and isinstance(choices[0], dict) and choices[0].get('message') \
               and isinstance(choices[0]['message'], dict) and choices[0]['message'].get('content'):
                main_content = choices[0]['message']['content'].strip()
                print("Warning: No structured 'search_results' found in API response or it was empty. Using main message content as a single snippet.")
                search_results_data.append({
                    "url": "https://perplexity.ai/summarized_result", # Placeholder for summarized content
                    "snippet": main_content
                })
            elif not choices or not isinstance(choices, list) or len(choices) == 0 \
                 or not isinstance(choices[0], dict) or not choices[0].get('message') \
                 or not isinstance(choices[0]['message'], dict) or not choices[0]['message'].get('content'):
                 print("Perplexity API did not return the expected content structure in choices.")
                 return []

            if not search_results_data:
                print("Warning: Perplexity API call succeeded but no content was processed into search_results_data.")

            # Save to database if we have data and a session_id
            if search_results_data and session_id:
                try:
                    self.db.save_search_results(session_id, search_results_data, raw_api_response)
                    print(f"Saved {len(search_results_data)} search results to database for session {session_id}")
                except Exception as e:
                    print(f"Error saving search results to database: {e}")

            return search_results_data

        except Exception as e:
            print(f"Error calling Perplexity API or processing its response: {e}")
            # Ensure traceback is printed for better debugging of other potential errors
            import traceback
            traceback.print_exc()
            return [] 
    
    def search_incremental(self, topic: str, session_id: Optional[int] = None) -> dict:
        """
        Perform search and return only NEW results not seen before.
        This is the main method for incremental content generation.
        """
        print(f"🔄 INCREMENTAL search for topic: '{topic}'")
        
        # Get all search results (both new and existing)
        all_results = self.search(topic, session_id)
        
        if not all_results:
            print("❌ No search results returned from API")
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
        
        result = processor.process_search_results_incrementally(all_results, raw_response)
        
        print(f"📊 Search processing summary:")
        print(f"   Total results: {result['total_processed']}")
        print(f"   New results: {len(result['new_results'])}")
        print(f"   Duplicates skipped: {result['duplicate_count']}")
        
        return result 
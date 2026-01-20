import google.generativeai as genai
from agent_service.config import GOOGLE_API_KEY
import os
import json
from typing import Optional
from agent_service.database import DatabaseHandler

class ReviewerAgent:
    def __init__(self):
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not configured.")
        genai.configure(api_key=GOOGLE_API_KEY)
        self.db = DatabaseHandler()
        # Initialize Gemini 2.5 Flash model
        # For now, we'll just print, model initialization will be more specific
        print("ReviewerAgent initialized with Gemini 2.5 Flash")
        self.model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20') # Using 1.5 flash as per PRD

    def review_and_distill(self, search_results: list, app_name: str, app_description: str, tuon_features_content: str, session_id: Optional[int] = None) -> dict:
        """
        Processes search results, identifies key pain points, and extracts topics
        relevant to the application being marketed, considering its specific features.
        """
        print(f"Reviewing search results for {app_name}: {app_description}, considering features.")
        
        # Check database cache first
        if session_id and self.db.has_reviewer_output(session_id):
            cached_output = self.db.get_reviewer_output(session_id)
            print(f"💾 CACHE HIT: Loaded reviewer output from database for session {session_id}")
            print(f"   🚀 Skipping API call - using cached data")
            return cached_output
        
        if session_id:
            print(f"💿 CACHE MISS: No cached reviewer output found for session {session_id}")
            print(f"   🌐 Making API call to Gemini...")
        else:
            print(f"❌ NO SESSION ID: Cannot use caching, making API call to Gemini...")
        
        # Constructing a prompt for Gemini
        prompt_parts = [
            "You are an expert content reviewer. Your task is to analyze the following search results:"
        ]
        for i, result in enumerate(search_results):
            prompt_parts.append(f"Result {i+1}: URL: {result['url']}, Snippet: {result['snippet']}")
        
        prompt_parts.extend([
            f"Now, consider the application '{app_name}', which is described as: '{app_description}'.",
            f"Here is a list of {app_name}'s key features:\n{tuon_features_content}\n",
            f"Based on ALL the above information (search results AND app features), identify key themes, pain points, and interesting angles.",
            f"The goal is to distill topics and talking points that are highly relevant for marketing '{app_name}' by highlighting how its specific features address the identified themes/pain points.",
            "Focus on extracting information that can be framed to highlight the benefits of this application by connecting search insights with the app's capabilities.",
            "Output a structured JSON object with two keys: 'distilled_topics' (a list of strings, where each string is a concise topic that connects a pain point/theme with how the app helps) and 'talking_points' (a list of strings, where each string is a more detailed point or angle for marketing). Example format:",
            "{\"distilled_topics\": [\"Topic 1: Search results indicate users struggle with X, and app_name's feature Y directly solves this by doing Z...\", \"Topic 2: An emerging theme is A, which app_name addresses with feature B...\"], \"talking_points\": [\"Focus on how feature Y saves time for users dealing with X...\", \"Emphasize the unique benefit of feature B when discussing theme A...\"]}"
        ])
        
        prompt = "\n".join(prompt_parts)
        print(f"-- Reviewer Agent Prompt to Gemini --\n{prompt[:500]}...\n-- End of Prompt Snippet --")

        # Actual call to Gemini API will go here
        response = self.model.generate_content(prompt)
        
        # Ensure the response is not empty and has text
        if not response.parts:
            print("Error: Received an empty response from Gemini.")
            return {"distilled_topics": [], "talking_points": []}
        
        # Assuming the first part contains the text response
        # Adjust if your model/API returns data differently
        try:
            # Attempt to get text directly if possible, or join parts if it's a multi-part response
            if hasattr(response, 'text'):
                api_response_text = response.text
            else:
                # Handling cases where response.parts might be a list of Part objects
                api_response_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))

            if not api_response_text:
                print("Error: Gemini response content is empty.")
                return {"distilled_topics": [], "talking_points": []}
            
            # Store raw API response for database storage
            raw_api_response = api_response_text

            print(f"-- Reviewer Agent API Response --\\\\\\n{api_response_text[:500]}...\\\\\\\\n-- End of API Response Snippet --")

            # Strip markdown code block if present
            text_to_parse = api_response_text.strip()
            if text_to_parse.startswith("```json"):
                text_to_parse = text_to_parse[7:]
            elif text_to_parse.startswith("```"):
                text_to_parse = text_to_parse[3:]
            
            if text_to_parse.endswith("```"):
                text_to_parse = text_to_parse[:-3]
            
            text_to_parse = text_to_parse.strip() # Clean up any leading/trailing whitespace

            # Find the start of the JSON object
            start_index = text_to_parse.find('{')
            if start_index == -1:
                print("Error: Could not find the start of JSON object in the API response.")
                return {"distilled_topics": [], "talking_points": []}
            
            # Try to find the corresponding end of the JSON object
            # This is a simplified way; a proper parser would be more robust for nested structures
            # but for typical LLM JSON outputs, this might suffice.
            open_braces = 0
            end_index = -1
            for i, char in enumerate(text_to_parse[start_index:]):
                if char == '{':
                    open_braces += 1
                elif char == '}':
                    open_braces -= 1
                    if open_braces == 0:
                        end_index = start_index + i + 1
                        break
            
            if end_index == -1:
                print("Error: Could not find the end of JSON object in the API response.")
                return {"distilled_topics": [], "talking_points": []}

            json_string = text_to_parse[start_index:end_index]

        except Exception as e:
            print(f"Error processing Gemini response: {e}")
            return {"distilled_topics": [], "talking_points": []}

        # Mock response for now
        # mock_response_text = \'\'\'
        # {
        #     "distilled_topics": [
        #         "Topic 1: Users struggle with organizing notes effectively. Tuon.io\'s AI features help categorize and find notes effortlessly.",
        #         "Topic 2: Information overload is a common pain point. Tuon.io can summarize long texts, making information digestible."
        #     ],
        #     "talking_points": [
        #         "Highlight Tuon.io\'s intelligent search.",
        #         "Showcase automated summarization for productivity."
        #     ]
        # }
        # \'\'\'
        # print(f"-- Reviewer Agent Mock Response --\\n{mock_response_text}\\n-- End of Mock Response --")
        
        try:
            # A more robust parsing and validation should be here
            # import json # Already imported at the top
            parsed_json = json.loads(json_string) # Use the extracted json_string
            
            # Save to database if we have a session_id
            if session_id:
                try:
                    self.db.save_reviewer_output(
                        session_id, 
                        parsed_json.get("distilled_topics", []), 
                        parsed_json.get("talking_points", []), 
                        raw_api_response
                    )
                    print(f"Saved reviewer output to database for session {session_id}")
                except Exception as e:
                    print(f"Error saving reviewer output to database: {e}")
            
            return parsed_json
        except json.JSONDecodeError:
            print(f"Error: Failed to parse API response from Reviewer Agent. Content: {json_string[:200]}...")
            return {"distilled_topics": [], "talking_points": []} 
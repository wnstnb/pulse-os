import google.generativeai as genai
from agent_service.config import GOOGLE_API_KEY
import re # Import re module
import os
import json
from typing import Optional
from agent_service.database import DatabaseHandler

class EditorAgent:
    def __init__(self):
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not configured.")
        genai.configure(api_key=GOOGLE_API_KEY)
        self.db = DatabaseHandler()
        # Initialize Gemini 2.5 Pro model
        print("EditorAgent initialized with Gemini 2.5 Pro")
        self.model = genai.GenerativeModel('gemini-2.5-pro-preview-05-06') # Using 1.5 pro as per PRD

    def craft_posts(self, distilled_content: dict, app_name: str, app_description: str, tuon_features_content: str, session_id: Optional[int] = None) -> list:
        """
        Takes curated topics and pain points and crafts engaging LinkedIn posts,
        incorporating app features.
        """
        print(f"Crafting LinkedIn posts for {app_name} based on distilled content and features.")

        # Check database cache first
        if session_id and self.db.has_editor_outputs(session_id):
            cached_posts = self.db.get_editor_outputs(session_id)
            print(f"💾 CACHE HIT: Loaded editor LinkedIn output from database for session {session_id}")
            print(f"   🚀 Skipping API call - using cached data")
            # Convert database results to expected format
            return [dict(post) for post in cached_posts]
        
        if session_id:
            print(f"💿 CACHE MISS: No cached editor outputs found for session {session_id}")
            print(f"   🌐 Making API calls to Gemini...")
        else:
            print(f"❌ NO SESSION ID: Cannot use caching, making API calls to Gemini...")

        social_media_posts = []
        all_raw_api_responses = [] # Renamed from all_raw_mock_generations

        topics = distilled_content.get("distilled_topics", [])
        # talking_points = distilled_content.get("talking_points", []) # Not directly used in this mock, but available

        if not topics:
            print("Warning: No distilled topics provided to Editor Agent.")
            return []

        for i, topic_text in enumerate(topics):
            # Constructing a prompt for Gemini Pro
            prompt_parts = [
                f"You are an expert LinkedIn copywriter for {app_name}. {app_name} is '{app_description}'.",
                f"Here is a list of {app_name}'s key features that you can subtly reference if relevant:\n{tuon_features_content}\n",
                f"Your task is to create an engaging and professional LinkedIn post based on the following topic: '{topic_text}'.",
                "Say the spicy truths out loud. Be bold, honest, and provocative to cut through the noise and make the main thing the main thing. For example:",
                "  * Most productivity tools are just digital clutter. Tuon is built to actually help you create, not just organize your chaos",
                "  * Switching between apps kills your flow. Tuon keeps you in one canvas, so your ideas never get lost in the shuffle.",
                "  * Your old notes are buried and forgotten in other tools. With Tuon, you can tag and resurface any document as context—never start from zero again.",
                "Use storytelling formats such as problem-solution arcs, user mini-journeys, or metaphor-based framing.",
                "Begin by identifying a common frustration or challenge professionals face.",
                f"Illustrate how a feature (or more) of {app_name} naturally resolves or reframes the issue.",
                "Avoid listing features—show their value through action, outcome, or user benefit.",
                "End with an insightful takeaway or reflection relevant to the reader's own workflow or mindset.",
                "Maintain a knowledgeable, helpful, and confident tone. No hashtags.",
                "Posts can be long or short. Hard character limit is 2000 characters.",
                "Output only the LinkedIn post text. Do not include any headings or labels."
            ]
            prompt = "\\n".join(prompt_parts)
            print(f"-- Editor Agent Prompt to Gemini (Topic {i+1}) --\\n{prompt[:500]}...\\n-- End of Prompt Snippet --")

            generated_post_text = "" # Initialize
            try:
                api_response = self.model.generate_content(prompt)
                # Extract text from API response
                if not api_response.parts:
                    print(f"Error: Received an empty API response from EditorAgent for topic {i+1}.")
                    generated_post_text = "#Error: Empty API Response"
                elif hasattr(api_response, 'text'):
                    generated_post_text = api_response.text
                else:
                    generated_post_text = "".join(part.text for part in api_response.parts if hasattr(part, 'text'))
                
                if not generated_post_text:
                    print(f"Error: API response content is empty for EditorAgent for topic {i+1}.")
                    generated_post_text = "#Error: Empty API Response Content"

            except Exception as e:
                print(f"Error calling Gemini API for EditorAgent (Topic {i+1}): {e}")
                generated_post_text = f"#Error: API Call Failed - {e}"

            print(f"-- Editor Agent API Response (Topic {i+1}) --\\n{generated_post_text[:300]}...\\n-- End of API Response Snippet --")
            
            all_raw_api_responses.append(f"--- Raw API Response for LinkedIn Post (Topic {i+1}: {topic_text}) ---\n{generated_post_text}\n")

            # Remove parsing for multiple variations
            # The generated_post_text is now assumed to be the single post
            single_post_content = generated_post_text.strip()
            if generated_post_text.startswith("#Error"):
                single_post_content = generated_post_text.strip() # Keep error message
            elif not single_post_content: # Handle case where API returns empty but not error state
                print(f"Warning: Received empty content (after stripping) for topic {i+1}, but no explicit error. Storing as empty.")
                single_post_content = "" 

            current_posts_data = { 
                "topic": topic_text,
                "linkedin_post": single_post_content # Changed from linkedin_posts list to single string
            }

            # Regex parsing might not be strictly needed if the LLM follows the new prompt structure well,
            # but we can keep a simple extraction for robustness or if the LLM adds minor artifacts.
            # For now, we assume generated_post_text IS the post due to the new prompt.
            # If LLM includes "**LinkedIn Post:**", we might want to strip it, but the prompt asks for direct text.
            
            # Example of a simple strip if the model *still* adds a prefix despite instructions:
            # prefix_to_strip = "**LinkedIn Post:**"
            # if generated_post_text.strip().startswith(prefix_to_strip):
            #    current_posts["linkedin_post"] = generated_post_text.strip()[len(prefix_to_strip):].strip()

            social_media_posts.append(current_posts_data) # Use renamed variable

        # Save to database if we have data and a session_id
        if social_media_posts and session_id:
            try:
                self.db.save_editor_outputs(session_id, social_media_posts, all_raw_api_responses)
                print(f"Saved editor LinkedIn output to database for session {session_id}")
            except Exception as e:
                print(f"Error saving editor LinkedIn output to database: {e}")

        return social_media_posts 
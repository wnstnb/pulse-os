import google.generativeai as genai
from x_agent_os.config import GOOGLE_API_KEY
import re # Import re module
import os
import json
from typing import Optional
from x_agent_os.database import DatabaseHandler

class EditorAgent:
    def __init__(self):
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not configured.")
        genai.configure(api_key=GOOGLE_API_KEY)
        self.db = DatabaseHandler()
        print("EditorAgent initialized with Gemini 3 Pro Preview")
        self.model = genai.GenerativeModel('gemini-3-pro-preview') # Using 1.5 pro as per PRD

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
                "You are a master conversion copywriter, narrative strategist, and voice engineer specializing in ",
                "high-performing LinkedIn content. You distill complex products into emotionally resonant stories that ",
                "shift beliefs, expose uncomfortable truths, and make people reconsider how they work.\n\n",
                f"{app_name} = '{app_description}'.\n\n",
                "Context for subtle reference:\n",
                f"{tuon_features_content}\n\n",
                "Audience: high-agency professionals who care about productivity, knowledge leverage, and creative output.\n",
                "They are busy, overloaded with tools, allergic to fluff, and skeptical of hype.\n\n"
                "Your task: write an engaging, belief-shifting LinkedIn post based on the topic below:\n",
                f"Topic: '{topic_text}'\n\n",
                "Core objective: say the spicy truths out loud. Challenge assumptions. Name the real pain. Make the reader feel:\n",
                "  → \"finally someone said it\"\n",
                "  → \"that’s why I’m frustrated\"\n",
                "  → \"there’s a better way\"\n\n",
                "Post Requirements:\n",
                "- Start with a strong pattern interrupt (spicy assertion, bold claim, or uncomfortable truth)\n",
                "- Use a problem → truth → reframe → solution → benefit → reflection structure\n",
                "- Reference features only through outcomes, not lists (feature → functional benefit → emotional benefit)\n",
                "- Use mini-stories, metaphors, or relatable scenarios\n",
                "- Keep pacing tight with short punchy sentences\n",
                "- No fluff, no hashtags, no emojis, no corporate speak\n",
                "- End on an insightful reflection that feels like a shift in worldview\n",
                "- Tone: bold, honest, expert-level clarity, anti-bullshit\n",
                "- Max length: 2000 characters\n\n",
                "Examples of acceptable 'spicy truths' (illustrative only):\n"
                "  * Most productivity tools are just digital clutter. Tuon is built to actually help you create.\n",
                "  * Switching between apps kills your flow. Staying in one workspace preserves cognitive momentum.\n",
                "  * Notes buried in old tools are dead notes. Context-aware resurfacing makes knowledge compounding.\n\n",
                "Output only the LinkedIn post text. No headings. No labels. No commentary."
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
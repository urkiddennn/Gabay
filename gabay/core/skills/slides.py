import logging
import json
import uuid
from gabay.core.connectors.google_api import create_google_presentation, add_slide_to_presentation, share_file
from gabay.core.config import settings
from groq import AsyncGroq

logger = logging.getLogger(__name__)

async def handle_slides_skill(user_id: int, topic: str, title: str = None, email_to: str = None, invite_email: str = None, share_mode: str = 'private', role: str = 'writer') -> str:
    """
    Handles creating a professional Google Slides presentation.
    Uses LLM to structure slides and Unsplash for beautiful imagery.
    """
    # Import inside to avoid circular deps if any
    from gabay.core.skills.email import send_smtp_email
    
    if not title:
        title = f"Presentation on {topic}"
        
    try:
        # 1. Generate Slide Content via LLM
        client = AsyncGroq(api_key=settings.groq_api_key)
        
        system_prompt = (
            "You are a professional presentation designer for a top-tier consulting firm (like McKinsey or BCG). "
            "Your goal is to structure a high-impact, 5-slide presentation that is both visually stunning and intellectually deep. "
            "For each slide, provide:\n"
            "1. A punchy, insightful Title.\n"
            "2. 3-4 professional bullet points that go beyond the obvious. Use '•' at the start of each bullet.\n"
            "3. A 'image_query' that specifically describes a high-resolution, professional, and abstract or relevant stock photo "
            "from Unsplash (e.g., 'modern neural network light trails', 'minimalist architecture office', 'sustainable energy concept'). "
            "Avoid generic or cartoonish queries.\n\n"
            "Return a JSON object with a key 'slides', which is a list of objects with keys: 'title', 'body', 'image_query'."
        )
        
        user_prompt = f"Topic: {topic}\n\nPlease generate a 5-slide professional presentation structure."
        
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={ "type": "json_object" }
        )
        
        content = response.choices[0].message.content
        if not content:
            return "The AI assistant returned an empty response. Please try again."

        # Safe parsing
        try:
            slides_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse slides JSON: {e}. Content: {content}")
            return "I failed to parse the presentation structure. Please try again."

        slides = slides_data.get("slides", [])
        if not slides:
            return "I couldn't generate any slides for this topic. Please try again."

        # 2. Create the Presentation
        presentation_result = create_google_presentation(str(user_id), title)
        if "error" in presentation_result:
            return f"Failed to create presentation: {presentation_result['error']}"
            
        presentation_id = presentation_result["id"]
        presentation_link = presentation_result["link"]

        # 3. Add Slides
        for i, s in enumerate(slides):
            s_title = s.get("title", f"Slide {i+1}")
            s_body = s.get("body", "")
            if isinstance(s_body, list):
                s_body = "\n".join([f"• {p}" for p in s_body])
            
            # Use Unsplash Source for beautiful, professional images
            image_query = s.get("image_query", topic).replace(" ", ",")
            image_url = f"https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&q=80&w=800" # Fallback professional office
            
            # Special trick: Unsplash Source is deprecated, but we can use their public search redirect
            # or just a high-quality placeholder for now. 
            # For "Internet images", we'll use a reliable source.
            if image_query:
                # We'll use a slightly more robust placeholder service that allows queries
                image_url = f"https://loremflickr.com/800/600/{image_query}/all"

            add_slide_to_presentation(str(user_id), presentation_id, s_title, s_body, image_url=image_url)

        result_msg = f"Professional presentation '{title}' created successfully!\nLink: {presentation_link}"

        # 4. Hybrid Orchestration: Sharing & Invites
        target_invite = invite_email or email_to
        if target_invite:
            share_result = share_file(str(user_id), presentation_id, email=target_invite, role=role)
            if "error" not in share_result:
                result_msg += f"\nI've invited {target_invite} to edit the presentation."
        elif share_mode == "public":
            share_file(str(user_id), presentation_id)
            result_msg += "\nI've made the presentation accessible to anyone with the link."

        # 5. Hybrid Orchestration: Email Follow-up
        if email_to:
            try:
                subject = f"Presentation: {title}"
                email_body = f"I've created a presentation on '{topic}' for you.\n\nLink: {presentation_link}\n\n--\nSent via Gabay."
                send_smtp_email(email_to, subject, email_body, user_id=str(user_id))
                result_msg += f" and sent the link to {email_to}."
            except Exception as e:
                logger.error(f"Failed to send follow-up email for slides: {e}")
                result_msg += " (Failed to send follow-up email)"

        return result_msg

    except Exception as e:
        logger.error(f"Error in slides skill: {e}")
        return f"I encountered an error making your presentation: {e}"

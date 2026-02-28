import logging
import json
import uuid
from gabay.core.connectors.google_api import create_google_presentation, add_slide_to_presentation, share_file
from gabay.core.config import settings
from gabay.core.utils.llm import get_llm_response
from gabay.core.utils.telegram import send_telegram_message

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
        # 1. Phase 1: Planning & Outline
        send_telegram_message(user_id, f"🎨 **Planning Presentation:** I'm drafting an outline for your slides on '{topic}'...")

        system_prompt = (
            "You are a professional presentation designer at a top-tier consulting firm. "
            "Your goal is to structure a high-impact, 7-slide presentation. "
            "First, return a JSON object with a key 'outline' which is a brief list of the 7 slide titles. "
            "Then, include a key 'slides', which is a list of 7 objects with 'title', 'body', and 'image_query'. "
            "IMPORTANT: For 'body', provide 3-4 professional sentences or phrases. DO NOT include bullet points (•, -, *) in the text; these will be added automatically. "
            "For 'image_query', provide a highly specific, keyword-rich description for a professional stock photo (e.g., 'abstract blue data visualization', 'modern skyscraper glass reflections', 'diverse team collaborating in bright office'). Avoid generic terms."
        )
        
        user_prompt = f"Topic: {topic}\n\nPlease plan and generate a 7-slide professional presentation."
        
        slides_data = await get_llm_response(
            system_prompt=system_prompt,
            prompt=user_prompt,
            response_format={ "type": "json_object" }
        )
        
        if not slides_data:
            return "The AI assistant returned an empty response. Please try again."

        outline = slides_data.get("outline", [])
        if outline:
            outline_str = "\n".join([f"{i+1}. {t}" for i, t in enumerate(outline)])
            send_telegram_message(user_id, f"📝 **Presentation Plan:**\n\n{outline_str}\n\n*Starting creation now...*")
        
        slides = slides_data.get("slides", [])
        if not slides:
            return "I couldn't generate any slides for this topic. Please try again."

        # 2. Create the Presentation
        send_telegram_message(user_id, "🔧 Creating Google Slides file...")
        presentation_result = create_google_presentation(str(user_id), title)
        if "error" in presentation_result:
            return f"Failed to create presentation: {presentation_result['error']}"
            
        presentation_id = presentation_result["id"]
        presentation_link = presentation_result["link"]

        # 3. Add Slides Step-by-Step
        num_slides = len(slides)
        for i, s in enumerate(slides):
            send_telegram_message(user_id, f"✍️ Adding slide {i+1} of {num_slides}: **{s.get('title')}**...")
            s_title = s.get("title", f"Slide {i+1}")
            s_body = s.get("body", "")
            if isinstance(s_body, list):
                s_body = "\n".join([f"• {p}" for p in s_body])
            
            # Use Unsplash Source for beautiful, professional images
            image_query = s.get("image_query", topic).replace(" ", ",")
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

import json
import logging
from typing import Any, Optional, List, Dict
from groq import AsyncGroq
import google.generativeai as genai
from gabay.core.config import settings

logger = logging.getLogger(__name__)

async def get_llm_response(
    prompt: str = None, 
    system_prompt: str = None, 
    messages: List[Dict[str, str]] = None,
    model: str = None,
    response_format: dict = None
) -> Any:
    """
    Consolidated helper to call Groq/Gemini, handle errors, and parse JSON if needed.
    """
    provider = settings.llm_provider
    
    # Construct standard message list if not provided
    if not messages:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if prompt:
            messages.append({"role": "user", "content": prompt})

    if provider == "gemini":
        return await _call_gemini(messages, model, response_format)
    else:
        return await _call_groq(messages, model, response_format)

async def _call_groq(messages: List[Dict[str, str]], model: str = None, response_format: dict = None) -> Any:
    if not settings.groq_api_key:
        logger.warning("Groq API Key missing")
        return None
    
    if not model:
        model = "llama-3.3-70b-versatile"

    try:
        client = AsyncGroq(api_key=settings.groq_api_key)
        kwargs = {
            "model": model,
            "messages": messages
        }
        if response_format:
            kwargs["response_format"] = response_format

        completion = await client.chat.completions.create(**kwargs)
        content = completion.choices[0].message.content

        if response_format and response_format.get("type") == "json_object":
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Groq JSON response: {content}")
                return None
        
        return content
    except Exception as e:
        logger.error(f"Groq LLM Error: {e}")
        return None

async def _call_gemini(messages: List[Dict[str, str]], model: str = None, response_format: dict = None) -> Any:
    if not settings.gemini_api_key:
        logger.warning("Gemini API Key missing")
        return None
    
    if not model:
        model = "gemini-3-flash-preview"

    try:
        genai.configure(api_key=settings.gemini_api_key)
        
        # Extract system prompt if present
        system_instruction = None
        filtered_messages = []
        for m in messages:
            if m["role"] == "system":
                system_instruction = m["content"]
            else:
                filtered_messages.append(m)

        generation_config = {}
        if response_format and response_format.get("type") == "json_object":
            generation_config["response_mime_type"] = "application/json"

        model_instance = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_instruction,
            generation_config=generation_config
        )
        
        # Gemini expects a specific history format or just a string for the last message
        # For simplicity in intent/chat, we'll join history or just send the last one if it's stateless
        # But for chat skill we need the history. genai has start_chat()
        
        if len(filtered_messages) > 1:
            # Chat mode
            chat = model_instance.start_chat(history=[
                {"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
                for m in filtered_messages[:-1]
            ])
            response = await chat.send_message_async(filtered_messages[-1]["content"])
        else:
            # Single prompt
            response = await model_instance.generate_content_async(filtered_messages[0]["content"])
            
        content = response.text

        if response_format and response_format.get("type") == "json_object":
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Gemini JSON response: {content}")
                return None
        
        return content
    except Exception as e:
        logger.error(f"Gemini LLM Error: {e}")
        return None

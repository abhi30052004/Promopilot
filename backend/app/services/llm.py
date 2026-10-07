import time
import json
import logging
from typing import Type, TypeVar, Any
from pydantic import BaseModel, ValidationError

from openai import OpenAI, RateLimitError as OpenAIRateLimitError, APITimeoutError as OpenAIAPITimeoutError
from groq import Groq, RateLimitError as GroqRateLimitError, APITimeoutError as GroqAPITimeoutError
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

T = TypeVar("T", bound=BaseModel)

class LLMError(Exception):
    pass

def _retry_with_backoff(func, max_retries=3):
    def wrapper(*args, **kwargs):
        retries = 0
        while retries < max_retries:
            try:
                return func(*args, **kwargs)
            except (OpenAIRateLimitError, OpenAIAPITimeoutError, GroqRateLimitError, GroqAPITimeoutError) as e:
                retries += 1
                if retries >= max_retries:
                    raise LLMError(f"Rate limit or timeout after {max_retries} attempts: {str(e)}")
                sleep_time = 2 ** retries
                logger.warning(f"Rate limit/timeout hit. Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            except Exception as e:
                raise LLMError(f"API Error: {str(e)}")
    return wrapper

def generate_openai_json(prompt: str, system_prompt: str, schema: Type[T], timeout: float = 30.0) -> T:
    if not settings.OPENAI_API_KEY:
        raise LLMError("OpenAI API key missing")
        
    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=timeout)
    model = settings.OPENAI_MODEL

    @_retry_with_backoff
    def _call(msgs):
        start = time.time()
        try:
            res = client.chat.completions.create(
                model=model,
                messages=msgs,
                response_format={"type": "json_object"}
            )
            latency = time.time() - start
            logger.info(f"OpenAI {model} request succeeded. Latency: {latency:.2f}s")
            return res.choices[0].message.content
        except Exception as e:
            latency = time.time() - start
            logger.error(f"OpenAI {model} request failed. Latency: {latency:.2f}s")
            raise e

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    content = _call(messages)
    
    try:
        return schema.model_validate_json(content)
    except ValidationError as e:
        logger.warning(f"OpenAI JSON validation failed: {e}. Retrying with repair prompt.")
        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": "return valid JSON only"})
        content = _call(messages)
        try:
            return schema.model_validate_json(content)
        except ValidationError as e2:
            raise LLMError(f"Failed to parse JSON after repair: {e2}")

def generate_groq_json(prompt: str, system_prompt: str, schema: Type[T], timeout: float = 30.0) -> T:
    if not settings.GROQ_API_KEY:
        raise LLMError("Groq API key missing")
        
    client = Groq(api_key=settings.GROQ_API_KEY, timeout=timeout)
    model = settings.GROQ_MODEL

    @_retry_with_backoff
    def _call(msgs):
        start = time.time()
        try:
            res = client.chat.completions.create(
                model=model,
                messages=msgs,
                response_format={"type": "json_object"}
            )
            latency = time.time() - start
            logger.info(f"Groq {model} request succeeded. Latency: {latency:.2f}s")
            return res.choices[0].message.content
        except Exception as e:
            latency = time.time() - start
            logger.error(f"Groq {model} request failed. Latency: {latency:.2f}s")
            raise e

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    content = _call(messages)
    
    try:
        return schema.model_validate_json(content)
    except ValidationError as e:
        logger.warning(f"Groq JSON validation failed: {e}. Retrying with repair prompt.")
        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": "return valid JSON only"})
        content = _call(messages)
        try:
            return schema.model_validate_json(content)
        except ValidationError as e2:
            raise LLMError(f"Failed to parse JSON after repair: {e2}")

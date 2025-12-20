"""
LLM Client Service - Interface to Groq API for SQL generation
(Previously used RunPod GPU LLM - now using Groq API like users/providers)
"""
import aiohttp
import json
import asyncio
from typing import Optional, Dict, Any
from app.core.config import settings


class LLMClient:
    """Client for interacting with Groq API (OpenAI-compatible endpoint)"""
    
    def __init__(self):
        # Groq API configuration
        self.api_key = settings.GROQ_API_KEY
        self.base_url = settings.GROQ_BASE_URL
        self.timeout = settings.LLM_TIMEOUT
        self.model = settings.LLM_MODEL
        
        # RunPod GPU configuration (COMMENTED OUT - Using Groq API instead)
        # self.api_key = settings.RUNPOD_API_KEY
        # self.endpoint_id = settings.RUNPOD_ENDPOINT_ID
        # self.base_url = settings.RUNPOD_BASE_URL
    
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        stop: Optional[list] = None
    ) -> str:
        """
        Generate text using Groq API
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
        
        Returns:
            Generated text
        """
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set")
        
        # Groq API uses OpenAI-compatible chat completions endpoint
        api_url = f"{self.base_url.rstrip('/')}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
            "stop": stop or []
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Retry logic for transient errors (502, 503, 504, timeout)
        max_retries = 3
        retry_delay = 2  # Start with 2 seconds
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    async with session.post(api_url, json=payload, headers=headers) as response:
                        # Handle 502/503/504 errors (bad gateway, service unavailable, gateway timeout)
                        if response.status in [502, 503, 504]:
                            error_text = await response.text()
                            if attempt < max_retries - 1:
                                wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                                print(f"⚠️ Groq API returned {response.status} (attempt {attempt + 1}/{max_retries}). Retrying in {wait_time}s...")
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                raise RuntimeError(
                                    f"Groq API endpoint is unavailable (502 Bad Gateway). "
                                    f"Please try again later."
                                )
                        
                        if response.status != 200:
                            error_text = await response.text()
                            raise RuntimeError(f"Groq API error {response.status}: {error_text[:500]}")
                        
                        result = await response.json()
                    
                    # Extract generated text from OpenAI-compatible response format
                    if isinstance(result, dict):
                        if "choices" in result and len(result["choices"]) > 0:
                            choice = result["choices"][0]
                            # Chat completions format
                            if "message" in choice:
                                message = choice["message"]
                                if isinstance(message, dict) and "content" in message:
                                    return message["content"]
                                elif isinstance(message, str):
                                    return message
                            # Completions format (fallback)
                            elif "text" in choice:
                                return choice["text"]
                        elif "text" in result:
                            return result["text"]
                    
                    # Fallback: return string representation
                    return str(result)
                    
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"⚠️ Groq API timeout (attempt {attempt + 1}/{max_retries}). Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise RuntimeError(
                        f"Groq API request timed out after {self.timeout}s. "
                        f"Please try again later."
                    )
            except aiohttp.ClientError as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"⚠️ Network error (attempt {attempt + 1}/{max_retries}): {str(e)[:100]}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise RuntimeError(f"Network error calling Groq API after {max_retries} attempts: {str(e)}")
            except Exception as e:
                # Don't retry on non-transient errors
                raise RuntimeError(f"Error generating text: {str(e)}")
        
        # Should not reach here, but just in case
        raise RuntimeError("Failed to generate text after all retry attempts")


# ============================================================================
# OLD RUNPOD GPU CODE (COMMENTED OUT - Using Groq API instead)
# ============================================================================
"""
    def _is_openai_compatible(self, url: str) -> bool:
        # Check if URL is OpenAI-compatible (has /v1/ in path)
        return "/v1/" in url or url.endswith("/v1")
    
    def _get_endpoint_url(self) -> str:
        # Get the RunPod endpoint URL
        if self.base_url:
            return self.base_url.rstrip('/')
        
        if not self.endpoint_id:
            raise ValueError("RUNPOD_ENDPOINT_ID or RUNPOD_BASE_URL must be set")
        
        return f"https://api.runpod.ai/v2/{self.endpoint_id}/runsync"
    
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        stop: Optional[list] = None
    ) -> str:
        # Generate text using RunPod LLM
        if not self.api_key:
            raise ValueError("RUNPOD_API_KEY is not set")
        
        endpoint_url = self._get_endpoint_url()
        is_openai = self._is_openai_compatible(endpoint_url)
        
        # If base URL doesn't have /v1/, we assume it's OpenAI-compatible and append /v1/
        # This handles cases where RUNPOD_BASE_URL is set to the base proxy URL
        if not is_openai and self.base_url and "proxy.runpod.net" in self.base_url:
            # Assume OpenAI-compatible endpoint, append /v1/ if not present
            if not endpoint_url.endswith("/v1") and not endpoint_url.endswith("/v1/"):
                endpoint_url = f"{endpoint_url.rstrip('/')}/v1"
            is_openai = True
        
        # Determine API format based on endpoint type
        if is_openai:
            # OpenAI-compatible endpoint format
            # Try chat completions first (better for instruct models), fallback to completions
            # Check if model name suggests it's an instruct/chat model
            is_instruct_model = "instruct" in self.model.lower() or "chat" in self.model.lower()
            
            if is_instruct_model:
                # Use chat completions for instruct models
                api_url = f"{endpoint_url.rstrip('/')}/chat/completions" if not endpoint_url.endswith("/chat/completions") else endpoint_url
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                    "stop": stop or []
                }
            else:
                # Use completions for base models
                api_url = f"{endpoint_url.rstrip('/')}/completions" if not endpoint_url.endswith("/completions") else endpoint_url
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                    "stop": stop or []
                }
        else:
            # Standard RunPod API format
            api_url = endpoint_url
            payload = {
                "input": {
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                    "stop": stop or []
                }
            }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Retry logic for transient errors (502, 503, 504, timeout)
        max_retries = 3
        retry_delay = 2  # Start with 2 seconds
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    async with session.post(api_url, json=payload, headers=headers) as response:
                        # Handle 502/503/504 errors (bad gateway, service unavailable, gateway timeout)
                        if response.status in [502, 503, 504]:
                            error_text = await response.text()
                            # Check if it's an HTML error page (Cloudflare)
                            if "<!DOCTYPE html>" in error_text or "Bad gateway" in error_text:
                                if attempt < max_retries - 1:
                                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                                    print(f"⚠️ RunPod endpoint returned {response.status} (attempt {attempt + 1}/{max_retries}). Retrying in {wait_time}s...")
                                    await asyncio.sleep(wait_time)
                                    continue
                                else:
                                    raise RuntimeError(
                                        f"RunPod GPU endpoint is unavailable (502 Bad Gateway). "
                                        f"The GPU pod at {endpoint_url} appears to be down or not responding. "
                                        f"Please check your RunPod pod status or try again later."
                                    )
                            else:
                                if attempt < max_retries - 1:
                                    wait_time = retry_delay * (2 ** attempt)
                                    await asyncio.sleep(wait_time)
                                    continue
                                else:
                                    raise RuntimeError(f"RunPod API error {response.status}: {error_text[:500]}")
                        
                        if response.status != 200:
                            error_text = await response.text()
                            raise RuntimeError(f"RunPod API error {response.status}: {error_text[:500]}")
                        
                        result = await response.json()
                    
                    # Extract generated text based on API format
                    if is_openai:
                        # OpenAI-compatible response format
                        if isinstance(result, dict):
                            if "choices" in result and len(result["choices"]) > 0:
                                choice = result["choices"][0]
                                # Chat completions format
                                if "message" in choice:
                                    message = choice["message"]
                                    if isinstance(message, dict) and "content" in message:
                                        return message["content"]
                                    elif isinstance(message, str):
                                        return message
                                # Completions format
                                elif "text" in choice:
                                    return choice["text"]
                            elif "text" in result:
                                return result["text"]
                    else:
                        # Standard RunPod response format
                        if isinstance(result, dict):
                            if "output" in result:
                                if isinstance(result["output"], str):
                                    return result["output"]
                                elif isinstance(result["output"], dict) and "text" in result["output"]:
                                    return result["output"]["text"]
                                elif isinstance(result["output"], list) and len(result["output"]) > 0:
                                    # Handle list of outputs
                                    return result["output"][0].get("text", "") if isinstance(result["output"][0], dict) else str(result["output"][0])
                            elif "text" in result:
                                return result["text"]
                            elif "response" in result:
                                return result["response"]
                    
                    # Fallback: return string representation
                    return str(result)
                    
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"⚠️ RunPod API timeout (attempt {attempt + 1}/{max_retries}). Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise RuntimeError(
                        f"RunPod API request timed out after {self.timeout}s. "
                        f"The endpoint may be overloaded or the GPU pod may be unresponsive. "
                        f"Please try again later."
                    )
            except aiohttp.ClientError as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"⚠️ Network error (attempt {attempt + 1}/{max_retries}): {str(e)[:100]}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise RuntimeError(f"Network error calling RunPod API after {max_retries} attempts: {str(e)}")
            except Exception as e:
                # Don't retry on non-transient errors
                raise RuntimeError(f"Error generating text: {str(e)}")
        
        # Should not reach here, but just in case
        raise RuntimeError("Failed to generate text after all retry attempts")
"""


# Global instance
llm_client = LLMClient()

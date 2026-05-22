"""
LLM Client for Hermes Agents.
Provides a unified interface for interacting with multiple LLM providers,
configured via central configuration and optionally via .env files.
"""

import os
import logging
import yaml
from typing import Optional, Dict, Any
from openai import OpenAI
import google.genai as genai
from google.genai import types
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the LLM Client.

        Args:
            config_path (str): Path to the configuration file.
        """
        # Load .env file if it exists in the current directory
        load_dotenv()

        self.config = self._load_config(config_path)
        self.provider = self.config.get("provider", "google")
        self.model = self.config.get("model")
        self.base_url = self.config.get("base_url")

        self._initialize_client()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        if not os.path.exists(config_path):
            logger.error(f"Configuration file not found: {config_path}")
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        return config.get("llm", {})

    def _get_env_var(self, env_name: str) -> Optional[str]:
        return os.getenv(env_name)

    def _initialize_client(self):
        if self.provider == "openai":
            api_key = self._get_env_var(self.config.get("openai_api_key_env", "OPENAI_API_KEY"))
            self.base_url = self.base_url or self._get_env_var(self.config.get("openai_base_url_env", "OPENAI_BASE_URL"))
            
            if not api_key:
                logger.warning("No API key provided for OpenAI. Requests will likely fail.")
            
            self.client = OpenAI(
                api_key=api_key,
                base_url=self.base_url
            )
            if not self.model:
                self.model = "gpt-4o"

        elif self.provider == "google":
            api_key = self._get_env_var(self.config.get("api_key_env", "GOOGLE_API_KEY_KANBAN"))
            
            if not api_key:
                logger.warning("No API key provided for Google. Requests will likely fail.")
            
            if not self.model:
                self.model = "gemini-1.5-pro"
            
            self.client = genai.Client(api_key=api_key)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        """
        Sends a single chat request to the LLM.
        """
        try:
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                )
                return response.choices[0].message.content.strip()

            elif self.provider == "google":
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature
                    )
                )
                return response.text.strip()

        except Exception as e:
            logger.error(f"{self.provider.capitalize()} chat failed: {str(e)}")
            raise e

    def generate_structured_content(self, system_prompt: str, user_prompt: str) -> str:
        """
        A wrapper for chat specifically for generating markdown content.
        """
        return self.chat(system_prompt, user_prompt, temperature=0.2)

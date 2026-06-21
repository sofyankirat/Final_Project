from ..LLMInterface import LLMInterface
from ..LLMEnums import GeminiEnums, DocumentTypeEnum
from models.enums.ResponseEnums import ResponseSignal
from stores.llm.templates.template_parser import TemplateParser
from typing import List, Union
from google import genai
from google.genai import types

import logging
import time

class GeminiProvider(LLMInterface):

    # TPM rate-limit constants
    TOKENS_PER_BATCH = 28_000       # max tokens to embed in one API call
    MAX_TOTAL_TOKENS = 280_000      # absolute ceiling (25k × 10 batches)
    BATCH_WAIT_SECONDS = 65         # cooldown between batches

    def __init__(self, api_key: str, template_parser: TemplateParser,
                 default_input_max_characters: int = 1000,
                 default_generation_max_output_tokens: int = 1000,
                 default_generation_temperature: float = 0.1,
                 ):

        self.api_key = api_key

        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature
        self.template_parser = template_parser

        self.generation_model_id = None
        self.embedding_model_id = None
        self.embedding_size = None

        self.client = genai.Client(api_key=self.api_key)

        self.enums = GeminiEnums
        self.logger = logging.getLogger(__name__)

    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def process_text(self, text: str):
        return text[:self.default_input_max_characters].strip()

    def generate_text(self, prompt: str, chat_history: list = [],
                      max_output_tokens: int = None, temperature: float = None):

        if not self.client:
            self.logger.error("Gemini generation model was not set — call set_generation_model() first")
            return None

        if not self.generation_model_id:
            self.logger.error("Generation model for Gemini was not set")
            return None

        max_output_tokens = max_output_tokens or self.default_generation_max_output_tokens
        temperature = temperature or self.default_generation_temperature

        chat_history.append(
            self.construct_prompt(prompt=prompt, role=GeminiEnums.USER.value)
        )

        # Override generation config per-call if custom values were provided
        generation_config = types.GenerateContentConfig(
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            system_instruction=self.template_parser.get("rag", "system_prompt")
        )

        try:
            response = self.client.models.generate_content(
                model=self.generation_model_id,
                contents=chat_history,
                config=generation_config,
            )
        except Exception as e:
            self.logger.error(f"Error while generating text with Gemini: {e}")
            return None

        if not response or not response.candidates:
            self.logger.error("Empty response received from Gemini")
            return None

        return response.text

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Estimate token count using the 1 token ≈ 4 characters heuristic."""
        return len(text) // 4

    def _split_into_token_batches(self, texts: List[str]):
        """Group texts into batches where each batch ≤ TOKENS_PER_BATCH tokens.
        Returns a list of sub-lists of texts."""
        batches = []
        current_batch = []
        current_token_count = 0

        for text in texts:
            token_count = self._estimate_tokens(text)

            # if adding this text would exceed the batch limit, seal the batch
            if current_batch and (current_token_count + token_count) > self.TOKENS_PER_BATCH:
                batches.append(current_batch)
                current_batch = []
                current_token_count = 0

            current_batch.append(text)
            current_token_count += token_count

        # don't forget the last batch
        if current_batch:
            batches.append(current_batch)

        return batches

    # ── embedding with TPM guard ─────────────────────────────────────────

    def embed_text(self, text: Union[str, List[str]], document_type: str = None):

        if not self.embedding_model_id:
            self.logger.error("Embedding model for Gemini was not set — call set_embedding_model() first")
            return None
        
        if isinstance(text, str):
            text = [text]

        # Map DocumentTypeEnum values to Gemini task_type strings
        task_type = self._resolve_task_type(document_type)

        # step 1: estimate total tokens and reject if too large
        total_tokens = sum(self._estimate_tokens(t) for t in text)

        if total_tokens > self.MAX_TOTAL_TOKENS:
            self.logger.warning(
                "Text too large for embedding: ~%d tokens (max %d)",
                total_tokens, self.MAX_TOTAL_TOKENS,
            )
            return ResponseSignal.FILE_CONTENT_TOO_LARGE

        # step 2: split texts into token-bounded batches
        batches = self._split_into_token_batches(text)

        # step 3: embed each batch, waiting between batches to respect TPM
        all_embeddings = []

        for batch_idx, batch_texts in enumerate(batches):

            # wait before the 2nd, 3rd, … batch to stay under TPM limit
            if batch_idx > 0:
                self.logger.info(
                    "Rate-limit cooldown: waiting %ds before batch %d/%d",
                    self.BATCH_WAIT_SECONDS, batch_idx + 1, len(batches),
                )
                time.sleep(self.BATCH_WAIT_SECONDS)

            try:
                # Wrap each text in its own Content object so the API returns
                # one embedding per Content (not one for the whole list).
                content_list = [
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=t)]
                    )
                    for t in batch_texts
                ]

                response = self.client.models.embed_content(
                    model=self.embedding_model_id,
                    contents=content_list,
                    config=types.EmbedContentConfig(task_type=task_type),
                )

                if not response or not response.embeddings:
                    self.logger.error("No embedding returned from Gemini for batch %d", batch_idx + 1)
                    return None

                if len(response.embeddings) != len(batch_texts):
                    self.logger.error(
                        "Mismatch: sent %d texts, got %d embeddings in batch %d",
                        len(batch_texts), len(response.embeddings), batch_idx + 1,
                    )
                    return None

                all_embeddings.extend([rec.values for rec in response.embeddings])

            except Exception as e:
                self.logger.error(f"Error while embedding text with Gemini (batch {batch_idx + 1}): {e}")
                return None

        return all_embeddings

    def construct_prompt(self, prompt: str, role: str):
        """
        Gemini expects:  {"role": "user" | "model", "parts": ["text"]}
        """
        return types.Content(
            role=role,
            parts=[types.Part(text=prompt)]
        )

    def _resolve_task_type(self, document_type: str) -> str:
        if document_type == DocumentTypeEnum.QUERY.value:
            return GeminiEnums.QUERY.value
        return GeminiEnums.DOCUMENT.value


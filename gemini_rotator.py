import itertools
import threading
from google import genai
from google.genai import types
from google.genai.errors import APIError

class GeminiKeyRotator:
    def __init__(self, api_keys: list[str]):
        self.api_keys = [k.strip() for k in api_keys if k.strip()]
        if not self.api_keys:
            raise ValueError("Danh sách API Key không được để trống!")
        self._key_cycle = itertools.cycle(self.api_keys)
        self._lock = threading.Lock()

    def get_next_client(self) -> tuple[genai.Client, str]:
        with self._lock:
            key = next(self._key_cycle)
        client = genai.Client(api_key=key)
        return client, key

    def generate_content_with_retry(
        self,
        contents: list,
        model: str = "gemini-2.5-flash",
        system_instruction: str = None
    ) -> str:
        """
        Gửi yêu cầu tới Gemini. Nếu gặp lỗi Rate Limit (429) hoặc Quota (403),
        tự động chuyển sang key kế tiếp để tiếp tục.
        """
        attempts = len(self.api_keys)
        last_error = None

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2
        ) if system_instruction else None

        for _ in range(attempts):
            client, key_in_use = self.get_next_client()
            masked_key = f"{key_in_use[:4]}...{key_in_use[-4:]}"
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config
                )
                return response.text
            except APIError as e:
                last_error = e
                if e.code in [429, 403] or "RESOURCE_EXHAUSTED" in str(e):
                    continue
                raise e
            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(f"Tất cả {attempts} API Keys đều bị cạn hạn ngạch hoặc lỗi. Chi tiết: {last_error}")
import itertools
import threading
from google import genai
from google.genai import types

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
        return genai.Client(api_key=key), key

    def generate_content_with_retry(
        self,
        contents: list,
        model: str = "gemini-2.5-flash",
        system_instruction: str = None
    ) -> str:
        attempts = len(self.api_keys)
        last_error = None

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2
        ) if system_instruction else None

        for _ in range(attempts):
            client, key = self.get_next_client()
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config
                )
                return response.text
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                    continue
                raise e

        raise RuntimeError(f"Tất cả {attempts} API Keys đều gặp lỗi hoặc hết quota. Chi tiết: {last_error}")
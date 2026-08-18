import itertools
import threading
import google.generativeai as genai

class GeminiKeyRotator:
    def __init__(self, api_keys: list[str]):
        self.api_keys = [k.strip() for k in api_keys if k.strip()]
        if not self.api_keys:
            raise ValueError("Danh sách API Key không được để trống!")
        self._key_cycle = itertools.cycle(self.api_keys)
        self._lock = threading.Lock()

    def get_next_key(self) -> str:
        with self._lock:
            return next(self._key_cycle)

    def generate_content_with_retry(
        self,
        contents: list,
        model_name: str = "gemini-1.5-flash",
        system_instruction: str = None
    ) -> str:
        attempts = len(self.api_keys)
        last_error = None

        for _ in range(attempts):
            key = self.get_next_key()
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=system_instruction
                )
                response = model.generate_content(contents)
                return response.text
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                    continue
                raise e

        raise RuntimeError(f"Tất cả {attempts} API Keys đều gặp lỗi hoặc hết hạn ngạch. Chi tiết: {last_error}")
import itertools
import threading
import base64
import io
import requests

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
        model: str = "gemini-2.5-flash",
        system_instruction: str = None
    ) -> str:
        attempts = len(self.api_keys)
        last_error = None

        # Chuẩn bị payload chuẩn theo định dạng REST của Google
        parts = []
        for item in contents:
            if isinstance(item, str):
                parts.append({"text": item})
            else:
                # Chuyển đổi ảnh PIL sang Base64
                buf = io.BytesIO()
                item.save(buf, format="JPEG", quality=90)
                b64_img = base64.b64encode(buf.getvalue()).decode("utf-8")
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": b64_img
                    }
                })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.2}
        }
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        for _ in range(attempts):
            api_key = self.get_next_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                res = requests.post(url, json=payload, timeout=60)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        text_parts = candidates[0]["content"].get("parts", [])
                        return "".join([p.get("text", "") for p in text_parts])
                    return ""
                elif res.status_code in [429, 403]:
                    continue
                else:
                    last_error = f"HTTP {res.status_code}: {res.text}"
            except Exception as e:
                last_error = str(e)
                continue

        raise RuntimeError(f"Tất cả {attempts} API Keys đều gặp lỗi. Chi tiết: {last_error}")
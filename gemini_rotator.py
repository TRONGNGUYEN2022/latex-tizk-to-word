import itertools
import threading
import base64
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

    def convert_pdf_to_latex(
        self,
        pdf_bytes: bytes,
        prompt_instruction: str,
        model: str = "gemini-2.5-flash"
    ) -> str:
        attempts = len(self.api_keys)
        last_error = None

        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

        system_instruction = (
            "Bạn là chuyên gia chuyển đổi tài liệu đề thi Toán sang LaTeX. "
            "Nhiệm vụ: Chuyển đổi toàn bộ nội dung trong PDF thành mã nguồn LaTeX hoàn chỉnh. "
            "Tất cả công thức toán đặt trong $...$ hoặc $$...$$. "
            "Các hình vẽ hình học, đồ thị BẮT BUỘC dựng bằng môi trường \\begin{tikzpicture}...\\end{tikzpicture}. "
            "Chỉ trả về trực tiếp mã LaTeX thuần giữa \\begin{document} và \\end{document}."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "application/pdf",
                                "data": pdf_b64
                            }
                        },
                        {
                            "text": prompt_instruction
                        }
                    ]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "temperature": 0.2
            }
        }

        for _ in range(attempts):
            api_key = self.get_next_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                res = requests.post(url, json=payload, timeout=120)
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

        raise RuntimeError(f"Tất cả {attempts} API Keys đều gặp sự cố. Chi tiết: {last_error}")
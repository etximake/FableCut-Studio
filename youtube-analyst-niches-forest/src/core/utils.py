import json
import re
from typing import Dict, Any

def extract_json_from_response(content: str) -> Dict[str, Any]:
    """
    Trích xuất và parse JSON an toàn từ phản hồi của LLM.
    Xử lý tự động các trường hợp:
    - Bị bọc trong ```json ... ``` hoặc ``` ... ```
    - Có tiền tố/hậu tố văn bản giải thích
    - Khoảng trắng thừa
    """
    if not content:
        raise ValueError("Phản hồi từ LLM trống rỗng.")

    cleaned = content.strip()

    # 1. Thử parse trực tiếp
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 2. Xóa markdown code block fences (```json ... ``` hoặc ``` ... ```)
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Tìm khối JSON đầu tiên bắt đầu bằng '{' và kết thúc bằng '}'
    match = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Không thể trích xuất JSON hợp lệ từ phản hồi LLM:\n{content[:500]}")

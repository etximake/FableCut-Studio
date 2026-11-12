import pytest
from src.core.utils import extract_json_from_response

def test_extract_json_direct():
    data = extract_json_from_response('{"status": "ok", "count": 42}')
    assert data["status"] == "ok"
    assert data["count"] == 42

def test_extract_json_with_markdown_fence():
    text = """```json
{
  "name": "Explainer",
  "wpm": 135
}
```"""
    data = extract_json_from_response(text)
    assert data["name"] == "Explainer"
    assert data["wpm"] == 135

def test_extract_json_with_surrounding_text():
    text = """Here is the generated commentary timeline:
```json
{
  "subject_matter": "Physics experiment",
  "confidence": 0.98
}
```
Hope this helps!"""
    data = extract_json_from_response(text)
    assert data["subject_matter"] == "Physics experiment"
    assert data["confidence"] == 0.98

def test_extract_json_invalid():
    with pytest.raises(ValueError):
        extract_json_from_response("Not a JSON object at all")

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("qa_check", ROOT / "scripts" / "qa_check.py")
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


def test_all_examples_validate_without_modifying_fixtures():
    schema = json.loads((ROOT / "schema" / "input_schema.json").read_text(encoding="utf-8"))
    for fixture in sorted((ROOT / "examples").glob("*.json")):
        before = fixture.read_bytes()
        qa.validate_input(fixture, schema, strict=False if "upload_" in fixture.name else None)
        assert fixture.read_bytes() == before


def test_all_irrigation_fixtures_generate_ops_and_pass_qa(tmp_path):
    import subprocess
    for fixture in sorted((ROOT / "examples").glob("irrigation-*.json")):
        ops_path = tmp_path / f"{fixture.stem}.ops.json"
        result = subprocess.run([
            "py", "-3.10", str(ROOT / "adapter" / "convert.py"), "--json", str(fixture), "--output", str(ops_path)
        ], cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        qa.validate_ops(ops_path)


def test_ops_reject_first_frame_hidden_text(tmp_path):
    path = tmp_path / "ops.json"
    path.write_text(json.dumps([{"op":"addClip","clip":{"id":"a","kind":"text","track":"V2","start":0,"duration":2,"props":{"textAnim":"word-pop","boxW":820,"boxH":300,"x":0,"y":0}}}]))
    with pytest.raises(ValueError, match="Frame 0"):
        qa.validate_ops(path)


def test_template_assets_resolve_to_library_fonts():
    qa.validate_template_assets()


def test_ops_reject_duplicate_transition_on_same_beat(tmp_path):
    ops = [{"op": "addClip", "clip": {"id": f"v{i}", "kind": "video", "track": "V1", "start": i, "duration": 1, "name": "HOOK footage", "transitionIn": {"type": "fade"}}} for i in range(2)]
    path = tmp_path / "ops.json"
    path.write_text(json.dumps(ops), encoding="utf-8")
    with pytest.raises(ValueError, match="first video cut"):
        qa.validate_ops(path)

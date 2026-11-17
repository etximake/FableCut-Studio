"""Chọn cảnh cho video dài hơn giới hạn Short.

Video gốc vẫn được phân tích toàn bộ (timeline đầy đủ). Khi viết kịch bản,
chỉ các cảnh đã chọn mới được dùng: chúng được ghép thành 1 clip liên tục
bằng FFmpeg và timeline được dồn mốc giây về 0, vì converter của FableCut
bắt buộc các segment liền mạch, không khoảng trống, và mốc giây của segment
vừa là vị trí xuất ra vừa là điểm cắt trên video nguồn.

Module này chỉ chứa hàm thuần túy (không đọc file, không gọi LLM) để dễ
kiểm thử: gợi ý cảnh từ timeline, kiểm tra cảnh người dùng chốt, và dồn
timeline theo cảnh đã chọn. Người dùng luôn có quyền sửa danh sách cảnh
trước khi viết kịch bản; gợi ý ở đây chỉ là điểm bắt đầu.

EditPlan giữ rõ mốc video nguồn và mốc timeline đầu ra để hướng dẫn editor,
không thay đổi hợp đồng timeline liền mạch của FableCut.
"""

from typing import List, Optional, Tuple

from src.models.schemas import ActionBlock, EditCut, EditPlan, SceneRange, TimeRange, VisualActionTimeline

MIN_SCENE_SECONDS = 2.0
# Gợi ý dừng khi cảnh còn lại kém giá trị hẳn so với cảnh tốt nhất: giới hạn
# 60s là TRẦN, không phải mục tiêu — tổng gợi ý thay đổi theo nội dung video.
_SCORE_FLOOR_RATIO = 0.5
_SCORE_FLOOR_MIN = 0.5
MIN_PROPOSAL_SECONDS = 15.0
_EPSILON = 0.01


def total_seconds(scenes: List[SceneRange]) -> float:
    return round(sum(scene.end - scene.start for scene in scenes), 3)


def needs_scene_selection(duration_seconds: float, max_seconds: float) -> bool:
    return duration_seconds > max_seconds + _EPSILON


def validate_scenes(
    scenes: List[SceneRange],
    video_duration: float,
    max_seconds: float,
) -> List[str]:
    """Trả về danh sách lỗi (rỗng = hợp lệ). Không tự sửa lặng lẽ."""
    errors: List[str] = []
    if not scenes:
        return ["Chưa chọn cảnh nào."]
    ordered = sorted(scenes, key=lambda scene: scene.start)
    previous_end: Optional[float] = None
    for index, scene in enumerate(ordered):
        label = f"Cảnh {index + 1} ({scene.start:.1f}–{scene.end:.1f}s)"
        if scene.end - scene.start < _EPSILON:
            errors.append(f"{label}: thời lượng phải lớn hơn 0.")
        if scene.start < 0:
            errors.append(f"{label}: bắt đầu trước 0s.")
        if scene.end > video_duration + _EPSILON:
            errors.append(f"{label}: kết thúc vượt thời lượng video ({video_duration:.1f}s).")
        if previous_end is not None and scene.start < previous_end - _EPSILON:
            errors.append(f"{label}: chồng lên cảnh trước.")
        previous_end = max(previous_end or 0.0, scene.end)
    total = total_seconds(ordered)
    if total > max_seconds + _EPSILON:
        errors.append(
            f"Tổng thời lượng các cảnh là {total:.1f}s, vượt giới hạn {max_seconds:.1f}s."
        )
    return errors


def _block_score(block: ActionBlock, index: int, block_count: int, template_id: Optional[str]) -> float:
    """Điểm mức độ đáng chọn của 1 block timeline, chỉ từ bằng chứng quan sát."""
    score = float(block.confidence)
    if block.evidence_source == "observed":
        score += 0.3
    elif block.evidence_source == "heard":
        score += 0.1
    score += min(0.3, len(block.observable_changes or "") / 200.0)
    if template_id == "shock-hook" and index == 0:
        # Hook cần mở đầu; block đầu tiên thường chứa chi tiết gây chú ý.
        score += 0.2
    if template_id == "before-after" and index in (0, block_count - 1):
        # Neo bắt buộc: trạng thái trước (đầu) và sau (cuối).
        score += 1.0
    return score


def _merge_adjacent(scenes: List[SceneRange]) -> List[SceneRange]:
    """Gộp các cảnh kề nhau (cảnh sau bắt đầu đúng lúc cảnh trước kết thúc)."""
    if not scenes:
        return []
    ordered = sorted(scenes, key=lambda scene: scene.start)
    merged: List[SceneRange] = [ordered[0]]
    for scene in ordered[1:]:
        last = merged[-1]
        if abs(scene.start - last.end) <= _EPSILON:
            merged[-1] = SceneRange(
                start=last.start,
                end=scene.end,
                reason=last.reason or scene.reason,
            )
        else:
            merged.append(scene)
    return merged


def propose_scenes(
    timeline: VisualActionTimeline,
    template_id: Optional[str],
    max_seconds: float,
    min_scene_seconds: float = MIN_SCENE_SECONDS,
) -> List[SceneRange]:
    """Gợi ý cảnh từ timeline, tổng không vượt max_seconds.

    max_seconds là TRẦN, không phải mục tiêu: chỉ chọn block có điểm bằng
    chứng đạt sàn (so với block tốt nhất); block yếu còn lại bị bỏ thay vì
    nhồi cho đủ 60s. Cộng điểm kề nhau để ưu tiên mạch liên tục (quan trọng
    với satisfying và hazard-rescue: cảnh cần bối cảnh trước/sau). Block chỉ
    bị cắt ngắn khi vượt ngân sách; nếu tổng dưới trần thì giữ nguyên mốc
    tự nhiên. Nếu mọi block đều yếu thì vẫn lấy đủ tối thiểu 15s để kịch
    bản có chất liệu.
    """
    duration = timeline.duration_seconds
    if not needs_scene_selection(duration, max_seconds):
        return [SceneRange(start=0.0, end=round(duration, 3), reason="Toàn bộ video.")]
    blocks = timeline.action_timeline or []
    if not blocks:
        return [SceneRange(start=0.0, end=round(max_seconds, 3), reason="Không có timeline; lấy từ đầu video.")]

    block_count = len(blocks)
    scores = [
        _block_score(block, index, block_count, template_id)
        for index, block in enumerate(blocks)
    ]
    # Điểm kề nhau: block nằm cạnh block điểm cao cũng đáng chọn (giữ mạch).
    for index in range(block_count):
        neighbors = []
        if index > 0:
            neighbors.append(scores[index - 1])
        if index < block_count - 1:
            neighbors.append(scores[index + 1])
        if neighbors:
            scores[index] += 0.15 * max(neighbors)

    order = sorted(range(block_count), key=lambda i: (-scores[i], blocks[i].time_range.start))
    floor = max(_SCORE_FLOOR_MIN, _SCORE_FLOOR_RATIO * max(scores))
    picked: List[Tuple[float, float, str]] = []
    picked_indexes: set = set()
    remaining = [max_seconds]

    def take(index: int) -> None:
        block = blocks[index]
        start = max(0.0, block.time_range.start)
        end = min(duration, block.time_range.end)
        if end - start < _EPSILON:
            return
        take_end = min(end, start + remaining[0])
        if take_end - start < min_scene_seconds - _EPSILON:
            return
        reason = (block.visual_action or "").strip()
        if len(reason) > 80:
            reason = reason[:77].rstrip() + "..."
        picked.append((round(start, 3), round(take_end, 3), reason))
        picked_indexes.add(index)
        remaining[0] -= take_end - start

    def picked_total() -> float:
        return total_seconds([SceneRange(start=s, end=e, reason=r) for s, e, r in picked])

    for index in order:
        if remaining[0] < min_scene_seconds - _EPSILON:
            break
        if scores[index] < floor:
            continue
        take(index)
    # Mọi block đều yếu: vẫn lấy đủ chất liệu tối thiểu.
    if picked_total() < MIN_PROPOSAL_SECONDS:
        for index in order:
            if remaining[0] < min_scene_seconds - _EPSILON:
                break
            if index in picked_indexes:
                continue
            take(index)
            if picked_total() >= MIN_PROPOSAL_SECONDS:
                break
    if not picked:
        first = blocks[0]
        end = min(duration, first.time_range.start + max_seconds)
        picked.append((round(first.time_range.start, 3), round(end, 3), "Cảnh đầu tiên."))
    scenes = [SceneRange(start=s, end=e, reason=r) for s, e, r in picked]
    merged = _merge_adjacent(scenes)
    # Chốt tổng đúng ngân sách sau làm tròn.
    total = total_seconds(merged)
    if total > max_seconds + _EPSILON and merged:
        overflow = total - max_seconds
        last = merged[-1]
        merged[-1] = SceneRange(start=last.start, end=round(last.end - overflow, 3), reason=last.reason)

    # Gán vai trò (role) và chỉ dẫn dựng (edit_guidance) cho từng cảnh
    for idx, sc in enumerate(merged):
        if idx == 0 and sc.start <= 5.0:
            sc.role = "hook"
            sc.edit_guidance = "Cắt giật vào hành động mở đầu, bỏ đoạn chờ máy/chuẩn bị để giữ chân người xem."
        elif idx == len(merged) - 1:
            sc.role = "payoff"
            sc.edit_guidance = "Cắt rộng cho thấy thành quả hoặc biến đổi sau toàn bộ quá trình."
        elif len(merged) >= 4 and idx == 1:
            sc.role = "setup"
            sc.edit_guidance = "Giữ một nhịp ngắn để xác lập bối cảnh và thao tác sắp diễn ra."
        elif len(merged) >= 3 and idx == len(merged) - 2:
            sc.role = "climax"
            sc.edit_guidance = "Cận cảnh khoảnh khắc tác động/áp lực mạnh nhất, giữ nguyên tốc độ để rõ chi tiết."
        else:
            sc.role = "action"
            sc.edit_guidance = "Giữ nhịp di chuyển ổn định, loại bỏ rung lắc camera hoặc khoảng lặng."

    return merged


def build_edit_plan(
    timeline: VisualActionTimeline,
    scenes: List[SceneRange],
    template_id: Optional[str] = None,
) -> EditPlan:
    """Xây dựng Kế hoạch Dựng phim & Cắt ghép (Edit Plan) chi tiết.

    Hoạt động cho cả video < 60s và video > 60s:
    - Mốc nguồn (source_start, source_end) vs Mốc đầu ra (output_start, output_end).
    - Vai trò từng cú cắt (hook, setup, action, climax, payoff).
    - Chỉ dẫn dựng chi tiết (transition, speed, camera treatment).
    - Thống kê các đoạn thừa/chết đã lược bỏ.
    """
    total_orig = timeline.duration_seconds
    blocks = timeline.action_timeline or []

    strategy_map = {
        "how-it-works": "Kể theo cấu trúc câu hỏi cơ chế -> bóc tách từng bước thao tác -> khoảnh khắc hiệu quả -> đúc kết kết quả.",
        "shock-hook": "Mở đầu bằng cú shock thị giác mạnh nhất -> giải thích sự thật phía sau -> cao trào xử lý.",
        "before-after": "Tạo tương phản mạnh mẽ giữa trạng thái ban đầu và sự biến đổi ngoạn mục ở cuối.",
        "satisfying": "Tập trung vào nhịp cắt mượt mà, chuyển động lặp đi lặp lại êm ái, phóng đại âm thanh vật lý.",
        "hazard-rescue": "Tạo cảm giác cấp bách ở đầu -> chẩn đoán tình huống -> hành động giải cứu quyết liệt.",
        "story": "Xây dựng bối cảnh nhân vật -> thử thách gặp phải -> hành động vượt khó -> bài học/thành quả.",
    }
    strategy = strategy_map.get(template_id or "", "Tối ưu hóa mạch kể chuyện: mở đầu lôi cuốn, lược bỏ đoạn chết, tập trung vào khoảnh khắc giá trị cao.")

    cuts: List[EditCut] = []

    if not scenes or covers_full_video(scenes, total_orig):
        # Video giữ nguyên hoặc dưới 60s
        if blocks:
            # Đặt overlay các event ngắn thành 4 hồi lớn có ý nghĩa để editor
            # nhìn thấy hook/setup/action/climax/payoff thay vì danh sách vụn.
            groups: List[Tuple[int, int]] = []
            group_count = min(5, len(blocks))
            for group_index in range(group_count):
                start_idx = round(group_index * len(blocks) / group_count)
                end_idx = round((group_index + 1) * len(blocks) / group_count)
                if end_idx > start_idx:
                    groups.append((start_idx, end_idx))
            roles = ["hook", "setup", "action", "climax", "payoff"]
            guidance_by_role = {
                "hook": "Mở ngay bằng hình ảnh/động tác gây tò mò; bỏ phần chuẩn bị và giữ khung hình ngắn.",
                "setup": "Thiết lập chủ thể, bối cảnh hoặc vấn đề trong một nhịp gọn trước khi vào thao tác.",
                "action": "Nối các bước quan trọng; cắt bỏ khoảng lặng và giữ liên tục hướng chuyển động.",
                "climax": "Giữ trọn khoảnh khắc tác động hoặc biến đổi mạnh nhất; tránh cắt trước điểm kết thúc.",
                "payoff": "Cho người xem thấy kết quả sau hành động; giữ đủ lâu để đọc được thay đổi cuối.",
            }
            cursor = 0.0
            for group_index, (block_start, block_end) in enumerate(groups):
                group = blocks[block_start:block_end]
                b_start = round(group[0].time_range.start, 3)
                b_end = round(group[-1].time_range.end, 3)
                dur = round(b_end - b_start, 3)
                if dur < 0.1:
                    continue
                role = roles[group_index] if group_count >= 4 else ("hook" if group_index == 0 else ("payoff" if group_index == group_count - 1 else "action"))
                guidance = guidance_by_role.get(role, "Duy trì góc máy ổn định, tập trung vào chi tiết quan trọng nhất.")
                actions = [b.visual_action for b in group if b.visual_action]
                cuts.append(EditCut(
                    order=len(cuts) + 1,
                    role=role,
                    source_start=b_start,
                    source_end=b_end,
                    output_start=round(cursor, 3),
                    output_end=round(cursor + dur, 3),
                    duration=dur,
                    reason=actions[0] if actions else f"Phân đoạn {group_index + 1}",
                    visual_action="; ".join(actions[:3]),
                    suggested_transition="hard_cut",
                    speed_factor=1.0,
                    edit_guidance=guidance,
                ))
                cursor += dur
        if not cuts:
            cuts.append(EditCut(
                order=1,
                role="hook",
                source_start=0.0,
                source_end=round(total_orig, 3),
                output_start=0.0,
                output_end=round(total_orig, 3),
                duration=round(total_orig, 3),
                reason="Toàn bộ video gốc.",
                visual_action=timeline.subject_matter or "Hành động chính trong video",
                suggested_transition="hard_cut",
                speed_factor=1.0,
                edit_guidance="Dùng toàn bộ video gốc, tập trung tạo điểm nhấn bằng lời bình và text overlay súc tích.",
            ))
        target_dur = round(total_orig, 3)
        trimmed_note = "Video nằm trong thời lượng Short; giữ trọn vẹn toàn bộ timeline và tối ưu nhịp dựng qua lời bình."
    else:
        # Video dài đã chọn cảnh
        ordered = sorted(scenes, key=lambda s: s.start)
        cursor = 0.0
        prev_end = None
        for idx, sc in enumerate(ordered):
            sc_dur = round(sc.end - sc.start, 3)
            out_s = round(cursor, 3)
            out_e = round(cursor + sc_dur, 3)

            trans = "hard_cut"
            if prev_end is not None and (sc.start - prev_end) > 5.0:
                trans = "dissolve" if (sc.start - prev_end) > 15.0 else "whip_pan"

            overlapping_actions = [
                b.visual_action for b in blocks
                if max(b.time_range.start, sc.start) < min(b.time_range.end, sc.end) and b.visual_action
            ]
            action_desc = "; ".join(overlapping_actions[:2]) if overlapping_actions else sc.reason

            role = sc.role or ("hook" if idx == 0 else ("payoff" if idx == len(ordered) - 1 else "action"))
            guidance = sc.edit_guidance or (
                "Cắt nhanh vào hành động, bỏ thời gian chết." if role == "hook"
                else ("Giữ nguyên khung hình đúc kết kết quả." if role == "payoff"
                      else "Cắt gọn đầu cuối, đảm bảo không có khung hình rung lắc.")
            )

            cuts.append(EditCut(
                order=len(cuts) + 1,
                role=role,
                source_start=sc.start,
                source_end=sc.end,
                output_start=out_s,
                output_end=out_e,
                duration=sc_dur,
                reason=sc.reason or f"Cảnh {idx + 1}",
                visual_action=action_desc or "",
                suggested_transition=trans,
                speed_factor=1.0,
                edit_guidance=guidance,
            ))
            cursor += sc_dur
            prev_end = sc.end
        target_dur = round(cursor, 3)
        trimmed_sec = max(0.0, round(total_orig - target_dur, 1))
        trimmed_note = f"Đã lược bỏ {trimmed_sec:.1f}s đoạn phụ/thừa trong video gốc để cô đọng câu chuyện thành {target_dur:.1f}s cuốn hút."

    return EditPlan(
        target_duration_seconds=target_dur,
        original_duration_seconds=round(total_orig, 3),
        narrative_strategy=strategy,
        cuts=cuts,
        trimmed_sections_note=trimmed_note,
    )


def rebase_timeline(
    timeline: VisualActionTimeline,
    scenes: List[SceneRange],
) -> VisualActionTimeline:
    """Dồn timeline theo cảnh đã chọn: mốc giây mới bắt đầu từ 0.

    Block nào nằm ngoài cảnh thì bỏ; block giao với cảnh thì cắt theo cảnh
    và dời về vị trí mới. initial_state chỉ giữ khi cảnh đầu bắt đầu từ 0;
    final_outcome chỉ giữ khi cảnh cuối chạm cuối video; nếu không, bỏ để
    khỏi mớm cho LLM nội dung ngoài phần đã chọn.
    """
    ordered = sorted(scenes, key=lambda scene: scene.start)
    new_blocks: List[ActionBlock] = []
    cursor = 0.0
    for scene in ordered:
        for block in timeline.action_timeline or []:
            start = max(block.time_range.start, scene.start)
            end = min(block.time_range.end, scene.end)
            if end - start < _EPSILON:
                continue
            new_blocks.append(
                ActionBlock(
                    time_range=TimeRange(
                        start=round(cursor + (start - scene.start), 3),
                        end=round(cursor + (end - scene.start), 3),
                    ),
                    visual_action=block.visual_action,
                    observable_changes=block.observable_changes,
                    confidence=block.confidence,
                    evidence_source=block.evidence_source,
                )
            )
        cursor += scene.end - scene.start
    first_scene_start = ordered[0].start if ordered else 0.0
    last_scene_end = ordered[-1].end if ordered else 0.0
    return VisualActionTimeline(
        video_id=timeline.video_id,
        duration_seconds=round(cursor, 3),
        subject_matter=timeline.subject_matter,
        initial_state=timeline.initial_state if first_scene_start <= _EPSILON else "",
        action_timeline=new_blocks,
        final_outcome=(
            timeline.final_outcome
            if abs(last_scene_end - timeline.duration_seconds) <= 0.5
            else ""
        ),
        evidence_signals=timeline.evidence_signals,
        selected_template_id=timeline.selected_template_id,
        template_recommendation_reason=timeline.template_recommendation_reason,
        template_selection_source=timeline.template_selection_source,
    )


def covers_full_video(scenes: List[SceneRange], duration_seconds: float) -> bool:
    """True khi cảnh đã chọn thực chất là toàn bộ video (không cần ghép)."""
    if len(scenes) != 1:
        return False
    scene = scenes[0]
    return scene.start <= _EPSILON and abs(scene.end - duration_seconds) <= _EPSILON


def describe_scenes(scenes: List[SceneRange]) -> str:
    """Chuỗi mô tả cảnh theo mốc giây gốc, để ghi vào prompt và nhật ký."""
    return ", ".join(f"{scene.start:.1f}–{scene.end:.1f}s" for scene in scenes)

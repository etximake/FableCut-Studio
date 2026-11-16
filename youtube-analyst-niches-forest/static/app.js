// Commentary Studio - Frontend Logic
let currentSelectedSkill = "curiosity-explainer";
let currentInputMode = "url";
let currentSelectedFile = null;
let currentResult = null;
let currentPlayingSfxBtn = null;
let modelTestResultTimeout = null;
// Batch 2: trạng thái luồng 2 bước
let templateRegistry = [];
let currentAnalysis = null;
let selectedTemplateId = null;
// SPEC-01: theo dõi bản sửa chưa lưu trong giao diện review
let isScriptDirty = false;
let lastSavedAt = null;

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  if (window.location.protocol === "file:") {
    alert("⚠️ CẢNH BÁO: Bạn đang mở trang web dạng file trực tiếp (file:///).\nVui lòng truy cập qua đường link server: http://localhost:8001/ để kết nối được với AI!");
  }
  initDropzone();
  fetchAiStatus();
  fetchSkills();
  fetchTemplates();
  fetchTtsVoices();
  ensureSaveBar();
  // SPEC-01: cảnh báo khi rời trang mà còn thay đổi chưa lưu
  window.addEventListener("beforeunload", (e) => {
    if (isScriptDirty) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
});

async function fetchTemplates() {
  try {
    const response = await fetch("/api/v1/templates");
    const data = await response.json();
    templateRegistry = data.templates || [];
  } catch (error) { console.warn("Template registry unavailable", error); }
}

// Nhãn cảm giác mục tiêu theo template (server trả target_feeling, đây chỉ là nhãn hiển thị).
const FEELING_LABELS = {
  curiosity: "Thu hút / tò mò",
  satisfaction: "Thỏa mãn",
  understanding: "Hiểu ra"
};

// Tín hiệu bắt buộc của từng template, mirror của _TEMPLATE_REQUIRED_SIGNAL
// trong src/analyzer/commentary_engine.py — chỉ dùng để cảnh báo trên giao diện.
const TEMPLATE_REQUIRED_SIGNAL = {
  "before-after": "has_transformation",
  "hazard-rescue": "has_hazard_or_breakdown",
  "shock-hook": "has_surprising_fact",
  "satisfying": "process_is_main_appeal",
  "story": "has_person_story"
};

const SIGNAL_LABELS = {
  has_transformation: "khác biệt trước–sau rõ rệt",
  has_hazard_or_breakdown: "sự cố/hỏng hóc/nguy hiểm",
  has_surprising_fact: "con số/sự thật gây ngạc nhiên",
  has_distinct_steps: "các bước/thao tác phân biệt được",
  has_person_story: "nhân vật trung tâm và câu chuyện của người đó",
  process_is_main_appeal: "quy trình tự thân đã hấp dẫn"
};

function renderTemplateCards() {
  const container = document.getElementById("templateCards");
  if (!container) return;
  container.innerHTML = "";
  const suggestedId = currentAnalysis?.template_recommendation?.template_id;
  templateRegistry.forEach(template => {
    const card = document.createElement("div");
    card.className = `template-card ${template.template_id === selectedTemplateId ? "active" : ""}`;
    card.dataset.templateId = template.template_id;
    card.onclick = () => selectTemplate(template.template_id);
    const feeling = FEELING_LABELS[template.target_feeling] || template.target_feeling || "";
    const suggestedBadge = template.template_id === suggestedId ? '<span class="template-suggested-badge">★ AI gợi ý</span>' : "";
    const bestFor = (template.best_for || []).join(" · ");
    card.innerHTML = `
      <div class="template-card-top">
        <span class="template-card-title">${escapeHtml(template.name_vi || template.name_en || template.template_id)}${suggestedBadge}</span>
        <span class="template-card-feeling">${escapeHtml(feeling)}</span>
      </div>
      <div class="template-card-desc">${escapeHtml(template.purpose || "")}${bestFor ? `<br>Hợp với: ${escapeHtml(bestFor)}` : ""}</div>
    `;
    container.appendChild(card);
  });
  updateTemplateWarning();
}

function selectTemplate(templateId) {
  selectedTemplateId = templateId;
  document.querySelectorAll(".template-card").forEach(c => {
    c.classList.toggle("active", c.dataset.templateId === templateId);
  });
  updateTemplateHint(currentAnalysis?.template_recommendation);
  updateTemplateWarning();
}

function updateTemplateWarning() {
  const warning = document.getElementById("templateWarning");
  if (!warning) return;
  const signals = currentAnalysis?.visual_timeline?.evidence_signals || {};
  const required = TEMPLATE_REQUIRED_SIGNAL[selectedTemplateId];
  if (required && !signals[required]) {
    warning.hidden = false;
    warning.textContent = `Lưu ý: timeline chưa cho thấy ${SIGNAL_LABELS[required]} mà template này cần. Bạn vẫn có thể tiếp tục nếu chắc chắn.`;
  } else {
    warning.hidden = true;
    warning.textContent = "";
  }
}

// Fetch TTS Voices
async function fetchTtsVoices() {
  const select = document.getElementById("ttsVoiceSelect");
  if (!select) return;
  try {
    const res = await fetch("/api/v1/tts/voices");
    const data = await res.json();
    const voices = data.voices || [];
    if (voices.length > 0) {
      select.innerHTML = "";
      voices.forEach(v => {
        const opt = document.createElement("option");
        opt.value = v.id;
        let prefix = "🎙️";
        if (v.id === "am_adam") prefix = "🌾";
        else if (v.id === "bm_george") prefix = "🎬";
        else if (v.id.includes("bella")) prefix = "🌿";
        else if (v.engine === "kokoro_local") prefix = "⚡";

        const badge = v.engine === "kokoro_local" ? "[Local Kokoro]" : "[Cloud Edge]";
        opt.innerText = `${prefix} ${v.name} ${badge}`;
        if (v.recommended || v.id === "am_adam") opt.selected = true;
        select.appendChild(opt);
      });
    }
  } catch (err) {
    console.error("Failed to fetch TTS voices:", err);
  }
}

function toggleTTSConfig(enabled) {
  const container = document.getElementById("ttsOptionsContainer");
  if (container) {
    container.style.display = enabled ? "block" : "none";
  }
}

function handleLanguageChange(lang) {
  const voiceSelect = document.getElementById("ttsVoiceSelect");
  if (!voiceSelect) return;
  if (lang === "vi") {
    for (let i = 0; i < voiceSelect.options.length; i++) {
      if (voiceSelect.options[i].value.startsWith("vi-")) {
        voiceSelect.selectedIndex = i;
        break;
      }
    }
  } else {
    for (let i = 0; i < voiceSelect.options.length; i++) {
      if (voiceSelect.options[i].value === "am_adam") {
        voiceSelect.selectedIndex = i;
        break;
      }
    }
  }
}

// Toast Notification
function showToast(message) {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerText = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    toast.style.transition = "all 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 2500);
}

// Fetch AI Status
async function fetchAiStatus() {
  try {
    const res = await fetch("/api/v1/ai/status");
    const data = await res.json();
    const pill = document.getElementById("aiStatusPill");
    const text = document.getElementById("aiStatusText");
    if (data.status === "ONLINE") {
      text.innerText = `AI: ${data.primary_provider} (${data.vision_model})`;
    }
  } catch (err) {
    console.error("AI Status error:", err);
  }
}

function updateTemplateHint(recommendation = null) {
  const note = document.getElementById("templateRecommendationNote");
  if (!note) return;
  if (selectedTemplateId && recommendation && selectedTemplateId !== recommendation.template_id) {
    note.textContent = `Bạn đã chọn template ${selectedTemplateId} (AI gợi ý ${recommendation.template_id}). ${recommendation.reason || ""}`;
  } else if (recommendation?.reason) {
    note.textContent = `Gợi ý: ${recommendation.template_id}. ${recommendation.reason}`;
  } else if (selectedTemplateId) {
    note.textContent = `Template đã chọn: ${selectedTemplateId}.`;
  } else {
    note.textContent = "Hệ thống sẽ gợi ý template sau khi phân tích xong.";
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

async function testAiModel(modelType, button) {
  const result = document.getElementById("modelTestResult");
  const buttons = document.querySelectorAll(".model-test-btn");
  if (modelTestResultTimeout) {
    clearTimeout(modelTestResultTimeout);
    modelTestResultTimeout = null;
  }
  buttons.forEach(item => { item.disabled = true; });
  result.hidden = false;
  result.setAttribute("aria-busy", "true");
  button.textContent = "Đang test…";
  result.className = "model-test-result";
  result.textContent = `⏳ Đang kiểm tra model ${modelType.toUpperCase()}…`;
  try {
    const response = await fetch(`/api/v1/ai/test/${modelType}`, { method: "POST" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Yêu cầu kiểm tra thất bại.");
    result.classList.add(data.ok ? "success" : "failure");
    result.textContent = `${data.ok ? "✅ THÀNH CÔNG" : "❌ THẤT BẠI"} · ${modelType.toUpperCase()} · ${data.model || "model chưa xác định"}: ${data.message || "Không nhận được kết quả kiểm tra."}${data.elapsed_ms == null ? "" : ` (${data.elapsed_ms} ms)`}`;
  } catch (error) {
    result.classList.add("failure");
    result.textContent = `❌ THẤT BẠI · ${modelType.toUpperCase()}: ${error.message || "Không kết nối được máy chủ."}`;
  } finally {
    result.removeAttribute("aria-busy");
    buttons.forEach(item => {
      item.disabled = false;
      item.textContent = item.dataset.model === "vision" ? "Test Vision" : "Test Text";
    });
    modelTestResultTimeout = setTimeout(() => {
      result.hidden = true;
      modelTestResultTimeout = null;
    }, 2000);
  }
}

// Fetch Skills Registry
async function fetchSkills() {
  const container = document.getElementById("skillsContainer");
  try {
    const res = await fetch("/api/v1/skills");
    const data = await res.json();
    const skills = data.skills || [];
    
    if (skills.length === 0) {
      container.innerHTML = '<div class="empty-placeholder">Không có skill nào.</div>';
      return;
    }

    container.innerHTML = "";
    skills.forEach((s, idx) => {
      const card = document.createElement("div");
      card.className = `skill-card ${s.skill_id === currentSelectedSkill ? "active" : ""}`;
      card.dataset.skillId = s.skill_id;
      card.onclick = () => selectSkill(s.skill_id);

      card.innerHTML = `
        <div class="skill-card-top">
          <span class="skill-card-title">${s.display_name}</span>
          <span class="skill-card-wpm">~${s.target_wpm} WPM</span>
        </div>
        <div class="skill-card-desc">${s.description}</div>
      `;
      container.appendChild(card);
    });

    updateActiveSkillBadge();
  } catch (err) {
    container.innerHTML = '<div class="empty-placeholder">Lỗi tải danh sách skills.</div>';
  }
}

function selectSkill(skillId) {
  currentSelectedSkill = skillId;
  document.querySelectorAll(".skill-card").forEach(c => {
    if (c.dataset.skillId === skillId) {
      c.classList.add("active");
    } else {
      c.classList.remove("active");
    }
  });
  updateActiveSkillBadge();
}

function updateActiveSkillBadge() {
  const badge = document.getElementById("activeSkillBadge");
  const activeCard = document.querySelector(`.skill-card[data-skill-id="${currentSelectedSkill}"] .skill-card-title`);
  if (activeCard) {
    badge.innerText = activeCard.innerText.split("(")[0].trim();
  }
}

// Input Mode Switcher
function switchInputMode(mode) {
  currentInputMode = mode;
  const tabUrl = document.getElementById("tabUrlBtn");
  const tabFile = document.getElementById("tabFileBtn");
  const groupUrl = document.getElementById("inputUrlGroup");
  const groupFile = document.getElementById("inputFileGroup");

  if (mode === "url") {
    tabUrl.classList.add("active");
    tabFile.classList.remove("active");
    groupUrl.style.display = "block";
    groupFile.style.display = "none";
  } else {
    tabUrl.classList.remove("active");
    tabFile.classList.add("active");
    groupUrl.style.display = "none";
    groupFile.style.display = "block";
  }
}

// Drag & Drop File Handler
function initDropzone() {
  const dropzone = document.getElementById("videoDropzone");
  
  ["dragenter", "dragover"].forEach(event => {
    dropzone.addEventListener(event, (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(event => {
    dropzone.addEventListener(event, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files);
    }
  });
}

function handleFileSelected(files) {
  if (!files || files.length === 0) return;
  currentSelectedFile = files[0];
  const nameDisplay = document.getElementById("selectedFileName");
  nameDisplay.innerText = `Đã chọn: ${currentSelectedFile.name} (${(currentSelectedFile.size / (1024 * 1024)).toFixed(1)} MB)`;
}

// Batch 2 — Bước 1: phân tích video (Vision mù), chưa viết kịch bản.
async function analyzeVideo() {
  const btn = document.getElementById("btnAnalyze");
  const btnText = document.getElementById("btnAnalyzeText");

  let videoUrl = null;
  let videoPath = null;

  if (currentInputMode === "url") {
    videoUrl = document.getElementById("videoUrlInput").value.trim();
    if (!videoUrl) {
      alert("Vui lòng nhập link video YouTube Shorts, TikTok hoặc Reels!");
      return;
    }
  } else if (!currentSelectedFile) {
    alert("Vui lòng chọn hoặc kéo thả 1 file video MP4!");
    return;
  }

  btn.disabled = true;
  btnText.innerHTML = '<span class="spinner"></span> Đang tạo Contact Sheet & Lập Timeline...';

  try {
    if (currentInputMode === "file" && currentSelectedFile) {
      btnText.innerHTML = '<span class="spinner"></span> Đang tải video lên server...';
      const formData = new FormData();
      formData.append("file", currentSelectedFile);
      const uploadRes = await fetch("/api/v1/commentary/upload-video", {
        method: "POST",
        body: formData
      });
      if (!uploadRes.ok) throw new Error("Lỗi tải video lên server.");
      const uploadData = await uploadRes.json();
      videoPath = uploadData.video_path;
    }

    btnText.innerHTML = '<span class="spinner"></span> AI đang quan sát ảnh lưới...';

    const res = await fetch("/api/v1/commentary/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_url: videoUrl, video_path: videoPath })
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Phân tích video thất bại.");
    }

    const data = await res.json();
    currentAnalysis = data;
    currentResult = data;
    selectedTemplateId = data.template_recommendation?.template_id || null;
    lastSavedAt = null;
    isScriptDirty = false;

    const narratorSelect = document.getElementById("narratorSelect");
    if (narratorSelect && data.narrator_mode) narratorSelect.value = data.narrator_mode;

    renderAnalysisResult(data);
    renderTemplateCards();
    updateTemplateHint(data.template_recommendation);
    document.getElementById("step2Section").style.display = "block";
    // Xóa kịch bản cũ khỏi cột biên tập: video mới chưa có kịch bản.
    document.getElementById("segmentsList").innerHTML = '<div class="empty-placeholder">Xem timeline ở cột giữa, chốt template ở cột trái, rồi bấm "Viết kịch bản".</div>';
    document.getElementById("metaDuration").innerText = `${Math.round(data.visual_timeline.duration_seconds || 0)}s`;
    document.getElementById("metaTotalWords").innerText = "0";
    document.getElementById("metaWpm").innerText = "0 WPM";
    document.getElementById("voiceoverPlayerBox").style.display = "none";
    showToast("Phân tích xong! Xem timeline rồi chốt template ở bước 2.");

  } catch (err) {
    let msg = err.message || "Đã xảy ra lỗi không xác định.";
    if (err.name === "TypeError" && msg.includes("fetch")) {
      msg = "Không thể kết nối đến máy chủ API (Failed to fetch).\n\nNguyên nhân có thể là:\n1. Server chưa được bật. Vui lòng chạy '.\\run.bat' trên terminal.\n2. Bạn đang mở sai cổng. Hãy chắc chắn URL trên trình duyệt là: " + window.location.origin + "\n3. File tải lên quá lớn hoặc mạng bị gián đoạn.";
    }
    alert("❌ Lỗi: " + msg);
  } finally {
    btn.disabled = false;
    btnText.innerText = "Bước 1: Phân tích video";
  }
}

function getDescriptionPayload() {
  return {
    description_subject: document.getElementById("descriptionSubjectInput")?.value.trim() || null,
    description_activity: document.getElementById("descriptionActivityInput")?.value.trim() || null,
    description_focus: document.getElementById("descriptionFocusInput")?.value.trim() || null
  };
}

// Batch 2 — Bước 2: viết kịch bản theo template đã chốt.
async function generateScriptFromAnalysis() {
  if (!currentAnalysis || !currentAnalysis.video_id) {
    alert("Vui lòng phân tích 1 video ở bước 1 trước!");
    return;
  }

  // Viết lại thay toàn bộ kịch bản, hỏi trước khi làm mất bản sửa chưa lưu.
  if (isScriptDirty && !confirm("Bạn có thay đổi chưa lưu. Viết kịch bản mới sẽ thay toàn bộ kịch bản và mất các sửa đổi. Tiếp tục?")) {
    return;
  }

  const btn = document.getElementById("btnGenerateScript");
  const btnText = document.getElementById("btnGenerateScriptText");
  const language = document.getElementById("languageSelect").value;
  const enableTts = document.getElementById("ttsToggle").checked;
  const ttsVoice = document.getElementById("ttsVoiceSelect").value;
  const ttsSpeed = parseFloat(document.getElementById("ttsSpeedRange").value) || 1.0;

  btn.disabled = true;
  btnText.innerHTML = '<span class="spinner"></span> AI đang viết kịch bản...';

  try {
    const res = await fetch("/api/v1/commentary/generate-script", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        video_id: currentAnalysis.video_id,
        skill_id: currentSelectedSkill,
        template_id: selectedTemplateId,
        ...getDescriptionPayload(),
        narrator_mode: document.getElementById("narratorSelect")?.value || null,
        language: language,
        enable_tts: enableTts,
        tts_voice: ttsVoice,
        tts_speed: ttsSpeed,
        content_only: false
      })
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Viết kịch bản thất bại.");
    }

    const data = await res.json();
    currentResult.capcut_json = data.capcut_json;
    currentResult.template_recommendation = data.template_recommendation;
    currentResult.review_notes = data.review_notes || [];
    currentResult.story_angle = data.story_angle;
    lastSavedAt = null;
    renderCommentarySegments(data.capcut_json);

    const notes = document.getElementById("reviewNotes");
    if (notes) {
      const items = [
        ...(data.story_angle ? [`Góc kể: ${data.story_angle}`] : []),
        ...(data.template_recommendation?.reason ? [`${data.template_recommendation.source === "manual" ? "Template người dùng chọn" : "Lý do gợi ý template"}: ${data.template_recommendation.reason}`] : []),
        ...(data.review_notes || [])
      ];
      notes.hidden = items.length === 0;
      notes.innerHTML = items.map(item => `<p>${escapeHtml(item)}</p>`).join("");
    }

    const playerBox = document.getElementById("voiceoverPlayerBox");
    const audioPlayer = document.getElementById("voiceoverAudioPlayer");
    const voiceBadge = document.getElementById("voiceNameBadge");
    if (enableTts) {
      playerBox.style.display = "block";
      audioPlayer.src = `/api/v1/commentary/${currentAnalysis.video_id}/audio?t=${Date.now()}`;
      const selectedVoiceOpt = document.getElementById("ttsVoiceSelect");
      const voiceText = selectedVoiceOpt ? selectedVoiceOpt.options[selectedVoiceOpt.selectedIndex].text : "AI Voice";
      voiceBadge.innerText = voiceText.replace(/[🌾🎬🌿🎙️📖📻⚡]/g, "").trim();
    } else {
      playerBox.style.display = "none";
    }

    showToast("Đã viết kịch bản theo template đã chốt!");
  } catch (err) {
    alert("❌ Lỗi: " + (err.message || "Đã xảy ra lỗi không xác định."));
  } finally {
    btn.disabled = false;
    btnText.innerText = "Viết kịch bản theo template đã chốt";
  }
}

// Render kết quả phân tích (bước 1): contact sheet, âm thanh, timeline, ghi chú.
function renderAnalysisResult(data) {
  const recommendation = data.template_recommendation;
  // 1. Render Contact Sheet 3x3
  const img = document.getElementById("contactSheetImg");
  const placeholder = document.getElementById("contactSheetPlaceholder");

  if (data.contact_sheet_url) {
    img.src = `${data.contact_sheet_url}?t=${Date.now()}`;
    img.style.display = "block";
    placeholder.style.display = "none";
  }

  // 2. Render Audio Hint
  const audioBadge = document.getElementById("audioStatusBadge");
  const audioSnippet = document.getElementById("audioSnippetText");
  const audioGuidance = document.getElementById("audioGuidanceText");

  if (data.audio_hint) {
    const ah = data.audio_hint;
    audioBadge.innerText = ah.status;
    audioBadge.className = "audio-badge";
    if (ah.status === "COMPLETE") {
      audioBadge.classList.add("badge-complete");
    } else if (ah.status.includes("TRUNCATED")) {
      audioBadge.classList.add("badge-truncated");
    } else {
      audioBadge.classList.add("badge-none");
    }

    audioSnippet.innerText = ah.clean_text ? `"${ah.clean_text}"` : '"(Không có giọng nói / Nhạc nền)"';
    audioGuidance.innerText = ah.guidance || "";
  }

  // 3. Render Visual Timeline
  const timelineList = document.getElementById("timelineList");
  if (data.visual_timeline && data.visual_timeline.action_timeline) {
    timelineList.innerHTML = "";
    data.visual_timeline.action_timeline.forEach(item => {
      const el = document.createElement("div");
      el.className = "timeline-item";
      const evidence = document.createElement("div");
      evidence.className = "timeline-evidence-tag";
      evidence.textContent = `${item.evidence_source || "unknown"} · tin cậy ${Math.round((item.confidence ?? 0) * 100)}%`;
      const action = document.createElement("textarea");
      action.className = "timeline-item-action timeline-edit";
      action.value = item.visual_action || "";
      action.setAttribute("aria-label", `Sự kiện ${formatSeconds(item.time_range.start)}: mô tả`);
      action.addEventListener("change", () => updateTimelineEvent(data.video_id, item, action.value));
      const source = document.createElement("select");
      source.className = "form-control timeline-source-select";
      [["observed", "Đã thấy"], ["heard", "Từ âm thanh"], ["inferred", "Suy luận"], ["unknown", "Chưa rõ"]].forEach(([value, label]) => {
        const option = document.createElement("option"); option.value = value; option.textContent = label;
        option.selected = (item.evidence_source || "unknown") === value; source.appendChild(option);
      });
      source.addEventListener("change", () => updateTimelineEvent(data.video_id, item, action.value, source.value));
      const time = document.createElement("div");
      time.className = "timeline-item-time";
      time.textContent = `[${formatSeconds(item.time_range.start)} - ${formatSeconds(item.time_range.end)}]`;
      el.append(time, evidence, action, source);
      timelineList.appendChild(el);
    });
  }

  const notes = document.getElementById("reviewNotes");
  if (notes) {
    const items = [
      ...(recommendation?.reason ? [`Lý do gợi ý template: ${recommendation.reason}`] : []),
      ...(data.review_notes || [])
    ];
    notes.hidden = items.length === 0;
    notes.innerHTML = items.map(item => `<p>${escapeHtml(item)}</p>`).join("");
  }
}

async function updateTimelineEvent(videoId, item, description, evidenceSource = item.evidence_source || "unknown") {
  const index = currentResult?.visual_timeline?.action_timeline?.indexOf(item);
  if (!videoId || index == null || index < 0) return;
  try {
    const response = await fetch(`/api/v1/commentary/${encodeURIComponent(videoId)}/analysis`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: { [index]: { visual_action: description, evidence_source: evidenceSource } } })
    });
    if (!response.ok) throw new Error("Không lưu được chỉnh sửa phân tích.");
    item.visual_action = description;
    item.evidence_source = evidenceSource;
    showToast("Đã lưu chỉnh sửa phân tích.");
  } catch (error) {
    const notes = document.getElementById("reviewNotes");
    if (notes) { notes.hidden = false; notes.textContent = error.message; }
  }
}

// Render Commentary Segments
function renderCommentarySegments(capcutJson) {
  if (!capcutJson) return;

  if (Array.isArray(currentResult?.review_notes)) {
    const notes = document.getElementById("reviewNotes");
    if (notes) {
      notes.hidden = currentResult.review_notes.length === 0;
      notes.innerHTML = currentResult.review_notes.map(item => `<p>${escapeHtml(item)}</p>`).join("");
    }
  }

  // SPEC-01: nội dung vừa render là trạng thái mới nhất từ server -> hết "chưa lưu"
  isScriptDirty = false;
  updateSaveStatus();

  const meta = capcutJson.video_metadata || {};
  document.getElementById("metaDuration").innerText = `${meta.duration_seconds || 45}s`;
  document.getElementById("metaTotalWords").innerText = meta.total_words || 0;
  
  const wpmBadge = document.getElementById("metaWpm");
  wpmBadge.innerText = `${meta.average_wpm || 0} WPM`;
  if (meta.average_wpm >= 115 && meta.average_wpm <= 150) {
    wpmBadge.className = "wpm-badge wpm-good";
  } else {
    wpmBadge.className = "wpm-badge wpm-fast";
  }

  const container = document.getElementById("segmentsList");
  container.innerHTML = "";

  (capcutJson.segments || []).forEach((seg, idx) => {
    const card = document.createElement("div");
    card.className = "segment-card";

    const sfxId = seg.sfx_cue?.suggested_sfx || null;
    const sfxName = sfxId ? sfxId.replace(/_/g, " ").toUpperCase() : "NO SFX";
    const overlayText = seg.text_overlay ? seg.text_overlay.text : "";
    const viText = seg.voiceover_vi_translation || seg.voiceover;

    card.innerHTML = `
      <div class="segment-header">
        <span class="beat-tag beat-${seg.beat}">[${seg.beat}]</span>
        <span class="segment-time">${formatSeconds(seg.time_range.start)} - ${formatSeconds(seg.time_range.end)}</span>
      </div>
      <textarea class="segment-textarea" oninput="updateSegmentVoiceover(${idx}, this.value)" placeholder="Câu lời bình (Voiceover)...">${seg.voiceover}</textarea>
      
      <!-- Khung Phụ đề Gợi ý Dịch nghĩa Tiếng Việt -->
      <div class="segment-vi-box">
        <div class="segment-vi-header">
          <span>🇻🇳</span>
          <span>GỢI Ý DỊCH TIẾNG VIỆT (SUBTITLE):</span>
        </div>
        <div class="segment-vi-text" contenteditable="true" onblur="updateSegmentViTranslation(${idx}, this.innerText)" title="Click để chỉnh sửa phụ đề tiếng Việt nếu muốn">${viText}</div>
      </div>

      <div class="segment-footer">
        <div class="text-overlay-pill" title="Chữ hiển thị trên màn hình">
          <span>🔤</span>
          <strong>${overlayText}</strong>
        </div>
        ${sfxId ? `<button type="button" class="sfx-player-btn" onclick="playSfx('${sfxId}', this)" title="Nghe thử âm thanh SFX">` : `<span class="sfx-player-btn">`}
          <span>🔊</span>
          <span>${sfxName}</span>
        ${sfxId ? `</button>` : `</span>`}
      </div>
      <button type="button" class="segment-rewrite-btn" onclick="rewriteOneSegment(${idx}, this)">Viết lại beat này</button>
    `;
    container.appendChild(card);
  });
}

async function rewriteOneSegment(index, button) {
  if (!currentResult?.video_id) return;
  const card = button.closest(".segment-card");
  const voiceover = card?.querySelector(".segment-textarea")?.value || "";
  button.disabled = true;
  try {
    const response = await fetch("/api/v1/commentary/rewrite-segment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_id: currentResult.video_id, segment_index: index, current_voiceover: voiceover, instruction: "Improve clarity while preserving the claim scope.", skill_id: currentSelectedSkill, language: document.getElementById("languageSelect").value })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Không thể viết lại beat.");
    currentResult.capcut_json.segments[index] = data.segment;
    isScriptDirty = true;
    renderCommentarySegments(currentResult.capcut_json);
    markScriptDirty();
  } catch (error) {
    const notes = document.getElementById("reviewNotes");
    if (notes) { notes.hidden = false; notes.textContent = error.message; }
  } finally { button.disabled = false; }
}

function updateSegmentViTranslation(index, newText) {
  if (!currentResult || !currentResult.capcut_json) return;
  const segments = currentResult.capcut_json.segments;
  if (segments && segments[index]) {
    segments[index].voiceover_vi_translation = newText.trim();
    markScriptDirty();
  }
}

function updateSegmentVoiceover(index, newText) {
  if (!currentResult || !currentResult.capcut_json) return;
  const segments = currentResult.capcut_json.segments;
  if (segments && segments[index]) {
    segments[index].voiceover = newText;
    markScriptDirty();
  }

  // Recalculate Words and WPM
  const totalWords = segments.reduce((sum, s) => sum + s.voiceover.trim().split(/\s+/).filter(Boolean).length, 0);
  const duration = currentResult.capcut_json.video_metadata.duration_seconds || 45;
  const wpm = Math.round((totalWords / duration) * 60);

  document.getElementById("metaTotalWords").innerText = totalWords;
  const wpmBadge = document.getElementById("metaWpm");
  wpmBadge.innerText = `${wpm} WPM`;
  wpmBadge.className = (wpm >= 115 && wpm <= 150) ? "wpm-badge wpm-good" : "wpm-badge wpm-fast";
}

// SPEC-01: nút Lưu bản sửa + trạng thái "Chưa lưu / Đã lưu lúc HH:MM"
function ensureSaveBar() {
  if (document.getElementById("btnSaveScript")) return;
  const actions = document.querySelector(".studio-actions");
  if (!actions) return;
  const status = document.createElement("span");
  status.id = "saveScriptStatus";
  status.style.cssText = "align-self:center;font-size:13px;opacity:0.85;";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn-secondary";
  btn.id = "btnSaveScript";
  btn.innerHTML = "<span>💾</span> <span>Lưu bản sửa</span>";
  btn.onclick = saveEditedScript;
  actions.prepend(status);
  actions.prepend(btn);
  updateSaveStatus();
}

function updateSaveStatus() {
  const el = document.getElementById("saveScriptStatus");
  if (!el) return;
  if (isScriptDirty) {
    el.innerText = "● Chưa lưu thay đổi";
  } else if (lastSavedAt) {
    el.innerText = `Đã lưu lúc ${lastSavedAt}`;
  } else {
    el.innerText = "";
  }
}

function markScriptDirty() {
  if (!isScriptDirty) {
    isScriptDirty = true;
    updateSaveStatus();
  }
}

// SPEC-01: lưu bản kịch bản đã sửa lên server (append phiên bản mới, không ghi đè)
async function saveEditedScript() {
  if (!currentResult || !currentResult.video_id || !currentResult.capcut_json) {
    showToast("Chưa có kịch bản để lưu!");
    return false;
  }

  const script = currentResult.capcut_json;
  // Cập nhật lại tổng số từ / WPM trong metadata theo đúng nội dung đã sửa
  const totalWords = (script.segments || []).reduce((sum, s) => sum + (s.voiceover || "").trim().split(/\s+/).filter(Boolean).length, 0);
  const duration = script.video_metadata.duration_seconds || 45;
  script.video_metadata.total_words = totalWords;
  script.video_metadata.average_wpm = Math.round((totalWords / duration) * 60);

  const btn = document.getElementById("btnSaveScript");
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`/api/v1/commentary/${currentResult.video_id}/script`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(script)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Lưu bản sửa thất bại.");
    }
    await res.json();
    isScriptDirty = false;
    lastSavedAt = new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
    updateSaveStatus();
    showToast("Đã lưu bản sửa!");
    return true;
  } catch (err) {
    alert("Lỗi lưu bản sửa: " + err.message);
    return false;
  } finally {
    if (btn) btn.disabled = false;
  }
}

// SFX Audio Playback
function playSfx(sfxId, btn) {
  const audio = document.getElementById("sfxAudioPlayer");
  
  if (currentPlayingSfxBtn === btn && !audio.paused) {
    audio.pause();
    btn.classList.remove("playing");
    btn.querySelector("span:first-child").innerText = "🔊";
    currentPlayingSfxBtn = null;
    return;
  }

  if (currentPlayingSfxBtn) {
    currentPlayingSfxBtn.classList.remove("playing");
    currentPlayingSfxBtn.querySelector("span:first-child").innerText = "🔊";
  }

  audio.src = `/api/v1/sfx/audio/${sfxId}`;
  audio.play().then(() => {
    btn.classList.add("playing");
    btn.querySelector("span:first-child").innerText = "⏹️";
    currentPlayingSfxBtn = btn;
  }).catch(err => {
    console.error("Audio playback error:", err);
    showToast("Không thể phát SFX");
  });

  audio.onended = () => {
    btn.classList.remove("playing");
    btn.querySelector("span:first-child").innerText = "🔊";
    currentPlayingSfxBtn = null;
  };
}

// Quick Rewrite with New Skill (Sub-second response, ~400 tokens)
async function handleQuickRewrite() {
  if (!currentResult || !currentResult.video_id) {
    alert("Vui lòng phân tích 1 video trước khi viết lại!");
    return;
  }

  // SPEC-01: viết lại thay toàn bộ kịch bản, hỏi trước khi làm mất bản sửa chưa lưu
  if (isScriptDirty && !confirm("Bạn có thay đổi chưa lưu. Viết lại sẽ thay toàn bộ kịch bản bằng bản mới và mất các sửa đổi. Tiếp tục?")) {
    return;
  }

  const btn = document.getElementById("btnRewrite");
  btn.disabled = true;
  btn.innerHTML = '<span>⏳</span> Đang đổi phong cách & thu âm...';

  const language = document.getElementById("languageSelect").value;
  const enableTts = document.getElementById("ttsToggle").checked;
  const ttsVoice = document.getElementById("ttsVoiceSelect").value;
  const ttsSpeed = parseFloat(document.getElementById("ttsSpeedRange").value) || 1.0;

  try {
    const res = await fetch("/api/v1/commentary/generate-script", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        video_id: currentResult.video_id,
        skill_id: currentSelectedSkill,
        template_id: selectedTemplateId,
        ...getDescriptionPayload(),
        narrator_mode: document.getElementById("narratorSelect")?.value || null,
        language: language,
        enable_tts: enableTts,
        tts_voice: ttsVoice,
        tts_speed: ttsSpeed,
        content_only: true
      })
    });

    if (!res.ok) throw new Error("Viết lại thất bại.");

    const rewriteData = await res.json();
    const newScript = rewriteData.capcut_json || rewriteData;
    currentResult.capcut_json = newScript;
    if (rewriteData.template_recommendation) {
      currentResult.template_recommendation = rewriteData.template_recommendation;
      updateTemplateHint(rewriteData.template_recommendation);
    }
    currentResult.review_notes = rewriteData.review_notes || [];
    lastSavedAt = null;
    renderCommentarySegments(newScript);

    // Cập nhật lại audio player nếu có TTS
    if (enableTts) {
      const playerBox = document.getElementById("voiceoverPlayerBox");
      const audioPlayer = document.getElementById("voiceoverAudioPlayer");
      playerBox.style.display = "block";
      audioPlayer.src = `/api/v1/commentary/${currentResult.video_id}/audio?t=${Date.now()}`;
    }

    showToast("Đã đổi giọng điệu kịch bản & cập nhật Voiceover thành công!");

  } catch (err) {
    alert("Lỗi viết lại: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>🔄</span> <span>Viết lại với Skill khác (1s)</span>';
  }
}

// Regenerate TTS Voiceover for Edited Script
async function regenerateTTSVoiceover() {
  if (!currentResult || !currentResult.video_id) {
    alert("Vui lòng phân tích 1 video trước khi tạo giọng đọc!");
    return;
  }

  // SPEC-01: lưu bản sửa trước khi tạo lại giọng đọc, để TTS đọc đúng bản đã sửa.
  // Lưu thất bại thì dừng, không chạy TTS bằng kịch bản cũ.
  if (isScriptDirty) {
    const saved = await saveEditedScript();
    if (!saved) return;
  }

  const btn = document.getElementById("btnRegenTTS");
  const btnText = document.getElementById("btnRegenTTSText");
  btn.disabled = true;
  btnText.innerHTML = '<span class="spinner"></span> Đang thu âm AI...';

  const ttsVoice = document.getElementById("ttsVoiceSelect").value;
  const ttsSpeed = parseFloat(document.getElementById("ttsSpeedRange").value) || 1.0;

  try {
    const res = await fetch("/api/v1/tts/synthesize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        video_id: currentResult.video_id,
        voice: ttsVoice,
        speed: ttsSpeed
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Không thể tạo giọng đọc.");
    }

    const data = await res.json();
    if (data.capcut_json) {
      currentResult.capcut_json = data.capcut_json;
      renderCommentarySegments(data.capcut_json);
    }

    const playerBox = document.getElementById("voiceoverPlayerBox");
    const audioPlayer = document.getElementById("voiceoverAudioPlayer");
    const voiceBadge = document.getElementById("voiceNameBadge");

    playerBox.style.display = "block";
    audioPlayer.src = `${data.audio_url}?t=${Date.now()}`;
    audioPlayer.play().catch(() => {});

    const selectedVoiceOpt = document.getElementById("ttsVoiceSelect");
    const voiceText = selectedVoiceOpt ? selectedVoiceOpt.options[selectedVoiceOpt.selectedIndex].text : data.voice;
    voiceBadge.innerText = voiceText.replace(/[🌾🎬🌿🎙️📖📻⚡]/g, "").trim();

    showToast("Đã tạo giọng đọc Voiceover & khớp lại timeline thành công!");
  } catch (err) {
    alert("Lỗi tạo giọng đọc: " + err.message);
  } finally {
    btn.disabled = false;
    btnText.innerText = "Tạo lại Giọng Đọc";
  }
}

// Download Full ZIP Bundle
function downloadZipBundle() {
  if (!currentResult || !currentResult.video_id) {
    showToast("Chưa có video để tải gói ZIP!");
    return;
  }
  showToast("Đang chuẩn bị gói ZIP, vui lòng đợi...");
  window.open(`/api/v1/commentary/${currentResult.video_id}/export?format=bundle_zip`, "_blank");
}

// Download Contact Sheet 3x3 Image
function downloadContactSheet() {
  if (!currentResult || !currentResult.video_id) {
    showToast("Chưa có video để tải Contact Sheet!");
    return;
  }
  window.open(`/api/v1/commentary/${currentResult.video_id}/export?format=contact_sheet`, "_blank");
}

// Download Thumbnail Image
function downloadThumbnail() {
  if (!currentResult || !currentResult.video_id) {
    showToast("Chưa có video để tải Thumbnail!");
    return;
  }
  window.open(`/api/v1/commentary/${currentResult.video_id}/export?format=thumbnail`, "_blank");
}

// Download Video Source File
function downloadVideoSource() {
  if (!currentResult || !currentResult.video_id) {
    showToast("Chưa có video gốc để tải!");
    return;
  }
  window.open(`/api/v1/commentary/${currentResult.video_id}/export?format=video`, "_blank");
}

// Download Voiceover Audio File
function downloadVoiceoverAudio() {
  if (!currentResult || !currentResult.video_id) {
    showToast("Chưa có video để tải âm thanh!");
    return;
  }
  window.open(`/api/v1/commentary/${currentResult.video_id}/export?format=audio`, "_blank");
}

// Copy All Voiceovers to Clipboard
function copyAllVoiceovers() {
  if (!currentResult || !currentResult.capcut_json || !currentResult.capcut_json.segments) {
    showToast("Chưa có kịch bản để copy!");
    return;
  }

  const lines = currentResult.capcut_json.segments.map(s => s.voiceover.trim());
  const fullText = lines.join("\n\n");
  navigator.clipboard.writeText(fullText).then(() => {
    showToast("Đã copy toàn bộ Voiceover vào Clipboard!");
  }).catch(() => {
    showToast("Lỗi khi copy vào clipboard.");
  });
}

// Download CapCut JSON
function downloadCapCutJson() {
  if (!currentResult || !currentResult.capcut_json) {
    showToast("Chưa có kịch bản để tải!");
    return;
  }

  const jsonStr = JSON.stringify(currentResult.capcut_json, null, 2);
  const blob = new Blob([jsonStr], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${currentResult.video_id}_commentary.capcut.json`;
  a.click();
  URL.revokeObjectURL(url);
  showToast("Đã tải file CapCut JSON!");
}

// Download SRT Gốc
function downloadSrt() {
  if (!currentResult || !currentResult.video_id) {
    showToast("Chưa có video để tải SRT!");
    return;
  }
  window.open(`/api/v1/commentary/${currentResult.video_id}/export?format=srt`, "_blank");
}

// Download SRT Phụ đề Tiếng Việt
function downloadSrtVi() {
  if (!currentResult || !currentResult.video_id) {
    showToast("Chưa có video để tải phụ đề tiếng Việt!");
    return;
  }
  window.open(`/api/v1/commentary/${currentResult.video_id}/export?format=srt_vi`, "_blank");
}

function openContactSheetModal() {
  const img = document.getElementById("contactSheetImg");
  if (img && img.src) {
    window.open(img.src, "_blank");
  }
}

function formatSeconds(secs) {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  const ms = Math.floor((secs % 1) * 10);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}.${ms}`;
}

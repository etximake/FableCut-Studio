// Commentary Studio - Frontend Logic
let currentSelectedSkill = "curiosity-explainer";
let currentInputMode = "url";
let currentSelectedFile = null;
let currentResult = null;
let currentPlayingSfxBtn = null;

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
});

async function fetchTemplates() {
  const select = document.getElementById("templateSelect");
  if (!select) return;
  try {
    const response = await fetch("/api/v1/templates");
    const data = await response.json();
    (data.templates || []).forEach(template => {
      const option = document.createElement("option");
      option.value = template.template_id;
      option.textContent = template.name_vi || template.name_en || template.template_id;
      select.appendChild(option);
    });
  } catch (error) { console.warn("Template registry unavailable", error); }
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

// Submit Process Video
async function submitVideoProcess() {
  const btn = document.getElementById("btnProcess");
  const btnText = document.getElementById("btnProcessText");
  const language = document.getElementById("languageSelect").value;

  let videoUrl = null;
  let videoPath = null;

  if (currentInputMode === "url") {
    videoUrl = document.getElementById("videoUrlInput").value.trim();
    if (!videoUrl) {
      alert("Vui lòng nhập link video YouTube Shorts, TikTok hoặc Reels!");
      return;
    }
  } else {
    if (!currentSelectedFile) {
      alert("Vui lòng chọn hoặc kéo thả 1 file video MP4!");
      return;
    }
  }

  // Set Loading State
  btn.disabled = true;
  btnText.innerHTML = '<span class="spinner"></span> Đang tạo Contact Sheet & Lập Timeline...';

  try {
    // Nếu là file, upload lên server trước
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

    btnText.innerHTML = '<span class="spinner"></span> AI đang quan sát ảnh lưới, biên kịch & thu âm...';

    const enableTts = document.getElementById("ttsToggle").checked;
    const ttsVoice = document.getElementById("ttsVoiceSelect").value;
    const ttsSpeed = parseFloat(document.getElementById("ttsSpeedRange").value) || 1.0;

    const payload = {
      video_url: videoUrl,
      video_path: videoPath,
      skill_id: currentSelectedSkill,
      template_id: document.getElementById("templateSelect")?.value || null,
      language: language,
      enable_tts: enableTts,
      tts_voice: ttsVoice,
      tts_speed: ttsSpeed
    };

    const res = await fetch("/api/v1/commentary/process-video", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Xử lý video thất bại.");
    }

    const data = await res.json();
    currentResult = data;
    renderFullResult(data);
    showToast("Phân tích và tạo kịch bản CapCut thành công!");

  } catch (err) {
    let msg = err.message || "Đã xảy ra lỗi không xác định.";
    if (err.name === "TypeError" && msg.includes("fetch")) {
      msg = "Không thể kết nối đến máy chủ API (Failed to fetch).\n\nNguyên nhân có thể là:\n1. Server chưa được bật. Vui lòng chạy '.\\run.bat' trên terminal.\n2. Bạn đang mở sai cổng. Hãy chắc chắn URL trên trình duyệt là: " + window.location.origin + "\n3. File tải lên quá lớn hoặc mạng bị gián đoạn.";
    }
    alert("❌ Lỗi: " + msg);
  } finally {
    btn.disabled = false;
    btnText.innerText = "Phân tích & Viết Lời bình";
  }
}

// Render Full Results
function renderFullResult(data) {
  // 1. Render Contact Sheet 3x3
  const imgBox = document.getElementById("contactSheetBox");
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
      el.innerHTML = `
        <div class="timeline-item-time">[${formatSeconds(item.time_range.start)} - ${formatSeconds(item.time_range.end)}]</div>
        <div class="timeline-item-action">${item.visual_action}</div>
      `;
      timelineList.appendChild(el);
    });
  }

  // 4. Render Commentary Studio
  renderCommentarySegments(data.capcut_json);

  // 5. Render Voiceover Audio Player nếu có
  const playerBox = document.getElementById("voiceoverPlayerBox");
  const audioPlayer = document.getElementById("voiceoverAudioPlayer");
  const voiceBadge = document.getElementById("voiceNameBadge");

  if (data.voiceover_audio_url) {
    playerBox.style.display = "block";
    audioPlayer.src = `${data.voiceover_audio_url}?t=${Date.now()}`;
    const selectedVoiceOpt = document.getElementById("ttsVoiceSelect");
    const voiceText = selectedVoiceOpt ? selectedVoiceOpt.options[selectedVoiceOpt.selectedIndex].text : "AI Voice";
    voiceBadge.innerText = voiceText.replace(/[🌾🎬🌿🎙️📖📻⚡]/g, "").trim();
  } else {
    playerBox.style.display = "none";
  }
}

// Render Commentary Segments
function renderCommentarySegments(capcutJson) {
  if (!capcutJson) return;

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
    `;
    container.appendChild(card);
  });
}

function updateSegmentViTranslation(index, newText) {
  if (!currentResult || !currentResult.capcut_json) return;
  const segments = currentResult.capcut_json.segments;
  if (segments && segments[index]) {
    segments[index].voiceover_vi_translation = newText.trim();
  }
}

function updateSegmentVoiceover(index, newText) {
  if (!currentResult || !currentResult.capcut_json) return;
  const segments = currentResult.capcut_json.segments;
  if (segments && segments[index]) {
    segments[index].voiceover = newText;
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

  const btn = document.getElementById("btnRewrite");
  btn.disabled = true;
  btn.innerHTML = '<span>⏳</span> Đang đổi phong cách & thu âm...';

  const language = document.getElementById("languageSelect").value;
  const enableTts = document.getElementById("ttsToggle").checked;
  const ttsVoice = document.getElementById("ttsVoiceSelect").value;
  const ttsSpeed = parseFloat(document.getElementById("ttsSpeedRange").value) || 1.0;

  try {
    const res = await fetch("/api/v1/commentary/rewrite", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        video_id: currentResult.video_id,
        new_skill_id: currentSelectedSkill,
        template_id: document.getElementById("templateSelect")?.value || null,
        language: language,
        enable_tts: enableTts,
        tts_voice: ttsVoice,
        tts_speed: ttsSpeed
      })
    });

    if (!res.ok) throw new Error("Viết lại thất bại.");

    const newScript = await res.json();
    currentResult.capcut_json = newScript;
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

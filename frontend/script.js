/* ═══════════════════════════════════════════════════════════
   Not So Quietly Disruptive — Article Studio Frontend
   ═══════════════════════════════════════════════════════════ */

const API = "/api";

// ── State ───────────────────────────────────────────────
let allVideos = [];
let videoDetails = {};
let activeJob = null;
let pollTimer = null;


// ═══════════════════════════════════════════════════════════
//  TOASTS
// ═══════════════════════════════════════════════════════════

function toast(message, type = "info") {
  const icons = { success: "✓", error: "✕", warning: "!", info: "i" };
  const container = document.getElementById("toastContainer");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `
    <span class="toast-icon">${icons[type] || icons.info}</span>
    <span class="toast-msg">${esc(message)}</span>
    <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
  `;
  container.appendChild(el);
  setTimeout(() => {
    el.classList.add("out");
    setTimeout(() => el.remove(), 300);
  }, 4000);
}


// ═══════════════════════════════════════════════════════════
//  CONFIRM DIALOG
// ═══════════════════════════════════════════════════════════

function confirmDialog(title, message) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "dialog-overlay";
    overlay.innerHTML = `
      <div class="dialog-box">
        <h3>${esc(title)}</h3>
        <p>${esc(message)}</p>
        <div class="dialog-actions">
          <button class="btn btn-ghost" id="dlgCancel">Cancel</button>
          <button class="btn btn-red" id="dlgConfirm">Delete</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    overlay.querySelector("#dlgCancel").onclick = () => { overlay.remove(); resolve(false); };
    overlay.querySelector("#dlgConfirm").onclick = () => { overlay.remove(); resolve(true); };
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) { overlay.remove(); resolve(false); }
    });
  });
}


// ═══════════════════════════════════════════════════════════
//  HELPERS
// ═══════════════════════════════════════════════════════════

function esc(text) {
  if (!text) return "";
  const m = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
  return String(text).replace(/[&<>"']/g, (c) => m[c]);
}

function escTpl(str) {
  if (!str) return "";
  return str.replace(/\\/g, "\\\\").replace(/`/g, "\\`").replace(/\$/g, "\\$");
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API}${path}`, opts);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`HTTP ${res.status}: ${body}`);
  }
  return res.json();
}


// ═══════════════════════════════════════════════════════════
//  LOAD & RENDER VIDEO LIST
// ═══════════════════════════════════════════════════════════

async function loadVideos() {
  try {
    allVideos = await apiFetch("/videos");
    // Index by id for fast lookup
    window.allVideosById = {};
    for (const v of allVideos) {
      if (v.id) window.allVideosById[v.id] = v;
    }
    renderVideoList(allVideos);
    updateStats();
  } catch (err) {
    console.error("Failed to load videos:", err);
  }
}

function updateStats() {
  const totalArticles = allVideos.reduce((s, v) => s + (v.article_count || 0), 0);
  document.getElementById("statVideoCount").textContent = allVideos.length;
  document.getElementById("statArticleCount").textContent = totalArticles;
}

function filterVideos() {
  const q = document.getElementById("searchBox").value.toLowerCase().trim();
  if (!q) { renderVideoList(allVideos); return; }
  renderVideoList(allVideos.filter((v) => v.title.toLowerCase().includes(q)));
}

function renderVideoList(videos) {
  const list = document.getElementById("videoList");
  const empty = document.getElementById("emptyState");
  const countEl = document.getElementById("videoCount");

  if (videos.length === 0) {
    list.innerHTML = "";
    empty.style.display = "block";
    countEl.textContent = "0 videos";
    return;
  }

  empty.style.display = "none";
  countEl.textContent = `${videos.length} video${videos.length !== 1 ? "s" : ""}`;

  list.innerHTML = videos
    .map(
      (v) => `
    <div class="video-card" id="vc-${v.id}" data-vid="${v.id}">
      <div class="video-card-header" onclick="toggleVideoCard('${v.id}')">
        ${v.thumbnail
          ? `<img class="video-thumb" src="${v.thumbnail}" alt="" loading="lazy" onerror="this.style.display='none'" />`
          : `<div class="video-thumb skeleton"></div>`
        }
        <div class="video-info">
          <div class="video-title">${esc(v.title)}</div>
          <div class="video-meta">
            ${v.has_transcript ? '<span class="tag tag-transcript">📄 Transcript</span>' : ""}
            ${v.article_count ? `<span class="tag tag-article">✍️ ${v.article_count} article${v.article_count !== 1 ? "s" : ""}</span>` : ""}
          </div>
        </div>
        <div class="expand-arrow">▾</div>
      </div>
      <div class="video-card-body" id="vcb-${v.id}">
        <div style="padding:32px; text-align:center; color:var(--text-muted);">
          <span class="spinner"></span>&nbsp; Loading...
        </div>
      </div>
    </div>`
    )
    .join("");
}


// ═══════════════════════════════════════════════════════════
//  TOGGLE / EXPAND
// ═══════════════════════════════════════════════════════════

async function toggleVideoCard(videoId) {
  const card = document.getElementById(`vc-${videoId}`);
  if (!card) return;

  const wasExpanded = card.classList.contains("expanded");

  // Collapse all
  document.querySelectorAll(".video-card.expanded").forEach((c) => c.classList.remove("expanded"));
  if (wasExpanded) return;

  card.classList.add("expanded");

  // Fetch detail if not cached
  if (!videoDetails[videoId]) {
    try {
      videoDetails[videoId] = await apiFetch(`/videos/${videoId}`);
    } catch (err) {
      document.getElementById(`vcb-${videoId}`).innerHTML = `
        <div style="padding:24px; color:var(--red);">Failed to load: ${esc(err.message)}</div>
      `;
      return;
    }
  }

  renderVideoDetail(videoId);
  setTimeout(() => card.scrollIntoView({ behavior: "smooth", block: "start" }), 120);
}


// ═══════════════════════════════════════════════════════════
//  RENDER VIDEO DETAIL
// ═══════════════════════════════════════════════════════════

function renderVideoDetail(videoId) {
  const d = videoDetails[videoId];
  if (!d) return;

  const body = document.getElementById(`vcb-${videoId}`);
  const hasTranscript = !!d.transcript;
  const hasArticles = d.articles && d.articles.length > 0;
  const hasRaw = !!d.articles_raw;

  let defaultTab = "articles";
  if (!hasArticles && hasTranscript) defaultTab = "transcript";

  body.innerHTML = `
    <div class="tabs">
      ${hasArticles ? `<div class="tab ${defaultTab === "articles" ? "active" : ""}" onclick="switchTab('${videoId}', 'articles', this)">✍️ Articles</div>` : ""}
      ${hasTranscript ? `<div class="tab ${defaultTab === "transcript" ? "active" : ""}" onclick="switchTab('${videoId}', 'transcript', this)">📄 Transcript</div>` : ""}
      ${hasRaw ? `<div class="tab" onclick="switchTab('${videoId}', 'fulltext', this)">📝 Full Text</div>` : ""}
      <div class="tab delete-all-tab" onclick="deleteVideo('${videoId}')">🗑 Delete</div>
    </div>

    ${hasArticles ? renderArticlesTab(videoId, d, defaultTab === "articles") : ""}
    ${hasTranscript ? renderTranscriptTab(videoId, d, defaultTab === "transcript") : ""}
    ${hasRaw ? renderFullTextTab(videoId, d) : ""}

    ${!hasTranscript && !hasArticles ? `
      <div style="padding:48px; text-align:center; color:var(--text-muted);">
        No content generated yet for this video.
      </div>
    ` : ""}
  `;
}


function switchTab(videoId, tab, tabEl) {
  const body = document.getElementById(`vcb-${videoId}`);
  body.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  body.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
  tabEl.classList.add("active");
  const panel = body.querySelector(`[data-tab="${tab}"]`);
  if (panel) panel.classList.add("active");
}


// ── Articles Tab ─────────────────────────────────────────

function renderArticlesTab(videoId, d, isActive) {
  const cards = d.articles
    .map((art, idx) => {
      const preview = getPreview(art.body || "");

      return `
    <div class="article-card" id="art-${videoId}-${idx}">
      <div class="article-header" onclick="toggleArticle('${videoId}', ${idx})">
        <div class="article-number">${idx + 1}</div>
        <div class="article-title-area">
          <div class="article-title">${esc(art.title)}</div>
          ${preview ? `<div class="article-preview">${esc(preview)}</div>` : ""}
        </div>
        <div class="article-actions" onclick="event.stopPropagation()">
          <button class="icon-btn" title="Copy article" onclick="copyArticle('${videoId}', ${idx})">📋</button>
          <button class="icon-btn danger" title="Delete article" onclick="deleteArticle('${videoId}', ${idx})">🗑</button>
        </div>
      </div>
      <div class="article-body">
        <div class="article-content">${esc(art.body)}</div>
      </div>
    </div>`;
    })
    .join("");

  return `
    <div class="tab-panel ${isActive ? "active" : ""}" data-tab="articles">
      <div class="panel-header">
        <span class="panel-title">${d.articles.length} Article Draft${d.articles.length !== 1 ? "s" : ""}</span>
        <button class="btn btn-sm btn-green" onclick="copyAllArticles('${videoId}')">📋 Copy All</button>
      </div>
      ${cards}
    </div>
  `;
}


// ── Transcript Tab ───────────────────────────────────────

function renderTranscriptTab(videoId, d, isActive) {
  let text = d.transcript || "";
  const start = text.indexOf("\n\n");
  const display = start > 0 ? text.substring(start).trim() : text;

  return `
    <div class="tab-panel ${isActive ? "active" : ""}" data-tab="transcript">
      <div class="panel-header">
        <span class="panel-title">Full Transcript</span>
        <button class="btn btn-sm btn-green" onclick="copyText(\`${escTpl(d.transcript)}\`, 'Transcript')">📋 Copy</button>
      </div>
      <div class="transcript-box">${esc(display)}</div>
    </div>
  `;
}


// ── Full Text Tab ────────────────────────────────────────

function renderFullTextTab(videoId, d) {
  return `
    <div class="tab-panel" data-tab="fulltext">
      <div class="panel-header">
        <span class="panel-title">Full Text (All Articles)</span>
        <button class="btn btn-sm btn-green" onclick="copyText(\`${escTpl(d.articles_raw)}\`, 'Full text')">📋 Copy</button>
      </div>
      <div class="transcript-box">${esc(d.articles_raw)}</div>
    </div>
  `;
}


// ═══════════════════════════════════════════════════════════
//  HELPERS
// ═══════════════════════════════════════════════════════════

function getPreview(text) {
  if (!text) return "";
  for (const line of text.split("\n")) {
    const clean = line.trim().replace(/^\*+/, "").replace(/\*+$/, "").replace(/^-+/, "").trim();
    if (clean.length > 25) {
      return clean.length > 120 ? clean.slice(0, 117) + "..." : clean;
    }
  }
  return "";
}

function toggleArticle(videoId, idx) {
  const card = document.getElementById(`art-${videoId}-${idx}`);
  if (card) card.classList.toggle("open");
}


// ═══════════════════════════════════════════════════════════
//  COPY FUNCTIONS
// ═══════════════════════════════════════════════════════════

function copyText(text, label = "Content") {
  navigator.clipboard.writeText(text).then(
    () => toast(`${label} copied!`, "success"),
    () => toast("Copy failed — try selecting manually", "error")
  );
}

function copyArticle(videoId, idx) {
  const d = videoDetails[videoId];
  if (!d) return;
  const art = d.articles[idx];
  if (!art) return;

  const text = `# ${art.title}\n\n${art.body}`;
  copyText(text, "Article");
}

function copyAllArticles(videoId) {
  const d = videoDetails[videoId];
  if (!d || !d.articles) return;

  const text = d.articles
    .map((art) => `# ${art.title}\n\n${art.body}`)
    .join("\n\n─────────────────────────────\n\n");

  copyText(text, "All articles");
}


// ═══════════════════════════════════════════════════════════
//  DELETE FUNCTIONS
// ═══════════════════════════════════════════════════════════

async function deleteVideo(videoId) {
  const d = videoDetails[videoId];
  const title = d ? d.title : videoId;

  const ok = await confirmDialog(
    "Delete this video?",
    `This will permanently remove the transcript and all articles for "${title}".`
  );
  if (!ok) return;

  try {
    await apiFetch(`/videos/${videoId}`, { method: "DELETE" });
    toast("Video deleted", "success");
    delete videoDetails[videoId];
    await loadVideos();
  } catch (err) {
    toast(`Delete failed: ${err.message}`, "error");
  }
}

async function deleteArticle(videoId, idx) {
  const d = videoDetails[videoId];
  if (!d) return;
  const art = d.articles[idx];
  if (!art) return;

  const ok = await confirmDialog(
    "Delete this article?",
    `"${art.title}" will be permanently removed.`
  );
  if (!ok) return;

  try {
    await apiFetch(`/videos/${videoId}/articles/${encodeURIComponent(art.title)}`, { method: "DELETE" });
    toast("Article deleted", "success");
    delete videoDetails[videoId];
    videoDetails[videoId] = await apiFetch(`/videos/${videoId}`);
    renderVideoDetail(videoId);
    await loadVideos();
  } catch (err) {
    toast(`Delete failed: ${err.message}`, "error");
  }
}


// ═══════════════════════════════════════════════════════════
//  GENERATION
// ═══════════════════════════════════════════════════════════

async function startGeneration() {
  const input = document.getElementById("videoUrl");
  const btn = document.getElementById("generateBtn");
  const url = input.value.trim();

  if (!url) {
    toast("Paste a YouTube URL or article link first", "warning");
    input.focus();
    return;
  }

  // Simple validation: must start with http/https or contain a domain-like pattern
  if (!url.startsWith("http://") && !url.startsWith("https://") && !url.includes(".")) {
    toast("That doesn't look like a valid URL", "warning");
    input.focus();
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Writing...';

  const progressArea = document.getElementById("progressArea");
  const progressBox = document.getElementById("progressBox");
  progressArea.classList.add("visible");
  progressBox.innerHTML = '<span class="status-badge running">Starting</span>';

  try {
    // Detect source type: YouTube or article
    let sourceType = "auto";
    if (url.includes("youtube.com") || url.includes("youtu.be")) {
      sourceType = "video";
    } else {
      sourceType = "article";
    }

    const res = await apiFetch("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url, source_type: sourceType }),
    });

    activeJob = res.job_id;
    input.value = "";
    pollJobStatus();
  } catch (err) {
    toast(`Generation failed: ${err.message}`, "error");
    btn.disabled = false;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19l7-7 3 3-7 7-3-3z"></path><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"></path><path d="M2 2l7.586 7.586"></path><circle cx="11" cy="11" r="2"></circle></svg> Write Articles`;
    progressArea.classList.remove("visible");
  }
}

function pollJobStatus() {
  if (!activeJob) return;
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    try {
      const job = await apiFetch(`/jobs/${activeJob}`);
      renderProgress(job);

      if (job.status === "completed" || job.status === "failed") {
        clearInterval(pollTimer);
        pollTimer = null;

        const btn = document.getElementById("generateBtn");
        btn.disabled = false;
        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19l7-7 3 3-7 7-3-3z"></path><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"></path><path d="M2 2l7.586 7.586"></path><circle cx="11" cy="11" r="2"></circle></svg> Write Articles`;

        if (job.status === "completed") {
          const result = job.result || {};
          toast(`Generated ${result.count || 0} article drafts!`, "success");
          videoDetails = {};
          await loadVideos();
          
          // Auto-open the newly generated source (only if valid)
          if (result.id) {
            try {
              await toggleVideoDetail(result.id);
            } catch (e) {
              console.log("Could not auto-open source detail", e);
            }
          }
        } else {
          toast(`Generation failed: ${job.error || "Unknown error"}`, "error");
        }

        setTimeout(() => {
          document.getElementById("progressArea").classList.remove("visible");
        }, 6000);

        activeJob = null;
      }
    } catch (err) {
      console.error("Poll error:", err);
    }
  }, 1500);
}

function renderProgress(job) {
  const box = document.getElementById("progressBox");
  const msgs = job.progress || [];

  const badgeClass = job.status === "completed" ? "completed" : job.status === "failed" ? "failed" : "running";
  const badgeText = job.status === "completed" ? "Complete" : job.status === "failed" ? "Failed" : (job.status || "Writing");

  box.innerHTML = `
    <span class="status-badge ${badgeClass}">${badgeText}</span>
    ${msgs.map((m) => `<div class="status-line">${esc(m.msg)}</div>`).join("")}
  `;

  box.scrollTop = box.scrollHeight;
}


// ═══════════════════════════════════════════════════════════
//  KEYBOARD SHORTCUTS
// ═══════════════════════════════════════════════════════════

document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    if (document.activeElement === document.getElementById("videoUrl")) {
      e.preventDefault();
      startGeneration();
    }
  }
  if (e.key === "Escape") {
    document.querySelectorAll(".video-card.expanded").forEach((c) => c.classList.remove("expanded"));
  }
});

document.getElementById("videoUrl").addEventListener("keypress", (e) => {
  if (e.key === "Enter") startGeneration();
});


// ═══════════════════════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════════════════════

loadVideos();

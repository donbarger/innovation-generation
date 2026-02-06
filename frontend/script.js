const API_BASE = "http://localhost:8000/api";
let currentInnovation = null;
let currentTranscript = null;

function switchMainTab(tab) {
  const videosPanel = document.getElementById('videosPanel');
  const transcriptsPanel = document.getElementById('transcriptsPanel');
  const tabVideos = document.getElementById('tabVideos');
  const tabTranscripts = document.getElementById('tabTranscripts');
  
  if (tab === 'videos') {
    videosPanel.style.display = 'block';
    transcriptsPanel.style.display = 'none';
    tabVideos.style.background = '#667eea';
    tabVideos.style.color = 'white';
    tabTranscripts.style.background = '#ccc';
    tabTranscripts.style.color = '#333';
  } else {
    videosPanel.style.display = 'none';
    transcriptsPanel.style.display = 'block';
    tabVideos.style.background = '#ccc';
    tabVideos.style.color = '#333';
    tabTranscripts.style.background = '#667eea';
    tabTranscripts.style.color = 'white';
    loadTranscripts();
  }
}

async function loadTranscripts() {
  try {
    const res = await fetch(`${API_BASE}/all_transcripts`).then(r => r.json());
    const transcriptsList = document.getElementById('transcriptsList');
    
    if (res.length === 0) {
      transcriptsList.innerHTML = '<div class="empty-state">No transcripts yet. Generate one to start!</div>';
      return;
    }
    
    transcriptsList.innerHTML = res.map((transcript, idx) => `
      <div class="innovation-item" onclick="showTranscriptPreview('${transcript.title.replace(/'/g, "\\'")}', ${idx})">
        <div class="innovation-title">📄 ${transcript.title}</div>
        <div class="innovation-preview">${transcript.preview.substring(0, 200)}...</div>
      </div>
    `).join('');
  } catch (err) {
    document.getElementById('transcriptsList').innerHTML = `<div class="status-box error">Error: ${err.message}</div>`;
  }
}

async function showTranscriptPreview(title, idx) {
  try {
    const res = await fetch(`${API_BASE}/all_transcripts`).then(r => r.json());
    const transcript = res[idx];
    
    if (!transcript) {
      alert('Transcript not found');
      return;
    }
    
    currentTranscript = transcript;
    
    // Show in right panel
    const panel = document.getElementById('panelContent');
    const preview = transcript.full_content.length > 2000 
      ? transcript.full_content.substring(0, 2000) + '...\n\n[Transcript truncated for display]'
      : transcript.full_content;
    
    panel.innerHTML = `
      <div style="margin-bottom: 20px;">
        <h2 style="color: #333; margin-bottom: 12px;">📄 ${escapeHtml(transcript.title)}</h2>
        <p style="color: #666; font-size: 0.9em; margin-bottom: 16px;">Video ID: ${escapeHtml(transcript.video_id)}</p>
        <div style="background: #f5f5f5; padding: 16px; border-radius: 8px; color: #666; white-space: pre-wrap; line-height: 1.6; font-size: 0.9em; max-height: 500px; overflow-y: auto;">
          ${escapeHtml(preview)}
        </div>
        <div style="display: flex; gap: 12px; margin-top: 16px;">
          <button class="btn-copy" onclick="copyTranscript()">📋 Copy Full Transcript</button>
        </div>
      </div>
    `;
  } catch (err) {
    alert('Error: ' + err.message);
  }
}

function copyTranscript() {
  if (!currentTranscript) return;
  
  navigator.clipboard.writeText(currentTranscript.full_content).then(() => {
    alert('✅ Transcript copied to clipboard!');
  }).catch(() => {
    alert('Failed to copy');
  });
}

function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}

async function loadVideos() {
  try {
    const res = await fetch(`${API_BASE}/videos`).then(r => r.json());
    const videosList = document.getElementById('videosList');
    
    if (res.length === 0) {
      videosList.innerHTML = '<div class="empty-state">No videos yet. Generate one to start!</div>';
      return;
    }
    
    videosList.innerHTML = res.map((video, idx) => `
      <div class="video-folder">
        <div class="video-header" onclick="toggleVideo(${idx})">
          <div class="video-title">📹 ${video.title}</div>
          <div class="toggle-arrow">▼</div>
        </div>
        <div class="video-content" id="video-${idx}">
          ${video.transcript ? `
            <div class="transcript-item" onclick="showTranscript('${video.transcript.file}')">
              📄 Transcript
            </div>
          ` : ''}
          ${video.innovations.map(innovation => `
            <div class="innovation-item" onclick="openInnovation('${innovation.title}', '${video.video_id}')">
              <div class="innovation-title">✨ ${innovation.title}</div>
              <div class="innovation-preview">${innovation.preview}...</div>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');
  } catch (err) {
    document.getElementById('videosList').innerHTML = `<div class="status-box error">Error: ${err.message}</div>`;
  }
}

function toggleVideo(idx) {
  const content = document.getElementById(`video-${idx}`);
  const header = content.previousElementSibling;
  
  content.classList.toggle('open');
  header.classList.toggle('expanded');
  header.querySelector('.toggle-arrow').classList.toggle('open');
}

async function openInnovation(innovationTitle, videoId) {
  try {
    // Fetch full innovation data
    const res = await fetch(`${API_BASE}/videos/${videoId}/innovations`).then(r => r.json());
    const innovation = res.find(i => i.title === innovationTitle);
    
    if (!innovation) {
      alert('Innovation not found');
      return;
    }
    
    currentInnovation = innovation;
    
    // Set header
    document.getElementById('articleTitle').textContent = innovation.title;
    document.getElementById('articleVideo').textContent = `📹 From selected video`;
    
    // Article tab content with better styling
    const articleContent = `
      <div class="article-section">
        <h3>Key Insight</h3>
        <p>${escapeHtml(innovation.key_insight)}</p>
      </div>
      
      <div class="article-section">
        <h3>Main Article</h3>
        <p>${escapeHtml(innovation.main_text)}</p>
      </div>
      
      <div class="article-section">
        <h3>Reflection</h3>
        <p>${escapeHtml(innovation.reflection)}</p>
      </div>
      
      <div class="article-section">
        <h3>Summary</h3>
        <p>${escapeHtml(innovation.summary)}</p>
      </div>
    `;
    
    document.getElementById('articleContent').innerHTML = articleContent;
    
    // Notes tab content with better styling
    const notesContent = innovation.notes.length > 0
      ? innovation.notes.map((note, idx) => `
        <div class="notes-item">
          <h4>Substack Note ${idx + 1}</h4>
          <p>${escapeHtml(note.content)}</p>
        </div>
      `).join('')
      : '<p style="color: #999; padding: 20px; text-align: center;">No Substack notes generated yet</p>';
    
    document.getElementById('notesContent').innerHTML = notesContent;
    
    // Open panel
    document.getElementById('articlePanel').classList.add('open');
  } catch (err) {
    alert('Error: ' + err.message);
  }
}

function switchArticleTab(tab) {
  // Hide all tab contents
  document.querySelectorAll('.article-tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.article-tab').forEach(el => el.classList.remove('active'));
  
  // Show selected tab
  if (tab === 'article') {
    document.getElementById('articleTabContent').classList.add('active');
    document.querySelector('.article-tab:first-child').classList.add('active');
  } else {
    document.getElementById('notesTabContent').classList.add('active');
    document.querySelector('.article-tab:last-child').classList.add('active');
  }
}

function closeArticle() {
  document.getElementById('articlePanel').classList.remove('open');
  currentInnovation = null;
}

function closeModal() {
  document.getElementById('modal').classList.remove('open');
  currentInnovation = null;
}

function copyArticleContent() {
  if (!currentInnovation) return;
  
  const text = `${currentInnovation.title}

KEY INSIGHT:
${currentInnovation.key_insight}

MAIN ARTICLE:
${currentInnovation.main_text}

REFLECTION:
${currentInnovation.reflection}

SUMMARY:
${currentInnovation.summary}`;
  
  navigator.clipboard.writeText(text).then(() => {
    alert('✅ Article copied to clipboard!');
  }).catch(() => {
    alert('Failed to copy');
  });
}

function deleteCurrentInnovation() {
  if (!currentInnovation) return;
  
  if (!confirm(`Delete "${currentInnovation.title}"? This cannot be undone.`)) {
    return;
  }
  
  // Call the API to delete
  (async () => {
    try {
      await fetch(`${API_BASE}/innovations/${currentInnovation.title}`, {
        method: 'DELETE'
      });
      
      alert('✅ Innovation deleted!');
      closeArticle();
      loadVideos();
    } catch (err) {
      alert('Error: ' + err.message);
    }
  })();
}



function showTranscript(filename) {
  // Show transcript in panel
  const panel = document.getElementById('panelContent');
  panel.innerHTML = `<p style="color: #666; white-space: pre-wrap; line-height: 1.6;">Loading...</p>`;
}


document.getElementById('generateBtn').addEventListener('click', async () => {
  const url = document.getElementById('videoUrl').value.trim();
  if (!url) {
    alert('Please enter a YouTube URL');
    return;
  }

  document.getElementById('generateBtn').disabled = true;
  document.getElementById('generateBtn').innerHTML = '<span class="loading-spinner"></span> Generating...';

  try {
    const res = await fetch(`${API_BASE}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_url: url })
    }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });

    const jobId = res.job_id;
    const statusEl = document.getElementById('jobStatus');
    statusEl.innerHTML = `<div class="status-box"><strong>Job:</strong> ${jobId}</div>`;

    let completed = false;
    const pollInterval = setInterval(async () => {
      try {
        const j = await fetch(`${API_BASE}/jobs/${jobId}`).then(r => r.json());
        const progress = j.progress || [];
        const progressHtml = progress.map(p => `<div class="progress-item">${escapeHtml(p.message)}</div>`).join('');

        if (j.status === 'completed') {
          statusEl.innerHTML = `
            <div class="status-box success">
              <strong>✅ Complete!</strong> Generated ${j.result?.count || 0} innovations.
              <div class="progress-log">${progressHtml}</div>
            </div>
          `;
          loadVideos();
          completed = true;
        } else if (j.status === 'failed') {
          statusEl.innerHTML = `
            <div class="status-box error">
              <strong>❌ Failed:</strong> ${j.error || 'Unknown error'}
              <div class="progress-log">${progressHtml}</div>
            </div>
          `;
          completed = true;
        } else {
          statusEl.innerHTML = `
            <div class="status-box">
              <strong>Status:</strong> ${j.status}
              <div class="progress-log">${progressHtml}</div>
            </div>
          `;
        }

        if (completed) {
          clearInterval(pollInterval);
          document.getElementById('generateBtn').disabled = false;
          document.getElementById('generateBtn').innerHTML = 'Generate';
          document.getElementById('videoUrl').value = '';
        }
      } catch (err) {
        statusEl.innerHTML = `<div class="status-box error">Poll error: ${err.message}</div>`;
      }
    }, 2000);
  } catch (err) {
    document.getElementById('jobStatus').innerHTML = `<div class="status-box error">Error: ${err.message}</div>`;
    document.getElementById('generateBtn').disabled = false;
    document.getElementById('generateBtn').innerHTML = 'Generate';
  }
});

// Load videos on startup and refresh periodically
loadVideos();
setInterval(loadVideos, 10000);

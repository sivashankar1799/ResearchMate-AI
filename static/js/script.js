/* =========================================================================
   ResearchMate AI — Frontend Logic (vanilla JS)
   Handles uploads, feature API calls, chat, voice, charts, AI panel.
   ========================================================================= */

// ---------- Generic helpers ----------
function $(sel) { return document.querySelector(sel); }
function $all(sel) { return Array.from(document.querySelectorAll(sel)); }

function showToast(message, type = "info") {
    const wrap = $("#toastWrap") || createToastWrap();
    const el = document.createElement("div");
    el.className = "alert alert-glass shadow mb-2";
    el.style.borderLeft = type === "error"
        ? "4px solid #ff5d73" : "4px solid #00e5ff";
    el.textContent = message;
    wrap.appendChild(el);
    setTimeout(() => el.remove(), 4200);
}
function createToastWrap() {
    const w = document.createElement("div");
    w.id = "toastWrap";
    w.style.cssText = "position:fixed;top:80px;right:20px;z-index:2000;max-width:340px;";
    document.body.appendChild(w);
    return w;
}

// POST JSON helper with unified error handling
async function postJSON(url, body) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {})
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || "Request failed");
    return data;
}

// Typing effect: reveal text character-by-character into an element
function typeText(el, text, speed = 14) {
    return new Promise(resolve => {
        el.textContent = "";
        let i = 0;
        const timer = setInterval(() => {
            el.textContent += text.charAt(i);
            i++;
            if (i >= text.length) { clearInterval(timer); resolve(); }
        }, speed);
    });
}

// ---------- AI Assistant Panel ----------
function initAIPanel() {
    const avatar = $("#aiAvatar");
    const body = $("#aiPanelBody");
    if (!avatar || !body) return;
    avatar.addEventListener("click", () => {
        body.classList.toggle("d-none");
    });
}
function aiPanelSay(message) {
    const body = $("#aiPanelBody");
    if (!body) return;
    body.classList.remove("d-none");
    const msg = $("#aiPanelMessage");
    if (msg) typeText(msg, message, 12);
}
function aiPanelTyping(on) {
    const ind = $("#aiPanelTyping");
    if (ind) ind.classList.toggle("d-none", !on);
}

// ---------- Upload ----------
function initUpload() {
    const form = $("#uploadForm");
    const input = $("#pdfInput");
    const dropzone = $("#dropzone");
    if (!form) return;

    if (dropzone) {
        dropzone.addEventListener("click", () => input.click());
        ["dragover", "dragenter"].forEach(ev =>
            dropzone.addEventListener(ev, e => {
                e.preventDefault(); dropzone.classList.add("dragover");
            }));
        ["dragleave", "drop"].forEach(ev =>
            dropzone.addEventListener(ev, e => {
                e.preventDefault(); dropzone.classList.remove("dragover");
            }));
        dropzone.addEventListener("drop", e => {
            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                updateFileLabel();
            }
        });
    }

    if (input) input.addEventListener("change", updateFileLabel);

    function updateFileLabel() {
        const label = $("#fileLabel");
        if (label && input.files.length) label.textContent = input.files[0].name;
    }

    form.addEventListener("submit", async e => {
        e.preventDefault();
        if (!input.files.length) { showToast("Please select a PDF file.", "error"); return; }

        const fd = new FormData();
        fd.append("file", input.files[0]);

        const status = $("#uploadStatus");
        if (status) status.innerHTML = '<div class="spinner-neon"></div>';
        aiPanelTyping(true);

        try {
            const res = await fetch("/upload", { method: "POST", body: fd });
            const data = await res.json();
            aiPanelTyping(false);
            if (!data.success) throw new Error(data.error);

            if (status) {
                status.innerHTML =
                    `<div class="alert alert-glass">
                        <strong>${data.filename}</strong> uploaded successfully!<br>
                        Pages: <b>${data.page_count}</b> · Words: <b>${data.word_count}</b>
                     </div>`;
            }
            aiPanelSay(`Loaded "${data.filename}". You can now summarize, take notes, or quiz yourself!`);
            showToast("PDF processed successfully.");
            setTimeout(() => { window.location.reload(); }, 1500);
        } catch (err) {
            aiPanelTyping(false);
            if (status) status.innerHTML = "";
            showToast(err.message, "error");
        }
    });
}

// ---------- Summary ----------
function initSummary() {
    const btn = $("#genSummaryBtn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
        setSkeleton(["shortSummary", "detailedSummary", "keyFindings", "conclusions"]);
        aiPanelTyping(true);
        try {
            const data = await postJSON("/summarize", {});
            aiPanelTyping(false);
            await typeText($("#shortSummary"), data.short_summary);
            await typeText($("#detailedSummary"), data.detailed_summary, 6);
            renderBullets($("#keyFindings"), data.key_findings);
            await typeText($("#conclusions"), data.conclusions);
            aiPanelSay("Summary ready! You can export it to PDF.");
        } catch (err) {
            aiPanelTyping(false);
            showToast(err.message, "error");
            clearSkeleton(["shortSummary", "detailedSummary", "keyFindings", "conclusions"]);
        }
    });

    const exportBtn = $("#exportSummaryBtn");
    if (exportBtn) exportBtn.addEventListener("click", () => downloadPost("/export-summary"));
}

// ---------- Notes ----------
function initNotes() {
    const btn = $("#genNotesBtn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
        const acc = $("#notesAccordion");
        if (acc) acc.innerHTML = '<div class="spinner-neon"></div>';
        aiPanelTyping(true);
        try {
            const data = await postJSON("/notes", {});
            aiPanelTyping(false);
            renderNotesAccordion(data.study_notes, data.revision_notes);
            aiPanelSay("Study & revision notes generated. Export them to Word anytime!");
        } catch (err) {
            aiPanelTyping(false);
            if (acc) acc.innerHTML = "";
            showToast(err.message, "error");
        }
    });

    const exportBtn = $("#exportNotesBtn");
    if (exportBtn) exportBtn.addEventListener("click", () => downloadPost("/export-notes"));
}

function renderNotesAccordion(study, revision) {
    const acc = $("#notesAccordion");
    if (!acc) return;
    let html = "";
    let idx = 0;

    study.forEach(group => {
        idx++;
        html += `
        <div class="accordion-item">
          <h2 class="accordion-header">
            <button class="accordion-button collapsed" type="button"
              data-bs-toggle="collapse" data-bs-target="#st${idx}">
              📘 ${group.topic}
            </button>
          </h2>
          <div id="st${idx}" class="accordion-collapse collapse"
               data-bs-parent="#notesAccordion">
            <div class="accordion-body">
              <ul>${group.points.map(p => `<li>${escapeHTML(p)}</li>`).join("")}</ul>
            </div>
          </div>
        </div>`;
    });

    idx++;
    html += `
    <div class="accordion-item">
      <h2 class="accordion-header">
        <button class="accordion-button" type="button"
          data-bs-toggle="collapse" data-bs-target="#rev${idx}">
          ⚡ Revision Notes
        </button>
      </h2>
      <div id="rev${idx}" class="accordion-collapse collapse show"
           data-bs-parent="#notesAccordion">
        <div class="accordion-body">
          <ul>${revision.map(p => `<li>${escapeHTML(p)}</li>`).join("")}</ul>
        </div>
      </div>
    </div>`;
    acc.innerHTML = html;
}

// ---------- Quiz ----------
let CURRENT_QUIZ = null;
function initQuiz() {
    const btn = $("#genQuizBtn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
        const container = $("#quizContainer");
        if (container) container.innerHTML = '<div class="spinner-neon"></div>';
        aiPanelTyping(true);
        try {
            const data = await postJSON("/quiz", {});
            aiPanelTyping(false);
            CURRENT_QUIZ = data;
            renderQuiz(data);
            aiPanelSay("Quiz generated! Answer all questions, then submit to see your score.");
        } catch (err) {
            aiPanelTyping(false);
            if (container) container.innerHTML = "";
            showToast(err.message, "error");
        }
    });
}

function renderQuiz(data) {
    const c = $("#quizContainer");
    if (!c) return;
    let html = '<form id="quizForm">';

    html += '<h4 class="card-title-neon">Multiple Choice</h4>';
    data.mcqs.forEach((q, i) => {
        html += `<div class="glass-card mb-3" data-answer="${escapeAttr(q.answer)}">
                   <p><b>Q${i + 1}.</b> ${escapeHTML(q.question)}</p>`;
        q.options.forEach((opt, j) => {
            html += `<div class="form-check quiz-option">
                       <input class="form-check-input" type="radio"
                              name="mcq${i}" id="mcq${i}o${j}" value="${escapeAttr(opt)}">
                       <label class="form-check-label" for="mcq${i}o${j}">${escapeHTML(opt)}</label>
                     </div>`;
        });
        html += `<div class="feedback mt-2"></div></div>`;
    });

    html += '<h4 class="card-title-neon mt-4">True / False</h4>';
    data.true_false.forEach((q, i) => {
        html += `<div class="glass-card mb-3" data-answer="${escapeAttr(q.answer)}">
                   <p><b>Q${i + 1}.</b> ${escapeHTML(q.statement)}</p>
                   <div class="form-check quiz-option">
                     <input class="form-check-input" type="radio" name="tf${i}"
                            id="tf${i}t" value="True">
                     <label class="form-check-label" for="tf${i}t">True</label>
                   </div>
                   <div class="form-check quiz-option">
                     <input class="form-check-input" type="radio" name="tf${i}"
                            id="tf${i}f" value="False">
                     <label class="form-check-label" for="tf${i}f">False</label>
                   </div>
                   <div class="feedback mt-2"></div>
                 </div>`;
    });

    html += `<button type="submit" class="btn btn-neon me-2">Submit Quiz</button>
             <button type="button" id="exportQuizBtn" class="btn btn-neon-purple">Export Results (PDF)</button>
             <div id="quizResult" class="quiz-result-banner mt-3"></div></form>`;
    c.innerHTML = html;

    $("#quizForm").addEventListener("submit", e => { e.preventDefault(); gradeQuiz(); });
    $("#exportQuizBtn").addEventListener("click", exportQuiz);
}

let LAST_SCORE = { score: 0, total: 0 };
function gradeQuiz() {
    const cards = $all("#quizForm .glass-card");
    let score = 0;
    cards.forEach(card => {
        const correct = card.getAttribute("data-answer");
        const chosen = card.querySelector("input:checked");
        const fb = card.querySelector(".feedback");
        if (chosen && chosen.value === correct) {
            score++;
            fb.innerHTML = `<span class="quiz-correct">✔ Correct</span>`;
        } else {
            fb.innerHTML = `<span class="quiz-wrong">�’ Incorrect — Correct answer: ${escapeHTML(correct)}</span>`;
        }
    });
    LAST_SCORE = { score: score, total: cards.length };
    $("#quizResult").textContent = `You scored ${score} / ${cards.length}`;
    aiPanelSay(`You scored ${score} out of ${cards.length}. Keep going!`);
}

async function exportQuiz() {
    try {
        const res = await fetch("/export-quiz", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(LAST_SCORE)
        });
        if (!res.ok) { const d = await res.json(); throw new Error(d.error); }
        triggerBlobDownload(await res.blob(), "ResearchMate_QuizResults.pdf");
    } catch (err) { showToast(err.message, "error"); }
}

// ---------- Chatbot ----------
function initChat() {
    const form = $("#chatForm");
    if (!form) return;
    const input = $("#chatInput");
    const win = $("#chatWindow");

    form.addEventListener("submit", async e => {
        e.preventDefault();
        const q = input.value.trim();
        if (!q) return;
        addBubble(win, q, "user");
        input.value = "";

        const typingEl = addTyping(win);
        try {
            const data = await postJSON("/chat", { question: q });
            typingEl.remove();
            const bubble = addBubble(win, "", "ai", data.timestamp);
            await typeText(bubble.querySelector(".bubble-text"), data.answer, 12);
            speak(data.answer);
        } catch (err) {
            typingEl.remove();
            addBubble(win, "Error: " + err.message, "ai");
        }
        win.scrollTop = win.scrollHeight;
    });

    initVoice();
}

function addBubble(win, text, who, stamp) {
    const div = document.createElement("div");
    div.className = "chat-bubble " + (who === "user" ? "chat-user" : "chat-ai");
    const time = stamp || new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    div.innerHTML = `<span class="bubble-text">${escapeHTML(text)}</span>
                     <span class="stamp">${time}</span>`;
    win.appendChild(div);
    win.scrollTop = win.scrollHeight;
    return div;
}
function addTyping(win) {
    const div = document.createElement("div");
    div.className = "chat-bubble chat-ai";
    div.innerHTML = `<span class="typing-indicator"><span></span><span></span><span></span></span>`;
    win.appendChild(div);
    win.scrollTop = win.scrollHeight;
    return div;
}

// ---------- Voice (Web Speech API) ----------
function initVoice() {
    const micBtn = $("#micBtn");
    if (!micBtn) return;

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
        micBtn.disabled = true;
        micBtn.title = "Speech recognition not supported in this browser";
        return;
    }
    const recognition = new SR();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    let listening = false;

    micBtn.addEventListener("click", () => {
        if (listening) { recognition.stop(); return; }
        recognition.start();
    });
    recognition.onstart = () => { listening = true; micBtn.classList.add("active"); };
    recognition.onend = () => { listening = false; micBtn.classList.remove("active"); };
    recognition.onerror = () => { listening = false; micBtn.classList.remove("active"); };
    recognition.onresult = e => {
        const transcript = e.results[0][0].transcript;
        $("#chatInput").value = transcript;
        $("#chatForm").dispatchEvent(new Event("submit"));
    };

    // Text-to-speech toggle
    const ttsToggle = $("#ttsToggle");
    if (ttsToggle) ttsToggle.addEventListener("change", () => {
        window.RM_TTS_ON = ttsToggle.checked;
    });
    window.RM_TTS_ON = true;
}

function speak(text) {
    if (!window.RM_TTS_ON) return;
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "en-US";
    utter.rate = 1;
    utter.pitch = 1;
    window.speechSynthesis.speak(utter);
}

// ---------- PPT ----------
function initPPT() {
    const btn = $("#genPptBtn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
        const status = $("#pptStatus");
        if (status) status.innerHTML = '<div class="spinner-neon"></div>';
        aiPanelTyping(true);
        try {
            const res = await fetch("/generate-ppt", { method: "POST" });
            aiPanelTyping(false);
            if (!res.ok) { const d = await res.json(); throw new Error(d.error); }
            triggerBlobDownload(await res.blob(), "ResearchMate_Presentation.pptx");
            if (status) status.innerHTML =
                '<div class="alert alert-glass">Presentation generated & downloaded!</div>';
            aiPanelSay("Your PowerPoint is ready and downloading now!");
        } catch (err) {
            aiPanelTyping(false);
            if (status) status.innerHTML = "";
            showToast(err.message, "error");
        }
    });
}

// ---------- Downloads ----------
async function downloadPost(url) {
    try {
        const res = await fetch(url, { method: "POST" });
        if (!res.ok) { const d = await res.json(); throw new Error(d.error); }
        const cd = res.headers.get("Content-Disposition") || "";
        const m = cd.match(/filename="?([^"]+)"?/);
        const name = m ? m[1] : "download";
        triggerBlobDownload(await res.blob(), name);
        showToast("Export downloaded.");
    } catch (err) { showToast(err.message, "error"); }
}
function triggerBlobDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    a.remove(); URL.revokeObjectURL(url);
}

// ---------- Render helpers ----------
function renderBullets(el, items) {
    if (!el) return;
    el.innerHTML = "<ul>" + items.map(i => `<li>${escapeHTML(i)}</li>`).join("") + "</ul>";
}
function setSkeleton(ids) {
    ids.forEach(id => {
        const el = $("#" + id);
        if (el) el.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton w-75"></div>';
    });
}
function clearSkeleton(ids) {
    ids.forEach(id => { const el = $("#" + id); if (el) el.innerHTML = ""; });
}
function escapeHTML(str) {
    return String(str).replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
}
function escapeAttr(str) { return escapeHTML(str).replace(/"/g, "&quot;"); }

// ---------- Dashboard charts (Chart.js) ----------
function initCharts() {
    const barEl = $("#pagesChart");
    const pieEl = $("#featureChart");
    if (!barEl && !pieEl) return;

    fetch("/stats").then(r => r.json()).then(d => {
        if (!d.success) return;
        const s = d.stats;

        if (barEl && window.Chart) {
            const papers = s.papers.slice(-8);
            new Chart(barEl, {
                type: "bar",
                data: {
                    labels: papers.map(p => p.name.length > 14 ? p.name.slice(0, 12) + "…" : p.name),
                    datasets: [{
                        label: "Pages per Paper",
                        data: papers.map(p => p.pages),
                        backgroundColor: "rgba(0,229,255,0.5)",
                        borderColor: "#00e5ff", borderWidth: 1, borderRadius: 6
                    }]
                },
                options: chartOpts("Pages Analyzed per Paper")
            });
        }

        if (pieEl && window.Chart) {
            const fu = s.feature_usage;
            new Chart(pieEl, {
                type: "doughnut",
                data: {
                    labels: ["Summaries", "Notes", "Quizzes", "Chats", "PPTs"],
                    datasets: [{
                        data: [fu.summaries, fu.notes, fu.quizzes, fu.chats, fu.ppts],
                        backgroundColor: ["#00e5ff", "#7b2ff7", "#f72f8e", "#4ee68a", "#ffb347"],
                        borderColor: "rgba(10,14,39,0.8)", borderWidth: 2
                    }]
                },
                options: chartOpts("Feature Usage", true)
            });
        }
    }).catch(() => { });
}
function chartOpts(title, legend) {
    return {
        responsive: true,
        plugins: {
            legend: { display: !!legend, labels: { color: "#e8ecff" } },
            title: { display: true, text: title, color: "#00e5ff" }
        },
        scales: legend ? {} : {
            y: { ticks: { color: "#9aa3c7" }, grid: { color: "rgba(255,255,255,.05)" } },
            x: { ticks: { color: "#9aa3c7" }, grid: { color: "rgba(255,255,255,.05)" } }
        }
    };
}

// ---------- Init on DOM ready ----------
document.addEventListener("DOMContentLoaded", () => {
    initAIPanel();
    initUpload();
    initSummary();
    initNotes();
    initQuiz();
    initChat();
    initPPT();
    initCharts();
});
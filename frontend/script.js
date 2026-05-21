const USE_MOCK = false;
const API_BASE_URL = "http://localhost:8000";

let selectedCodebase = null;
let companyRepos = [];

/* =========================================================
   MOCK COMPANY REPOS
   Chỉ dùng khi USE_MOCK = true.
========================================================= */
const SOURCE_CODE_COMPANY_REPOS = [
    {
        id: "company_auth_service",
        name: "auth-service",
        github_url: "https://github.com/company/auth-service",
        description: "Repo xử lý login, JWT, permission.",
        status: "ready",
        enabled: true,
        visible_to_user: true,
        file_count: 42,
        chunk_count: 218,
        doc_count: 11,
        text_count: 0,
        json_count: 0,
        ignored_file_count: 8,
        updated_at: "2026-05-17 09:30",
    },
    {
        id: "company_payment_service",
        name: "payment-service",
        github_url: "https://github.com/company/payment-service",
        description: "Repo xử lý payment và webhook.",
        status: "ready",
        enabled: true,
        visible_to_user: true,
        file_count: 37,
        chunk_count: 164,
        doc_count: 9,
        text_count: 0,
        json_count: 0,
        ignored_file_count: 5,
        updated_at: "2026-05-17 10:15",
    },
];

const companyRepoSelect = document.getElementById("companyRepoSelect");
const selectedRepoStats = document.getElementById("selectedRepoStats");
const repoStatsCard = document.getElementById("repoStatsCard");

const temporaryRepoType = document.getElementById("temporaryRepoType");
const githubTempBox = document.getElementById("githubTempBox");
const zipTempBox = document.getElementById("zipTempBox");
const tempGithubUrl = document.getElementById("tempGithubUrl");
const indexTempGithubBtn = document.getElementById("indexTempGithubBtn");
const tempZipFile = document.getElementById("tempZipFile");
const uploadTempZipBtn = document.getElementById("uploadTempZipBtn");
const userStatusBox = document.getElementById("userStatusBox");
let headerStatusBox = document.getElementById("headerStatusBox");

const currentRetrievalMode = document.getElementById("currentRetrievalMode");
const retrievalDescription = document.getElementById("retrievalDescription");
const debugToggle = document.getElementById("debugToggle");
const chatTitle = document.getElementById("chatTitle");
const messages = document.getElementById("messages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const sendChatBtn = document.getElementById("sendChatBtn");

bindEvents();
init();

function bindEvents() {
    companyRepoSelect.addEventListener("change", handleSelectCompanyRepo);
    temporaryRepoType.addEventListener("change", handleTemporaryRepoTypeChange);
    indexTempGithubBtn.addEventListener("click", handleIndexTemporaryGithubRepo);
    uploadTempZipBtn.addEventListener("click", handleUploadTemporaryZipRepo);
    chatForm.addEventListener("submit", handleUserChatSubmit);

    document.querySelectorAll("input[name='retrievalMode']").forEach((radio) => {
        radio.addEventListener("change", () => {
            const mode = getRetrievalMode();
            currentRetrievalMode.textContent = mode;

            if (mode === "fast") {
                retrievalDescription.textContent = "Graph RAG + Hybrid retrieval";
            } else if (mode === "accurate") {
                retrievalDescription.textContent = "Graph RAG + Hybrid retrieval + Cross-Encoder";
            }

            if (selectedCodebase) {
                showUserStatus(
                    "Retrieval mode đã đổi. Mode mới sẽ áp dụng khi bạn load lại company repo hoặc index lại temporary repo."
                );
            }
        });
    });
}

async function init() {
    handleTemporaryRepoTypeChange();

    const mode = getRetrievalMode();
    currentRetrievalMode.textContent = mode;

    if (mode === "fast") {
        retrievalDescription.textContent = "Graph RAG + Hybrid retrieval";
    } else if (mode === "accurate") {
        retrievalDescription.textContent = "Graph RAG + Hybrid retrieval + Cross-Encoder";
    }

    if (!USE_MOCK) {
        try {
            await healthCheckApi();
            showUserStatus("Backend connected.");
        } catch (error) {
            showUserStatus(
                "Không kết nối được backend. Hãy chắc chắn FastAPI đang chạy ở " +
                API_BASE_URL +
                ". Chi tiết: " +
                error.message
            );
        }
    }

    await loadVisibleCompanyRepos();
}

/* =========================
   USER WORKSPACE
========================= */

async function loadVisibleCompanyRepos() {
    try {
        const data = await getVisibleCompanyReposApi();
        companyRepos = data.repos || [];
        renderCompanyRepoSelect();
    } catch (error) {
        showUserStatus("Không tải được danh sách company repos: " + error.message);
    }
}

function renderCompanyRepoSelect() {
    companyRepoSelect.innerHTML = "";

    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = "Chọn repo công ty";
    companyRepoSelect.appendChild(emptyOption);

    companyRepos.forEach((repo) => {
        const option = document.createElement("option");
        option.value = repo.id;
        option.textContent = `${repo.name} — ${repo.status}`;
        companyRepoSelect.appendChild(option);
    });
}

async function handleSelectCompanyRepo() {
    const repoId = companyRepoSelect.value;

    if (!repoId) {
        selectedCodebase = null;
        repoStatsCard.classList.add("hidden");
        chatTitle.textContent = "Chọn repo hoặc index repo tạm thời";
        showUserStatus("Chưa chọn repository.");
        return;
    }

    const repo = companyRepos.find((item) => item.id === repoId);
    if (!repo) return;

    selectedCodebase = null;
    repoStatsCard.classList.add("hidden");
    chatTitle.textContent = `Đang load ${repo.name}...`;
    showUserStatus(`Đang load company repo: ${repo.name}...`);
    companyRepoSelect.disabled = true;

    try {
        const data = await loadCompanyRepoApi(repoId);

        selectedCodebase = {
            id: data.repo_id,
            name: data.repo_name,
            type: data.source_type || "company",
            session_id: data.session_id,
            meta: data,
        };

        renderRepoStats(data);

        chatTitle.textContent = `Chat với ${data.repo_name}`;
        showUserStatus(
            `Đã load company repo: ${data.repo_name}\n` +
            `Session: ${data.session_id}\n` +
            `Files: ${data.file_count}\n` +
            `Chunks: ${data.chunk_count}`
        );

        addAssistantMessage(
            messages,
            `Company repo "${data.repo_name}" đã sẵn sàng. Bạn có thể hỏi đáp.`
        );
    } catch (error) {
        selectedCodebase = null;
        chatTitle.textContent = "Chọn repo hoặc index repo tạm thời";
        showUserStatus("Không load được repo: " + error.message);
    } finally {
        companyRepoSelect.disabled = false;
    }
}

function renderRepoStats(repo) {
    repoStatsCard.classList.remove("hidden");

    const docsTextCount = repo.docs_text_count ?? ((repo.doc_count || 0) + (repo.text_count || 0));

    selectedRepoStats.innerHTML = `
        <span>Python: ${repo.file_count || 0}</span>
        <span>Docs/Text: ${docsTextCount || 0}</span>
        <span>JSON: ${repo.json_count || 0}</span>
        <span>Chunks: ${repo.chunk_count || 0}</span>
        <span>Ignored: ${repo.ignored_file_count || 0}</span>
    `;
}

function handleTemporaryRepoTypeChange() {
    const type = temporaryRepoType.value;

    githubTempBox.classList.toggle("hidden", type !== "github");
    zipTempBox.classList.toggle("hidden", type !== "zip");
}

async function handleIndexTemporaryGithubRepo() {
    const githubUrl = tempGithubUrl.value.trim();

    if (!githubUrl) {
        showUserStatus("Bạn cần nhập GitHub public repo URL.");
        return;
    }

    selectedCodebase = null;
    setButtonLoading(indexTempGithubBtn, true, "Đang index...");
    showUserStatus("Đang clone và index GitHub repo tạm thời...");

    try {
        const data = await indexTemporaryGithubRepoApi({
            github_url: githubUrl,
        });

        selectedCodebase = {
            id: data.repo_id,
            name: data.repo_name,
            type: data.source_type || "github",
            session_id: data.session_id,
            meta: data,
        };

        companyRepoSelect.value = "";
        renderRepoStats(data);
        chatTitle.textContent = `Chat với temporary repo: ${data.repo_name}`;

        showUserStatus(
            `Index GitHub tạm thời thành công: ${data.repo_name}\n` +
            `Session: ${data.session_id}\n` +
            `Files: ${data.file_count}\n` +
            `Chunks: ${data.chunk_count}`
        );

        addAssistantMessage(
            messages,
            `Temporary GitHub repo "${data.repo_name}" đã sẵn sàng. Bạn có thể hỏi đáp.`
        );
    } catch (error) {
        showUserStatus("Lỗi index GitHub repo: " + error.message);
    } finally {
        setButtonLoading(indexTempGithubBtn, false, "Index GitHub");
    }
}

async function handleUploadTemporaryZipRepo() {
    const file = tempZipFile.files[0];

    if (!file) {
        showUserStatus("Bạn cần chọn file .zip repo.");
        return;
    }

    selectedCodebase = null;
    setButtonLoading(uploadTempZipBtn, true, "Đang upload...");
    showUserStatus("Đang upload và index file .zip tạm thời...");

    try {
        const data = await uploadTemporaryZipRepoApi(file);

        selectedCodebase = {
            id: data.repo_id,
            name: data.repo_name,
            type: data.source_type || "zip_upload",
            session_id: data.session_id,
            meta: data,
        };

        companyRepoSelect.value = "";
        renderRepoStats(data);
        chatTitle.textContent = `Chat với temporary repo: ${data.repo_name}`;

        showUserStatus(
            `Index ZIP tạm thời thành công: ${data.repo_name}\n` +
            `Session: ${data.session_id}\n` +
            `Files: ${data.file_count}\n` +
            `Chunks: ${data.chunk_count}`
        );

        addAssistantMessage(
            messages,
            `Temporary .zip repo "${data.repo_name}" đã sẵn sàng. Bạn có thể hỏi đáp.`
        );
    } catch (error) {
        showUserStatus("Lỗi upload/index zip: " + error.message);
    } finally {
        setButtonLoading(uploadTempZipBtn, false, "Upload & Index tạm thời");
    }
}

async function handleUserChatSubmit(event) {
    event.preventDefault();

    const question = chatInput.value.trim();
    if (!question) return;

    if (!selectedCodebase || !selectedCodebase.session_id) {
        addAssistantMessage(
            messages,
            "Bạn cần chọn company repo hoặc index repo tạm thời trước."
        );
        return;
    }

    addUserMessage(messages, question);
    chatInput.value = "";

    const loadingId = addAssistantMessage(messages, "Đang suy nghĩ...");
    setMessageQuestion(loadingId, question);
    setButtonLoading(sendChatBtn, true, "Đang gửi...");

    try {
        const data = await chatWithCodebaseApi({
            session_id: selectedCodebase.session_id,
            question,
        });

        updateAssistantMessage(
            loadingId,
            data.answer || "Không có câu trả lời.",
            data.sources || [],
            {
                query_type: data.query_type,
                tools_used: data.tools_used || [],
                raw_results: data.raw_results || {},
                warnings: data.warnings || [],
            },
            debugToggle.checked
        );
    } catch (error) {
        updateAssistantMessage(
            loadingId,
            "Có lỗi khi gọi chatbot: " + error.message,
            [],
            null,
            false
        );
    } finally {
        setButtonLoading(sendChatBtn, false, "Gửi");
    }
}

function getRetrievalMode() {
    const checked = document.querySelector("input[name='retrievalMode']:checked");
    return checked ? checked.value : "fast";
}


function ensureHeaderStatusBox() {
    if (headerStatusBox) {
        return headerStatusBox;
    }

    headerStatusBox = document.createElement("div");
    headerStatusBox.id = "headerStatusBox";
    headerStatusBox.className = "header-status hidden";

    const headerMain = document.querySelector(".chat-header-main");
    const titleContainer = chatTitle ? chatTitle.parentElement : null;

    if (headerMain) {
        headerMain.appendChild(headerStatusBox);
    } else if (titleContainer) {
        titleContainer.insertAdjacentElement("afterend", headerStatusBox);
    } else {
        document.body.appendChild(headerStatusBox);
    }

    return headerStatusBox;
}

function showUserStatus(text) {
    const statusBox = ensureHeaderStatusBox();

    statusBox.classList.remove("hidden");
    statusBox.textContent = text;

    // The sidebar status box is kept only for old markup compatibility.
    // Hide it so status messages never cover the chat area.
    if (userStatusBox) {
        userStatusBox.classList.add("hidden");
        userStatusBox.textContent = "";
    }
}

/* =========================
   MESSAGE UI
========================= */

function addUserMessage(container, text) {
    const row = document.createElement("div");
    row.className = "message-row user-row";

    row.innerHTML = `
        <div class="message-body">
            <div class="bubble user-bubble"></div>
            <div class="message-time">${getTime()}</div>
        </div>
    `;

    row.querySelector(".bubble").textContent = text;
    container.appendChild(row);
    scrollMessages(container);

    return row.id;
}

function addAssistantMessage(container, text) {
    const id = `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;

    const row = document.createElement("div");
    row.className = "message-row assistant-row";
    row.id = id;

    row.innerHTML = `
        <div class="avatar"><img src="./logo_chatbot.jpg" alt="avatar" /></div>
        <div class="message-body">
            <div class="bubble assistant-bubble"></div>
            <div class="message-time">${getTime()}</div>
        </div>
    `;

    row.querySelector(".bubble").textContent = text;
    container.appendChild(row);
    scrollMessages(container);

    return id;
}

function setMessageQuestion(messageId, question) {
    const row = document.getElementById(messageId);
    if (row) {
        row.dataset.question = question || "";
    }
}

function updateAssistantMessage(id, answer, sources, debug, showDebug) {
    const row = document.getElementById(id);
    if (!row) return;

    const body = row.querySelector(".message-body");
    const rawResults = debug?.raw_results || debug?.rawResults || {};
    const question = row.dataset.question || debug?.question || "";

    const answerCodeFallback = extractFirstCodeBlock(answer);
    const enrichedSources = enrichSourcesWithRawResults(
        sources || [],
        rawResults,
        answerCodeFallback
    );

    row.classList.add("streamlit-answer-row");
    body.classList.add("streamlit-answer-body");
    body.innerHTML = "";

    const report = createStreamlitReport({
        question,
        answer,
        sources: enrichedSources,
        debug,
        showDebug,
        rawResults,
    });

    body.appendChild(report);

    const time = document.createElement("div");
    time.className = "message-time";
    time.textContent = getTime();
    body.appendChild(time);

    scrollMessages(row.closest(".messages"));
}

function createStreamlitReport({ question, answer, sources, debug, showDebug, rawResults }) {
    const wrapper = document.createElement("article");
    wrapper.className = "streamlit-report";

    if (question) {
        wrapper.appendChild(createSectionTitle("Question"));

        const questionText = document.createElement("p");
        questionText.className = "streamlit-question-text";
        questionText.textContent = question;
        wrapper.appendChild(questionText);
    }

    const warnings = normalizeWarnings(debug?.warnings || inferWarningsFromRawResults(rawResults));

    if (warnings.length > 0) {
        wrapper.appendChild(createWarningsBlock(warnings));
    }

    wrapper.appendChild(createSectionTitle("Answer"));

    const answerBlock = document.createElement("div");
    answerBlock.className = "streamlit-answer-markdown";
    answerBlock.innerHTML = renderAnswerMarkdown(answer || "Không có câu trả lời.");
    wrapper.appendChild(answerBlock);

    if (showDebug && debug) {
        const debugGrid = document.createElement("div");
        debugGrid.className = "streamlit-debug-grid";

        const queryCard = document.createElement("div");
        queryCard.className = "streamlit-debug-card";
        queryCard.innerHTML = `
            <h3>Query Type</h3>
            <div class="streamlit-mono-box">${escapeHtml(debug.query_type || "unknown")}</div>
        `;

        const toolsCard = document.createElement("div");
        toolsCard.className = "streamlit-debug-card";
        toolsCard.innerHTML = `
            <h3>Tools Used</h3>
            <div class="streamlit-tools-list">
                ${(debug.tools_used || [])
                    .map((tool) => `<div class="streamlit-mono-box">${escapeHtml(tool)}</div>`)
                    .join("") || '<div class="streamlit-mono-box">No tools reported</div>'}
            </div>
        `;

        debugGrid.appendChild(queryCard);
        debugGrid.appendChild(toolsCard);
        wrapper.appendChild(debugGrid);
    }

    if (sources && sources.length > 0) {
        wrapper.appendChild(createStreamlitSourcesBlock(sources));
    }

    if (showDebug && rawResults && Object.keys(rawResults).length > 0) {
        wrapper.appendChild(createRawResultsDetails(rawResults));
    }

    return wrapper;
}


function normalizeWarnings(value) {
    if (!value) {
        return [];
    }

    if (typeof value === "string") {
        const clean = value.trim();
        return clean ? [clean] : [];
    }

    if (Array.isArray(value)) {
        return value
            .map((item) => String(item || "").trim())
            .filter(Boolean)
            .filter((item, index, array) => array.indexOf(item) === index);
    }

    return [];
}


function inferWarningsFromRawResults(rawResults) {
    const warnings = [];

    function addWarning(message, path = "") {
        const clean = String(message || "").trim();

        if (clean) {
            const finalMsg = path ? `[Found at ${path}] ${clean}` : clean;
            if (!warnings.includes(finalMsg)) {
                warnings.push(finalMsg);
            }
        }
    }

    function visit(value, key, path = "root") {
        if (!value) {
            return;
        }

        // Do not scan source code or text excerpts for warnings
        if (key === "source_excerpts" || key === "search_results" || key === "sources" || key === "text" || key === "content") {
            return;
        }

        if (typeof value === "string") {
            const lower = value.toLowerCase();

            if (
                lower.includes("llm") &&
                (
                    lower.includes("unavailable") ||
                    lower.includes("rate-limited") ||
                    lower.includes("rate limited") ||
                    lower.includes("fallback") ||
                    lower.includes("failed") ||
                    lower.includes("error")
                )
            ) {
                if (lower.includes("router")) {
                    addWarning("LLM Query Router is currently unavailable or rate-limited. The system is using the fallback rule-based router.", path);
                } else if (lower.includes("answer") || lower.includes("generation")) {
                    addWarning("LLM answer generation is currently unavailable or rate-limited. Showing the fallback tool/retrieval-based answer.", path);
                } else {
                    addWarning(value, path);
                }
            }

            return;
        }

        if (Array.isArray(value)) {
            value.forEach((item, index) => visit(item, key, `${path}[${index}]`));
            return;
        }

        if (typeof value !== "object") {
            return;
        }

        const router = value.router;

        if (typeof router === "string" && router.startsWith("fallback")) {
            addWarning("LLM Query Router is currently unavailable or rate-limited. The system is using the fallback rule-based router.");
        }

        const routers = value.routers;

        if (
            Array.isArray(routers) &&
            routers.some((item) => typeof item === "string" && item.startsWith("fallback"))
        ) {
            addWarning("LLM Query Router is currently unavailable or rate-limited. The system is using the fallback rule-based router.");
        }

        if (value.router_error || value.router_errors) {
            addWarning("LLM Query Router is currently unavailable or rate-limited. The system is using the fallback rule-based router.", path);
        }

        if (value.llm_warning || value.llm_error) {
            addWarning("LLM answer generation is currently unavailable or rate-limited. Showing the fallback tool/retrieval-based answer.", path);
        }

        Object.entries(value).forEach(([k, v]) => visit(v, k, `${path}.${k}`));
    }

    visit(rawResults, "raw_results", "raw_results");
    return warnings;
}


function createWarningsBlock(warnings) {
    const wrapper = document.createElement("div");
    wrapper.className = "llm-warnings-block";

    warnings.forEach((warning) => {
        const item = document.createElement("div");
        item.className = "llm-warning-item";
        item.textContent = warning;
        wrapper.appendChild(item);
    });

    return wrapper;
}


function createSectionTitle(text) {
    const title = document.createElement("h2");
    title.className = "streamlit-section-title";
    title.textContent = text;
    return title;
}

function createStreamlitSourcesBlock(sources) {
    const section = document.createElement("section");
    section.className = "streamlit-sources";

    section.appendChild(createSectionTitle("Sources"));

    const list = document.createElement("ol");
    list.className = "streamlit-source-list";

    sources.forEach((source) => {
        const item = document.createElement("li");
        item.className = "streamlit-source-item";

        const path = normalizePathForDisplay(
            source.relative_path || source.file_path || source.path || "unknown"
        );
        const startLine = source.start_line || source.line_start;
        const endLine = source.end_line || source.line_end;
        const line = startLine && endLine ? `:${startLine}-${endLine}` : "";
        const symbol = source.symbol_name || source.qualified_name || source.symbol || "";

        const header = document.createElement("div");
        header.className = "streamlit-source-header";

        const pathSpan = document.createElement("span");
        pathSpan.className = "inline-code";
        pathSpan.textContent = `${path}${line}`;
        header.appendChild(pathSpan);

        if (symbol) {
            const dash = document.createElement("span");
            dash.className = "streamlit-source-dash";
            dash.textContent = " — ";
            header.appendChild(dash);

            const symbolSpan = document.createElement("span");
            symbolSpan.className = "inline-code";
            symbolSpan.textContent = symbol;
            header.appendChild(symbolSpan);
        }

        item.appendChild(header);

        const excerptText = getSourceExcerptText(source);
        const details = document.createElement("details");
        details.className = "streamlit-details source-excerpt-details";

        const summary = document.createElement("summary");
        summary.textContent = "View source excerpt";
        details.appendChild(summary);

        const pre = document.createElement("pre");
        pre.className = "streamlit-code-excerpt";
        pre.textContent = excerptText;
        details.appendChild(pre);

        item.appendChild(details);
        list.appendChild(item);
    });

    section.appendChild(list);
    return section;
}

function createRawResultsDetails(rawResults) {
    const details = document.createElement("details");
    details.className = "streamlit-details raw-results-details";

    const summary = document.createElement("summary");
    summary.textContent = "Raw Results";
    details.appendChild(summary);

    const pre = document.createElement("pre");
    pre.className = "raw-json";
    pre.textContent = formatJsonForDisplay(rawResults);
    details.appendChild(pre);

    return details;
}

function scrollMessages(container) {
    if (!container) return;
    container.scrollTop = container.scrollHeight;
}

function getTime() {
    return new Date().toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
    });
}

function setButtonLoading(button, loading, text) {
    button.disabled = loading;
    button.textContent = text;
}

function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function renderAnswerMarkdown(value) {
    const text = String(value || "").replace(/\r\n/g, "\n");
    const codeBlocks = [];

    const withPlaceholders = text.replace(
        /```([a-zA-Z0-9_-]*)\s*\n?([\s\S]*?)```/g,
        (_, language, code) => {
            const index = codeBlocks.length;
            codeBlocks.push({
                language: language || "",
                code: code.trimEnd(),
            });
            return `\n__CODE_BLOCK_${index}__\n`;
        }
    );

    const parts = withPlaceholders.split(/(__CODE_BLOCK_\d+__)/g);

    return parts
        .map((part) => {
            const match = part.match(/^__CODE_BLOCK_(\d+)__$/);
            if (match) {
                const block = codeBlocks[Number(match[1])];
                const label = block.language
                    ? `<div class="answer-code-label">${escapeHtml(block.language)}</div>`
                    : "";

                return `
                    <div class="answer-code-wrap">
                        ${label}
                        <pre class="answer-code"><code>${escapeHtml(block.code)}</code></pre>
                    </div>
                `;
            }

            return renderTextSegment(part);
        })
        .filter(Boolean)
        .join("");
}

function renderTextSegment(segment) {
    const text = String(segment || "").trim();
    if (!text) return "";

    const lines = text.split("\n");
    const html = [];
    let listBuffer = [];

    function flushList() {
        if (listBuffer.length === 0) return;

        html.push(
            `<ol class="answer-list">${listBuffer
                .map((line) => `<li>${renderInlineMarkdown(line)}</li>`)
                .join("")}</ol>`
        );
        listBuffer = [];
    }

    for (const line of lines) {
        const numbered = line.match(/^\s*\d+\.\s+(.*)$/);

        if (numbered) {
            listBuffer.push(numbered[1]);
            continue;
        }

        flushList();

        if (!line.trim()) {
            continue;
        }

        html.push(`<p class="answer-paragraph">${renderInlineMarkdown(line)}</p>`);
    }

    flushList();

    return html.join("");
}

function renderInlineMarkdown(value) {
    let html = escapeHtml(value);

    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    return html;
}

function enrichSourcesWithRawResults(sources, rawResults, answerCodeFallback = "") {
    return (sources || []).map((source) => {
        const existingExcerpt =
            source.excerpt ||
            source.text ||
            source.content ||
            source.code ||
            "";

        if (existingExcerpt) {
            return {
                ...source,
                excerpt: existingExcerpt,
            };
        }

        const rawExcerpt = findExcerptForSource(source, rawResults);

        return {
            ...source,
            excerpt: rawExcerpt || answerCodeFallback,
        };
    });
}

function findExcerptForSource(source, rawResults) {
    if (!rawResults) return "";

    const directFileContent =
        rawResults.file_content ||
        rawResults.fileContent ||
        rawResults.source_excerpt ||
        rawResults.sourceExcerpt;

    if (typeof directFileContent === "string" && directFileContent.trim()) {
        return directFileContent;
    }

    const sourceExcerpts =
        rawResults.source_excerpts ||
        rawResults.sourceExcerpts ||
        rawResults.excerpts;

    const fromSourceExcerpts = findExcerptInValue(source, sourceExcerpts, 0, true);
    if (fromSourceExcerpts) return fromSourceExcerpts;

    const fileContents =
        rawResults.file_contents ||
        rawResults.fileContents ||
        rawResults.files;

    const fromFileContents = findExcerptInValue(source, fileContents, 0, true);
    if (fromFileContents) return fromFileContents;

    return findExcerptInValue(source, rawResults, 0, false);
}

function findExcerptInValue(source, value, depth = 0, allowStringFallback = false) {
    if (!value || depth > 7) {
        return "";
    }

    if (typeof value === "string") {
        return allowStringFallback ? value : "";
    }

    if (Array.isArray(value)) {
        for (const item of value) {
            const result = findExcerptInValue(source, item, depth + 1, allowStringFallback);
            if (result) return result;
        }

        return "";
    }

    if (typeof value !== "object") {
        return "";
    }

    const sourcePath = normalizePathForCompare(
        source.relative_path || source.file_path || source.path || ""
    );

    for (const [key, item] of Object.entries(value)) {
        const keyPath = normalizePathForCompare(key);

        if (
            typeof item === "string" &&
            sourcePath &&
            pathsLookRelated(sourcePath, keyPath)
        ) {
            return item;
        }
    }

    const objectPath = normalizePathForCompare(
        value.relative_path ||
        value.file_path ||
        value.path ||
        value.filename ||
        value.file ||
        ""
    );

    const objectExcerpt =
        value.excerpt ||
        value.text ||
        value.content ||
        value.code ||
        value.file_content ||
        value.fileContent ||
        "";

    if (
        typeof objectExcerpt === "string" &&
        objectExcerpt.trim() &&
        (!sourcePath || !objectPath || pathsLookRelated(sourcePath, objectPath))
    ) {
        return objectExcerpt;
    }

    for (const item of Object.values(value)) {
        const result = findExcerptInValue(source, item, depth + 1, allowStringFallback);
        if (result) return result;
    }

    return "";
}

function extractFirstCodeBlock(value) {
    const text = String(value || "").replace(/\r\n/g, "\n");
    const match = text.match(/```[a-zA-Z0-9_-]*\s*\n?([\s\S]*?)```/);

    if (!match) return "";

    return match[1].trim();
}

function pathsLookRelated(a, b) {
    if (!a || !b) return false;

    return (
        a === b ||
        a.endsWith(b) ||
        b.endsWith(a) ||
        a.includes(b) ||
        b.includes(a)
    );
}

function getSourceExcerptText(source) {
    const excerpt =
        source.excerpt ||
        source.text ||
        source.content ||
        source.code ||
        "";

    if (!excerpt) {
        return "Backend chưa trả excerpt cho source này.";
    }

    return String(excerpt);
}

function formatJsonForDisplay(value) {
    try {
        const text = JSON.stringify(value, null, 2);
        const maxLength = 25000;

        if (text.length > maxLength) {
            return text.slice(0, maxLength) + "\n... truncated ...";
        }

        return text;
    } catch (error) {
        return String(value);
    }
}

function normalizePathForDisplay(value) {
    return String(value || "").replaceAll("\\", "/");
}

function normalizePathForCompare(value) {
    return normalizePathForDisplay(value).toLowerCase();
}


/* =========================
   API LAYER
========================= */

async function request(path, options = {}) {
    let response;

    try {
        response = await fetch(`${API_BASE_URL}${path}`, options);
    } catch (error) {
        throw new Error(
            "Không kết nối được API. Hãy kiểm tra FastAPI đang chạy và CORS. " +
            error.message
        );
    }

    if (!response.ok) {
        const contentType = response.headers.get("content-type") || "";
        let message = `API error ${response.status}`;

        if (contentType.includes("application/json")) {
            const error = await response.json().catch(() => ({}));
            message = error.detail || error.message || error.error || message;
        } else {
            const text = await response.text().catch(() => "");
            message = text || message;
        }

        throw new Error(message);
    }

    if (response.status === 204) {
        return {};
    }

    return response.json();
}

function normalizeCompanyRepo(repo) {
    return {
        id: repo.repo_id || repo.id,
        name: repo.repo_name || repo.name || repo.repo_id || repo.id,
        status: repo.status || "ready",
        source_type: repo.source_type || "company",
        is_persistent: repo.is_persistent ?? true,
        file_count: repo.file_count || 0,
        doc_count: repo.doc_count || 0,
        text_count: repo.text_count || 0,
        docs_text_count: repo.docs_text_count || ((repo.doc_count || 0) + (repo.text_count || 0)),
        json_count: repo.json_count || 0,
        ignored_file_count: repo.ignored_file_count || 0,
        chunk_count: repo.chunk_count || 0,
        local_path: repo.local_path || "",
        collection_name: repo.collection_name || "",
    };
}

async function healthCheckApi() {
    if (USE_MOCK) {
        await wait(100);
        return { status: "ok" };
    }

    return request("/health");
}

async function getVisibleCompanyReposApi() {
    if (USE_MOCK) {
        await wait(300);

        return {
            repos: SOURCE_CODE_COMPANY_REPOS
                .filter((repo) => repo.enabled && repo.visible_to_user)
                .map((repo) => ({ ...repo })),
        };
    }

    const repos = await request("/company-repos");

    return {
        repos: Array.isArray(repos)
            ? repos.map(normalizeCompanyRepo)
            : [],
    };
}

async function loadCompanyRepoApi(repoId) {
    if (USE_MOCK) {
        await wait(600);

        const repo = companyRepos.find((item) => item.id === repoId) || {
            id: repoId,
            name: repoId,
            file_count: 0,
            doc_count: 0,
            text_count: 0,
            json_count: 0,
            chunk_count: 0,
            ignored_file_count: 0,
        };

        return {
            session_id: "mock_session_" + Date.now(),
            repo_id: repo.id,
            repo_name: repo.name,
            source_type: "company",
            is_persistent: true,
            local_path: "",
            collection_name: repo.id,
            file_count: repo.file_count || 0,
            doc_count: repo.doc_count || 0,
            text_count: repo.text_count || 0,
            docs_text_count: repo.docs_text_count || ((repo.doc_count || 0) + (repo.text_count || 0)),
            json_count: repo.json_count || 0,
            ignored_file_count: repo.ignored_file_count || 0,
            chunk_count: repo.chunk_count || 0,
            retrieval_mode: getRetrievalMode(),
        };
    }

    return request(`/company-repos/${encodeURIComponent(repoId)}/load`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            retrieval_mode: getRetrievalMode(),
            use_llm: true,
            use_llm_router: true,
        }),
    });
}

async function indexTemporaryGithubRepoApi(payload) {
    if (USE_MOCK) {
        await wait(900);

        const repoName =
            payload.github_url.split("/").filter(Boolean).slice(-1)[0] ||
            "github-temp-repo";

        return {
            session_id: "mock_session_" + Date.now(),
            repo_id: "temp_github_" + Date.now(),
            repo_name: repoName,
            source_type: "github",
            is_persistent: false,
            local_path: "",
            collection_name: repoName,
            file_count: 26,
            doc_count: 3,
            text_count: 1,
            docs_text_count: 4,
            json_count: 1,
            ignored_file_count: 0,
            chunk_count: 141,
            retrieval_mode: getRetrievalMode(),
        };
    }

    return request("/temporary-repos/github", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            github_url: payload.github_url,
            branch: payload.branch || null,
            retrieval_mode: getRetrievalMode(),
            use_llm: true,
            use_llm_router: true,
        }),
    });
}

async function uploadTemporaryZipRepoApi(file) {
    if (USE_MOCK) {
        await wait(900);

        const repoName = file.name.replace(/\.zip$/i, "");

        return {
            session_id: "mock_session_" + Date.now(),
            repo_id: "temp_zip_" + Date.now(),
            repo_name: repoName,
            source_type: "zip_upload",
            is_persistent: false,
            local_path: "",
            collection_name: repoName,
            file_count: 18,
            doc_count: 3,
            text_count: 1,
            docs_text_count: 4,
            json_count: 1,
            ignored_file_count: 0,
            chunk_count: 87,
            retrieval_mode: getRetrievalMode(),
        };
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("retrieval_mode", getRetrievalMode());
    formData.append("use_llm", "true");
    formData.append("use_llm_router", "true");

    return request("/temporary-repos/zip", {
        method: "POST",
        body: formData,
    });
}

async function deleteTemporaryRepoApi(repoId, sessionId) {
    const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";

    return request(`/temporary-repos/${encodeURIComponent(repoId)}${query}`, {
        method: "DELETE",
    });
}

async function chatWithCodebaseApi(payload) {
    if (USE_MOCK) {
        await wait(900);

        return {
            session_id: payload.session_id,
            question: payload.question,
            answer:
                `Đây là câu trả lời mock cho câu hỏi:\n\n"${payload.question}"\n\n` +
                `Session ID: ${payload.session_id}\n\n` +
                `Khi nối FastAPI thật, response này sẽ đến từ LLM Query Router + RAG + Graph RAG.`,
            query_type: "code_explanation",
            tools_used: ["query_router", "retriever", "answer_generator"],
            raw_results: {},
            sources: [
                {
                    file_path: "src/indexing/codebase_indexer.py",
                    relative_path: "src/indexing/codebase_indexer.py",
                    start_line: 28,
                    end_line: 88,
                    symbol_name: "build_codebase_agent",
                    score: 0.91,
                    excerpt:
                        "def build_codebase_agent(...):\n    python_files = scan_python_files(repo_path)\n    markdown_files = scan_markdown_files(repo_path)\n    ...",
                },
            ],
        };
    }

    return request("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            session_id: payload.session_id,
            question: payload.question,
        }),
    });
}

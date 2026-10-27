(() => {
  "use strict";
  const words = {
    zh: {
      skip: "跳转到主要内容", navigation: "工作空间导航", brand: "客服知识台", workspace: "工作空间", chatNav: "知识问答", sessionsNav: "会话记录", ownedSessions: "记录归当前浏览器所有", language: "界面语言", productNote: "本地知识 · 来源可查",
      chatEyebrow: "CUSTOMER SUPPORT / 知识检索", chatTitle: "答案，从依据开始。", chatSubtitle: "检索本地知识文档，逐条查看回答背后的原文。", newChat: "新建会话", demoTitle: "本地检索摘录，未调用 LLM", demoDescription: "无需 API key。回答来自本地文档片段，不是模型生成。", apiTitle: "API 模式 · 使用你配置的模型服务", apiDescription: "需要自备服务与凭据。消息、对话上下文和检索片段会发送至配置的提供方。", conversation: "对话", unsavedSession: "尚未开始", sessionPrefix: "会话", emptyTitle: "先问一个具体问题", emptyDescription: "试试虚构客服知识库中的配送、退换货与客服时间问题。", shippingPrompt: "订单一般多久发货？", returnsPrompt: "如何申请退货？", supportPrompt: "客服什么时候在线？", messageLabel: "输入问题", messagePlaceholder: "输入你的客服问题…", send: "发送", thinking: "正在检索知识文档…", contactConsent: "允许将本条消息中的联系方式另存为本地线索", contactPrivacy: "默认不提取联系方式；本应用不会主动外发线索或联系你。", contactPrivacyApi: "默认不另存联系方式；本应用不主动外发线索。API 模式下，消息内容仍会发送至你配置的模型服务。", keyboardHint: "Enter 发送 · Shift+Enter 换行", evidence: "来源证据", evidenceIntro: "原始相对路径、字符范围和检索分数，保留可核查的上下文。", evidenceEmptyTitle: "证据会显示在这里", evidenceEmptyDescription: "发送问题后查看命中的文档片段。无匹配时会明确说明。", noEvidenceTitle: "没有匹配的来源", noEvidenceDescription: "当前回答没有可引用的知识片段。请换个具体问题，或检查本地知识文档。", evidenceFooter: "切换语言不会改写文档原文", retrievalQuery: "检索问题", source: "来源", score: "分数", chunk: "片段", characters: "字符范围", userRole: "你", assistantRole: "知识助手", demoMode: "本地摘录 · 无 LLM", apiMode: "API 模式", sourceAction: "查看来源", noGrounding: "未找到依据", contactSaved: "已按授权保存本地线索", feedbackSaved: "已记录本地反馈", loadingConversation: "正在恢复会话…", conversationRestored: "会话已恢复，可以继续提问。", requestFailed: "请求失败。草稿已保留，请稍后重试。", networkError: "连接失败，请确认本地服务仍在运行。", sessionNotFound: "找不到该会话，或当前浏览器无权访问。", invalidMessage: "请输入 1 至 {limit} 个字符的问题。", csrfError: "安全校验未通过。请刷新页面后重试。", providerError: "模型服务请求失败。请检查本地 API 配置；本次没有回退为本地演示。", indexError: "知识索引不可用或需要重建，请运行 build_index 后重试。", configurationError: "运行配置或可选依赖不完整，请检查终端与项目文档。", invalidRequest: "请求格式无效，请刷新页面后重试。", tooLarge: "输入过长，请缩短问题后重试。", unexpectedError: "服务暂时无法完成请求，请检查本地终端。",
      sessionsEyebrow: "YOUR WORKSPACE / 会话档案", sessionsTitle: "继续上一次的对话。", sessionsSubtitle: "只显示当前浏览器拥有的记录；可恢复、导出或删除。", allSessions: "全部会话", refresh: "刷新列表", loadingSessions: "正在加载你的会话…", noSessionsTitle: "这里还没有会话", noSessionsDescription: "完成第一次问答后，记录会自动保存在本地数据库中。", startConversation: "开始问答", historyFootnote: "导出文件含消息与来源片段。删除会话也会删除其本地线索和反馈；清除浏览器 cookie 后可能无法再次访问旧会话。", untitledSession: "未命名会话", messageCount: "条消息", updated: "更新于", restore: "继续对话", export: "导出 JSON", delete: "删除", deleting: "正在删除…", exporting: "正在导出…", deleteConfirm: "删除此会话及其消息、本地线索和反馈？此操作无法撤销。", sessionDeleted: "会话已删除。", exportDone: "会话 JSON 已导出。", unknownDate: "时间未知", sourceUnavailable: "来源路径缺失"
    },
    en: {
      skip: "Skip to main content", navigation: "Workspace navigation", brand: "Support desk", workspace: "WORKSPACE", chatNav: "Knowledge chat", sessionsNav: "Conversations", ownedSessions: "History belongs to this browser", language: "Interface language", productNote: "Local knowledge · traceable sources",
      chatEyebrow: "CUSTOMER SUPPORT / KNOWLEDGE RETRIEVAL", chatTitle: "Every answer starts with evidence.", chatSubtitle: "Search local knowledge and inspect the original passages behind each answer.", newChat: "New conversation", demoTitle: "Local retrieval excerpts · no LLM called", demoDescription: "No API key needed. Answers quote local document chunks; they are not model-generated.", apiTitle: "API mode · your configured model provider", apiDescription: "Bring your own provider and credentials. Messages, conversation context and retrieved passages are sent to that provider.", conversation: "Conversation", unsavedSession: "Not started", sessionPrefix: "Session", emptyTitle: "Start with a specific question", emptyDescription: "Try shipping, returns or support hours from the fictional support knowledge base.", shippingPrompt: "When will my order ship?", returnsPrompt: "How do I request a return?", supportPrompt: "When is customer support available?", messageLabel: "Your question", messagePlaceholder: "Ask a customer support question…", send: "Send", thinking: "Searching the knowledge documents…", contactConsent: "Save contact details in this message as a separate local lead", contactPrivacy: "Contact capture is off by default. This app does not send leads out or contact you.", contactPrivacyApi: "Separate contact capture is off by default; this app does not send leads out. In API mode, message content is still sent to your configured model provider.", keyboardHint: "Enter to send · Shift+Enter for a new line", evidence: "Source evidence", evidenceIntro: "Actual relative paths, character ranges and retrieval scores preserve inspectable context.", evidenceEmptyTitle: "Evidence appears here", evidenceEmptyDescription: "Send a question to inspect retrieved passages. A missing match is shown explicitly.", noEvidenceTitle: "No matching source", noEvidenceDescription: "There is no supporting knowledge passage for this answer. Try a more specific question or check the local documents.", evidenceFooter: "Language changes preserve the original source text", retrievalQuery: "Retrieval question", source: "Source", score: "Score", chunk: "Chunk", characters: "Characters", userRole: "You", assistantRole: "Knowledge assistant", demoMode: "Local excerpts · no LLM", apiMode: "API mode", sourceAction: "View sources", noGrounding: "No supporting passage", contactSaved: "Local lead saved with consent", feedbackSaved: "Local feedback recorded", loadingConversation: "Restoring your conversation…", conversationRestored: "Conversation restored. You can continue asking questions.", requestFailed: "The request failed. Your draft was kept; please try again later.", networkError: "Connection failed. Check that the local server is running.", sessionNotFound: "This conversation was not found or is not owned by this browser.", invalidMessage: "Enter a question containing 1 to {limit} characters.", csrfError: "The security check failed. Refresh the page and try again.", providerError: "The model provider request failed. Check your local API configuration. This request did not fall back to the local demo.", indexError: "The knowledge index is unavailable or needs rebuilding. Run build_index and try again.", configurationError: "Configuration or optional dependencies are incomplete. Check your terminal and the project documentation.", invalidRequest: "Invalid request format. Refresh the page and try again.", tooLarge: "The input is too long. Shorten the question and try again.", unexpectedError: "The service could not complete this request. Check the local terminal.",
      sessionsEyebrow: "YOUR WORKSPACE / CONVERSATION ARCHIVE", sessionsTitle: "Pick up where you left off.", sessionsSubtitle: "Only this browser's conversations appear here. Restore, export or delete them.", allSessions: "All conversations", refresh: "Refresh", loadingSessions: "Loading your conversations…", noSessionsTitle: "No conversations yet", noSessionsDescription: "Your first completed exchange will be saved in the local database.", startConversation: "Start a conversation", historyFootnote: "Exports contain messages and source passages. Deleting a conversation also deletes its local leads and feedback. Clearing browser cookies can remove access to previous conversations.", untitledSession: "Untitled conversation", messageCount: "messages", updated: "Updated", restore: "Continue", export: "Export JSON", delete: "Delete", deleting: "Deleting…", exporting: "Exporting…", deleteConfirm: "Delete this conversation, its messages, local leads and feedback? This cannot be undone.", sessionDeleted: "Conversation deleted.", exportDone: "Conversation JSON exported.", unknownDate: "Unknown date", sourceUnavailable: "Source path missing"
    }
  };
  let lang = "zh";
  try { if (localStorage.getItem("lang") === "en") lang = "en"; } catch (_) { /* Browser storage can be disabled. */ }
  const t = key => words[lang][key] || words.zh[key] || key;
  const node = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  };
  const applyLanguage = () => {
    document.documentElement.lang = lang === "en" ? "en" : "zh-CN";
    document.querySelectorAll("[data-i18n]").forEach(element => { element.textContent = t(element.dataset.i18n); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(element => { element.placeholder = t(element.dataset.i18nPlaceholder); });
    document.querySelectorAll("[data-i18n-aria]").forEach(element => { element.setAttribute("aria-label", t(element.dataset.i18nAria)); });
    const select = document.getElementById("language");
    if (select) { select.value = lang; select.setAttribute("aria-label", t("language")); }
    document.title = `${document.body.dataset.page === "sessions" ? t("sessionsNav") : t("brand")} · RAG Workbench`;
    document.dispatchEvent(new CustomEvent("workbench:language", {detail: {lang}}));
  };
  const csrfToken = () => {
    const token = document.querySelector("[name=csrfmiddlewaretoken]");
    if (token && token.value) return token.value;
    const cookie = document.cookie.split(";").find(value => value.trim().startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.trim().slice("csrftoken=".length)) : "";
  };
  const request = async (url, options = {}) => {
    const method = options.method || "GET";
    const headers = {Accept: "application/json", ...(options.headers || {})};
    if (method !== "GET") headers["X-CSRFToken"] = csrfToken();
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    let response;
    try { response = await fetch(url, {...options, method, headers, credentials: "same-origin"}); }
    catch (_) { throw {code: "network_error", status: 0}; }
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* Framework errors may be HTML. */ }
    if (!response.ok) throw {...(payload && payload.error ? payload.error : {}), status: response.status};
    if (!payload || typeof payload !== "object") throw {code: "invalid_response", status: response.status};
    return payload;
  };
  const errorText = error => {
    const code = String(error && error.code || "").toLowerCase();
    if (code === "network_error") return t("networkError");
    if ((error && error.status === 403) || code.includes("csrf")) return t("csrfError");
    if ((error && error.status === 404) || code.includes("not_found") || code.includes("ownership")) return t("sessionNotFound");
    if ((error && error.status === 413) || code.includes("too_large") || code.includes("too_long")) return t("tooLarge");
    if (/provider|upstream|api_error|model_error/.test(code)) return t("providerError");
    if (/index|corpus|document|empty_knowledge/.test(code)) return t("indexError");
    if (/config|dependency|dependencies|missing_key|missing_api|backend/.test(code)) return t("configurationError");
    if (/message|question/.test(code)) return t("invalidMessage").replace("{limit}", document.body.dataset.maxQuestionChars || "4000");
    if ((error && error.status === 400) || /invalid|json|method/.test(code)) return t("invalidRequest");
    return t("unexpectedError");
  };
  const alert = (element, text, success = false) => {
    element.textContent = text || "";
    element.hidden = !text;
    element.classList.toggle("success", success);
  };
  const date = value => {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return t("unknownDate");
    return new Intl.DateTimeFormat(lang === "en" ? "en-GB" : "zh-CN", {year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"}).format(parsed);
  };
  const exportSession = async sessionId => {
    const payload = await request(`/api/sessions/${encodeURIComponent(sessionId)}/export/`);
    const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json;charset=utf-8"});
    const url = URL.createObjectURL(blob);
    const link = node("a");
    link.href = url;
    link.download = `conversation-${String(sessionId).replace(/[^A-Za-z0-9-]/g, "")}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  window.Workbench = {t, node, request, errorText, alert, date, exportSession, get lang() { return lang; }};
  document.getElementById("language").addEventListener("change", event => {
    lang = event.target.value === "en" ? "en" : "zh";
    try { localStorage.setItem("lang", lang); } catch (_) { /* The selected language still works for this page. */ }
    applyLanguage();
  });
  applyLanguage();
})();

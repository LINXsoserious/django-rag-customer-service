(() => {
  "use strict";
  const ui = window.Workbench;
  const form = document.getElementById("chat-form");
  const input = document.getElementById("message");
  const consent = document.getElementById("store-contact");
  const send = document.getElementById("send-message");
  const newChat = document.getElementById("new-chat");
  const messages = document.getElementById("messages");
  const empty = document.getElementById("empty-state");
  const pending = document.getElementById("pending");
  const chatAlert = document.getElementById("chat-alert");
  const scroll = document.getElementById("conversation-scroll");
  const evidence = document.getElementById("evidence-content");
  const backend = document.body.dataset.backend;
  const state = {sessionId: null, messages: [], busy: false, selected: null, queried: false, alert: null};
  const modeKey = mode => mode === "openai" ? "apiMode" : "demoMode";
  const isApi = () => backend === "openai";
  const busy = value => {
    state.busy = value;
    pending.hidden = !value;
    send.disabled = value || !input.value.trim();
    newChat.disabled = value;
    input.setAttribute("aria-busy", String(value));
  };
  const showAlert = (key, success = false, error = null) => {
    state.alert = key || error ? {key, success, error} : null;
    ui.alert(chatAlert, error ? ui.errorText(error) : key ? ui.t(key) : "", success);
  };
  const scrollToEnd = () => requestAnimationFrame(() => { scroll.scrollTop = scroll.scrollHeight; });
  const updateBanner = () => {
    const api = isApi();
    document.getElementById("mode-banner").classList.toggle("api", api);
    document.getElementById("mode-badge").textContent = api ? "YOUR API" : "LOCAL DEMO";
    document.getElementById("mode-title").textContent = ui.t(api ? "apiTitle" : "demoTitle");
    document.getElementById("mode-description").textContent = ui.t(api ? "apiDescription" : "demoDescription");
    document.getElementById("privacy-note").textContent = ui.t(api ? "contactPrivacyApi" : "contactPrivacy");
    document.getElementById("session-label").textContent = state.sessionId ? `${ui.t("sessionPrefix")} ${state.sessionId.slice(0, 8)}` : ui.t("unsavedSession");
  };
  const renderEvidence = () => {
    evidence.replaceChildren();
    const selected = state.selected === null ? null : state.messages[state.selected];
    const sources = selected && Array.isArray(selected.sources) ? selected.sources : [];
    document.getElementById("source-count").textContent = String(sources.length);
    const query = selected && selected.retrieval_query;
    document.getElementById("retrieval-query-wrap").hidden = !query;
    document.getElementById("retrieval-query").textContent = query || "";
    if (!sources.length) {
      const blank = ui.node("div", "evidence-empty");
      const glyph = ui.node("span", "", "⌕");
      glyph.setAttribute("aria-hidden", "true");
      blank.append(glyph, ui.node("h3", "", ui.t(state.queried ? "noEvidenceTitle" : "evidenceEmptyTitle")), ui.node("p", "", ui.t(state.queried ? "noEvidenceDescription" : "evidenceEmptyDescription")));
      evidence.append(blank);
      return;
    }
    sources.forEach((source, index) => {
      const card = ui.node("article", "source-card");
      const top = ui.node("div", "source-top");
      const numericScore = Number(source.score);
      const score = Number.isFinite(numericScore) ? numericScore.toFixed(4) : "—";
      top.append(ui.node("span", "source-number", String(index + 1).padStart(2, "0")), ui.node("span", "source-score", `${ui.t("score")} ${score}`));
      const start = Number.isInteger(source.start) ? source.start : "?";
      const end = Number.isInteger(source.end) ? source.end : "?";
      card.append(top, ui.node("h3", "source-path", source.source || ui.t("sourceUnavailable")), ui.node("p", "source-meta", `${ui.t("chunk")} ${source.chunk_id === undefined ? "?" : source.chunk_id} · ${ui.t("characters")} ${start}–${end}`), ui.node("p", "source-snippet", source.text || ""));
      evidence.append(card);
    });
  };
  const renderMessages = () => {
    empty.hidden = state.messages.length > 0 || state.busy;
    messages.replaceChildren();
    state.messages.forEach((message, index) => {
      const assistant = message.role === "assistant";
      const article = ui.node("article", `message ${assistant ? "assistant" : "user"}`);
      const heading = ui.node("div", "message-heading");
      const avatar = ui.node("span", "avatar", assistant ? "R" : "U");
      avatar.setAttribute("aria-hidden", "true");
      heading.append(avatar, ui.node("span", "message-role", ui.t(assistant ? "assistantRole" : "userRole")));
      if (assistant) heading.append(ui.node("span", "message-mode", ui.t(modeKey(message.mode))));
      article.append(heading, ui.node("div", "message-content", message.content || ""));
      if (assistant) {
        const actions = ui.node("div", "message-actions");
        const button = ui.node("button", "evidence-button", `${ui.t("sourceAction")} · ${Array.isArray(message.sources) ? message.sources.length : 0}`);
        button.type = "button";
        button.setAttribute("aria-pressed", String(state.selected === index));
        button.addEventListener("click", () => { state.selected = index; state.queried = true; renderMessages(); renderEvidence(); });
        actions.append(button);
        if (message.grounded === false || !Array.isArray(message.sources) || !message.sources.length) actions.append(ui.node("span", "grounding-note", ui.t("noGrounding")));
        article.append(actions);
      }
      messages.append(article);
    });
  };
  const refreshLanguage = () => {
    const previousScrollTop = scroll.scrollTop;
    updateBanner();
    renderMessages();
    renderEvidence();
    if (state.alert) ui.alert(chatAlert, state.alert.error ? ui.errorText(state.alert.error) : ui.t(state.alert.key), state.alert.success);
    requestAnimationFrame(() => { scroll.scrollTop = previousScrollTop; });
  };
  const restore = async sessionId => {
    busy(true);
    showAlert("loadingConversation");
    try {
      const payload = await ui.request(`/api/sessions/${encodeURIComponent(sessionId)}/`);
      state.sessionId = String(payload.session_id);
      state.messages = Array.isArray(payload.messages) ? payload.messages : [];
      state.selected = null;
      state.messages.forEach((message, index) => { if (message.role === "assistant") state.selected = index; });
      state.queried = state.selected !== null;
      showAlert("conversationRestored", true);
    } catch (error) { showAlert(null, false, error); }
    finally { busy(false); refreshLanguage(); scrollToEnd(); }
  };
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const question = input.value.trim();
    if (state.busy || !question) return;
    const userMessage = {role: "user", content: question, sources: []};
    state.messages.push(userMessage);
    input.value = "";
    showAlert(null);
    busy(true);
    renderMessages();
    scrollToEnd();
    try {
      const body = {message: question, lang: ui.lang, store_contact: consent.checked};
      if (state.sessionId) body.session_id = state.sessionId;
      const payload = await ui.request("/api/chat/", {method: "POST", body: JSON.stringify(body)});
      state.sessionId = String(payload.session_id);
      state.messages.push({role: "assistant", content: payload.answer, sources: payload.sources, mode: payload.mode, retrieval_query: payload.retrieval_query, grounded: payload.grounded});
      state.selected = state.messages.length - 1;
      state.queried = true;
      const current = new URL(window.location.href);
      current.searchParams.set("session", state.sessionId);
      history.replaceState(null, "", `${current.pathname}${current.search}`);
      if (payload.contact_recorded) showAlert("contactSaved", true);
      else if (payload.feedback_recorded) showAlert("feedbackSaved", true);
    } catch (error) {
      const index = state.messages.indexOf(userMessage);
      if (index !== -1) state.messages.splice(index, 1);
      if (!input.value) input.value = question;
      showAlert(null, false, error);
    } finally {
      busy(false);
      refreshLanguage();
      scrollToEnd();
      input.focus();
    }
  });
  input.addEventListener("input", () => { send.disabled = state.busy || !input.value.trim(); });
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!send.disabled) form.requestSubmit(); }
  });
  newChat.addEventListener("click", () => {
    if (state.busy) return;
    state.sessionId = null;
    state.messages = [];
    state.selected = null;
    state.queried = false;
    consent.checked = false;
    input.value = "";
    showAlert(null);
    history.replaceState(null, "", window.location.pathname);
    busy(false);
    refreshLanguage();
    input.focus();
  });
  document.querySelectorAll("[data-prompt]").forEach(button => {
    button.addEventListener("click", () => {
      input.value = ui.t(`${button.dataset.prompt}Prompt`);
      send.disabled = state.busy || !input.value.trim();
      input.focus();
    });
  });
  document.addEventListener("workbench:language", refreshLanguage);
  refreshLanguage();
  const initialSession = new URLSearchParams(window.location.search).get("session");
  if (initialSession) restore(initialSession);
})();

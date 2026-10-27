(() => {
  "use strict";
  const ui = window.Workbench;
  const list = document.getElementById("sessions-list");
  const loading = document.getElementById("sessions-loading");
  const empty = document.getElementById("sessions-empty");
  const refresh = document.getElementById("refresh-sessions");
  const alertBox = document.getElementById("sessions-alert");
  const state = {sessions: [], busy: false, loaded: false, alert: null};
  const showAlert = (key, success = false, error = null) => {
    state.alert = key || error ? {key, success, error} : null;
    ui.alert(alertBox, error ? ui.errorText(error) : key ? ui.t(key) : "", success);
  };
  const render = () => {
    list.replaceChildren();
    document.getElementById("history-count").textContent = String(state.sessions.length);
    empty.hidden = state.busy || !state.loaded || state.sessions.length > 0;
    state.sessions.forEach(session => {
      const id = String(session.session_id);
      const card = ui.node("article", "session-card");
      const top = ui.node("div", "session-card-top");
      top.append(ui.node("span", "session-id", id.slice(0, 8)), ui.node("span", "count-badge", `${Number(session.message_count) || 0} ${ui.t("messageCount")}`));
      card.append(top, ui.node("h3", "", session.preview || ui.t("untitledSession")), ui.node("p", "session-meta", `${ui.t("updated")} ${ui.date(session.updated_at || session.created_at)}`));
      const actions = ui.node("div", "session-actions");
      const open = ui.node("a", "button button-primary", ui.t("restore"));
      open.href = `/?session=${encodeURIComponent(id)}`;
      const exportButton = ui.node("button", "button", ui.t("export"));
      exportButton.type = "button";
      exportButton.addEventListener("click", async () => {
        exportButton.disabled = true;
        exportButton.textContent = ui.t("exporting");
        try { await ui.exportSession(id); showAlert("exportDone", true); }
        catch (error) { showAlert(null, false, error); }
        finally { exportButton.disabled = false; exportButton.textContent = ui.t("export"); }
      });
      const deleteButton = ui.node("button", "button button-danger", ui.t("delete"));
      deleteButton.type = "button";
      deleteButton.addEventListener("click", async () => {
        if (!window.confirm(ui.t("deleteConfirm"))) return;
        deleteButton.disabled = true;
        deleteButton.textContent = ui.t("deleting");
        try {
          await ui.request(`/api/sessions/${encodeURIComponent(id)}/`, {method: "DELETE"});
          state.sessions = state.sessions.filter(item => String(item.session_id) !== id);
          showAlert("sessionDeleted", true);
          render();
        } catch (error) { showAlert(null, false, error); }
        finally { deleteButton.disabled = false; deleteButton.textContent = ui.t("delete"); }
      });
      actions.append(open, exportButton, deleteButton);
      card.append(actions);
      list.append(card);
    });
  };
  const load = async () => {
    if (state.busy) return;
    state.busy = true;
    loading.hidden = false;
    empty.hidden = true;
    refresh.disabled = true;
    showAlert(null);
    try {
      const payload = await ui.request("/api/sessions/");
      state.sessions = Array.isArray(payload.sessions) ? payload.sessions : [];
      state.loaded = true;
    } catch (error) { showAlert(null, false, error); }
    finally { state.busy = false; loading.hidden = true; refresh.disabled = false; render(); }
  };
  refresh.addEventListener("click", load);
  document.addEventListener("workbench:language", () => {
    render();
    if (state.alert) ui.alert(alertBox, state.alert.error ? ui.errorText(state.alert.error) : ui.t(state.alert.key), state.alert.success);
  });
  load();
})();

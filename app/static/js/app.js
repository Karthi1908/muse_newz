// Plain JS Controller for Your Daily Muse (Archive, Topics, Schedule, Live Build Progress)
window.DailyMuseApp = {
  currentProposal: null,
  pollTimer: null,
  editableTopics: [],
  editableGeoPreference: "Global",

  init: function () {
    this.initTopics();
    this.startStatusPolling();
  },

  togglePanel: function (panelId) {
    document.querySelectorAll(".app-drawer").forEach((el) => {
      if (el.id === panelId) {
        el.hidden = !el.hidden;
      } else {
        el.hidden = true;
      }
    });
  },

  toggleDarkMode: function () {
    const html = document.documentElement;
    const current = html.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", next);
    localStorage.setItem("daily_muse_theme", next);
  },

  // ---- Topic Management (1 to max 5 Topics — Multi-Add & Multi-Delete) ----
  initTopics: function () {
    const rawData = document.getElementById("active-topics-data");
    if (rawData) {
      try {
        this.editableTopics = JSON.parse(rawData.textContent);
      } catch (e) {
        this.editableTopics = [];
      }
    }
    this.editableGeoPreference = this.getSelectedGeoPreference();
    this.renderEditableChips();
  },

  getSelectedGeoPreference: function () {
    const sel = document.getElementById("reader-geo-select");
    const customIn = document.getElementById("reader-geo-custom-input");
    if (!sel) return this.editableGeoPreference || "Global";
    if (sel.value === "__custom__") {
      return (customIn && customIn.value.trim()) ? customIn.value.trim() : "Global";
    }
    return sel.value || "Global";
  },

  syncGeoSelectorUI: function (geoVal) {
    if (!geoVal) return;
    this.editableGeoPreference = geoVal;
    const sel = document.getElementById("reader-geo-select");
    const customIn = document.getElementById("reader-geo-custom-input");
    const toolbarGeo = document.getElementById("toolbar-geo-label");
    if (toolbarGeo) toolbarGeo.textContent = geoVal;
    if (!sel) return;
    const hasOption = Array.from(sel.options).some((o) => o.value === geoVal);
    if (hasOption) {
      sel.value = geoVal;
      if (customIn) customIn.style.display = "none";
    } else {
      sel.value = "__custom__";
      if (customIn) {
        customIn.style.display = "block";
        customIn.value = geoVal;
      }
    }
  },

  onGeoSelectChange: function () {
    const sel = document.getElementById("reader-geo-select");
    const customIn = document.getElementById("reader-geo-custom-input");
    if (sel && sel.value === "__custom__") {
      if (customIn) {
        customIn.style.display = "block";
        customIn.focus();
      }
      return;
    }
    if (customIn) customIn.style.display = "none";
    const geo = this.getSelectedGeoPreference();
    this.editableGeoPreference = geo;
    this.renderTopicProposal({
      transcript_or_input: `set region to ${geo}`,
      current_topics: this.editableTopics,
      proposed_topics: [...this.editableTopics],
      proposed_geographic_preference: geo,
      requires_replacement_choice: false,
      assistant_message: `Geographic preference updated to "${geo}". Click 'Confirm & Save' below to apply to your next edition.`,
    });
  },

  onGeoCustomChange: function () {
    const geo = this.getSelectedGeoPreference();
    this.editableGeoPreference = geo;
    this.renderTopicProposal({
      transcript_or_input: `set region to ${geo}`,
      current_topics: this.editableTopics,
      proposed_topics: [...this.editableTopics],
      proposed_geographic_preference: geo,
      requires_replacement_choice: false,
      assistant_message: `Custom geographic preference set to "${geo}". Click 'Confirm & Save' below to apply.`,
    });
  },

  onReaderNameInputChange: function () {
    const raw = (document.getElementById("reader-name-input")?.value || "").trim();
    let clean = raw;
    if (clean.toLowerCase().startsWith("the ")) clean = clean.slice(4).trim();
    if (clean.toLowerCase().endsWith(" courier")) clean = clean.slice(0, -8).trim();
    const display = clean || "Muse";
    const pubTitle = `The ${display} Courier`;
    const pubTagline = `“Made for ${display}. Checked before print.”`;
    const hintEl = document.getElementById("masthead-preview-hint");
    if (hintEl) {
      hintEl.innerHTML = `Masthead: <strong>${pubTitle}</strong> — <em>${pubTagline}</em>`;
    }
    this.renderTopicProposal({
      transcript_or_input: `set masthead name to ${display}`,
      current_topics: this.editableTopics,
      proposed_topics: [...this.editableTopics],
      proposed_geographic_preference: this.getSelectedGeoPreference(),
      requires_replacement_choice: false,
      assistant_message: `Masthead updated to "${pubTitle}" (${pubTagline}). Click 'Confirm & Save' below to apply.`,
    });
  },

  renderEditableChips: function () {
    const container = document.getElementById("active-topic-chips");
    const countEl = document.getElementById("active-topic-count");
    const countToolbarEl = document.getElementById("toolbar-topic-count");
    if (countEl) countEl.textContent = `${this.editableTopics.length} of max 5`;
    if (countToolbarEl) countToolbarEl.textContent = `${this.editableTopics.length}/5`;
    if (!container) return;

    container.innerHTML = "";
    this.editableTopics.forEach((topic, idx) => {
      const chip = document.createElement("div");
      chip.className = "topic-chip";
      chip.innerHTML = `
        <span>${topic}</span>
        <button type="button" class="topic-chip-del" title="Remove '${topic}'" onclick="window.DailyMuseApp.removeTopicByIndex(${idx})">✕</button>
      `;
      container.appendChild(chip);
    });

    const addBtn = document.getElementById("btn-add-topic-direct");
    const addInput = document.getElementById("new-topic-direct-input");
    if (this.editableTopics.length >= 5) {
      if (addBtn) addBtn.disabled = true;
      if (addInput) {
        addInput.disabled = true;
        addInput.placeholder = "Maximum 5 topics reached (remove a topic to add more)";
      }
    } else {
      if (addBtn) addBtn.disabled = false;
      if (addInput) {
        addInput.disabled = false;
        addInput.placeholder = "Enter new topic (or comma-separated topics)...";
      }
    }
  },

  removeTopicByIndex: function (idx) {
    if (this.editableTopics.length <= 1) {
      alert("You must keep at least 1 topic (between 1 and max 5 topics).");
      return;
    }
    const removedTopic = this.editableTopics[idx];
    this.editableTopics.splice(idx, 1);
    this.renderEditableChips();

    this.renderTopicProposal({
      transcript_or_input: `remove ${removedTopic}`,
      current_topics: this.editableTopics,
      proposed_topics: [...this.editableTopics],
      requires_replacement_choice: false,
      assistant_message: `Removed "${removedTopic}". You now have ${this.editableTopics.length} of max 5 topics. Click 'Confirm & Save' below to apply to future editions.`,
    });
  },

  addTopicDirectly: async function () {
    const input = document.getElementById("new-topic-direct-input");
    if (!input) return;
    const val = input.value.trim();
    if (!val) return;

    const resp = await fetch("/api/topics/propose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: `add ${val}` }),
    });
    const proposal = await resp.json();
    if (proposal.proposed_topics && !proposal.requires_replacement_choice) {
      this.editableTopics = [...proposal.proposed_topics];
      this.renderEditableChips();
      input.value = "";
    }
    this.renderTopicProposal(proposal);
  },

  resetDefaultTopics: function () {
    const defaults = [
      "Frontier AI & Agentic Systems",
      "Grid-Scale Clean Energy & Batteries",
      "Global Semiconductor Supply Chain",
      "Biotech & Longevity Clinical Trials",
      "Space Launch & Orbital Infrastructure",
    ];
    this.editableTopics = [...defaults];
    this.renderEditableChips();
    this.renderTopicProposal({
      transcript_or_input: "reset to defaults",
      current_topics: defaults,
      proposed_topics: defaults,
      requires_replacement_choice: false,
      assistant_message: "Reset to default 5 editorial beats. Click 'Confirm & Save' below to apply.",
    });
  },

  submitTopicCommand: async function (replaceTarget = null) {
    const input = document.getElementById("topic-command-input");
    const cmd = input ? input.value.trim() : "";
    if (!cmd && !replaceTarget) return;

    const resp = await fetch("/api/topics/propose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: cmd, replace_target: replaceTarget }),
    });
    const proposal = await resp.json();
    if (proposal.proposed_topics && !proposal.requires_replacement_choice) {
      this.editableTopics = [...proposal.proposed_topics];
      this.renderEditableChips();
    }
    this.renderTopicProposal(proposal);
  },

  renderTopicProposal: function (proposal) {
    this.currentProposal = proposal;
    if (proposal.proposed_topics && !proposal.requires_replacement_choice) {
      this.editableTopics = [...proposal.proposed_topics];
      this.renderEditableChips();
    }
    if (proposal.proposed_geographic_preference) {
      this.syncGeoSelectorUI(proposal.proposed_geographic_preference);
    }

    const box = document.getElementById("topic-proposal-box");
    const msg = document.getElementById("proposal-assistant-msg");
    const list = document.getElementById("proposal-topics-list");
    const replaceBox = document.getElementById("proposal-replace-picker");
    const confirmBtn = document.getElementById("btn-confirm-topics");

    if (!box) return;
    box.hidden = false;
    msg.textContent = proposal.assistant_message;
    list.innerHTML = "";
    (proposal.proposed_topics || []).forEach((t, idx) => {
      const li = document.createElement("li");
      li.textContent = `${idx + 1}. ${t}`;
      list.appendChild(li);
    });
    const geoToShow = proposal.proposed_geographic_preference || this.getSelectedGeoPreference();
    if (geoToShow) {
      const geoLi = document.createElement("li");
      geoLi.style.marginTop = "0.35rem";
      geoLi.innerHTML = `<strong>Geographic Preference:</strong> ${geoToShow}`;
      list.appendChild(geoLi);
    }

    if (proposal.requires_replacement_choice && proposal.overflow_topic_candidate) {
      replaceBox.hidden = false;
      confirmBtn.hidden = true;
      const select = document.getElementById("replace-topic-select");
      select.innerHTML = "";
      (proposal.proposed_topics || proposal.current_topics).forEach((existing) => {
        const opt = document.createElement("option");
        opt.value = existing;
        opt.textContent = `Replace "${existing}" with "${proposal.overflow_topic_candidate}"`;
        select.appendChild(opt);
      });
    } else {
      replaceBox.hidden = true;
      confirmBtn.hidden = Boolean(proposal.unclear_audio);
    }
  },

  applyReplacementChoice: async function () {
    const select = document.getElementById("replace-topic-select");
    if (!select || !this.currentProposal) return;
    const resp = await fetch("/api/topics/propose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command: this.currentProposal.overflow_topic_candidate,
        replace_target: select.value,
      }),
    });
    const proposal = await resp.json();
    this.renderTopicProposal(proposal);
  },

  confirmTopicSave: async function () {
    const topicsToSave = (this.currentProposal && this.currentProposal.proposed_topics && this.currentProposal.proposed_topics.length > 0)
      ? this.currentProposal.proposed_topics
      : this.editableTopics;

    if (!topicsToSave || topicsToSave.length === 0) {
      alert("Please select between 1 and 5 topics.");
      return;
    }
    const rawReaderName = document.getElementById("reader-name-input")
      ? document.getElementById("reader-name-input").value.trim()
      : "Muse";
    const readerName = rawReaderName || "Muse";
    const geoPref = (this.currentProposal && this.currentProposal.proposed_geographic_preference)
      ? this.currentProposal.proposed_geographic_preference
      : this.getSelectedGeoPreference();
    let data = null;
    try {
      const resp = await fetch("/api/topics/confirm", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reader_name: readerName,
          topics: topicsToSave,
          geographic_preference: geoPref || "Global",
        }),
      });
      data = await resp.json().catch(() => null);
      if (!resp.ok && !(data && data.status === "saved")) {
        alert("Could not save topics: " + ((data && (data.message || data.detail)) || ("server error " + resp.status)));
        return;
      }
    } catch (err) {
      alert("Could not save topics: " + err);
      return;
    }
    if (data && data.status === "saved") {
      window.location.reload();
    }
  },

  // ---- Schedule & Generate Now (FR-004..013, FR-038) ----
  previewScheduleNextRun: async function () {
    const payload = this._collectScheduleForm();
    const resp = await fetch("/api/schedule/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    const el = document.getElementById("schedule-preview-text");
    if (el && data.next_due_at) {
      el.textContent = `Next planned edition (${data.format_label}): ${new Date(data.next_due_at).toLocaleString()} (${data.next_due_at})`;
    }
  },

  saveSchedule: async function () {
    const payload = this._collectScheduleForm();
    const resp = await fetch("/api/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await resp.json();
    window.location.reload();
  },

  togglePauseSchedule: async function (pausedState) {
    const payload = this._collectScheduleForm();
    payload.paused = pausedState;
    await fetch("/api/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    window.location.reload();
  },

  generateNow: async function () {
    const bar = document.getElementById("live-build-progress-banner");
    const txt = document.getElementById("live-build-progress-text");
    if (bar && txt) {
      bar.hidden = false;
      txt.textContent = "Dispatching parallel Beat Reporters & Adversarial Fact-Checker...";
    }
    const resp = await fetch("/api/editions/generate-now", { method: "POST" });
    const data = await resp.json();
    if (data.action === "completed" && data.edition_id) {
      window.location.href = `/?edition_id=${encodeURIComponent(data.edition_id)}`;
    } else if (data.reason) {
      alert(data.reason);
      if (bar) bar.hidden = true;
    }
  },

  filterArchive: async function (formatFilter) {
    const resp = await fetch(`/api/editions?format=${encodeURIComponent(formatFilter || "")}`);
    const data = await resp.json();
    const container = document.getElementById("archive-editions-list");
    if (!container) return;
    container.innerHTML = "";
    data.editions.forEach((ed) => {
      const li = document.createElement("li");
      li.className = "archive-item";
      li.innerHTML = `
        <a href="/?edition_id=${encodeURIComponent(ed.edition_id)}">
          <strong>No. ${ed.edition_number} — ${ed.format_label}</strong>
          <span>(${ed.total_pages}p, ${ed.total_articles} articles)</span>
        </a>
        <div class="archive-meta">
          ${new Date(ed.published_at).toLocaleString()} ·
          Verified: ${ed.claims_verified}/${ed.claims_checked} claims ·
          Corrections: ${ed.corrections_count} ·
          Design v${ed.design_version}
        </div>
      `;
      container.appendChild(li);
    });
  },

  _collectScheduleForm: function () {
    return {
      cadence: document.getElementById("sched-cadence")?.value || "daily",
      start_time_local: document.getElementById("sched-start-time")?.value || "07:00",
      weekly_weekday: document.getElementById("sched-weekday")?.value || "SUN",
      time_zone:
        document.getElementById("sched-timezone")?.value ||
        Intl.DateTimeFormat().resolvedOptions().timeZone ||
        "UTC",
      paused: false,
      demo_mode: Boolean(document.getElementById("sched-demo-mode")?.checked),
    };
  },

  startStatusPolling: function () {
    setInterval(async () => {
      try {
        const resp = await fetch("/api/status");
        const st = await resp.json();
        const bar = document.getElementById("live-build-progress-banner");
        const txt = document.getElementById("live-build-progress-text");
        if (st.active_run && st.active_run.status === "running") {
          if (bar && txt) {
            bar.hidden = false;
            txt.textContent = `[${st.active_run.progress_pct}%] ${st.active_run.progress_message}`;
          }
        } else if (bar && !bar.hidden) {
          bar.hidden = true;
        }
        const newBadge = document.getElementById("new-edition-indicator");
        if (newBadge && st.schedule && st.schedule.new_edition_available) {
          newBadge.hidden = false;
        }
      } catch (_) {}
    }, 3000);
  },
};

document.addEventListener("DOMContentLoaded", () => {
  const savedTheme = localStorage.getItem("daily_muse_theme");
  if (savedTheme === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  }
  window.DailyMuseApp.init();
});

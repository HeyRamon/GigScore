/* =============================================================================
   CreditWise demo - view layer.

   Structure:
     1. DOM helpers        - build nodes, never HTML strings
     2. Formatting         - pure functions, no DOM access
     3. State loading      - validate before adopting
     4. Panel renderers    - one function per tab, plus the presenter controls
     5. Event handlers     - named, registered once
   ============================================================================= */

(function initCreditWiseDemo(config, embeddedState) {
  "use strict";

  const {
    SCHEMA_VERSION,
    REQUIRED_MEMBER_FIELDS,
    SCORE,
    BANDS,
    FACTOR_STATUS_MODIFIER,
    DEFAULT_STATUS_MODIFIER,
    EVENT_LABELS,
    COPY,
    STATE_URL,
  } = config;

  /* ---------------------------------------------------------------------------
     1. DOM helpers
     Text always arrives as a text node, so member data can never be parsed as
     markup and no escaping step can be forgotten.
     ------------------------------------------------------------------------ */

  /**
   * @param {string} tagName
   * @param {{className?: string, text?: string, attrs?: Object, vars?: Object}} options
   * @param {Array<Node|string>} children
   */
  function createElement(tagName, options = {}, children = []) {
    const node = document.createElement(tagName);
    if (options.className) node.className = options.className;
    if (options.text !== undefined) node.textContent = String(options.text);
    Object.entries(options.attrs || {}).forEach(([name, value]) => {
      node.setAttribute(name, String(value));
    });
    Object.entries(options.vars || {}).forEach(([name, value]) => {
      node.style.setProperty(name, String(value));
    });
    children.forEach((child) => {
      node.append(typeof child === "string" ? document.createTextNode(child) : child);
    });
    return node;
  }

  function useIcon(iconId, className = "icon") {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", className);
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `#${iconId}`);
    svg.append(use);
    return svg;
  }

  function replaceChildren(node, children) {
    node.replaceChildren(...children);
  }

  function setVisible(node, isVisible) {
    node.hidden = !isVisible;
  }

  function setProgress(node, percent) {
    node.style.setProperty("--progress", `${percent}%`);
  }

  /** Splits text on a pattern and wraps the matches in <strong>. */
  function withEmphasis(text, pattern) {
    const fragment = document.createDocumentFragment();
    String(text)
      .split(pattern)
      .forEach((part, index) => {
        /* split() with a capturing group puts the matches at the odd indexes. */
        const isMatch = index % 2 === 1;
        fragment.append(
          isMatch
            ? createElement("strong", { text: part })
            : document.createTextNode(part)
        );
      });
    return fragment;
  }

  const POINTS_PATTERN = /(\+\d+ pts)/;

  /* ---------------------------------------------------------------------------
     2. Formatting - pure
     ------------------------------------------------------------------------ */

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  /** Position of a score along the full 300-850 track, as a percentage. */
  function scorePositionPercent(score) {
    return clamp(((score - SCORE.MIN) / SCORE.RANGE) * 100, 0, 100);
  }

  function findBandFloor(bandName) {
    const band = BANDS.find((candidate) => candidate.name === bandName);
    if (!band) {
      console.warn(`[creditwise] unknown band "${bandName}", using score floor`);
      return SCORE.MIN;
    }
    return band.floor;
  }

  /** Progress from the current band's floor to the next milestone threshold. */
  function milestoneProgressPercent(member) {
    if (!member.next_milestone) return 100;
    const floor = findBandFloor(member.band);
    const span = member.next_milestone.threshold - floor;
    if (span <= 0) return 100;
    const raw = ((member.score - floor) / span) * 100;
    return clamp(raw, SCORE.MIN_VISIBLE_PROGRESS_PCT, 100);
  }

  function statusModifier(status) {
    const modifier = FACTOR_STATUS_MODIFIER[status];
    if (!modifier) {
      console.warn(`[creditwise] unmapped factor status "${status}"`);
      return DEFAULT_STATUS_MODIFIER;
    }
    return modifier;
  }

  function formatWeekDelta(weekDelta) {
    const prefix = weekDelta < 0 ? COPY.scoreDownAffix : COPY.scoreUpAffix;
    return `${prefix}${weekDelta}${COPY.weekSuffix}`;
  }

  function formatSignedPoints(delta) {
    return delta < 0 ? `\u2212${Math.abs(delta)}` : `+${delta}`;
  }

  function describeEvent(event) {
    const label = EVENT_LABELS[event.event_type];
    if (!label) {
      console.warn(`[creditwise] no copy for event_type "${event.event_type}"`);
      return { label: COPY.unknownEvent, delta: event.delta };
    }
    return { label, delta: event.delta };
  }

  /* ---------------------------------------------------------------------------
     3. State loading
     ------------------------------------------------------------------------ */

  /** @returns {string[]} human-readable problems; empty means the payload is usable. */
  function findStateProblems(payload) {
    if (!payload || typeof payload !== "object") return ["payload is not an object"];

    const problems = [];
    if (payload.schema_version !== SCHEMA_VERSION) {
      problems.push(
        `schema_version is ${payload.schema_version}, expected ${SCHEMA_VERSION}`
      );
    }
    if (!Array.isArray(payload.members) || payload.members.length === 0) {
      problems.push("members[] is missing or empty");
      return problems;
    }
    payload.members.forEach((member, index) => {
      REQUIRED_MEMBER_FIELDS.filter((field) => member[field] === undefined).forEach(
        (field) => problems.push(`members[${index}].${field} is missing`)
      );
    });
    return problems;
  }

  /* ---------------------------------------------------------------------------
     Element registry. Looked up once; a missing id fails loudly here rather than
     as a null dereference somewhere inside a renderer.
     ------------------------------------------------------------------------ */
  const ELEMENT_IDS = [
    "score-value", "score-band", "score-fill", "score-tick", "score-updated",
    "score-delta", "factor-list", "score-unlock", "score-unlock-title",
    "score-unlock-progress", "account-list", "strength-value", "strength-progress",
    "coach-headline", "coach-how", "coach-why", "coach-why-toggle", "unlocked-card",
    "unlocked-title", "unlocked-detail", "milestone-card", "milestone-title",
    "milestone-detail", "milestone-from", "milestone-to", "milestone-progress",
    "wins-title", "win-list", "cohort-chips", "cohort-summary", "data-notice",
    "feedback-bar",
  ];

  function collectElements() {
    const registry = {};
    const missing = [];
    ELEMENT_IDS.forEach((id) => {
      const node = document.getElementById(id);
      if (!node) missing.push(id);
      /* score-value -> scoreValue */
      registry[id.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = node;
    });
    if (missing.length) {
      throw new Error(`[creditwise] markup is missing #${missing.join(", #")}`);
    }
    return registry;
  }

  const dom = collectElements();

  /* Mutable view state, always replaced through adoptState()/selectMember(). */
  let state = embeddedState;
  let selectedMemberIndex = 0;

  function currentMember() {
    return state.members[selectedMemberIndex];
  }

  /* ---------------------------------------------------------------------------
     4. Panel renderers
     ------------------------------------------------------------------------ */

  function buildFactorRow(factor) {
    return createElement("div", { className: "factor-row" }, [
      createElement("div", { className: "factor-row__content" }, [
        createElement("div", { className: "factor-row__label", text: factor.label }),
        createElement("div", { className: "factor-row__driver", text: factor.driver }),
      ]),
      createElement("span", {
        className: `factor-row__status factor-row__status--${statusModifier(factor.status)}`,
        text: String(factor.status).toUpperCase(),
      }),
      useIcon("icon-chevron-right", "icon row-chevron icon--chevron"),
    ]);
  }

  function renderScorePanel(member) {
    const markerPercent = `${scorePositionPercent(member.score)}%`;

    dom.scoreValue.textContent = member.score;
    dom.scoreBand.textContent = member.band;
    dom.scoreUpdated.textContent = member.updated_line;
    [dom.scoreBand, dom.scoreFill, dom.scoreTick].forEach((node) => {
      node.style.setProperty("--marker", markerPercent);
    });

    dom.scoreDelta.textContent = formatWeekDelta(member.week_delta);
    dom.scoreDelta.classList.toggle("delta-pill--negative", member.week_delta < 0);

    replaceChildren(dom.factorList, member.factors.map(buildFactorRow));

    const hasMilestone = Boolean(member.next_milestone);
    setVisible(dom.scoreUnlock, hasMilestone);
    if (hasMilestone) {
      dom.scoreUnlockTitle.textContent =
        `${member.gap_to_next} pts to ${member.next_milestone.product}`;
      setProgress(dom.scoreUnlockProgress, milestoneProgressPercent(member));
    }
  }

  function buildAccountRow(account) {
    const action = account.connected
      ? createElement("span", { className: "status-badge", text: "Connected" })
      : createElement("button", {
          className: "connect-button",
          text: "Connect",
          attrs: { type: "button" },
        });

    return createElement("div", { className: "account-row" }, [
      createElement("span", {
        className: "account-row__avatar",
        text: account.name.charAt(0).toUpperCase(),
        attrs: { "aria-hidden": "true" },
      }),
      createElement("span", { className: "account-row__content" }, [
        createElement("div", { className: "account-row__name", text: account.name }),
        createElement("div", { className: "account-row__source", text: account.sub }),
      ]),
      action,
    ]);
  }

  function renderConnectPanel(member) {
    replaceChildren(dom.accountList, member.accounts.map(buildAccountRow));
    dom.strengthValue.textContent =
      `${member.sources_connected} of ${member.sources_total} sources`;
    const sourcePercent = member.sources_total
      ? (member.sources_connected / member.sources_total) * 100
      : 0;
    setProgress(dom.strengthProgress, sourcePercent);
  }

  function buildWinRow(win) {
    const isNegative = String(win.delta).startsWith("-") || String(win.delta).startsWith("\u2212");
    return createElement("div", { className: "win-row" }, [
      createElement("span", {
        className: `win-row__delta${isNegative ? " win-row__delta--negative" : ""}`,
        text: win.delta,
      }),
      createElement("span", { className: "win-row__label", text: win.label }),
    ]);
  }

  function renderCoachPanel(member) {
    replaceChildren(dom.coachHeadline, [
      withEmphasis(member.coach.headline, POINTS_PATTERN),
    ]);
    replaceChildren(dom.coachHow, [
      withEmphasis(member.coach.how_to_improve, POINTS_PATTERN),
    ]);

    dom.coachWhy.textContent = member.coach.why_important || "";
    setVisible(dom.coachWhy, false);
    dom.coachWhyToggle.setAttribute("aria-expanded", "false");

    const unlocked = member.unlocked?.[0];
    setVisible(dom.unlockedCard, Boolean(unlocked));
    if (unlocked) {
      dom.unlockedTitle.textContent = `${unlocked.threshold} — ${unlocked.product}`;
      dom.unlockedDetail.textContent = unlocked.detail;
    }

    const milestone = member.next_milestone;
    setVisible(dom.milestoneCard, Boolean(milestone));
    if (milestone) {
      dom.milestoneTitle.textContent = `${milestone.threshold} — ${milestone.product}`;
      dom.milestoneDetail.textContent = milestone.detail;
      dom.milestoneFrom.textContent = member.score;
      dom.milestoneTo.textContent = milestone.threshold;
      setProgress(dom.milestoneProgress, milestoneProgressPercent(member));
    }

    const wins = member.recent_wins ?? [];
    setVisible(dom.winsTitle, wins.length > 0);
    setVisible(dom.winList, wins.length > 0);
    replaceChildren(dom.winList, wins.map(buildWinRow));
  }

  function buildCohortChip(member, index) {
    return createElement(
      "button",
      {
        className: "cohort__chip",
        attrs: {
          type: "button",
          "data-member-index": index,
          "aria-pressed": index === selectedMemberIndex ? "true" : "false",
        },
      },
      [
        member.name,
        createElement("span", { className: "cohort__chip-score", text: member.score }),
      ]
    );
  }

  function buildEventSummary(ledger) {
    if (!ledger?.length) return [COPY.noEvents];

    const parts = [];
    ledger.forEach((event, index) => {
      if (index > 0) parts.push(" · ");
      const { label, delta } = describeEvent(event);
      parts.push(`${label} `);
      parts.push(createElement("strong", { text: formatSignedPoints(delta) }));
    });
    return parts;
  }

  function renderCohortSwitcher(member) {
    replaceChildren(dom.cohortChips, state.members.map(buildCohortChip));
    replaceChildren(dom.cohortSummary, [
      createElement("strong", { text: member.name }),
      " — this week: ",
      ...buildEventSummary(member.ledger),
      " → ",
      createElement("strong", { text: `${member.score} ${member.band}` }),
      `. ${COPY.cohortFootnote}`,
    ]);
  }

  function render() {
    const member = currentMember();
    renderScorePanel(member);
    renderConnectPanel(member);
    renderCoachPanel(member);
    renderCohortSwitcher(member);
  }

  function showNotice(message) {
    dom.dataNotice.textContent = message;
    setVisible(dom.dataNotice, true);
  }

  /* ---------------------------------------------------------------------------
     5. Event handlers
     ------------------------------------------------------------------------ */

  function selectMember(index) {
    selectedMemberIndex = clamp(index, 0, state.members.length - 1);
    render();
  }

  function handleCohortChipClick(event) {
    const chip = event.target.closest(".cohort__chip");
    if (!chip) return;
    selectMember(Number(chip.dataset.memberIndex));
  }

  function handleTabClick(event) {
    const tab = event.target.closest(".segmented-control__option");
    if (!tab) return;

    document.querySelectorAll(".segmented-control__option").forEach((option) => {
      option.setAttribute("aria-selected", String(option === tab));
    });
    const activePanelId = tab.getAttribute("aria-controls");
    document.querySelectorAll(".tab-panel").forEach((panel) => {
      setVisible(panel, panel.id === activePanelId);
    });
    document.querySelector(".app-content").scrollTop = 0;
  }

  function handleWhyToggleClick() {
    const isOpen = dom.coachWhy.hidden;
    setVisible(dom.coachWhy, isOpen);
    dom.coachWhyToggle.setAttribute("aria-expanded", String(isOpen));
  }

  function handleFeedbackClick(event) {
    const button = event.target.closest(".feedback-button");
    if (!button) return;
    replaceChildren(dom.feedbackBar, [
      document.createTextNode(COPY.feedbackLogged),
    ]);
  }

  function registerHandlers() {
    dom.cohortChips.addEventListener("click", handleCohortChipClick);
    document
      .querySelector(".segmented-control")
      .addEventListener("click", handleTabClick);
    dom.coachWhyToggle.addEventListener("click", handleWhyToggleClick);
    dom.feedbackBar.addEventListener("click", handleFeedbackClick);
  }

  /* ---------------------------------------------------------------------------
     Live state: prefer a freshly exported state.json when one is being served.
     Adopted only after validation; every failure path tells the presenter which
     data they are looking at.
     ------------------------------------------------------------------------ */

  function adoptState(payload) {
    state = payload;
    selectMember(selectedMemberIndex);
  }

  function loadLiveState() {
    if (!window.location.protocol.startsWith("http")) {
      console.info("[creditwise] opened from disk - using bundled demo state");
      return;
    }
    fetch(STATE_URL)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`${STATE_URL} responded ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        const problems = findStateProblems(payload);
        if (problems.length) {
          console.error(`[creditwise] rejected ${STATE_URL}:`, problems);
          showNotice(COPY.liveDataRejected);
          return;
        }
        adoptState(payload);
      })
      .catch((error) => {
        console.warn(`[creditwise] could not load ${STATE_URL}:`, error);
        showNotice(COPY.liveDataUnavailable);
      });
  }

  function start() {
    const problems = findStateProblems(state);
    if (problems.length) {
      console.error("[creditwise] bundled demo state is invalid:", problems);
      showNotice(COPY.liveDataRejected);
      return;
    }
    registerHandlers();
    render();
    loadLiveState();
  }

  start();
})(GIGSCORE_CONFIG, window.GIGSCORE_EMBEDDED_STATE);

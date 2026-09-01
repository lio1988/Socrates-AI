"use strict";

/*
 * SOCRATES UI V0.2 — ADDITIVE LOCAL CED ADAPTER
 * ------------------------------------------------
 * DEMO MODE remains the V0.1 timer-driven fixture in app.js. LOCAL CED is a
 * separate source: it renders only the versioned public events emitted by the
 * same-origin local bridge. It never derives protocol authority in the browser.
 */

const PUBLIC_EVENT_SCHEMA = "socrates.public-council.v1";
const PUBLIC_EVENT_TYPES = Object.freeze([
  "run.started",
  "phase.started",
  "move.accepted",
  "operation.rejected",
  "commitments.snapshot",
  "phase.completed",
  "ratification.completed",
  "run.completed",
  "run.failed",
]);
const LOCAL_PHASE_IDS = Object.freeze([
  "opening",
  "initial_response",
  "elenchus",
  "reflection",
  "reconstruction",
  "synthesis",
  "ratification",
]);
const LOCAL_RUN_ID = /^ced_[a-f0-9]{24}$/;

const DEMO_VIEW = Object.freeze({
  commitments: [
    { commitment_id: "A1", status: "revised", claim: "Automation of tasks is not equivalent to elimination of occupations.", is_current: false },
    { commitment_id: "B1", status: "retained", claim: "Transition speed determines the scale of near-term harm.", is_current: false },
    { commitment_id: "C1", status: "withdrawn", claim: "New work automatically offsets every displaced role.", is_current: false },
    { commitment_id: "A2", status: "asserted", claim: "Long-run outcomes depend on task creation, demand and adaptation.", is_current: true },
  ],
  final: {
    answer_released: true,
    outcome: "demo",
    notice: "",
    sections: [
      { title: "Key conclusion", content: "AI automation does not necessarily reduce total employment. It can displace existing tasks while creating complementary work, but the net outcome depends on transition speed, demand growth and whether people can move into newly valuable tasks." },
      { title: "Strongest qualification", content: "Short-run displacement can be severe and uneven even when new work emerges." },
      { title: "Remaining uncertainty", content: "The pace and accessibility of new task creation cannot be inferred from historical analogy alone." },
    ],
  },
});

const bridgeElements = {
  demoMode: document.querySelector("#demo-mode-button"),
  localMode: document.querySelector("#local-mode-button"),
  connectionPanel: document.querySelector("#connection-panel"),
  connectionStatus: document.querySelector("#connection-status"),
  retryConnection: document.querySelector("#retry-connection"),
  recordSource: document.querySelector("#record-source-label"),
  commitmentSummary: document.querySelector("#commitment-summary"),
  commitmentList: document.querySelector("#commitment-list"),
  finalSource: document.querySelector("#final-source-label"),
  ratificationBadge: document.querySelector("#ratification-badge"),
  synthesisAnswer: document.querySelector("#synthesis-answer"),
  synthesisGrid: document.querySelector("#synthesis-grid"),
  governingNotice: document.querySelector("#governing-notice"),
};

const localState = {
  sourceMode: "demo",
  available: null,
  runId: null,
  generation: 0,
  lastSequence: -1,
  fingerprints: new Map(),
  eventSource: null,
  requestController: null,
  terminal: false,
  ratification: null,
};
runState.sourceMode = "demo";
runState.lifecycle = "idle";

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function closeLocalTransport() {
  if (localState.eventSource) {
    localState.eventSource.close();
    localState.eventSource = null;
  }
  if (localState.requestController) {
    localState.requestController.abort();
    localState.requestController = null;
  }
}

function setConnection(message, state, { retry = false } = {}) {
  bridgeElements.connectionPanel.hidden = localState.sourceMode !== "local-ced";
  bridgeElements.connectionPanel.dataset.state = state;
  bridgeElements.connectionStatus.textContent = message;
  bridgeElements.retryConnection.hidden = !retry;
}

function syncSourceControls() {
  const isDemo = localState.sourceMode === "demo";
  const running = isDemo
    ? runState.mode === "running"
    : ["starting", "running"].includes(runState.lifecycle);
  bridgeElements.demoMode.classList.toggle("is-selected", isDemo);
  bridgeElements.localMode.classList.toggle("is-selected", !isDemo);
  bridgeElements.demoMode.setAttribute("aria-pressed", String(isDemo));
  bridgeElements.localMode.setAttribute("aria-pressed", String(!isDemo));
  bridgeElements.demoMode.disabled = running;
  bridgeElements.localMode.disabled = running;
  elements.completeButton.hidden = !isDemo;
  elements.conveneButton.disabled = running || (!isDemo && localState.available !== true);
  elements.exampleButton.disabled = running;
  bridgeElements.recordSource.textContent = isDemo ? "demonstration" : "canonical local CED";
  bridgeElements.connectionPanel.hidden = isDemo;
}

function renderCommitments(items) {
  bridgeElements.commitmentList.replaceChildren();
  const commitments = Array.isArray(items) ? items : [];
  commitments.forEach((item, index) => {
    if (!isPlainObject(item) || typeof item.claim !== "string") {
      return;
    }
    const state = item.is_current === true ? "current" : String(item.status || "asserted");
    const row = createElement("li", "");
    row.dataset.commitmentState = state;
    const mark = createElement("span", "", `C${index + 1}`);
    const status = createElement("strong", "", state.toUpperCase());
    status.dataset.commitmentStatus = state;
    const claim = createElement("p", "", item.claim);
    row.append(mark, status, claim);
    bridgeElements.commitmentList.append(row);
  });
  const count = bridgeElements.commitmentList.children.length;
  bridgeElements.commitmentSummary.textContent =
    `${count} tracked ${count === 1 ? "position" : "positions"} · position history`;
  elements.commitments.dataset.empty = String(count === 0);
}

function renderFinal(final, { demo = false, ratification = null } = {}) {
  const released = isPlainObject(final) && final.answer_released === true;
  const sections = released && Array.isArray(final.sections) ? final.sections : [];
  bridgeElements.finalSource.textContent = demo
    ? "GOVERNED COUNCIL OUTPUT · DEMONSTRATION"
    : "GOVERNED COUNCIL OUTPUT · CANONICAL LOCAL CED";
  const ratificationStatus = ratification && typeof ratification.status === "string"
    ? ratification.status.replaceAll("_", " ").toUpperCase()
    : released
      ? "ANSWER RELEASED"
      : "PUBLIC ANSWER WITHHELD";
  bridgeElements.ratificationBadge.textContent = demo ? "RATIFIED WITH CAVEAT" : ratificationStatus;
  bridgeElements.ratificationBadge.dataset.outcome = released ? "released" : "withheld";
  bridgeElements.synthesisGrid.replaceChildren();

  if (released && sections.length > 0) {
    const [lead, ...rest] = sections;
    bridgeElements.synthesisAnswer.textContent = lead.content || "";
    rest.forEach((section) => {
      if (!isPlainObject(section)) {
        return;
      }
      const block = createElement("div", "");
      block.append(
        createElement("span", "", String(section.title || "Council section").toUpperCase()),
        createElement("p", "", String(section.content || "")),
      );
      bridgeElements.synthesisGrid.append(block);
    });
  } else {
    bridgeElements.synthesisAnswer.textContent = released
      ? String(final.public_answer || "")
      : "The governing release did not authorize publication of the council candidate.";
  }

  const notice = !demo && typeof final.notice === "string" ? final.notice : "";
  bridgeElements.governingNotice.textContent = notice;
  bridgeElements.governingNotice.hidden = notice.length === 0;
  elements.finalSynthesis.hidden = false;
}

function renderDemoView() {
  renderCommitments(DEMO_VIEW.commitments);
  renderFinal(DEMO_VIEW.final, { demo: true });
  elements.finalSynthesis.hidden = runState.mode !== "complete";
}

function renderLocalIdle(message = "LOCAL CED READY · ENTER A QUESTION") {
  clearRenderedRun();
  renderIdleSeats();
  renderTimeline(-1);
  renderCommitments([]);
  elements.activeQuestion.textContent = "Waiting for a question.";
  elements.phaseBrief.querySelector("span").textContent = "LOCAL CED";
  elements.phaseBrief.querySelector("h4").textContent = "Canonical council standing by";
  elements.phaseBrief.querySelector("p").textContent =
    "The browser will render only accepted public events from an isolated offline-mock CED run.";
  setRunStatus(message);
  runState.mode = "idle";
  runState.lifecycle = "idle";
  runState.stage = "idle";
  runState.phaseIndex = -1;
  setControlState();
  syncSourceControls();
}

function renderLocalSeats(seats) {
  const assigned = new Map();
  (Array.isArray(seats) ? seats : []).forEach((seat) => {
    if (isPlainObject(seat) && typeof seat.seat_id === "string") {
      assigned.set(seat.seat_id, seat);
    }
  });
  elements.seats.forEach((card) => {
    const assignment = assigned.get(card.dataset.seatId);
    card.removeAttribute("aria-current");
    card.querySelector(".seat-role span").textContent = "TEMPORARY CED ROLE";
    if (!assignment) {
      card.dataset.state = "waiting";
      card.querySelector(".seat-role strong").textContent = "Awaiting this phase";
      card.querySelector(".seat-state-label").textContent = "Waiting";
      return;
    }
    card.dataset.state = "active";
    card.setAttribute("aria-current", "true");
    card.querySelector(".seat-role strong").textContent = String(assignment.role_label || assignment.role || "Assigned");
    card.querySelector(".seat-state-label").textContent = "Active";
  });
}

function renderLocalPhase(data) {
  if (!isPlainObject(data) || !isPlainObject(data.phase)) {
    throw new Error("invalid phase event");
  }
  const index = data.phase.index;
  if (!Number.isInteger(index) || index < 0 || index >= LOCAL_PHASE_IDS.length
      || data.phase.id !== LOCAL_PHASE_IDS[index]) {
    throw new Error("invalid canonical phase identity");
  }
  runState.phaseIndex = index;
  runState.stage = "deliberating";
  renderTimeline(index);
  renderLocalSeats(data.seats);
  elements.phaseBrief.querySelector("span").textContent =
    `PHASE ${String(index + 1).padStart(2, "0")} · ${String(data.phase.label || data.phase.id).toUpperCase()}`;
  elements.phaseBrief.querySelector("h4").textContent = "Canonical CED phase active";
  elements.phaseBrief.querySelector("p").textContent =
    "Temporary roles and active seats are projected from the server-owned session state.";
  setRunStatus(`PHASE ${String(index + 1).padStart(2, "0")} OF 07 · ${String(data.phase.label || data.phase.id).toUpperCase()}`);
}

function renderLocalMove(move) {
  if (!isPlainObject(move) || typeof move.move_id !== "string"
      || typeof move.display_text !== "string" || move.status !== "accepted") {
    throw new Error("invalid public move");
  }
  if (runState.renderedMoveIds.has(move.move_id)) {
    return;
  }
  const phaseIndex = LOCAL_PHASE_IDS.indexOf(move.phase);
  const cardMove = {
    id: move.move_id,
    mark: String(elements.contributionList.children.length + 1).padStart(2, "0"),
    agent: String(move.alias || "Council member"),
    role: String(move.role_label || move.role || "Council role"),
    phase: phaseIndex >= 0 ? `${String(phaseIndex + 1).padStart(2, "0")} ${move.phase.replaceAll("_", " ")}` : "Council phase",
    status: "Accepted",
    confidence: String(move.confidence_label || "Moderate"),
    content: move.display_text,
  };
  runState.renderedMoveIds.add(move.move_id);
  elements.contributionList.append(buildMoveCard(cardMove, { isNew: true }));
  syncContributionDisclosure();
}

function markLocalSeatsComplete() {
  elements.seats.forEach((seat) => {
    const role = seat.querySelector(".seat-role strong").textContent;
    seat.dataset.state = "complete";
    seat.removeAttribute("aria-current");
    seat.querySelector(".seat-role span").textContent = `LAST ROLE · ${role.toUpperCase()}`;
    seat.querySelector(".seat-role strong").textContent = "SESSION COMPLETE";
    seat.querySelector(".seat-state-label").textContent = "Complete";
  });
}

function failLocalView(message) {
  closeLocalTransport();
  runState.mode = "failed";
  runState.lifecycle = "failed";
  runState.stage = "failed";
  localState.terminal = true;
  setRunStatus(message);
  elements.phaseBrief.querySelector("span").textContent = "LOCAL CED UNAVAILABLE";
  elements.phaseBrief.querySelector("h4").textContent = "The public run could not be displayed";
  elements.phaseBrief.querySelector("p").textContent =
    "No private backend diagnostic was exposed. Retry the local connection or return to Demo Mode.";
  setControlState();
  syncSourceControls();
}

function validateEvent(payload) {
  if (!isPlainObject(payload)
      || payload.schema_version !== PUBLIC_EVENT_SCHEMA
      || payload.run_id !== localState.runId
      || !Number.isInteger(payload.sequence)
      || payload.sequence < 0
      || !PUBLIC_EVENT_TYPES.includes(payload.type)
      || !isPlainObject(payload.data)) {
    throw new Error("invalid public event envelope");
  }
  const fingerprint = JSON.stringify(payload);
  if (payload.sequence <= localState.lastSequence) {
    if (localState.fingerprints.get(payload.sequence) === fingerprint) {
      return false;
    }
    throw new Error("conflicting replay event");
  }
  if (payload.sequence !== localState.lastSequence + 1) {
    throw new Error("public event sequence gap");
  }
  localState.fingerprints.set(payload.sequence, fingerprint);
  localState.lastSequence = payload.sequence;
  return true;
}

function applyPublicEvent(payload) {
  if (!validateEvent(payload)) {
    return;
  }
  const data = payload.data;
  switch (payload.type) {
    case "run.started":
      runState.mode = "running";
      runState.lifecycle = "running";
      runState.stage = "accepted";
      elements.activeQuestion.textContent = String(data.question || elements.questionInput.value.trim());
      setRunStatus("CANONICAL LOCAL CED · COUNCIL STARTED");
      break;
    case "phase.started":
      renderLocalPhase(data);
      break;
    case "move.accepted":
      renderLocalMove(data.move);
      break;
    case "operation.rejected":
      setRunStatus("A CANDIDATE MOVE WAS REJECTED · CANONICAL RUN CONTINUES");
      break;
    case "commitments.snapshot":
      renderCommitments(data.commitments);
      break;
    case "phase.completed":
      break;
    case "ratification.completed":
      localState.ratification = isPlainObject(data.ratification) ? data.ratification : null;
      if (localState.ratification) {
        setRunStatus(`RATIFICATION · ${String(localState.ratification.status || "complete").replaceAll("_", " ").toUpperCase()}`);
      }
      break;
    case "run.completed": {
      localState.terminal = true;
      closeLocalTransport();
      const final = data.final;
      if (!isPlainObject(final)) {
        throw new Error("invalid final projection");
      }
      runState.mode = data.status === "completed" ? "complete" : "blocked";
      runState.lifecycle = data.status === "completed" ? "completed" : "blocked";
      runState.stage = "complete";
      renderTimeline(LOCAL_PHASE_IDS.length - 1, true);
      markLocalSeatsComplete();
      renderFinal(final, { ratification: localState.ratification });
      elements.phaseBrief.querySelector("span").textContent = "CANONICAL COUNCIL COMPLETE";
      elements.phaseBrief.querySelector("h4").textContent = final.answer_released
        ? "Governing release rendered"
        : "Public answer withheld";
      elements.phaseBrief.querySelector("p").textContent = final.answer_released
        ? "The final text below is exactly the public answer authorized by the normal governing renderer."
        : "The candidate remains private because the governing renderer did not authorize publication.";
      setRunStatus(final.answer_released
        ? "COUNCIL COMPLETE · GOVERNED ANSWER AVAILABLE"
        : "COUNCIL COMPLETE · PUBLIC ANSWER WITHHELD");
      elements.synthesisTitle.focus({ preventScroll: true });
      break;
    }
    case "run.failed":
      failLocalView("LOCAL CED RUN FAILED · PUBLIC DIAGNOSTIC WITHHELD");
      break;
    default:
      throw new Error("unknown public event");
  }
  setControlState();
  syncSourceControls();
}

function attachEventStream(runId, generation) {
  const source = new EventSource(`/api/council/${encodeURIComponent(runId)}/events`);
  localState.eventSource = source;
  const receive = (event) => {
    if (generation !== localState.generation || localState.terminal) {
      return;
    }
    try {
      const payload = JSON.parse(event.data);
      if (payload.type !== event.type) {
        throw new Error("event type mismatch");
      }
      applyPublicEvent(payload);
    } catch (_error) {
      failLocalView("LOCAL CED PUBLIC EVENT REJECTED · DISPLAY FAILED CLOSED");
    }
  };
  PUBLIC_EVENT_TYPES.forEach((eventType) => source.addEventListener(eventType, receive));
  source.addEventListener("open", () => {
    if (!localState.terminal) {
      setConnection("Connected · canonical CED · offline mock providers", "available");
    }
  });
  source.addEventListener("error", () => {
    if (!localState.terminal && generation === localState.generation) {
      setConnection("Connection interrupted · browser retrying safely", "checking");
    }
  });
}

async function startLocalCouncil(question) {
  if (localState.available !== true) {
    setConnection("Local CED is not available. Start the server and retry.", "unavailable", { retry: true });
    return;
  }
  closeLocalTransport();
  invalidateRun();
  clearRenderedRun();
  renderCommitments([]);
  localState.generation += 1;
  const generation = localState.generation;
  localState.runId = null;
  localState.lastSequence = -1;
  localState.fingerprints.clear();
  localState.terminal = false;
  localState.ratification = null;
  runState.mode = "running";
  runState.lifecycle = "starting";
  runState.stage = "accepted";
  runState.phaseIndex = -1;
  elements.activeQuestion.textContent = question;
  renderIdleSeats();
  renderTimeline(-1);
  setRunStatus("QUESTION ACCEPTED · STARTING CANONICAL LOCAL CED");
  elements.phaseBrief.querySelector("span").textContent = "QUESTION ACCEPTED";
  elements.phaseBrief.querySelector("h4").textContent = "Starting the canonical council";
  elements.phaseBrief.querySelector("p").textContent =
    "The local API is creating an isolated real CED session with scripted offline providers.";
  setControlState();
  syncSourceControls();
  elements.council.scrollIntoView({
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    block: "start",
  });

  const controller = new AbortController();
  localState.requestController = controller;
  try {
    const response = await fetch("/api/council", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal,
      credentials: "same-origin",
    });
    if (generation !== localState.generation) {
      return;
    }
    if (!response.ok) {
      throw new Error("start rejected");
    }
    const payload = await response.json();
    if (!isPlainObject(payload) || !LOCAL_RUN_ID.test(payload.run_id)
        || !["queued", "running"].includes(payload.status)) {
      throw new Error("invalid start response");
    }
    localState.runId = payload.run_id;
    localState.requestController = null;
    attachEventStream(payload.run_id, generation);
  } catch (error) {
    if (error && error.name === "AbortError") {
      return;
    }
    failLocalView("LOCAL CED COULD NOT START · NO PRIVATE ERROR EXPOSED");
  }
}

async function checkLocalHealth() {
  if (localState.sourceMode !== "local-ced") {
    return;
  }
  setConnection("Checking the local CED bridge…", "checking");
  localState.available = null;
  syncSourceControls();
  try {
    const response = await fetch("/api/council/health", {
      headers: { "Accept": "application/json" },
      credentials: "same-origin",
      cache: "no-store",
    });
    const payload = response.ok ? await response.json() : null;
    if (!isPlainObject(payload)
        || payload.status !== "available"
        || payload.ced !== "real"
        || payload.providers !== "offline_mock") {
      throw new Error("health contract mismatch");
    }
    localState.available = true;
    setConnection("Connected · canonical CED · offline mock providers", "available");
    setRunStatus("LOCAL CED AVAILABLE · READY TO CONVENE");
  } catch (_error) {
    localState.available = false;
    setConnection("Local CED unavailable · start the local server, then retry", "unavailable", { retry: true });
    setRunStatus("LOCAL CED UNAVAILABLE · DEMO MODE REMAINS AVAILABLE");
  }
  syncSourceControls();
}

function selectDemoMode() {
  if (runState.mode === "running") {
    return;
  }
  closeLocalTransport();
  localState.generation += 1;
  localState.sourceMode = "demo";
  runState.sourceMode = "demo";
  localState.runId = null;
  localState.terminal = false;
  resetDemo({ focusQuestion: false });
  runState.lifecycle = "idle";
  renderDemoView();
  setRunStatus("DEMO MODE · READY TO CONVENE");
  syncSourceControls();
}

function selectLocalMode() {
  if (runState.mode === "running") {
    return;
  }
  invalidateRun();
  localState.generation += 1;
  localState.sourceMode = "local-ced";
  runState.sourceMode = "local-ced";
  runState.lifecycle = "idle";
  localState.runId = null;
  localState.terminal = false;
  renderLocalIdle("LOCAL CED · CHECKING CONNECTION");
  checkLocalHealth();
}

function resetLocalView() {
  const mayContinue = Boolean(localState.runId && !localState.terminal);
  closeLocalTransport();
  invalidateRun();
  localState.generation += 1;
  localState.runId = null;
  localState.lastSequence = -1;
  localState.fingerprints.clear();
  localState.terminal = false;
  localState.ratification = null;
  runState.lifecycle = "idle";
  renderLocalIdle(mayContinue
    ? "LOCAL VIEW RESET · THE SERVER RUN MAY CONTINUE"
    : "LOCAL CED AVAILABLE · VIEW RESET");
  setQuestionError(false);
  elements.questionInput.focus();
}

bridgeElements.demoMode.addEventListener("click", selectDemoMode);
bridgeElements.localMode.addEventListener("click", selectLocalMode);
bridgeElements.retryConnection.addEventListener("click", checkLocalHealth);

elements.form.addEventListener("submit", (event) => {
  if (localState.sourceMode !== "local-ced") {
    window.queueMicrotask(syncSourceControls);
    return;
  }
  event.preventDefault();
  event.stopImmediatePropagation();
  if (runState.mode === "running") {
    return;
  }
  const question = currentQuestion();
  if (question) {
    startLocalCouncil(question);
  }
}, true);

elements.resetButton.addEventListener("click", (event) => {
  if (localState.sourceMode !== "local-ced") {
    return;
  }
  event.preventDefault();
  event.stopImmediatePropagation();
  resetLocalView();
}, true);

elements.completeButton.addEventListener("click", (event) => {
  if (localState.sourceMode === "local-ced") {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}, true);

new MutationObserver(syncSourceControls).observe(elements.council, {
  attributes: true,
  attributeFilter: ["data-run-state", "data-run-stage"],
});

renderDemoView();
syncSourceControls();

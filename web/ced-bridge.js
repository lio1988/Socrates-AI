"use strict";

/*
 * SOCRATES UI V0.3A — ADDITIVE LOCAL + NORMAL LIVE LIFECYCLE
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
const SAFE_PUBLIC_ID = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$/;
const NORMAL_PREFLIGHT_ID = /^nlpf_[a-f0-9]{36}$/;
const NORMAL_APPROVAL_REFERENCE = /^normalapprovalv1_[a-f0-9]{64}$/;
const SHA256_HEX = /^[a-f0-9]{64}$/;
const UTC_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const EXACT_PREFLIGHT_KEYS = Object.freeze([
  "preflight_id",
  "approval_reference",
  "question_sha256",
  "question",
  "run_mode",
  "seats",
  "provider_count",
  "base_calls",
  "retry_calls",
  "maximum_calls",
  "maximum_cost_usd",
  "confirmation_required",
  "source_authorization_status",
  "validity_seconds",
  "expires_at_utc",
]);
// The BYOK projection carries no approval reference: the user's own
// confirmation is the spend authorization, and the six-line operator package
// exists for the operator-funded path alone.
const EXACT_BYOK_PREFLIGHT_KEYS = Object.freeze([
  "preflight_id",
  "question_sha256",
  "question",
  "run_mode",
  "seats",
  "provider_count",
  "base_calls",
  "retry_calls",
  "maximum_calls",
  "maximum_cost_usd",
  "confirmation_required",
  "credential_required",
  "source_authorization_status",
  "validity_seconds",
  "expires_at_utc",
]);
const BYOK_ENDPOINTS = Object.freeze({
  preflight: "/api/council/byok/preflight",
  execute: "/api/council/byok/execute",
  cancel: "/api/council/byok/cancel",
});
const EXACT_SEAT_KEYS = Object.freeze(["seat_id", "alias"]);
const EXACT_EXECUTE_KEYS = Object.freeze(["run_id", "status"]);
const EXACT_DECIMAL = /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/;

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
  byokMode: document.querySelector("#byok-mode-button"),
  normalLiveMode: document.querySelector("#normal-live-mode-button"),
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
  providerStopNotice: document.querySelector("#provider-stop-notice"),
  liveConfirmation: document.querySelector("#live-confirmation-panel"),
  liveSourceStatus: document.querySelector("#live-source-status"),
  liveSeatCount: document.querySelector("#live-seat-count"),
  liveMaximumCalls: document.querySelector("#live-maximum-calls"),
  liveMaximumCost: document.querySelector("#live-maximum-cost"),
  liveApprovalReference: document.querySelector("#live-approval-reference"),
  liveQuestionSha256: document.querySelector("#live-question-sha256"),
  liveExpiresAt: document.querySelector("#live-expires-at"),
  liveCopyApproval: document.querySelector("#live-copy-approval-button"),
  liveCopyStatus: document.querySelector("#live-copy-status"),
  liveCancel: document.querySelector("#live-cancel-button"),
  liveConfirm: document.querySelector("#live-confirm-button"),
  liveConfirmationMode: document.querySelector("#live-confirmation-mode"),
  liveApprovalReferenceRow: document.querySelector("#live-approval-reference-row"),
  byokBlock: document.querySelector("#byok-credential-block"),
  byokKeyInput: document.querySelector("#byok-key-input"),
  byokReveal: document.querySelector("#byok-reveal-button"),
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
  preflightCapability: null,
  preflight: null,
};
runState.sourceMode = "demo";
runState.lifecycle = "idle";

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(value, expected) {
  if (!isPlainObject(value)) {
    return false;
  }
  const actual = Object.keys(value).sort();
  const required = [...expected].sort();
  return actual.length === required.length
    && actual.every((key, index) => key === required[index]);
}

function validateLivePreflight(payload) {
  if (!hasExactKeys(payload, EXACT_PREFLIGHT_KEYS)
      || !NORMAL_PREFLIGHT_ID.test(payload.preflight_id)
      || typeof payload.approval_reference !== "string"
      || !NORMAL_APPROVAL_REFERENCE.test(payload.approval_reference)
      || typeof payload.question_sha256 !== "string"
      || !SHA256_HEX.test(payload.question_sha256)
      || typeof payload.question !== "string"
      || payload.question.length < 1
      || payload.question.length > 8000
      || payload.run_mode !== "normal_live"
      || payload.confirmation_required !== true
      || payload.source_authorization_status !== "authorized"
      || !Array.isArray(payload.seats)
      || !Number.isInteger(payload.provider_count)
      || payload.provider_count < 1
      || payload.provider_count > defaultSeatTemplates.length
      || payload.provider_count !== payload.seats.length
      || !Number.isInteger(payload.base_calls)
      || payload.base_calls < 0
      || !Number.isInteger(payload.retry_calls)
      || payload.retry_calls < 0
      || !Number.isInteger(payload.maximum_calls)
      || payload.maximum_calls <= 0
      || payload.maximum_calls !== payload.base_calls + payload.retry_calls
      || typeof payload.maximum_cost_usd !== "string"
      || payload.maximum_cost_usd.length > 64
      || !EXACT_DECIMAL.test(payload.maximum_cost_usd)
      || payload.validity_seconds !== 900
      || typeof payload.expires_at_utc !== "string"
      || !UTC_TIMESTAMP.test(payload.expires_at_utc)
      || !Number.isFinite(Date.parse(payload.expires_at_utc))) {
    throw new Error("invalid Normal Live preflight projection");
  }
  const seen = new Set();
  const seats = payload.seats.map((seat) => {
    if (!hasExactKeys(seat, EXACT_SEAT_KEYS)
        || typeof seat.seat_id !== "string"
        || !SAFE_PUBLIC_ID.test(seat.seat_id)
        || seen.has(seat.seat_id)
        || typeof seat.alias !== "string"
        || seat.alias.trim() !== seat.alias
        || seat.alias.length < 1
        || seat.alias.length > 80) {
      throw new Error("invalid Normal Live public seat");
    }
    seen.add(seat.seat_id);
    return Object.freeze({ seat_id: seat.seat_id, alias: seat.alias });
  });
  const publicProjection = Object.freeze({
    approval_reference: payload.approval_reference,
    question_sha256: payload.question_sha256,
    question: payload.question,
    run_mode: payload.run_mode,
    seats: Object.freeze(seats),
    provider_count: payload.provider_count,
    base_calls: payload.base_calls,
    retry_calls: payload.retry_calls,
    maximum_calls: payload.maximum_calls,
    maximum_cost_usd: payload.maximum_cost_usd,
    confirmation_required: true,
    source_authorization_status: "authorized",
    validity_seconds: payload.validity_seconds,
    expires_at_utc: payload.expires_at_utc,
  });
  return Object.freeze({
    privatePreflightId: payload.preflight_id,
    publicProjection,
  });
}

function validateByokPreflight(payload) {
  if (!hasExactKeys(payload, EXACT_BYOK_PREFLIGHT_KEYS)
      || !NORMAL_PREFLIGHT_ID.test(payload.preflight_id)
      || typeof payload.question_sha256 !== "string"
      || !SHA256_HEX.test(payload.question_sha256)
      || typeof payload.question !== "string"
      || payload.question.length < 1
      || payload.question.length > 8000
      || payload.run_mode !== "byok_live"
      || payload.confirmation_required !== true
      || payload.credential_required !== true
      || payload.source_authorization_status !== "authorized"
      || !Array.isArray(payload.seats)
      || !Number.isInteger(payload.provider_count)
      || payload.provider_count < 1
      || payload.provider_count > defaultSeatTemplates.length
      || payload.provider_count !== payload.seats.length
      || !Number.isInteger(payload.base_calls)
      || payload.base_calls < 0
      || !Number.isInteger(payload.retry_calls)
      || payload.retry_calls < 0
      || !Number.isInteger(payload.maximum_calls)
      || payload.maximum_calls <= 0
      || payload.maximum_calls !== payload.base_calls + payload.retry_calls
      || typeof payload.maximum_cost_usd !== "string"
      || payload.maximum_cost_usd.length > 64
      || !EXACT_DECIMAL.test(payload.maximum_cost_usd)
      || payload.validity_seconds !== 900
      || typeof payload.expires_at_utc !== "string"
      || !UTC_TIMESTAMP.test(payload.expires_at_utc)
      || !Number.isFinite(Date.parse(payload.expires_at_utc))) {
    throw new Error("invalid BYOK preflight projection");
  }
  const seen = new Set();
  const seats = payload.seats.map((seat) => {
    if (!hasExactKeys(seat, EXACT_SEAT_KEYS)
        || typeof seat.seat_id !== "string"
        || !SAFE_PUBLIC_ID.test(seat.seat_id)
        || seen.has(seat.seat_id)
        || typeof seat.alias !== "string"
        || seat.alias.trim() !== seat.alias
        || seat.alias.length < 1
        || seat.alias.length > 80) {
      throw new Error("invalid BYOK public seat");
    }
    seen.add(seat.seat_id);
    return Object.freeze({ seat_id: seat.seat_id, alias: seat.alias });
  });
  const publicProjection = Object.freeze({
    question_sha256: payload.question_sha256,
    question: payload.question,
    run_mode: payload.run_mode,
    seats: Object.freeze(seats),
    provider_count: payload.provider_count,
    base_calls: payload.base_calls,
    retry_calls: payload.retry_calls,
    maximum_calls: payload.maximum_calls,
    maximum_cost_usd: payload.maximum_cost_usd,
    confirmation_required: true,
    credential_required: true,
    source_authorization_status: "authorized",
    validity_seconds: payload.validity_seconds,
    expires_at_utc: payload.expires_at_utc,
  });
  return Object.freeze({
    privatePreflightId: payload.preflight_id,
    publicProjection,
  });
}

// The credential lives in the password input and in one local variable inside
// the request that carries it. It is never copied into localState, never put in
// a data attribute, and never rendered as text.
function readByokKey() {
  const input = bridgeElements.byokKeyInput;
  return input && typeof input.value === "string" ? input.value : "";
}

function clearByokKey() {
  const input = bridgeElements.byokKeyInput;
  if (!input) {
    return;
  }
  input.value = "";
  input.type = "password";
  if (bridgeElements.byokReveal) {
    bridgeElements.byokReveal.textContent = "Show";
    bridgeElements.byokReveal.setAttribute("aria-pressed", "false");
  }
}

function toggleByokReveal() {
  const input = bridgeElements.byokKeyInput;
  const button = bridgeElements.byokReveal;
  if (!input || !button) {
    return;
  }
  const revealed = input.type === "text";
  input.type = revealed ? "password" : "text";
  button.textContent = revealed ? "Show" : "Hide";
  button.setAttribute("aria-pressed", revealed ? "false" : "true");
}

function syncByokConfirmEnabled() {
  if (localState.sourceMode !== "byok-live") {
    return;
  }
  const ready = runState.lifecycle === "awaiting_confirmation"
    && Boolean(localState.preflight)
    && readByokKey().trim().length > 0;
  bridgeElements.liveConfirm.disabled = !ready;
}

function validateExecuteResponse(payload) {
  if (!hasExactKeys(payload, EXACT_EXECUTE_KEYS)
      || typeof payload.run_id !== "string"
      || !SAFE_PUBLIC_ID.test(payload.run_id)
      || !["queued", "running"].includes(payload.status)) {
    throw new Error("invalid Normal Live execute response");
  }
  return Object.freeze({ run_id: payload.run_id, status: payload.status });
}

function clearLiveConfirmation() {
  localState.preflightCapability = null;
  localState.preflight = null;
  bridgeElements.liveConfirmation.hidden = true;
  bridgeElements.liveSourceStatus.textContent = "—";
  bridgeElements.liveSeatCount.textContent = "—";
  bridgeElements.liveMaximumCalls.textContent = "—";
  bridgeElements.liveMaximumCost.textContent = "—";
  bridgeElements.liveApprovalReference.textContent = "—";
  bridgeElements.liveQuestionSha256.textContent = "—";
  bridgeElements.liveExpiresAt.textContent = "—";
  bridgeElements.liveExpiresAt.removeAttribute("datetime");
  bridgeElements.liveCopyStatus.textContent = "";
  clearByokKey();
  bridgeElements.byokBlock.hidden = true;
}

function renderLiveConfirmation(preflight) {
  const byok = preflight.run_mode === "byok_live";
  bridgeElements.liveSourceStatus.textContent = "SOURCE AUTHORIZED";
  bridgeElements.liveConfirmationMode.textContent = byok
    ? "YOUR OPENROUTER KEY · ONE COUNCIL RUN"
    : "NORMAL LIVE COUNCIL";
  bridgeElements.liveSeatCount.textContent = `${preflight.provider_count} model seats`;
  bridgeElements.liveMaximumCalls.textContent = `Up to ${preflight.maximum_calls} calls`;
  bridgeElements.liveMaximumCost.textContent =
    `Absolute maximum permitted for this run: $${preflight.maximum_cost_usd}`;
  bridgeElements.liveApprovalReferenceRow.hidden = byok;
  bridgeElements.liveApprovalReference.textContent = byok
    ? "—"
    : preflight.approval_reference;
  bridgeElements.liveQuestionSha256.textContent = preflight.question_sha256;
  bridgeElements.liveExpiresAt.textContent = preflight.expires_at_utc;
  bridgeElements.liveExpiresAt.setAttribute("datetime", preflight.expires_at_utc);
  bridgeElements.liveCopyStatus.textContent = "";
  bridgeElements.byokBlock.hidden = !byok;
  bridgeElements.liveCopyApproval.hidden = byok;
  bridgeElements.liveConfirm.disabled = byok;
  bridgeElements.liveConfirmation.hidden = false;
  bridgeElements.liveConfirmation.focus({ preventScroll: true });
  if (byok) {
    clearByokKey();
  }
}

function byokConfirmationMatches(preflight) {
  // Same guarantee as the operator check: what the user saw is what is about to
  // be authorized. The approval reference is absent by design, so the displayed
  // ceilings, fingerprint and expiry carry the whole comparison.
  return Boolean(preflight)
    && !bridgeElements.liveConfirmation.hidden
    && !bridgeElements.byokBlock.hidden
    && elements.activeQuestion.textContent === preflight.question
    && bridgeElements.liveSourceStatus.textContent === "SOURCE AUTHORIZED"
    && bridgeElements.liveSeatCount.textContent === `${preflight.provider_count} model seats`
    && bridgeElements.liveMaximumCalls.textContent === `Up to ${preflight.maximum_calls} calls`
    && bridgeElements.liveMaximumCost.textContent
      === `Absolute maximum permitted for this run: $${preflight.maximum_cost_usd}`
    && bridgeElements.liveQuestionSha256.textContent === preflight.question_sha256
    && bridgeElements.liveExpiresAt.textContent === preflight.expires_at_utc
    && bridgeElements.liveExpiresAt.getAttribute("datetime") === preflight.expires_at_utc;
}

function liveConfirmationMatches(preflight) {
  return Boolean(preflight)
    && bridgeElements.liveConfirmation.hidden === false
    && elements.activeQuestion.textContent === preflight.question
    && bridgeElements.liveSourceStatus.textContent === "SOURCE AUTHORIZED"
    && bridgeElements.liveSeatCount.textContent === `${preflight.provider_count} model seats`
    && bridgeElements.liveMaximumCalls.textContent === `Up to ${preflight.maximum_calls} calls`
    && bridgeElements.liveMaximumCost.textContent ===
      `Absolute maximum permitted for this run: $${preflight.maximum_cost_usd}`
    && bridgeElements.liveApprovalReference.textContent === preflight.approval_reference
    && bridgeElements.liveQuestionSha256.textContent === preflight.question_sha256
    && bridgeElements.liveExpiresAt.textContent === preflight.expires_at_utc
    && bridgeElements.liveExpiresAt.getAttribute("datetime") === preflight.expires_at_utc;
}

function buildLiveApprovalPackage(preflight) {
  return [
    "AUTHORIZE ONE NORMAL LIVE RUN",
    `APPROVAL_REFERENCE = ${preflight.approval_reference}`,
    `QUESTION_SHA256 = ${preflight.question_sha256}`,
    `MAXIMUM_CALLS = ${preflight.maximum_calls}`,
    `MAXIMUM_COST_USD = ${preflight.maximum_cost_usd}`,
    `EXPIRES_AT_UTC = ${preflight.expires_at_utc}`,
  ].join("\n");
}

async function copyLiveApprovalPackage() {
  const preflight = localState.preflight;
  const generation = localState.generation;
  if (runState.lifecycle !== "awaiting_confirmation"
      || !preflight
      || !liveConfirmationMatches(preflight)) {
    bridgeElements.liveCopyStatus.textContent =
      "Approval display mismatch · request a new preflight.";
    return;
  }
  const approvalPackage = buildLiveApprovalPackage(preflight);
  try {
    if (!navigator.clipboard || typeof navigator.clipboard.writeText !== "function") {
      throw new Error("clipboard unavailable");
    }
    await navigator.clipboard.writeText(approvalPackage);
    if (generation === localState.generation
        && preflight === localState.preflight
        && liveConfirmationMatches(preflight)) {
      bridgeElements.liveCopyStatus.textContent = "Approval package copied.";
    }
  } catch (_error) {
    if (generation === localState.generation && preflight === localState.preflight) {
      bridgeElements.liveCopyStatus.textContent =
        "Approval package could not be copied.";
    }
  }
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
  bridgeElements.connectionPanel.hidden = localState.sourceMode === "demo";
  bridgeElements.connectionPanel.dataset.state = state;
  bridgeElements.connectionStatus.textContent = message;
  bridgeElements.retryConnection.hidden = !retry || localState.sourceMode !== "local-ced";
}

function sourceLifecycleLocked() {
  return [
    "preflighting",
    "awaiting_confirmation",
    "cancelling",
    "executing",
    "starting",
    "running",
  ].includes(runState.lifecycle);
}

function syncSourceControls() {
  const isDemo = localState.sourceMode === "demo";
  const isLocal = localState.sourceMode === "local-ced";
  const isNormal = localState.sourceMode === "normal-live";
  const isByok = localState.sourceMode === "byok-live";
  const locked = isDemo
    ? runState.mode === "running"
    : sourceLifecycleLocked();
  bridgeElements.demoMode.classList.toggle("is-selected", isDemo);
  bridgeElements.localMode.classList.toggle("is-selected", isLocal);
  bridgeElements.byokMode.classList.toggle("is-selected", isByok);
  bridgeElements.normalLiveMode.classList.toggle("is-selected", isNormal);
  bridgeElements.demoMode.setAttribute("aria-pressed", String(isDemo));
  bridgeElements.localMode.setAttribute("aria-pressed", String(isLocal));
  bridgeElements.byokMode.setAttribute("aria-pressed", String(isByok));
  bridgeElements.normalLiveMode.setAttribute("aria-pressed", String(isNormal));
  bridgeElements.demoMode.disabled = locked;
  bridgeElements.localMode.disabled = locked;
  bridgeElements.byokMode.disabled = locked;
  bridgeElements.normalLiveMode.disabled = locked;
  elements.completeButton.hidden = !isDemo;
  elements.conveneButton.disabled = locked || (isLocal && localState.available !== true);
  elements.exampleButton.disabled = locked;
  elements.questionInput.readOnly = locked;
  const busy = isDemo
    ? runState.mode === "running"
    : [
      "preflighting",
      "cancelling",
      "executing",
      "starting",
      "running",
    ].includes(runState.lifecycle);
  elements.form.setAttribute("aria-busy", String(busy));
  bridgeElements.liveCopyApproval.disabled = runState.lifecycle !== "awaiting_confirmation";
  bridgeElements.liveCancel.disabled = runState.lifecycle !== "awaiting_confirmation";
  bridgeElements.liveConfirm.disabled = runState.lifecycle !== "awaiting_confirmation";
  if (isNormal || isByok) {
    const labels = isByok
      ? {
        idle: "PLAN THIS COUNCIL",
        preflighting: "CHECKING AUTHORIZATION",
        awaiting_confirmation: "AWAITING YOUR KEY",
        cancelling: "CANCELLING PREFLIGHT",
        executing: "CONVENING COUNCIL",
        starting: "CONVENING COUNCIL",
        running: "COUNCIL IN SESSION",
      }
      : {
        idle: "CHECK LIVE PREFLIGHT",
        preflighting: "CHECKING AUTHORIZATION",
        awaiting_confirmation: "AWAITING CONFIRMATION",
        cancelling: "CANCELLING PREFLIGHT",
        executing: "CONVENING NORMAL LIVE",
        starting: "CONVENING NORMAL LIVE",
        running: "COUNCIL IN SESSION",
      };
    elements.conveneLabel.textContent =
      labels[runState.lifecycle] || (isByok ? "PLAN THIS COUNCIL" : "CHECK LIVE PREFLIGHT");
  }
  bridgeElements.recordSource.textContent = isDemo
    ? "demonstration"
    : isNormal
      ? "canonical Normal Live"
      : isByok
        ? "canonical council · your OpenRouter key"
        : "canonical local CED";
  bridgeElements.connectionPanel.hidden = isDemo;
  // In BYOK the confirmation is also a spend authorization, so it stays
  // disabled until a key is actually present in the private input.
  syncByokConfirmEnabled();
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
    : localState.sourceMode === "normal-live"
      ? "GOVERNED COUNCIL OUTPUT · NORMAL LIVE"
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
  // Cleared on every render so a stop notice from an earlier run can never
  // survive beside a later run's answer. The completion handler sets it again
  // immediately afterwards when the server sent one.
  bridgeElements.providerStopNotice.textContent = "";
  bridgeElements.providerStopNotice.hidden = true;
  elements.finalSynthesis.hidden = false;
}

function renderDemoView() {
  restoreDefaultSeatTopology();
  renderCommitments(DEMO_VIEW.commitments);
  renderFinal(DEMO_VIEW.final, { demo: true });
  elements.finalSynthesis.hidden = runState.mode !== "complete";
}

function renderLocalIdle(message = "LOCAL CED READY · ENTER A QUESTION") {
  restoreDefaultSeatTopology();
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

function renderNormalIdle(
  message = "NORMAL LIVE READY · CHECK PREFLIGHT",
  {
    eyebrow = "NORMAL LIVE",
    connection = "Normal Live preflight has not been checked.",
  } = {},
) {
  clearRenderedRun();
  clearSeatTopology();
  renderTimeline(-1);
  renderCommitments([]);
  clearLiveConfirmation();
  elements.activeQuestion.textContent = "Waiting for a question.";
  elements.phaseBrief.querySelector("span").textContent = eyebrow;
  elements.phaseBrief.querySelector("h4").textContent = "Authorization preflight required";
  elements.phaseBrief.querySelector("p").textContent =
    "The server must authorize the exact source set, derive the full call plan, and present its conservative cost ceiling before confirmation.";
  setRunStatus(message);
  setConnection(connection, "checking");
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

function failNormalView(message, { providerStartImpossible = false } = {}) {
  closeLocalTransport();
  clearLiveConfirmation();
  runState.mode = "failed";
  runState.lifecycle = "unavailable";
  runState.stage = "failed";
  localState.terminal = true;
  setConnection(message, "unavailable");
  setRunStatus(message.toUpperCase());
  elements.phaseBrief.querySelector("span").textContent = "NORMAL LIVE UNAVAILABLE";
  elements.phaseBrief.querySelector("h4").textContent = providerStartImpossible
    ? "Execution was not authorized"
    : "Public completion could not be confirmed";
  elements.phaseBrief.querySelector("p").textContent = providerStartImpossible
    ? "No provider call was started and no private backend diagnostic was exposed."
    : "The server run may have started or may continue. The browser failed closed without exposing a private backend diagnostic.";
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
      setRunStatus(localState.sourceMode === "normal-live"
        ? "NORMAL LIVE · CANONICAL COUNCIL STARTED"
        : "CANONICAL LOCAL CED · COUNCIL STARTED");
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
      // Server-authored, drawn from a closed table, and shown beside the
      // governing notice rather than inside it: the two say different things.
      const stopNotice = typeof data.provider_stop_notice === "string"
        ? data.provider_stop_notice.slice(0, 400)
        : "";
      bridgeElements.providerStopNotice.textContent = stopNotice;
      bridgeElements.providerStopNotice.hidden = stopNotice.length === 0;
      elements.phaseBrief.querySelector("span").textContent = localState.sourceMode === "normal-live"
        ? "NORMAL LIVE COUNCIL COMPLETE"
        : "CANONICAL COUNCIL COMPLETE";
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
      if (localState.sourceMode === "normal-live") {
        failNormalView("Normal Live run failed · public diagnostic withheld.");
      } else {
        failLocalView("LOCAL CED RUN FAILED · PUBLIC DIAGNOSTIC WITHHELD");
      }
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
      if (localState.sourceMode === "normal-live") {
        failNormalView("Normal Live public event rejected · display failed closed.");
      } else {
        failLocalView("LOCAL CED PUBLIC EVENT REJECTED · DISPLAY FAILED CLOSED");
      }
    }
  };
  PUBLIC_EVENT_TYPES.forEach((eventType) => source.addEventListener(eventType, receive));
  source.addEventListener("open", () => {
    if (!localState.terminal && generation === localState.generation) {
      setConnection(localState.sourceMode === "normal-live"
        ? "Connected · canonical Normal Live council"
        : "Connected · canonical CED · offline mock providers", "available");
    }
  });
  source.addEventListener("error", () => {
    if (!localState.terminal && generation === localState.generation) {
      setConnection(localState.sourceMode === "normal-live"
        ? "Normal Live connection interrupted · browser retrying safely"
        : "Connection interrupted · browser retrying safely", "checking");
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

async function startNormalPreflight(question) {
  closeLocalTransport();
  invalidateRun();
  clearRenderedRun();
  renderCommitments([]);
  clearLiveConfirmation();
  clearSeatTopology();
  localState.generation += 1;
  const generation = localState.generation;
  localState.runId = null;
  localState.lastSequence = -1;
  localState.fingerprints.clear();
  localState.terminal = false;
  localState.ratification = null;
  runState.mode = "idle";
  runState.lifecycle = "preflighting";
  runState.stage = "preflight";
  runState.phaseIndex = -1;
  elements.activeQuestion.textContent = question;
  renderTimeline(-1);
  setConnection("Checking source authorization and canonical cost bounds…", "checking");
  setRunStatus("NORMAL LIVE · CHECKING AUTHORIZATION");
  elements.phaseBrief.querySelector("span").textContent = "NORMAL LIVE PREFLIGHT";
  elements.phaseBrief.querySelector("h4").textContent = "Verifying the execution boundary";
  elements.phaseBrief.querySelector("p").textContent =
    "No provider call begins during preflight. The server derives all seats, calls, and cost authority.";
  setControlState();
  syncSourceControls();

  const controller = new AbortController();
  localState.requestController = controller;
  try {
    const response = await fetch("/api/council/live/preflight", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal,
      credentials: "same-origin",
    });
    if (generation !== localState.generation) {
      return;
    }
    localState.requestController = null;
    if (!response.ok) {
      failNormalView(response.status === 503
        ? "Normal Live is not yet authorized for this build."
        : "Normal Live preflight was refused.", { providerStartImpossible: true });
      return;
    }
    const validated = validateLivePreflight(await response.json());
    localState.preflightCapability = validated.privatePreflightId;
    localState.preflight = validated.publicProjection;
    const preflight = localState.preflight;
    elements.activeQuestion.textContent = preflight.question;
    renderPublicSeatTopology(preflight.seats);
    renderLiveConfirmation(localState.preflight);
    runState.lifecycle = "awaiting_confirmation";
    runState.stage = "confirmation";
    setConnection("Source authorized · explicit confirmation required", "available");
    setRunStatus("NORMAL LIVE · REVIEW CALL AND COST CEILING");
    elements.phaseBrief.querySelector("h4").textContent = "Awaiting explicit confirmation";
    elements.phaseBrief.querySelector("p").textContent =
      "Cancel consumes no provider calls. Confirm starts this exact one-use server-owned preflight.";
    setControlState();
    syncSourceControls();
  } catch (error) {
    if (error && error.name === "AbortError") {
      return;
    }
    if (generation === localState.generation) {
      failNormalView("Normal Live preflight could not be verified.", {
        providerStartImpossible: true,
      });
    }
  }
}

async function cancelNormalPreflight({ focusQuestion = true } = {}) {
  if (runState.lifecycle !== "awaiting_confirmation"
      || !localState.preflight
      || !localState.preflightCapability) {
    return;
  }
  const preflightId = localState.preflightCapability;
  const generation = localState.generation;
  runState.lifecycle = "cancelling";
  setRunStatus("NORMAL LIVE · CANCELLING PREFLIGHT");
  syncSourceControls();
  const controller = new AbortController();
  localState.requestController = controller;
  try {
    const response = await fetch("/api/council/live/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ preflight_id: preflightId }),
      signal: controller.signal,
      credentials: "same-origin",
    });
    if (generation !== localState.generation) {
      return;
    }
    localState.requestController = null;
    if (response.status !== 204) {
      throw new Error("cancel refused");
    }
    renderNormalIdle("NORMAL LIVE PREFLIGHT CANCELLED · NO RUN STARTED");
    setConnection("Preflight cancelled · no provider call started", "available");
    if (focusQuestion) {
      elements.questionInput.focus();
    }
  } catch (error) {
    if (error && error.name === "AbortError") {
      return;
    }
    if (generation === localState.generation) {
      failNormalView("Normal Live preflight cancellation could not be confirmed.");
    }
  }
}

async function executeNormalPreflight() {
  if (runState.lifecycle !== "awaiting_confirmation"
      || !localState.preflight
      || !localState.preflightCapability) {
    return;
  }
  const preflight = localState.preflight;
  const preflightId = localState.preflightCapability;
  if (!liveConfirmationMatches(preflight)) {
    failNormalView("Normal Live approval display changed · execution blocked.", {
      providerStartImpossible: true,
    });
    return;
  }
  const generation = localState.generation;
  runState.mode = "running";
  runState.lifecycle = "executing";
  runState.stage = "accepted";
  setConnection("Confirmation received · consuming one-use preflight", "checking");
  setRunStatus("NORMAL LIVE · CONVENING CANONICAL COUNCIL");
  setControlState();
  syncSourceControls();
  const controller = new AbortController();
  localState.requestController = controller;
  try {
    const response = await fetch("/api/council/live/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ preflight_id: preflightId, confirmed: true }),
      signal: controller.signal,
      credentials: "same-origin",
    });
    if (generation !== localState.generation) {
      return;
    }
    localState.requestController = null;
    if (!response.ok) {
      throw new Error("execute refused");
    }
    const started = validateExecuteResponse(await response.json());
    localState.runId = started.run_id;
    clearLiveConfirmation();
    runState.lifecycle = "starting";
    attachEventStream(started.run_id, generation);
    syncSourceControls();
  } catch (error) {
    if (error && error.name === "AbortError") {
      return;
    }
    if (generation === localState.generation) {
      failNormalView("Normal Live execution response could not be confirmed.");
    }
  }
}

function renderByokIdle(message = "READY · PLAN YOUR COUNCIL") {
  renderNormalIdle(message, {
    eyebrow: "YOUR OPENROUTER KEY",
    connection: "Plan a council to see its exact call and spend ceiling.",
  });
}

async function startByokPreflight(question) {
  closeLocalTransport();
  invalidateRun();
  clearRenderedRun();
  renderCommitments([]);
  clearLiveConfirmation();
  clearSeatTopology();
  localState.generation += 1;
  const generation = localState.generation;
  localState.runId = null;
  localState.lastSequence = -1;
  localState.fingerprints.clear();
  localState.terminal = false;
  localState.ratification = null;
  runState.mode = "idle";
  runState.lifecycle = "preflighting";
  runState.stage = "preflight";
  runState.phaseIndex = -1;
  elements.activeQuestion.textContent = question;
  renderTimeline(-1);
  setConnection("Deriving the council plan and its spend ceiling…", "checking");
  setRunStatus("PLANNING COUNCIL · NO KEY SENT YET");
  elements.phaseBrief.querySelector("span").textContent = "COUNCIL PREFLIGHT";
  elements.phaseBrief.querySelector("h4").textContent = "Deriving the execution boundary";
  elements.phaseBrief.querySelector("p").textContent =
    "No provider call begins during preflight, and your key is not part of this request.";
  setControlState();
  syncSourceControls();

  const controller = new AbortController();
  localState.requestController = controller;
  try {
    const response = await fetch(BYOK_ENDPOINTS.preflight, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal,
      credentials: "same-origin",
    });
    if (generation !== localState.generation) {
      return;
    }
    localState.requestController = null;
    if (!response.ok) {
      failNormalView(
        response.status === 429
          ? "Capacity for this preview was temporarily reached. Try again shortly."
          : response.status === 503
            ? "This build is not authorized to convene a live council."
            : "The council plan was refused.",
        { providerStartImpossible: true },
      );
      return;
    }
    const validated = validateByokPreflight(await response.json());
    localState.preflightCapability = validated.privatePreflightId;
    localState.preflight = validated.publicProjection;
    const preflight = localState.preflight;
    elements.activeQuestion.textContent = preflight.question;
    renderPublicSeatTopology(preflight.seats);
    renderLiveConfirmation(preflight);
    runState.lifecycle = "awaiting_confirmation";
    runState.stage = "confirmation";
    setConnection("Plan ready · enter your OpenRouter key to confirm", "available");
    setRunStatus("REVIEW THE CEILING · THEN ENTER YOUR KEY");
    elements.phaseBrief.querySelector("h4").textContent = "Awaiting your key and confirmation";
    elements.phaseBrief.querySelector("p").textContent =
      "Cancel consumes nothing. Confirming spends from your own OpenRouter account, once.";
    setControlState();
    syncSourceControls();
    bridgeElements.byokKeyInput.focus({ preventScroll: true });
  } catch (error) {
    if (error && error.name === "AbortError") {
      return;
    }
    if (generation === localState.generation) {
      failNormalView("The council plan could not be verified.", {
        providerStartImpossible: true,
      });
    }
  }
}

async function cancelByokPreflight({ focusQuestion = true } = {}) {
  if (runState.lifecycle !== "awaiting_confirmation"
      || !localState.preflight
      || !localState.preflightCapability) {
    return;
  }
  const preflightId = localState.preflightCapability;
  const generation = localState.generation;
  runState.lifecycle = "cancelling";
  setRunStatus("CANCELLING · NO CHARGE");
  clearByokKey();
  syncSourceControls();
  const controller = new AbortController();
  localState.requestController = controller;
  try {
    const response = await fetch(BYOK_ENDPOINTS.cancel, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ preflight_id: preflightId }),
      signal: controller.signal,
      credentials: "same-origin",
    });
    if (generation !== localState.generation) {
      return;
    }
    localState.requestController = null;
    if (response.status !== 204) {
      throw new Error("cancel refused");
    }
    renderByokIdle("PREFLIGHT CANCELLED · NOTHING WAS CHARGED");
    setConnection("Preflight cancelled · no provider call started", "available");
    if (focusQuestion) {
      elements.questionInput.focus();
    }
  } catch (error) {
    if (error && error.name === "AbortError") {
      return;
    }
    if (generation === localState.generation) {
      failNormalView("The cancellation could not be confirmed.");
    }
  }
}

async function executeByokPreflight() {
  if (runState.lifecycle !== "awaiting_confirmation"
      || !localState.preflight
      || !localState.preflightCapability) {
    return;
  }
  const preflight = localState.preflight;
  const preflightId = localState.preflightCapability;
  if (!byokConfirmationMatches(preflight)) {
    failNormalView("The displayed plan changed · execution blocked.", {
      providerStartImpossible: true,
    });
    clearByokKey();
    return;
  }
  // Read once, into one local. It is never written to localState, never stored
  // and never logged; the reference dies with this function's frame.
  const key = readByokKey();
  if (!key.trim()) {
    syncByokConfirmEnabled();
    return;
  }
  const generation = localState.generation;
  runState.mode = "running";
  runState.lifecycle = "executing";
  runState.stage = "accepted";
  setConnection("Confirmation received · consuming one-use preflight", "checking");
  setRunStatus("CONVENING CANONICAL COUNCIL");
  setControlState();
  syncSourceControls();
  const controller = new AbortController();
  localState.requestController = controller;
  try {
    const response = await fetch(BYOK_ENDPOINTS.execute, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({
        preflight_id: preflightId,
        confirmed: true,
        openrouter_api_key: key,
      }),
      signal: controller.signal,
      credentials: "same-origin",
    });
    // Cleared on every outcome, before anything else can await again.
    clearByokKey();
    if (generation !== localState.generation) {
      return;
    }
    localState.requestController = null;
    if (!response.ok) {
      failNormalView(
        response.status === 429
          ? "Capacity for this preview was temporarily reached. Try again shortly."
          : response.status === 400
            ? "That OpenRouter key was rejected. Check it and enter it again."
            : "The council could not be started.",
      );
      return;
    }
    const started = validateExecuteResponse(await response.json());
    localState.runId = started.run_id;
    clearLiveConfirmation();
    runState.lifecycle = "starting";
    attachEventStream(started.run_id, generation);
    syncSourceControls();
  } catch (error) {
    clearByokKey();
    if (error && error.name === "AbortError") {
      return;
    }
    if (generation === localState.generation) {
      failNormalView("The council response could not be confirmed.");
    }
  }
}

async function checkLocalHealth() {
  if (localState.sourceMode !== "local-ced") {
    return;
  }
  setConnection("Checking the local CED bridge…", "checking");
  localState.available = null;
  const generation = localState.generation;
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
    if (generation !== localState.generation || localState.sourceMode !== "local-ced") {
      return;
    }
    localState.available = true;
    setConnection("Connected · canonical CED · offline mock providers", "available");
    setRunStatus("LOCAL CED AVAILABLE · READY TO CONVENE");
  } catch (_error) {
    if (generation !== localState.generation || localState.sourceMode !== "local-ced") {
      return;
    }
    localState.available = false;
    setConnection("Local CED unavailable · start the local server, then retry", "unavailable", { retry: true });
    setRunStatus("LOCAL CED UNAVAILABLE · DEMO MODE REMAINS AVAILABLE");
  }
  syncSourceControls();
}

function selectDemoMode() {
  if (sourceLifecycleLocked()) {
    return;
  }
  closeLocalTransport();
  localState.generation += 1;
  localState.sourceMode = "demo";
  runState.sourceMode = "demo";
  localState.runId = null;
  localState.terminal = false;
  clearLiveConfirmation();
  resetDemo({ focusQuestion: false });
  runState.lifecycle = "idle";
  renderDemoView();
  setRunStatus("DEMO MODE · READY TO CONVENE");
  syncSourceControls();
}

function selectLocalMode() {
  if (sourceLifecycleLocked()) {
    return;
  }
  invalidateRun();
  localState.generation += 1;
  localState.sourceMode = "local-ced";
  runState.sourceMode = "local-ced";
  runState.lifecycle = "idle";
  localState.runId = null;
  localState.terminal = false;
  clearLiveConfirmation();
  renderLocalIdle("LOCAL CED · CHECKING CONNECTION");
  checkLocalHealth();
}

function selectNormalLiveMode() {
  if (sourceLifecycleLocked()) {
    return;
  }
  closeLocalTransport();
  invalidateRun();
  localState.generation += 1;
  localState.sourceMode = "normal-live";
  runState.sourceMode = "normal-live";
  runState.lifecycle = "idle";
  localState.runId = null;
  localState.terminal = false;
  localState.lastSequence = -1;
  localState.fingerprints.clear();
  localState.ratification = null;
  renderNormalIdle();
}

function selectByokMode() {
  if (sourceLifecycleLocked()) {
    return;
  }
  closeLocalTransport();
  invalidateRun();
  localState.generation += 1;
  localState.sourceMode = "byok-live";
  runState.sourceMode = "byok-live";
  runState.lifecycle = "idle";
  localState.runId = null;
  localState.terminal = false;
  localState.lastSequence = -1;
  localState.fingerprints.clear();
  localState.ratification = null;
  clearByokKey();
  renderByokIdle();
}

function resetByokView() {
  if (runState.lifecycle === "awaiting_confirmation") {
    cancelByokPreflight();
    return;
  }
  if (runState.lifecycle === "cancelling") {
    return;
  }
  const mayContinue = Boolean(localState.runId && !localState.terminal)
    || ["executing", "starting", "running"].includes(runState.lifecycle);
  closeLocalTransport();
  invalidateRun();
  localState.generation += 1;
  localState.runId = null;
  localState.lastSequence = -1;
  localState.fingerprints.clear();
  localState.terminal = false;
  localState.ratification = null;
  clearLiveConfirmation();
  clearByokKey();
  renderByokIdle(mayContinue
    ? "VIEW RESET · THE SERVER RUN MAY CONTINUE"
    : "READY · PLAN YOUR COUNCIL");
  setQuestionError(false);
  elements.questionInput.focus();
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

function resetNormalView() {
  if (runState.lifecycle === "awaiting_confirmation") {
    cancelNormalPreflight();
    return;
  }
  if (runState.lifecycle === "cancelling") {
    return;
  }
  const mayContinue = Boolean(localState.runId && !localState.terminal)
    || ["executing", "starting", "running"].includes(runState.lifecycle);
  closeLocalTransport();
  invalidateRun();
  localState.generation += 1;
  localState.runId = null;
  localState.lastSequence = -1;
  localState.fingerprints.clear();
  localState.terminal = false;
  localState.ratification = null;
  clearLiveConfirmation();
  renderNormalIdle(mayContinue
    ? "NORMAL LIVE VIEW RESET · THE SERVER RUN MAY CONTINUE"
    : "NORMAL LIVE · READY FOR A NEW PREFLIGHT");
  setQuestionError(false);
  elements.questionInput.focus();
}

bridgeElements.demoMode.addEventListener("click", selectDemoMode);
bridgeElements.localMode.addEventListener("click", selectLocalMode);
bridgeElements.byokMode.addEventListener("click", selectByokMode);
bridgeElements.normalLiveMode.addEventListener("click", selectNormalLiveMode);
bridgeElements.retryConnection.addEventListener("click", checkLocalHealth);
bridgeElements.liveCopyApproval.addEventListener("click", copyLiveApprovalPackage);
bridgeElements.liveCancel.addEventListener("click", () => {
  if (localState.sourceMode === "byok-live") {
    cancelByokPreflight();
  } else {
    cancelNormalPreflight();
  }
});
bridgeElements.liveConfirm.addEventListener("click", () => {
  if (localState.sourceMode === "byok-live") {
    executeByokPreflight();
  } else {
    executeNormalPreflight();
  }
});
bridgeElements.byokReveal.addEventListener("click", toggleByokReveal);
bridgeElements.byokKeyInput.addEventListener("input", syncByokConfirmEnabled);
// Enter inside the key field confirms rather than submitting the outer form,
// which would otherwise start a second preflight and orphan the first.
bridgeElements.byokKeyInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  if (!bridgeElements.liveConfirm.disabled) {
    executeByokPreflight();
  }
});
// Best effort only: a page teardown is not a guarantee, and the credential has
// already left for the server by the time any run is under way.
window.addEventListener("pagehide", clearByokKey);
window.addEventListener("beforeunload", clearByokKey);

elements.form.addEventListener("submit", (event) => {
  if (localState.sourceMode === "demo") {
    window.queueMicrotask(syncSourceControls);
    return;
  }
  event.preventDefault();
  event.stopImmediatePropagation();
  if (runState.mode === "running" || sourceLifecycleLocked()) {
    return;
  }
  const question = currentQuestion();
  if (question) {
    if (localState.sourceMode === "normal-live") {
      startNormalPreflight(question);
    } else if (localState.sourceMode === "byok-live") {
      startByokPreflight(question);
    } else {
      startLocalCouncil(question);
    }
  }
}, true);

elements.resetButton.addEventListener("click", (event) => {
  if (localState.sourceMode === "demo") {
    return;
  }
  event.preventDefault();
  event.stopImmediatePropagation();
  if (localState.sourceMode === "normal-live") {
    resetNormalView();
  } else if (localState.sourceMode === "byok-live") {
    resetByokView();
  } else {
    resetLocalView();
  }
}, true);

elements.completeButton.addEventListener("click", (event) => {
  if (localState.sourceMode !== "demo") {
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

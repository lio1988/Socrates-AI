"use strict";

/*
 * SOCRATES UI V0.1 — LOCAL DEMONSTRATION FIXTURES
 * ------------------------------------------------
 * Everything below is static mock data for the visual prototype. It does not
 * call a backend, provider, model, API, or network resource.
 */

const DEMO_FIXTURES = Object.freeze({
  question:
    "Does widespread AI automation necessarily reduce total employment, or can it create enough new categories of work to offset displacement?",
  completionAssignments: [
    { role: "Reconstructor", state: "complete" },
    { role: "Elenchus critic", state: "complete" },
    { role: "Synthesizer", state: "complete" },
    { role: "Evaluator", state: "complete" },
  ],
  phases: [
    {
      name: "Opening",
      briefTitle: "Expose the load-bearing assumption",
      brief:
        "The council begins by separating automation of existing tasks from the permanent disappearance of economically valuable work.",
      assignments: [
        { role: "Socrates", state: "active" },
        { role: "Independent analyst", state: "thinking" },
        { role: "Empiricist", state: "thinking" },
        { role: "Elenchus critic", state: "thinking" },
      ],
      moves: [
        {
          id: "opening-01",
          mark: "01",
          agent: "Aletheia",
          role: "Socrates",
          phase: "01 Opening",
          status: "Submitted",
          confidence: "High",
          content:
            "Which assumption connects automation of existing tasks to a permanent reduction in the total number of economically valuable tasks?",
        },
      ],
    },
    {
      name: "Initial responses",
      briefTitle: "Form positions independently",
      brief:
        "Independent seats answer before seeing how the final synthesis will be assembled.",
      assignments: [
        { role: "Independent analyst", state: "submitted" },
        { role: "Position author", state: "active" },
        { role: "Empiricist", state: "thinking" },
        { role: "Position author", state: "thinking" },
      ],
      moves: [
        {
          id: "initial-01",
          mark: "02",
          agent: "Logos",
          role: "Position author",
          phase: "02 Initial responses",
          status: "Submitted",
          confidence: "Moderate",
          content:
            "Displacement is task-specific. Aggregate employment also depends on whether lower costs expand demand and create complementary work.",
        },
        {
          id: "initial-02",
          mark: "03",
          agent: "Praxis",
          role: "Empiricist",
          phase: "02 Initial responses",
          status: "Submitted",
          confidence: "Moderate",
          content:
            "Historical transitions show both displacement and task creation; the net effect depends strongly on adjustment speed and sector.",
        },
      ],
    },
    {
      name: "Elenchus",
      briefTitle: "Attack the reasoning, not the speaker",
      brief:
        "The critic identifies what would have to be true for either permanent job loss or automatic compensation to follow.",
      assignments: [
        { role: "Respondent", state: "submitted" },
        { role: "Elenchus critic", state: "active" },
        { role: "Empiricist", state: "accepted" },
        { role: "Socrates", state: "thinking" },
      ],
      moves: [
        {
          id: "elenchus-01",
          mark: "02",
          agent: "Logos",
          role: "Elenchus critic",
          phase: "03 Elenchus",
          status: "Accepted challenge",
          confidence: "High",
          content:
            "The displacement argument assumes demand for new complementary work does not expand enough to absorb released labour.",
        },
      ],
    },
    {
      name: "Reflection",
      briefTitle: "Revise when criticism succeeds",
      brief:
        "Positions are updated explicitly. Earlier commitments remain visible instead of being silently overwritten.",
      assignments: [
        { role: "Reflector", state: "thinking" },
        { role: "Reflector", state: "submitted" },
        { role: "Reflector", state: "accepted" },
        { role: "Lead reflector", state: "active" },
      ],
      moves: [
        {
          id: "reflection-01",
          mark: "04",
          agent: "Metis",
          role: "Reflector",
          phase: "04 Reflection",
          status: "Revised",
          confidence: "High",
          content:
            "The original claim should be narrowed: short-run displacement can be substantial without implying permanent aggregate job loss.",
        },
      ],
    },
    {
      name: "Reconstruction",
      briefTitle: "Build the strongest surviving position",
      brief:
        "The council reconstructs an answer from claims that survived challenge and revision.",
      assignments: [
        { role: "Reconstructor", state: "active" },
        { role: "Elenchus critic", state: "submitted" },
        { role: "Empiricist", state: "accepted" },
        { role: "Socrates", state: "thinking" },
      ],
      moves: [
        {
          id: "reconstruction-01",
          mark: "01",
          agent: "Aletheia",
          role: "Reconstructor",
          phase: "05 Reconstruction",
          status: "Accepted",
          confidence: "High",
          content:
            "The strongest defensible position separates transition costs from the long-run employment equilibrium.",
        },
      ],
    },
    {
      name: "Synthesis",
      briefTitle: "Assemble a concise public answer",
      brief:
        "The synthesis preserves the conclusion, strongest qualification and remaining uncertainty as separate elements.",
      assignments: [
        { role: "Elenchus critic", state: "accepted" },
        { role: "Empiricist", state: "submitted" },
        { role: "Synthesizer", state: "active" },
        { role: "Socrates", state: "thinking" },
      ],
      moves: [
        {
          id: "synthesis-01",
          mark: "03",
          agent: "Praxis",
          role: "Synthesizer",
          phase: "06 Synthesis",
          status: "Submitted",
          confidence: "Moderate",
          content:
            "Automation changes the composition of work. Its employment effect is contingent, with transition speed and access to new tasks carrying the largest qualification.",
        },
      ],
    },
    {
      name: "Ratification",
      briefTitle: "Check discipline before release",
      brief:
        "Independent evaluators inspect the synthesis for coherence, explicit uncertainty and unresolved objections.",
      assignments: [
        { role: "Evaluator", state: "accepted" },
        { role: "Evaluator", state: "accepted" },
        { role: "Evaluator", state: "submitted" },
        { role: "Lead evaluator", state: "active", status: "Evaluating" },
      ],
      moves: [
        {
          id: "ratification-01",
          mark: "04",
          agent: "Metis",
          role: "Evaluator",
          phase: "07 Ratification",
          status: "Complete",
          confidence: "Moderate",
          content:
            "Accept with caveat: the conclusion is calibrated, but the pace and distribution of new task creation remain genuinely uncertain.",
        },
      ],
    },
  ],
});

const phaseDuration = 1350;
const openingTransitionDelays = Object.freeze({
  seats: 220,
  phase: 520,
  firstMove: 900,
});

const elements = {
  form: document.querySelector("#question-form"),
  questionInput: document.querySelector("#question-input"),
  questionError: document.querySelector("#question-error"),
  exampleButton: document.querySelector("#example-button"),
  conveneButton: document.querySelector("#convene-button"),
  conveneLabel: document.querySelector("#convene-button .button-label"),
  completeButton: document.querySelector("#complete-button"),
  resetButton: document.querySelector("#reset-button"),
  council: document.querySelector("#council"),
  runStatusText: document.querySelector("#run-status-text"),
  seatGrid: document.querySelector("#seat-grid"),
  seatTopologyTitle: document.querySelector("#seat-topology-title"),
  seats: Array.from(document.querySelectorAll(".seat-card")),
  phaseItems: Array.from(document.querySelectorAll("#phase-rail li")),
  phaseCount: document.querySelector("#phase-count"),
  phaseProgress: document.querySelector(".phase-progress"),
  progressFill: document.querySelector("#progress-fill"),
  activeQuestion: document.querySelector("#active-question"),
  contributionList: document.querySelector("#contribution-list"),
  recordSummary: document.querySelector("#record-summary"),
  recordToggle: document.querySelector("#record-toggle"),
  feedEmpty: document.querySelector("#feed-empty"),
  phaseBrief: document.querySelector("#phase-brief"),
  commitments: document.querySelector("#commitments-panel"),
  finalSynthesis: document.querySelector("#final-synthesis"),
  synthesisTitle: document.querySelector("#synthesis-title"),
};

const defaultSeatTemplates = elements.seats.map((seat) => seat.cloneNode(true));
const defaultSeatTopologyTitle = elements.seatTopologyTitle.textContent;

const runState = {
  mode: "idle",
  stage: "idle",
  phaseIndex: -1,
  generation: 0,
  timerIds: [],
  renderedMoveIds: new Set(),
  recordExpanded: false,
  visibleContributionLimit: 2,
};

function clearRunTimers() {
  runState.timerIds.forEach((timerId) => window.clearTimeout(timerId));
  runState.timerIds = [];
}

function invalidateRun() {
  clearRunTimers();
  runState.generation += 1;
}

function createElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  if (typeof text === "string") {
    element.textContent = text;
  }
  return element;
}

function setQuestionError(isVisible) {
  elements.questionError.hidden = !isVisible;
  elements.questionInput.setAttribute("aria-invalid", String(isVisible));
}

function currentQuestion({ allowExampleFallback = false } = {}) {
  const typedQuestion = elements.questionInput.value.trim();
  if (typedQuestion) {
    setQuestionError(false);
    return typedQuestion;
  }
  if (allowExampleFallback) {
    elements.questionInput.value = DEMO_FIXTURES.question;
    setQuestionError(false);
    return DEMO_FIXTURES.question;
  }
  setQuestionError(true);
  elements.questionInput.focus();
  return null;
}

function setControlState() {
  const isRunning = runState.mode === "running";
  const isComplete = runState.mode === "complete";
  const isConvening = isRunning && runState.stage !== "deliberating";
  elements.council.dataset.runState = runState.mode;
  elements.council.dataset.runStage = runState.stage;
  elements.form.setAttribute("aria-busy", String(isRunning));
  elements.questionInput.readOnly = isRunning;
  elements.conveneButton.disabled = isRunning;
  elements.exampleButton.disabled = isRunning;
  elements.conveneLabel.textContent = isRunning
    ? isConvening
      ? "CONVENING COUNCIL"
      : "COUNCIL IN SESSION"
    : "CONVENE COUNCIL";
  elements.completeButton.textContent = isRunning ? "Skip demo" : "Show complete run";
  elements.completeButton.disabled = isComplete;
}

function setRunStatus(message) {
  elements.runStatusText.textContent = message;
}

function replaceSeatCards(cards) {
  elements.seatGrid.replaceChildren(...cards);
  elements.seats = Array.from(cards);
  elements.seatGrid.style.setProperty("--seat-count", String(cards.length || 1));
}

function restoreDefaultSeatTopology() {
  replaceSeatCards(defaultSeatTemplates.map((seat) => seat.cloneNode(true)));
  elements.seatTopologyTitle.textContent = defaultSeatTopologyTitle;
}

function clearSeatTopology() {
  replaceSeatCards([]);
  elements.seatTopologyTitle.textContent = "Seat topology supplied at preflight.";
}

function renderPublicSeatTopology(seats) {
  const cards = seats.map((seat, index) => {
    const card = defaultSeatTemplates[index].cloneNode(true);
    const number = String(index + 1).padStart(2, "0");
    card.dataset.seat = String(index);
    card.dataset.seatId = seat.seat_id;
    card.dataset.state = "idle";
    card.querySelector(".seat-avatar").textContent = number;
    card.querySelector(".seat-copy p").textContent = `AGENT ${number}`;
    card.querySelector(".seat-copy h3").textContent = seat.alias;
    card.querySelector(".seat-role span").textContent = "ROLE ROTATES BY PHASE";
    card.querySelector(".seat-role strong").textContent = "Awaiting assignment";
    card.querySelector(".seat-state-label").textContent = "Idle";
    card.removeAttribute("aria-current");
    return card;
  });
  replaceSeatCards(cards);
  elements.seatTopologyTitle.textContent = `${cards.length} seats. Roles rotate.`;
}

function renderIdleSeats() {
  elements.seats.forEach((seat) => {
    seat.dataset.state = "idle";
    seat.removeAttribute("aria-current");
    seat.querySelector(".seat-role span").textContent = "ROLE ROTATES BY PHASE";
    seat.querySelector(".seat-role strong").textContent = "Awaiting assignment";
    seat.querySelector(".seat-state-label").textContent = "Idle";
  });
}

function renderConveningSeats(assignments) {
  elements.seats.forEach((seat, index) => {
    const assignment = assignments[index];
    seat.dataset.state = "ready";
    seat.removeAttribute("aria-current");
    seat.querySelector(".seat-role span").textContent = "TEMPORARY CED ROLE";
    seat.querySelector(".seat-role strong").textContent = assignment.role;
    seat.querySelector(".seat-state-label").textContent = "Ready";
  });
}

function renderSeats(assignments) {
  elements.seats.forEach((seat, index) => {
    const assignment = assignments[index];
    seat.dataset.state = assignment.state;
    if (assignment.state === "active") {
      seat.setAttribute("aria-current", "true");
    } else {
      seat.removeAttribute("aria-current");
    }
    seat.querySelector(".seat-role span").textContent = "TEMPORARY CED ROLE";
    seat.querySelector(".seat-role strong").textContent = assignment.role;
    seat.querySelector(".seat-state-label").textContent = assignment.status
      || assignment.state.charAt(0).toUpperCase() + assignment.state.slice(1);
  });
}

function renderTimeline(activeIndex, isComplete = false) {
  elements.phaseItems.forEach((item, index) => {
    let phaseState = "upcoming";
    if (isComplete || index < activeIndex) {
      phaseState = "complete";
    } else if (index === activeIndex) {
      phaseState = "active";
    }
    item.dataset.state = phaseState;
    item.querySelector("em").textContent =
      phaseState === "active" ? "Active" : phaseState === "complete" ? "Complete" : "Upcoming";
    if (phaseState === "active") {
      item.setAttribute("aria-current", "step");
    } else {
      item.removeAttribute("aria-current");
    }
  });

  const completedPhases = isComplete ? DEMO_FIXTURES.phases.length : Math.max(activeIndex + 1, 0);
  elements.phaseCount.textContent = String(completedPhases).padStart(2, "0");
  elements.phaseProgress.setAttribute("aria-valuenow", String(completedPhases));
  elements.phaseProgress.setAttribute(
    "aria-valuetext",
    isComplete
      ? "All 7 council phases complete"
      : activeIndex >= 0
        ? `Phase ${activeIndex + 1} of 7: ${DEMO_FIXTURES.phases[activeIndex].name}`
        : "Council not yet started",
  );
  elements.progressFill.style.width = `${(completedPhases / DEMO_FIXTURES.phases.length) * 100}%`;
}

function setPhaseBrief(phase, phaseIndex) {
  elements.phaseBrief.querySelector("span").textContent =
    `PHASE ${String(phaseIndex + 1).padStart(2, "0")} · ${phase.name.toUpperCase()}`;
  elements.phaseBrief.querySelector("h4").textContent = phase.briefTitle;
  elements.phaseBrief.querySelector("p").textContent = phase.brief;
}

function buildConfidence(move) {
  return createElement("span", "confidence", `Confidence · ${move.confidence}`);
}

function buildMoveCard(move, { isNew = false } = {}) {
  const card = createElement(
    "article",
    isNew ? "contribution-card is-new" : "contribution-card",
  );
  card.setAttribute("role", "listitem");
  card.dataset.moveId = move.id;

  const mark = createElement("div", "move-mark", move.mark);
  mark.setAttribute("aria-hidden", "true");

  const body = createElement("div", "move-body");
  const meta = createElement("div", "move-meta");
  meta.append(createElement("strong", "", move.role));
  meta.append(createElement("span", "", `Agent · ${move.agent}`));
  meta.append(createElement("span", "", move.phase));
  meta.append(createElement("span", "", `Status · ${move.status}`));

  const content = createElement("p", "move-content", move.content);
  const footer = createElement("footer", "move-footer");
  footer.append(createElement("span", "", "Public council contribution"));
  footer.append(buildConfidence(move));
  body.append(meta, content, footer);
  card.append(mark, body);
  if (isNew) {
    card.addEventListener(
      "animationend",
      () => card.classList.remove("is-new"),
      { once: true },
    );
  }
  return card;
}

function syncContributionDisclosure() {
  const cards = Array.from(elements.contributionList.children);
  const hiddenCount = Math.max(0, cards.length - runState.visibleContributionLimit);
  const latestIndex = cards.length - 1;

  cards.forEach((card, index) => {
    card.hidden = !runState.recordExpanded && index < hiddenCount;
    card.classList.toggle("is-latest", index === latestIndex);
    card.classList.toggle("is-prior", index < latestIndex);
  });

  elements.feedEmpty.hidden = cards.length > 0;
  elements.recordToggle.hidden = hiddenCount === 0;
  elements.recordToggle.setAttribute("aria-expanded", String(runState.recordExpanded));
  elements.recordToggle.textContent = runState.recordExpanded
    ? "Show latest contributions"
    : `Show complete public record (${cards.length})`;
  elements.recordSummary.textContent =
    cards.length === 0
      ? "Showing 0 contributions"
      : runState.recordExpanded || hiddenCount === 0
        ? `Showing all ${cards.length} ${cards.length === 1 ? "contribution" : "contributions"}`
        : `Showing latest ${runState.visibleContributionLimit} of ${cards.length} contributions`;
}

function renderPhaseMoves(phase, { animate = true, sync = true } = {}) {
  phase.moves.forEach((move) => {
    if (runState.renderedMoveIds.has(move.id)) {
      return;
    }
    runState.renderedMoveIds.add(move.id);
    elements.contributionList.append(buildMoveCard(move, { isNew: animate }));
  });
  if (sync) {
    syncContributionDisclosure();
  }
}

function renderAllMoves() {
  DEMO_FIXTURES.phases.forEach((phase) => {
    renderPhaseMoves(phase, { animate: false, sync: false });
  });
  syncContributionDisclosure();
}

function clearRenderedRun() {
  elements.contributionList.replaceChildren();
  runState.renderedMoveIds.clear();
  runState.recordExpanded = false;
  syncContributionDisclosure();
  elements.finalSynthesis.hidden = true;
}

function setPhase(phaseIndex, { includeMoves = true } = {}) {
  if (runState.mode !== "running") {
    return;
  }
  runState.phaseIndex = phaseIndex;
  const phase = DEMO_FIXTURES.phases[phaseIndex];
  renderTimeline(phaseIndex);
  renderSeats(phase.assignments);
  setPhaseBrief(phase, phaseIndex);
  if (includeMoves) {
    renderPhaseMoves(phase);
  }
  setRunStatus(
    `PHASE ${String(phaseIndex + 1).padStart(2, "0")} OF 07 · ${phase.name.toUpperCase()}`,
  );
}

function finishDemo({ focusSynthesis = false } = {}) {
  invalidateRun();
  runState.mode = "complete";
  runState.stage = "complete";
  runState.phaseIndex = DEMO_FIXTURES.phases.length - 1;
  renderAllMoves();
  renderTimeline(runState.phaseIndex, true);
  renderSeats(DEMO_FIXTURES.completionAssignments);
  elements.seats.forEach((seat, index) => {
    const finalRole = DEMO_FIXTURES.completionAssignments[index].role;
    seat.dataset.state = "complete";
    seat.removeAttribute("aria-current");
    seat.querySelector(".seat-role span").textContent = `LAST ROLE · ${finalRole.toUpperCase()}`;
    seat.querySelector(".seat-role strong").textContent = "SESSION COMPLETE";
    seat.querySelector(".seat-state-label").textContent = "Complete";
  });
  elements.phaseBrief.querySelector("span").textContent = "COUNCIL COMPLETE";
  elements.phaseBrief.querySelector("h4").textContent = "Synthesis released with caveat";
  elements.phaseBrief.querySelector("p").textContent =
    "The public record preserves the conclusion, qualification and remaining uncertainty separately.";
  elements.finalSynthesis.hidden = false;
  setRunStatus("COUNCIL COMPLETE · FINAL SYNTHESIS AVAILABLE");
  setControlState();

  if (focusSynthesis) {
    elements.synthesisTitle.focus({ preventScroll: true });
    elements.finalSynthesis.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "start",
    });
  }
}

function scheduleRunStep(delay, generation, callback) {
  const timerId = window.setTimeout(() => {
    if (generation !== runState.generation || runState.mode !== "running") {
      return;
    }
    callback();
  }, delay);
  runState.timerIds.push(timerId);
}

function scheduleNextPhase(phaseIndex, generation) {
  const timerId = window.setTimeout(() => {
    if (generation !== runState.generation || runState.mode !== "running") {
      return;
    }
    if (phaseIndex < DEMO_FIXTURES.phases.length - 1) {
      const nextPhase = phaseIndex + 1;
      setPhase(nextPhase);
      scheduleNextPhase(nextPhase, generation);
      return;
    }
    finishDemo({ focusSynthesis: true });
  }, phaseDuration);
  runState.timerIds.push(timerId);
}

function startDemo(question) {
  invalidateRun();
  clearRenderedRun();
  runState.mode = "running";
  runState.stage = "accepted";
  runState.phaseIndex = -1;
  elements.activeQuestion.textContent = question;
  elements.commitments.open = false;
  renderIdleSeats();
  renderTimeline(-1);
  elements.phaseBrief.querySelector("span").textContent = "QUESTION ACCEPTED";
  elements.phaseBrief.querySelector("h4").textContent = "Convening the council";
  elements.phaseBrief.querySelector("p").textContent =
    "Stable seats are activating before the first temporary roles and public move are revealed.";
  setRunStatus("QUESTION ACCEPTED · CONVENING COUNCIL");
  setControlState();
  const generation = runState.generation;
  elements.council.scrollIntoView({
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    block: "start",
  });
  elements.phaseBrief.focus({ preventScroll: true });

  const activateSeats = () => {
    runState.stage = "seats";
    renderConveningSeats(DEMO_FIXTURES.phases[0].assignments);
    setControlState();
  };
  const activateOpening = () => {
    runState.stage = "phase";
    setPhase(0, { includeMoves: false });
    setControlState();
  };
  const publishFirstMove = () => {
    runState.stage = "deliberating";
    renderPhaseMoves(DEMO_FIXTURES.phases[0]);
    setControlState();
    scheduleNextPhase(0, generation);
  };

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    activateSeats();
    activateOpening();
    publishFirstMove();
    return;
  }

  scheduleRunStep(openingTransitionDelays.seats, generation, activateSeats);
  scheduleRunStep(openingTransitionDelays.phase, generation, activateOpening);
  scheduleRunStep(openingTransitionDelays.firstMove, generation, publishFirstMove);
}

function resetDemo({ focusQuestion = true } = {}) {
  invalidateRun();
  runState.mode = "idle";
  runState.stage = "idle";
  runState.phaseIndex = -1;
  clearRenderedRun();
  renderIdleSeats();
  renderTimeline(-1);
  elements.activeQuestion.textContent = "Waiting for a question.";
  elements.phaseBrief.querySelector("span").textContent = "NOT YET STARTED";
  elements.phaseBrief.querySelector("h4").textContent = "Council standing by";
  elements.phaseBrief.querySelector("p").textContent =
    "The process begins by identifying the assumption on which the question turns.";
  elements.commitments.open = false;
  setQuestionError(false);
  setRunStatus("READY TO CONVENE · QUESTION RETAINED");
  setControlState();
  if (focusQuestion) {
    elements.questionInput.focus();
  }
}

elements.exampleButton.addEventListener("click", () => {
  elements.questionInput.value = DEMO_FIXTURES.question;
  setQuestionError(false);
  elements.questionInput.focus();
});

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (runState.mode === "running") {
    return;
  }
  const question = currentQuestion();
  if (question) {
    startDemo(question);
  }
});

elements.questionInput.addEventListener("input", () => {
  if (elements.questionInput.value.trim()) {
    setQuestionError(false);
  }
});

elements.questionInput.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    elements.form.requestSubmit();
  }
});

elements.completeButton.addEventListener("click", () => {
  if (runState.mode === "complete") {
    return;
  }
  const question = currentQuestion({ allowExampleFallback: true });
  elements.activeQuestion.textContent = question;
  if (runState.mode === "idle") {
    clearRenderedRun();
  }
  finishDemo({ focusSynthesis: true });
});

elements.recordToggle.addEventListener("click", () => {
  runState.recordExpanded = !runState.recordExpanded;
  syncContributionDisclosure();
});

elements.resetButton.addEventListener("click", () => {
  resetDemo();
});

renderIdleSeats();
renderTimeline(-1);
setControlState();

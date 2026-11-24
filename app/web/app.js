"use strict";
const question = document.getElementById("research-question");
const button = document.getElementById("research-submit");
const status = document.getElementById("research-status");
const answer = document.getElementById("research-answer");
const evidencePanel = document.getElementById("evidence-panel");
const responseTag = document.getElementById("response-tag");

fetch("/api/snapshot").then(response => {
  if (!response.ok) throw new Error("Unable to load the saved snapshot");
  return response.json();
}).then(snapshot => {
  const season = snapshot.season.replace("_", "/");
  if (snapshot.recorded_demo) {
    document.querySelector('.data-badge').textContent = 'Recorded demo';
    question.value = snapshot.example_question;
    question.readOnly = true;
    button.textContent = 'Replay saved research ↗';
    document.querySelector('.form-hint').textContent = 'Recorded example. No model call or dataset needed.';
    document.querySelector('.examples').hidden = true;
    responseTag.textContent = 'Recorded demo';
    status.textContent = 'Replay a saved answer and inspect the tool evidence. Start live mode to ask new questions.';
  }

  document.getElementById("snapshot-label").textContent = `${season} · GW${snapshot.first_gameweek}–${snapshot.last_completed_gameweek}`;
  document.getElementById("scope-note").textContent = `The saved season covers GW${snapshot.first_gameweek}–${snapshot.last_completed_gameweek}. Ask for an explicit range, the first or last gameweeks, or the whole season.`;
}).catch(error => { document.getElementById("snapshot-label").textContent = error.message; });

document.querySelectorAll("[data-example]").forEach(example => example.addEventListener("click", () => {
  question.value = example.dataset.example;
  question.focus();
}));

function renderAnswer(text) {
  answer.replaceChildren();
  for (const paragraph of text.split(/\n\s*\n/)) {
    const p = document.createElement("p");
    paragraph.split(/(\*\*[^*]+\*\*)/g).forEach(part => {
      const node = document.createElement(part.startsWith("**") && part.endsWith("**") ? "strong" : "span");
      node.textContent = node.tagName === "STRONG" ? part.slice(2, -2) : part;
      p.append(node);
    });
    answer.append(p);
  }
}

document.getElementById("research-form").addEventListener("submit", async event => {
  event.preventDefault();
  button.disabled = true;
  evidencePanel.hidden = true;
  evidencePanel.open = false;
  answer.replaceChildren();
  document.getElementById("answer-title").textContent = "Looking into your question…";
  responseTag.textContent = "Working";
  status.textContent = "The agent is checking its available evidence. This can take a few minutes.";
  try {
    const response = await fetch("/api/search", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({question:question.value})});
    if (!(response.headers.get("Content-Type") || "").includes("application/json")) throw new Error("Search unavailable. Check the local app and try again.");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Search failed");
    if (typeof result.answer !== "string") throw new Error("The agent returned an invalid response");
    document.getElementById("answer-title").textContent = "What the agent found";
    renderAnswer(result.answer);
    status.textContent = result.periods && result.periods.length ? "Data used: " + result.periods.map(([a,b]) => `GW${a}–${b}`).join(", ") + ". Prices are recorded at or before each interval end." : "Review the response and its supporting evidence.";
    responseTag.textContent = result.evidence?.recorded_demo ? "Recorded response" : "Response received";
    document.getElementById("trace-label").textContent = "Saved trace: " + result.trace;
    document.getElementById("research-evidence").textContent = JSON.stringify(result.evidence, null, 2);
    evidencePanel.hidden = false;
  } catch(error) {
    document.getElementById("answer-title").textContent = "The search could not finish";
    status.textContent = error.message;
    responseTag.textContent = "Try again";
  } finally { button.disabled = false; }
});

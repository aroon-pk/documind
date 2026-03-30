const HISTORY_LIMIT = 5;
const SOURCE_PREVIEW_LENGTH = 280;

const dom = {
  pdfFileInput: document.getElementById("pdfFile"),
  questionInput: document.getElementById("questionInput"),
  uploadButton: document.getElementById("uploadButton"),
  askButton: document.getElementById("askButton"),
  documentScope: document.getElementById("documentScope"),
  documentsCount: document.getElementById("documentsCount"),
  scopeSummary: document.getElementById("scopeSummary"),
  agentSummary: document.getElementById("agentSummary"),
  statusBanner: document.getElementById("statusBanner"),
  statusText: document.getElementById("statusText"),
  selectedFileText: document.getElementById("selectedFileText"),
  uploadedDocsList: document.getElementById("uploadedDocsList"),
  libraryCount: document.getElementById("libraryCount"),
  providerText: document.getElementById("providerText"),
  answerEmptyState: document.getElementById("answerEmptyState"),
  answerContent: document.getElementById("answerContent"),
  answerText: document.getElementById("answerText"),
  sourcesList: document.getElementById("sourcesList"),
  loader: document.getElementById("loader"),
  loaderText: document.getElementById("loaderText"),
  workflowAsk: document.getElementById("workflowAsk"),
  workflowReview: document.getElementById("workflowReview"),
  chipButtons: Array.from(document.querySelectorAll(".chip-button")),
  dropzone: document.getElementById("dropzone"),
  copyAnswerButton: document.getElementById("copyAnswerButton"),
  historyList: document.getElementById("historyList"),
  clearHistoryButton: document.getElementById("clearHistoryButton"),
  sourceModal: document.getElementById("sourceModal"),
  closeModalButton: document.getElementById("closeModalButton"),
  sourceModalFile: document.getElementById("sourceModalFile"),
  sourceModalPage: document.getElementById("sourceModalPage"),
  sourceModalText: document.getElementById("sourceModalText"),
  agentMetaText: document.getElementById("agentMetaText"),
  agentStepsList: document.getElementById("agentStepsList"),
};

const state = {
  documents: [],
  selectedScope: "",
  isLoading: false,
  questionHistory: [],
};

const api = {
  async getDocuments() {
    return requestJson("/documents");
  },
  async uploadDocument(formData) {
    return requestJson("/upload", {
      method: "POST",
      body: formData,
    });
  },
  async askQuestion(payload) {
    return requestJson("/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  },
  async deleteDocument(documentId) {
    return requestJson(`/documents/${documentId}`, {
      method: "DELETE",
    });
  },
};

function hasDocuments() {
  return state.documents.length > 0;
}

function requestJson(url, options = {}) {
  return fetch(url, options).then(async (response) => {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || "Something went wrong.");
    }
    return payload;
  });
}

function sortDocuments(documents) {
  return [...documents].sort((left, right) => left.filename.localeCompare(right.filename));
}

function syncSelectedScope(preferredScope = "") {
  if (!hasDocuments()) {
    state.selectedScope = "";
    return;
  }

  const validDocumentIds = new Set(state.documents.map((documentItem) => documentItem.document_id));

  if (preferredScope === "__all__" && state.documents.length > 1) {
    state.selectedScope = "__all__";
    return;
  }

  if (preferredScope && validDocumentIds.has(preferredScope)) {
    state.selectedScope = preferredScope;
    return;
  }

  if (state.selectedScope === "__all__" && state.documents.length > 1) {
    return;
  }

  if (validDocumentIds.has(state.selectedScope)) {
    return;
  }

  state.selectedScope = state.documents.length > 1 ? "__all__" : state.documents[0].document_id;
}

function getSelectedDocument() {
  if (!hasDocuments() || state.selectedScope === "__all__") {
    return null;
  }

  return state.documents.find((documentItem) => documentItem.document_id === state.selectedScope) || null;
}

function getScopeLabel() {
  if (!hasDocuments()) {
    return "No scope yet";
  }

  if (state.selectedScope === "__all__") {
    return `All ${state.documents.length} PDFs`;
  }

  return getSelectedDocument()?.filename || "Selected PDF";
}

function getQuestionScopeLabel() {
  if (!hasDocuments()) {
    return "No scope";
  }

  if (state.selectedScope === "__all__") {
    return `All PDFs (${state.documents.length})`;
  }

  return getSelectedDocument()?.filename || "Selected PDF";
}

function setStatus(type, message) {
  dom.statusBanner.className = `status-banner ${type}`;
  dom.statusText.textContent = message;
}

function setLoading(isLoading, message = "Working on your request...") {
  state.isLoading = isLoading;
  dom.loader.classList.toggle("hidden", !isLoading);
  dom.loaderText.textContent = message;
  renderControls();
  renderLibrary();
}

function markWorkflow(card, isComplete) {
  card.classList.toggle("is-complete", isComplete);
}

function renderSummary() {
  dom.documentsCount.textContent = String(state.documents.length);
  dom.scopeSummary.textContent = getScopeLabel();
  dom.libraryCount.textContent = `${state.documents.length} document${state.documents.length === 1 ? "" : "s"}`;
}

function renderScopeOptions() {
  dom.documentScope.replaceChildren();

  if (!hasDocuments()) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Upload a PDF first";
    dom.documentScope.appendChild(option);
    return;
  }

  if (state.documents.length > 1) {
    const allOption = document.createElement("option");
    allOption.value = "__all__";
    allOption.textContent = `Search across all indexed PDFs (${state.documents.length})`;
    dom.documentScope.appendChild(allOption);
  }

  sortDocuments(state.documents).forEach((documentItem) => {
    const option = document.createElement("option");
    option.value = documentItem.document_id;
    option.textContent = `${documentItem.filename} - ${documentItem.page_label}`;
    dom.documentScope.appendChild(option);
  });

  dom.documentScope.value = state.selectedScope;
}

function createDeleteButton(documentItem) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "library-card__delete";
  button.textContent = "Delete";
  button.dataset.documentId = documentItem.document_id;
  button.dataset.filename = documentItem.filename;
  button.disabled = state.isLoading;
  return button;
}

function renderLibrary() {
  dom.uploadedDocsList.replaceChildren();

  if (!hasDocuments()) {
    const emptyState = document.createElement("p");
    emptyState.className = "library-empty";
    emptyState.textContent = "No PDFs indexed yet. Upload a document to create your searchable library.";
    dom.uploadedDocsList.appendChild(emptyState);
    return;
  }

  sortDocuments(state.documents).forEach((documentItem) => {
    const card = document.createElement("article");
    const top = document.createElement("div");
    const title = document.createElement("h3");
    const actions = document.createElement("div");
    const badge = document.createElement("span");
    const meta = document.createElement("p");

    card.className = "library-card";
    if (state.selectedScope !== "__all__" && state.selectedScope === documentItem.document_id) {
      card.classList.add("is-active");
    }

    top.className = "library-card__top";
    title.className = "library-card__title";
    actions.className = "library-card__actions";
    badge.className = "library-card__badge";
    meta.className = "library-card__meta";

    title.textContent = documentItem.filename;
    badge.textContent = documentItem.page_label;
    meta.textContent = `${documentItem.chunk_count} chunks indexed`;

    actions.appendChild(badge);
    actions.appendChild(createDeleteButton(documentItem));
    top.appendChild(title);
    top.appendChild(actions);
    card.appendChild(top);
    card.appendChild(meta);
    dom.uploadedDocsList.appendChild(card);
  });
}

function renderControls() {
  const shouldDisableInputs = state.isLoading || !hasDocuments();
  const shouldDisableUpload = state.isLoading;

  dom.uploadButton.disabled = shouldDisableUpload;
  dom.pdfFileInput.disabled = shouldDisableUpload;
  dom.documentScope.disabled = shouldDisableInputs;
  dom.questionInput.disabled = shouldDisableInputs;
  dom.askButton.disabled = shouldDisableInputs;
  dom.copyAnswerButton.disabled = !dom.answerText.textContent || state.isLoading;
  dom.clearHistoryButton.disabled = state.questionHistory.length === 0;

  dom.chipButtons.forEach((button) => {
    button.disabled = shouldDisableInputs;
  });
}

function renderAgentEmpty() {
  dom.agentSummary.textContent = "Planner inactive";
  dom.agentMetaText.textContent = "The planner steps will appear here.";
  dom.agentStepsList.replaceChildren();
}

function renderEmptyAnswer() {
  dom.answerText.textContent = "";
  dom.providerText.textContent = hasDocuments()
    ? "Ask a question to generate a cited answer from the indexed documents."
    : "Upload a PDF and ask a question to see the answer here.";
  dom.answerEmptyState.classList.remove("hidden");
  dom.answerContent.classList.add("hidden");
  dom.sourcesList.replaceChildren();
  renderAgentEmpty();
  markWorkflow(dom.workflowReview, false);
  renderControls();
}

function buildConfidenceLabel(distance) {
  if (typeof distance !== "number") {
    return "Relevant match";
  }
  if (distance <= 0.25) {
    return "High match";
  }
  if (distance <= 0.5) {
    return "Good match";
  }
  return "Possible match";
}

function truncateText(text, maxLength = SOURCE_PREVIEW_LENGTH) {
  if (text.length <= maxLength) {
    return { preview: text, truncated: false };
  }

  const sliced = text.slice(0, maxLength);
  const lastSpace = sliced.lastIndexOf(" ");
  const preview = lastSpace > 120 ? sliced.slice(0, lastSpace) : sliced;
  return { preview: `${preview}...`, truncated: true };
}

function openSourceModal(source) {
  dom.sourceModalFile.textContent = source.filename;
  dom.sourceModalPage.textContent = source.page_label;
  dom.sourceModalText.textContent = source.text;
  dom.sourceModal.classList.remove("hidden");
  dom.sourceModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeSourceModal() {
  dom.sourceModal.classList.add("hidden");
  dom.sourceModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
}

function renderSources(sources) {
  dom.sourcesList.replaceChildren();

  sources.forEach((source) => {
    const card = document.createElement("article");
    const top = document.createElement("div");
    const heading = document.createElement("strong");
    const file = document.createElement("span");
    const meta = document.createElement("div");
    const pagePill = document.createElement("span");
    const chunkPill = document.createElement("span");
    const confidencePill = document.createElement("span");
    const text = document.createElement("p");
    const actions = document.createElement("div");
    const readMoreButton = document.createElement("button");
    const preview = truncateText(source.text);

    card.className = "source-card";
    top.className = "source-card__top";
    meta.className = "source-card__meta";
    pagePill.className = "source-card__pill";
    chunkPill.className = "source-card__pill";
    confidencePill.className = "source-card__confidence";
    text.className = "source-card__text";
    actions.className = "source-card__actions";
    readMoreButton.className = "source-card__read-more";
    readMoreButton.type = "button";

    heading.textContent = source.source_label;
    file.textContent = source.filename;
    pagePill.textContent = source.page_label;
    chunkPill.textContent = `Chunk ${source.chunk_index + 1}`;
    confidencePill.textContent = buildConfidenceLabel(source.distance);
    text.textContent = preview.preview;
    readMoreButton.textContent = "Read more";
    readMoreButton.dataset.source = JSON.stringify(source);

    top.appendChild(heading);
    top.appendChild(file);
    meta.appendChild(pagePill);
    meta.appendChild(chunkPill);
    meta.appendChild(confidencePill);
    card.appendChild(top);
    card.appendChild(meta);
    card.appendChild(text);

    if (preview.truncated) {
      actions.appendChild(readMoreButton);
      card.appendChild(actions);
    }

    dom.sourcesList.appendChild(card);
  });
}

function renderAgentWorkflow(agent) {
  dom.agentStepsList.replaceChildren();

  if (!agent || !agent.enabled) {
    renderAgentEmpty();
    return;
  }

  dom.agentSummary.textContent = agent.strategy || "Planner active";
  dom.agentMetaText.textContent = `Intent: ${agent.intent}. Strategy: ${agent.strategy}.`;

  (agent.steps || []).forEach((item, index) => {
    const card = document.createElement("article");
    const number = document.createElement("span");
    const content = document.createElement("div");
    const title = document.createElement("p");
    const detail = document.createElement("p");

    card.className = "agent-step";
    number.className = "agent-step__number";
    title.className = "agent-step__title";
    detail.className = "agent-step__detail";

    number.textContent = String(index + 1);
    title.textContent = item.step;
    detail.textContent = item.detail;

    content.appendChild(title);
    content.appendChild(detail);
    card.appendChild(number);
    card.appendChild(content);
    dom.agentStepsList.appendChild(card);
  });
}

function saveHistory() {
  window.localStorage.setItem("documind-lite-history", JSON.stringify(state.questionHistory));
}

function loadHistory() {
  try {
    const rawHistory = window.localStorage.getItem("documind-lite-history");
    state.questionHistory = rawHistory ? JSON.parse(rawHistory) : [];
  } catch {
    state.questionHistory = [];
  }
}

function renderHistory() {
  dom.historyList.replaceChildren();

  if (state.questionHistory.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "history-empty";
    emptyState.textContent = "No questions asked yet.";
    dom.historyList.appendChild(emptyState);
    renderControls();
    return;
  }

  state.questionHistory.forEach((entry, index) => {
    const card = document.createElement("article");
    const top = document.createElement("div");
    const question = document.createElement("p");
    const scope = document.createElement("span");
    const answer = document.createElement("p");
    const footer = document.createElement("div");
    const time = document.createElement("span");
    const reuse = document.createElement("button");

    card.className = "history-card";
    top.className = "history-card__top";
    question.className = "history-card__question";
    scope.className = "history-card__scope";
    answer.className = "history-card__answer";
    footer.className = "history-card__footer";
    time.className = "history-card__time";
    reuse.className = "history-card__reuse";
    reuse.type = "button";
    reuse.dataset.historyIndex = String(index);

    question.textContent = entry.question;
    scope.textContent = entry.scope;
    answer.textContent = entry.answer;
    time.textContent = entry.time;
    reuse.textContent = "Reuse question";

    top.appendChild(question);
    top.appendChild(scope);
    footer.appendChild(time);
    footer.appendChild(reuse);
    card.appendChild(top);
    card.appendChild(answer);
    card.appendChild(footer);
    dom.historyList.appendChild(card);
  });

  renderControls();
}

function addHistoryEntry(question, answer, scope) {
  const preview = answer.length > 180 ? `${answer.slice(0, 180)}...` : answer;
  const timestamp = new Date().toLocaleString();

  state.questionHistory = [
    {
      question,
      answer: preview,
      scope,
      time: timestamp,
    },
    ...state.questionHistory,
  ].slice(0, HISTORY_LIMIT);

  saveHistory();
  renderHistory();
}

function renderAnswer(result, question) {
  dom.providerText.textContent = `Generated with ${result.provider}. Evidence came from ${result.documents_used.join(", ")}.`;
  dom.answerText.textContent = result.answer;
  dom.answerEmptyState.classList.add("hidden");
  dom.answerContent.classList.remove("hidden");
  renderAgentWorkflow(result.agent);
  renderSources(result.sources || []);
  markWorkflow(dom.workflowReview, true);
  addHistoryEntry(question, result.answer, getQuestionScopeLabel());
  renderControls();
}

function renderAll() {
  renderSummary();
  renderScopeOptions();
  renderLibrary();
  renderControls();
  renderHistory();
}

async function refreshDocuments(preferredScope = "") {
  const payload = await api.getDocuments();
  state.documents = payload.documents || [];
  syncSelectedScope(preferredScope);
  renderAll();

  if (hasDocuments()) {
    setStatus("success", "Knowledge base ready. Choose a search scope and ask a question.");
    markWorkflow(dom.workflowAsk, true);
  } else {
    markWorkflow(dom.workflowAsk, false);
    renderEmptyAnswer();
  }
}

function assignSelectedFile(file) {
  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(file);
  dom.pdfFileInput.files = dataTransfer.files;
  handleFileSelection();
}

async function handleUpload() {
  const selectedFile = dom.pdfFileInput.files[0];
  if (!selectedFile) {
    setStatus("error", "Choose a PDF file before uploading.");
    return;
  }

  if (selectedFile.type && selectedFile.type !== "application/pdf") {
    setStatus("error", "Only PDF files are supported.");
    return;
  }

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    setLoading(true, "Uploading the PDF and creating embeddings...");
    setStatus("info", "Indexing your document. This may take a moment for larger PDFs.");

    const uploadResult = await api.uploadDocument(formData);
    await refreshDocuments(uploadResult.document_id);
    dom.selectedFileText.textContent = `Last uploaded: ${uploadResult.filename} - ${uploadResult.page_range || `${uploadResult.pages_extracted} pages`}.`;
    dom.questionInput.focus();
  } catch (error) {
    setStatus("error", error.message);
  } finally {
    setLoading(false);
  }
}

async function handleQuestion() {
  if (!hasDocuments()) {
    setStatus("error", "Upload at least one PDF before asking a question.");
    return;
  }

  const question = dom.questionInput.value.trim();
  if (!question) {
    setStatus("error", "Type a meaningful question before generating an answer.");
    return;
  }

  const isAllScope = state.selectedScope === "__all__";
  const scopeLabel = isAllScope
    ? `all ${state.documents.length} indexed PDFs`
    : getSelectedDocument()?.filename || "the selected PDF";

  try {
    setLoading(true, "Planner is selecting a strategy and retrieving evidence...");
    setStatus("info", `Running the agent over ${scopeLabel}.`);

    const result = await api.askQuestion({
      question,
      document_id: isAllScope ? null : state.selectedScope,
    });

    renderAnswer(result, question);
    setStatus("success", "Answer ready. Review the agent steps, citations, and supporting chunks.");
  } catch (error) {
    setStatus("error", error.message);
    renderEmptyAnswer();
  } finally {
    setLoading(false);
  }
}

async function handleDeleteClick(event) {
  const deleteButton = event.target.closest(".library-card__delete");
  if (!deleteButton || state.isLoading) {
    return;
  }

  const { documentId, filename } = deleteButton.dataset;
  const confirmed = window.confirm(`Delete "${filename}" from the knowledge base?`);
  if (!confirmed) {
    return;
  }

  const wasSelected = state.selectedScope === documentId;

  try {
    setLoading(true, `Deleting ${filename} from the knowledge base...`);
    setStatus("info", `Removing ${filename} and its indexed chunks.`);

    const result = await api.deleteDocument(documentId);
    const nextScope = wasSelected ? "__all__" : state.selectedScope;
    await refreshDocuments(nextScope);
    setStatus("success", `${result.filename} deleted successfully.`);
  } catch (error) {
    setStatus("error", error.message);
  } finally {
    setLoading(false);
  }
}

function handleScopeChange(event) {
  state.selectedScope = event.target.value;
  renderSummary();
  renderLibrary();
}

function handleFileSelection() {
  const selectedFile = dom.pdfFileInput.files[0];
  dom.selectedFileText.textContent = selectedFile
    ? `Ready to upload: ${selectedFile.name}`
    : "No file selected yet.";
}

function handleChipClick(event) {
  if (event.currentTarget.disabled) {
    return;
  }

  dom.questionInput.value = event.currentTarget.dataset.question;
  dom.questionInput.focus();
}

function handleDropzoneKeydown(event) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    dom.pdfFileInput.click();
  }
}

function handleDropzoneDrag(event) {
  event.preventDefault();
  dom.dropzone.classList.add("is-dragover");
}

function handleDropzoneLeave(event) {
  event.preventDefault();
  dom.dropzone.classList.remove("is-dragover");
}

function handleDropzoneDrop(event) {
  event.preventDefault();
  dom.dropzone.classList.remove("is-dragover");

  const [file] = Array.from(event.dataTransfer.files || []);
  if (!file) {
    return;
  }

  if (file.type && file.type !== "application/pdf") {
    setStatus("error", "Only PDF files can be dropped here.");
    return;
  }

  assignSelectedFile(file);
}

async function handleCopyAnswer() {
  const answer = dom.answerText.textContent.trim();
  if (!answer) {
    return;
  }

  try {
    await navigator.clipboard.writeText(answer);
    setStatus("success", "Answer copied to clipboard.");
  } catch {
    setStatus("error", "Could not copy the answer automatically.");
  }
}

function handleHistoryClick(event) {
  const reuseButton = event.target.closest(".history-card__reuse");
  if (!reuseButton) {
    return;
  }

  const historyIndex = Number(reuseButton.dataset.historyIndex);
  const entry = state.questionHistory[historyIndex];
  if (!entry) {
    return;
  }

  dom.questionInput.value = entry.question;
  dom.questionInput.focus();
  setStatus("info", "Previous question restored. You can ask it again or edit it first.");
}

function handleClearHistory() {
  state.questionHistory = [];
  saveHistory();
  renderHistory();
  setStatus("success", "Recent question history cleared.");
}

function handleQuestionShortcut(event) {
  if (event.key === "Enter" && event.ctrlKey && !dom.askButton.disabled) {
    event.preventDefault();
    handleQuestion();
  }
}

function handleSourceActionClick(event) {
  const readMoreButton = event.target.closest(".source-card__read-more");
  if (!readMoreButton) {
    return;
  }

  const source = JSON.parse(readMoreButton.dataset.source);
  openSourceModal(source);
}

function handleModalClick(event) {
  if (event.target.dataset.closeModal === "true") {
    closeSourceModal();
  }
}

function handleGlobalKeydown(event) {
  if (event.key === "Escape" && !dom.sourceModal.classList.contains("hidden")) {
    closeSourceModal();
  }
}

async function bootstrap() {
  loadHistory();
  renderAll();
  renderEmptyAnswer();

  try {
    await refreshDocuments();
    if (!hasDocuments()) {
      setStatus("info", "No PDFs loaded yet. Upload your first document to start building the knowledge base.");
    }
  } catch (error) {
    setStatus("error", error.message);
  }
}

dom.pdfFileInput.addEventListener("change", handleFileSelection);
dom.uploadButton.addEventListener("click", handleUpload);
dom.askButton.addEventListener("click", handleQuestion);
dom.documentScope.addEventListener("change", handleScopeChange);
dom.uploadedDocsList.addEventListener("click", handleDeleteClick);
dom.dropzone.addEventListener("keydown", handleDropzoneKeydown);
dom.dropzone.addEventListener("dragenter", handleDropzoneDrag);
dom.dropzone.addEventListener("dragover", handleDropzoneDrag);
dom.dropzone.addEventListener("dragleave", handleDropzoneLeave);
dom.dropzone.addEventListener("drop", handleDropzoneDrop);
dom.copyAnswerButton.addEventListener("click", handleCopyAnswer);
dom.historyList.addEventListener("click", handleHistoryClick);
dom.clearHistoryButton.addEventListener("click", handleClearHistory);
dom.questionInput.addEventListener("keydown", handleQuestionShortcut);
dom.sourcesList.addEventListener("click", handleSourceActionClick);
dom.sourceModal.addEventListener("click", handleModalClick);
dom.closeModalButton.addEventListener("click", closeSourceModal);
document.addEventListener("keydown", handleGlobalKeydown);
dom.chipButtons.forEach((button) => {
  button.addEventListener("click", handleChipClick);
});

bootstrap();

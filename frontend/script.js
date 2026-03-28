const pdfFileInput = document.getElementById("pdfFile");
const questionInput = document.getElementById("questionInput");
const uploadButton = document.getElementById("uploadButton");
const askButton = document.getElementById("askButton");
const uploadStatus = document.getElementById("uploadStatus");
const errorMessage = document.getElementById("errorMessage");
const loader = document.getElementById("loader");
const responsePanel = document.getElementById("responsePanel");
const answerText = document.getElementById("answerText");
const providerText = document.getElementById("providerText");
const sourcesList = document.getElementById("sourcesList");

let activeDocumentId = null;

function setLoading(isLoading) {
  loader.classList.toggle("hidden", !isLoading);
  uploadButton.disabled = isLoading;
  askButton.disabled = isLoading;
}

function clearMessages() {
  uploadStatus.textContent = "";
  errorMessage.textContent = "";
}

function renderSources(sources) {
  sourcesList.innerHTML = "";

  sources.forEach((source, index) => {
    const card = document.createElement("article");
    const heading = document.createElement("h4");
    const text = document.createElement("p");

    card.className = "source-card";
    heading.textContent = `Chunk ${index + 1} - ${source.filename}`;
    text.textContent = source.text;

    card.appendChild(heading);
    card.appendChild(text);
    sourcesList.appendChild(card);
  });
}

uploadButton.addEventListener("click", async () => {
  clearMessages();
  responsePanel.classList.add("hidden");

  const file = pdfFileInput.files[0];
  if (!file) {
    errorMessage.textContent = "Please choose a PDF file first.";
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  try {
    setLoading(true);
    const response = await fetch("/upload", {
      method: "POST",
      body: formData,
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Upload failed.");
    }

    activeDocumentId = payload.document_id;
    uploadStatus.textContent = `${payload.filename} uploaded. Indexed ${payload.chunks_indexed} chunks.`;
  } catch (error) {
    errorMessage.textContent = error.message;
  } finally {
    setLoading(false);
  }
});

askButton.addEventListener("click", async () => {
  clearMessages();
  responsePanel.classList.add("hidden");

  const question = questionInput.value.trim();
  if (!question) {
    errorMessage.textContent = "Please enter a question.";
    return;
  }

  try {
    setLoading(true);
    const response = await fetch("/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        document_id: activeDocumentId,
      }),
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Question failed.");
    }

    answerText.textContent = payload.answer;
    providerText.textContent = `Answered with ${payload.provider}`;
    renderSources(payload.sources || []);
    responsePanel.classList.remove("hidden");
  } catch (error) {
    errorMessage.textContent = error.message;
  } finally {
    setLoading(false);
  }
});

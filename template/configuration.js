import {
  buildDomain,
  buildGeneratedConfig,
  buildTemplateConfig,
  createDownloadName,
  normalizeDomainPrefix,
  validateConfigInput,
} from "./yealink_cfg_logic.js";

const form = document.querySelector("[data-config-form]");
const preview = document.querySelector("#cfg-preview");
const statusBox = document.querySelector("#cfg-status");
const domainInput = document.querySelector("#domain-prefix");
const domainDisplay = document.querySelector("#full-domain");
const w70bToggle = document.querySelector("#is-w70b");
const dssSection = document.querySelector("#dsskey-section");
const dssRows = document.querySelector("#dsskey-rows");
const dssToggle = document.querySelector("#toggle-dsskey");
const addDssRowButton = document.querySelector("#add-dsskey-row");
const w70bSection = document.querySelector("#w70b-section");
const w70bRows = document.querySelector("#w70b-rows");
const addW70bRowButton = document.querySelector("#add-w70b-row");
const downloadButton = document.querySelector("#download-generated");
const downloadTemplateButton = document.querySelector("#download-template");
const generateButton = document.querySelector("#generate-preview");

function setStatus(message, type = "info") {
  statusBox.textContent = message;
  statusBox.dataset.state = type;
}

function createField(labelText, inputHtml) {
  return `
    <label class="inline-field">
      <span>${labelText}</span>
      ${inputHtml}
    </label>
  `;
}

function createDssRow(values = {}) {
  const row = document.createElement("div");
  row.className = "config-row";
  row.innerHTML = `
    ${createField("Value", `<input data-dss-value type="text" inputmode="numeric" value="${values.value ?? ""}" placeholder="201">`)}
    ${createField("Label", `<input data-dss-label type="text" value="${values.label ?? ""}" placeholder="201">`)}
    ${createField("Line", `
      <select data-dss-line>
        ${Array.from({ length: 10 }, (_, index) => {
          const line = String(index + 1);
          const selected = (values.line ?? "1") === line ? "selected" : "";
          return `<option value="${line}" ${selected}>Line${line}</option>`;
        }).join("")}
      </select>
    `)}
    ${createField("Extension", `<input data-dss-extension type="text" value="${values.extension ?? "**"}" placeholder="**">`)}
    <button class="row-remove" type="button" data-remove-row>Remove</button>
  `;
  return row;
}

function createW70bRow(values = {}) {
  const row = document.createElement("div");
  row.className = "config-row";
  row.innerHTML = `
    ${createField("Extension", `<input data-w70b-extension type="text" inputmode="numeric" value="${values.extension ?? ""}" placeholder="201">`)}
    ${createField("Password", `<input data-w70b-password type="text" value="${values.password ?? ""}" placeholder="Use main password if empty">`)}
    <button class="row-remove" type="button" data-remove-row>Remove</button>
  `;
  return row;
}

function downloadTextFile(filename, content) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function getDssKeys() {
  return Array.from(dssRows.querySelectorAll(".config-row")).map((row) => ({
    value: row.querySelector("[data-dss-value]")?.value ?? "",
    label: row.querySelector("[data-dss-label]")?.value ?? "",
    line: row.querySelector("[data-dss-line]")?.value ?? "1",
    extension: row.querySelector("[data-dss-extension]")?.value ?? "**",
  }));
}

function getAdditionalAccounts() {
  return Array.from(w70bRows.querySelectorAll(".config-row")).map((row) => ({
    extension: row.querySelector("[data-w70b-extension]")?.value ?? "",
    password: row.querySelector("[data-w70b-password]")?.value ?? "",
  }));
}

function getState() {
  return {
    domainPrefix: normalizeDomainPrefix(domainInput.value),
    extension: document.querySelector("#extension")?.value ?? "",
    password: document.querySelector("#password")?.value ?? "",
    isW70B: w70bToggle.checked,
    dssKeys: getDssKeys(),
    additionalAccounts: getAdditionalAccounts(),
  };
}

function updateDomainDisplay() {
  domainDisplay.textContent = buildDomain(domainInput.value) || "1234.nimbusip.com";
}

function updateModeVisibility() {
  const isW70B = w70bToggle.checked;
  w70bSection.hidden = !isW70B;
  dssSection.hidden = isW70B || dssSection.dataset.open !== "true";
  dssToggle.disabled = isW70B;
  addDssRowButton.disabled = isW70B;
  addW70bRowButton.disabled = !isW70B;
  dssToggle.textContent = isW70B ? "Dsskey disabled for W70B" : "Dsskey";
}

function ensureInitialRows() {
  if (!dssRows.children.length) {
    dssRows.append(createDssRow());
  }
  if (!w70bRows.children.length) {
    w70bRows.append(createW70bRow());
  }
}

function renderPreview() {
  const state = getState();
  const validation = validateConfigInput(state);
  const generated = buildGeneratedConfig(state);

  if (validation.errors.length) {
    preview.textContent = "Complete the required fields to generate the cfg preview.";
    setStatus(validation.errors[0], "error");
    downloadButton.disabled = true;
    return;
  }

  preview.textContent = generated.content;
  setStatus(
    state.isW70B
      ? "W70B cfg is ready. Extra account passwords default to the main password when left empty."
      : "CFG preview is ready. Dsskey rows start from LineKey.2.",
    "success",
  );
  downloadButton.disabled = false;
}

function handleRowRemoval(event) {
  const button = event.target.closest("[data-remove-row]");
  if (!button) return;
  button.closest(".config-row")?.remove();
  renderPreview();
}

function handleDssToggle() {
  dssSection.dataset.open = dssSection.dataset.open === "true" ? "false" : "true";
  dssSection.hidden = dssSection.dataset.open !== "true" || w70bToggle.checked;
  if (dssSection.dataset.open === "true" && !dssRows.children.length) {
    dssRows.append(createDssRow());
  }
}

function sanitizeDomainInput() {
  const cleaned = domainInput.value.replace(/\D+/g, "");
  if (cleaned !== domainInput.value) {
    domainInput.value = cleaned;
    setStatus("Domain accepts numbers only.", "info");
  }
  updateDomainDisplay();
}

function attachEvents() {
  form.addEventListener("input", (event) => {
    if (event.target === domainInput) {
      sanitizeDomainInput();
    }
    renderPreview();
  });

  form.addEventListener("change", () => {
    updateModeVisibility();
    renderPreview();
  });

  dssToggle.addEventListener("click", () => {
    handleDssToggle();
    renderPreview();
  });

  addDssRowButton.addEventListener("click", () => {
    dssRows.append(createDssRow());
    dssSection.dataset.open = "true";
    dssSection.hidden = false;
    renderPreview();
  });

  addW70bRowButton.addEventListener("click", () => {
    w70bRows.append(createW70bRow());
    renderPreview();
  });

  dssRows.addEventListener("click", handleRowRemoval);
  w70bRows.addEventListener("click", handleRowRemoval);

  generateButton.addEventListener("click", () => {
    renderPreview();
    preview.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  downloadButton.addEventListener("click", () => {
    const state = getState();
    const generated = buildGeneratedConfig(state);
    if (generated.errors.length) {
      setStatus(generated.errors[0], "error");
      downloadButton.disabled = true;
      return;
    }
    downloadTextFile(createDownloadName(state), generated.content);
    setStatus("Generated cfg downloaded.", "success");
  });

  downloadTemplateButton.addEventListener("click", () => {
    downloadTextFile("yealink-static-template.cfg", buildTemplateConfig());
    setStatus("Static cfg template downloaded.", "success");
  });
}

ensureInitialRows();
updateDomainDisplay();
updateModeVisibility();
attachEvents();
renderPreview();

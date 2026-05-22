const DEFAULT_MODEL = "google/gemini-3.5-flash";
const CUSTOM_MODEL = "__custom__";

const state = {
  generatedPrompt: "",
  apiKeyConfigured: false,
  modelPresets: [],
};

const els = {
  mode: document.querySelector("#mode"),
  targetPath: document.querySelector("#targetPath"),
  projectName: document.querySelector("#projectName"),
  rawIdea: document.querySelector("#rawIdea"),
  browseButton: document.querySelector("#browseButton"),
  settingsButton: document.querySelector("#settingsButton"),
  settingsPanel: document.querySelector("#settingsPanel"),
  closeSettingsButton: document.querySelector("#closeSettingsButton"),
  settingsSummary: document.querySelector("#settingsSummary"),
  apiKey: document.querySelector("#apiKey"),
  model: document.querySelector("#model"),
  customModel: document.querySelector("#customModel"),
  customModelRow: document.querySelector("#customModelRow"),
  overwrite: document.querySelector("#overwrite"),
  overwriteRow: document.querySelector("#overwriteRow"),
  saveConfigButton: document.querySelector("#saveConfigButton"),
  primaryActionButton: document.querySelector("#primaryActionButton"),
  newProjectFields: document.querySelector("#newProjectFields"),
  resultTitle: document.querySelector("#resultTitle"),
  result: document.querySelector("#result"),
  scoreBox: document.querySelector("#scoreBox"),
  promptTitle: document.querySelector("#promptTitle"),
  promptOutput: document.querySelector("#promptOutput"),
  copyPrompt: document.querySelector("#copyPrompt"),
};

function requestBody() {
  return {
    mode: els.mode.value,
    target_path: els.targetPath.value.trim(),
    project_name: els.projectName.value.trim() || null,
    raw_idea: els.rawIdea.value.trim() || null,
    openrouter_model: selectedModelId(),
    overwrite: els.overwrite.checked,
  };
}

function setStatus(label, kind = "") {
  document.body.dataset.status = kind || label.toLowerCase().replaceAll(" ", "-");
}

function setResult(payload) {
  const mode = payload.mode || els.mode.value;
  const isVerify = mode === "verify_repair";
  els.result.hidden = !isVerify;
  els.scoreBox.hidden = !isVerify;
  if (!isVerify) {
    state.generatedPrompt = payload.next_prompt || "";
    els.resultTitle.textContent = "Next Agent Prompt";
    els.promptTitle.textContent = mode === "new_project" ? "Critical Validation Prompt" : "Context Fill Prompt";
    els.promptOutput.value = state.generatedPrompt;
    setStatus("Prompt ready", "ready");
    return;
  }
  els.resultTitle.textContent = "Result";
  els.result.textContent = JSON.stringify({message: payload.message, score: payload.score}, null, 2);
  const score = payload.score?.total;
  els.scoreBox.textContent = Number.isInteger(score) ? `${score}/100` : "No score";
  const useRepair = Boolean(payload.repair_prompt);
  state.generatedPrompt = useRepair ? payload.repair_prompt : "";
  els.promptTitle.textContent = useRepair ? "Repair Prompt" : "No Repair Needed";
  els.promptOutput.value = state.generatedPrompt;
  if (!useRepair) {
    els.promptOutput.value = "Context score is ready. No repair prompt is needed.";
  }
  if (payload.score) {
    setStatus(payload.score.ready ? "Ready" : "Needs repair", payload.score.ready ? "ready" : "error");
  }
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Request failed");
  }
  return payload;
}

async function getJson(url) {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Request failed");
  }
  return payload;
}

async function loadSettings() {
  try {
    const payload = await getJson("/api/config/openrouter");
    state.apiKeyConfigured = Boolean(payload.api_key_configured);
    if (payload.last_model) {
      renderModelOptions(payload.last_model);
    }
    renderSettingsSummary();
  } catch (error) {
    els.settingsSummary.textContent = error.message;
  }
}

async function loadModelPresets() {
  try {
    const payload = await getJson("/api/model-presets");
    state.modelPresets = payload.models || [];
  } catch {
    state.modelPresets = [{
      id: DEFAULT_MODEL,
      name: "Gemini 3.5 Flash",
      tier: "Default value",
      description: "Fallback default model.",
      context: "1M",
      price: "",
    }];
  }
  renderModelOptions(els.model.value || DEFAULT_MODEL);
}

function renderModelOptions(selectedModel) {
  const selected = selectedModel || DEFAULT_MODEL;
  const isPreset = state.modelPresets.some((preset) => preset.id === selected);
  els.model.replaceChildren();
  for (const preset of state.modelPresets) {
    const option = document.createElement("option");
    option.value = preset.id;
    option.textContent = `${preset.name} - ${preset.tier}`;
    option.title = `${preset.id} | ${preset.context} | ${preset.price}. ${preset.description}`;
    els.model.append(option);
  }
  const customOption = document.createElement("option");
  customOption.value = CUSTOM_MODEL;
  customOption.textContent = "Custom OpenRouter model";
  els.model.append(customOption);
  if (selected && !isPreset) {
    els.customModel.value = selected;
  }
  els.model.value = isPreset ? selected : CUSTOM_MODEL;
  syncCustomModel(false);
}

function selectedModelId() {
  if (els.model.value !== CUSTOM_MODEL) {
    return els.model.value || DEFAULT_MODEL;
  }
  const modelId = els.customModel.value.trim();
  if (!modelId) {
    throw new Error("Enter a custom OpenRouter model ID or choose a preset.");
  }
  return modelId;
}

function syncCustomModel(shouldFocus = true) {
  const isCustom = els.model.value === CUSTOM_MODEL;
  els.customModelRow.hidden = !isCustom;
  if (isCustom && shouldFocus) {
    els.customModel.focus();
  }
}

function renderSettingsSummary() {
  const keyState = state.apiKeyConfigured ? "API key saved locally" : "API key not saved";
  const customValue = els.customModel.value.trim();
  const model = state.modelPresets.find((preset) => preset.id === els.model.value);
  const label = model
    ? `${model.name} (${model.tier})`
    : customValue
      ? `Custom (${customValue})`
      : "Custom model not set";
  els.settingsSummary.textContent = `${keyState}. Default model: ${label}.`;
}

async function saveConfig() {
  setStatus("Saving settings");
  try {
    await postJson("/api/config/openrouter", {
      openrouter_api_key: els.apiKey.value.trim() || null,
      last_model: selectedModelId(),
    });
    els.apiKey.value = "";
    await loadSettings();
    setStatus("Settings saved", "ready");
  } catch (error) {
    setStatus("Failed", "error");
    els.resultTitle.textContent = "Error";
    els.result.hidden = false;
    els.result.textContent = error.message;
  }
}

async function openNativeFolderPicker() {
  setStatus("Opening file picker");
  try {
    const payload = await postJson("/api/fs/pick-directory", {
      initial_path: els.targetPath.value.trim() || null,
    });
    if (payload.path) {
      els.targetPath.value = payload.path;
      setStatus("Folder selected", "ready");
      return;
    }
    setStatus("Idle");
  } catch (error) {
    setStatus("Failed", "error");
    els.resultTitle.textContent = "Error";
    els.result.hidden = false;
    els.result.textContent = error.message;
  }
}

async function runPrimaryAction() {
  const isVerify = els.mode.value === "verify_repair";
  const url = isVerify ? "/api/verify" : "/api/setup/apply";
  setStatus(isVerify ? "Verifying" : "Writing files");
  els.result.hidden = !isVerify;
  els.scoreBox.hidden = !isVerify;
  els.result.textContent = isVerify ? "Verifying context..." : "";
  try {
    const body = isVerify ? {target_path: els.targetPath.value.trim()} : requestBody();
    const payload = await postJson(url, body);
    setResult(payload);
  } catch (error) {
    setStatus("Failed", "error");
    els.resultTitle.textContent = "Error";
    els.result.hidden = false;
    els.scoreBox.hidden = true;
    els.result.textContent = error.message;
  }
}

function syncMode() {
  const isNew = els.mode.value === "new_project";
  const isVerify = els.mode.value === "verify_repair";
  els.newProjectFields.hidden = !isNew;
  els.overwriteRow.hidden = isVerify;
  els.resultTitle.textContent = isVerify ? "Result" : "Next Agent Prompt";
  els.result.hidden = !isVerify;
  els.scoreBox.hidden = !isVerify;
  els.promptTitle.textContent = isVerify
    ? "Repair Prompt"
    : isNew
      ? "Critical Validation Prompt"
      : "Context Fill Prompt";
  els.promptOutput.placeholder = isVerify
    ? "Run verification to generate a repair prompt when issues are found."
    : "Run setup to generate the prompt to copy into your coding agent.";
  if (isNew) {
    els.primaryActionButton.textContent = "Create Project Context";
    return;
  }
  if (isVerify) {
    els.primaryActionButton.textContent = "Verify & Repair Context";
    return;
  }
  els.primaryActionButton.textContent = "Set Up Existing Repo";
}

async function copy(text) {
  if (!text) return;
  await navigator.clipboard.writeText(text);
}

els.mode.addEventListener("change", syncMode);
els.browseButton.addEventListener("click", openNativeFolderPicker);
els.settingsButton.addEventListener("click", () => {
  els.settingsPanel.hidden = !els.settingsPanel.hidden;
});
els.closeSettingsButton.addEventListener("click", () => {
  els.settingsPanel.setAttribute("hidden", "");
});
els.saveConfigButton.addEventListener("click", saveConfig);
els.primaryActionButton.addEventListener("click", runPrimaryAction);
els.copyPrompt.addEventListener("click", () => copy(state.generatedPrompt));
els.model.addEventListener("change", () => {
  syncCustomModel(true);
  renderSettingsSummary();
});
els.customModel.addEventListener("input", renderSettingsSummary);

syncMode();
loadModelPresets().then(loadSettings);

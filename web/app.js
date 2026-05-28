const state = {
  profile: null,
  intent: null,
  result: null,
  runId: null,
  revision: null,
  manifest: null,
  plotSpec: null,
};

const PLOT_KIND_OPTIONS = ["auto", "scatter", "line", "bar", "histogram"];

const requestText = document.querySelector("#requestText");
const datasetPath = document.querySelector("#datasetPath");
const useOrigin = document.querySelector("#useOrigin");
const intakeButton = document.querySelector("#intakeButton");
const runButton = document.querySelector("#runButton");
const profileSummary = document.querySelector("#profileSummary");
const slotGrid = document.querySelector("#slotGrid");
const questions = document.querySelector("#questions");
const assumptions = document.querySelector("#assumptions");
const previewFrame = document.querySelector("#previewFrame");
const resultSummary = document.querySelector("#resultSummary");
const artifactList = document.querySelector("#artifactList");
const dataState = document.querySelector("#dataState");
const intentState = document.querySelector("#intentState");
const runState = document.querySelector("#runState");
const aiMode = document.querySelector("#aiMode");
const originMode = document.querySelector("#originMode");
const qwenKeyState = document.querySelector("#qwenKeyState");
const qwenApiKey = document.querySelector("#qwenApiKey");
const qwenModel = document.querySelector("#qwenModel");
const qwenBaseUrl = document.querySelector("#qwenBaseUrl");
const qwenThinking = document.querySelector("#qwenThinking");
const saveQwenKeyButton = document.querySelector("#saveQwenKeyButton");
const deleteQwenKeyButton = document.querySelector("#deleteQwenKeyButton");
const qwenSettings = document.querySelector(".key-panel");
const modifyPanel = document.querySelector("#modifyPanel");
const modifyText = document.querySelector("#modifyText");
const modifyButton = document.querySelector("#modifyButton");
const editPlanSummary = document.querySelector("#editPlanSummary");
const revisionList = document.querySelector("#revisionList");
const revisionState = document.querySelector("#revisionState");
const feedbackPanel = document.querySelector("#feedbackPanel");
const feedbackText = document.querySelector("#feedbackText");
const correctionText = document.querySelector("#correctionText");
const feedbackButton = document.querySelector("#feedbackButton");
const feedbackState = document.querySelector("#feedbackState");
const workflowState = document.querySelector("#workflowState");
const flowSteps = Array.from(document.querySelectorAll("[data-step]"));
const sampleButtons = Array.from(document.querySelectorAll(".sample-chip"));

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    const status = await response.json();
    const qwenSuffix = status.qwen && status.qwen.configured ? ` / ${status.qwen.model}` : "";
    aiMode.textContent = `AI: ${status.ai_mode}${qwenSuffix}`;
    originMode.textContent = status.origin_mode && status.origin_mode.includes("optional")
      ? "Origin: 可选（右侧开启）"
      : `Origin: ${status.origin_mode}`;
    renderQwenStatus(status.qwen);
  } catch (error) {
    aiMode.textContent = "AI: 服务未连接";
    originMode.textContent = "Origin: 服务未连接";
  }
}

async function saveQwenKey() {
  setBusy(saveQwenKeyButton, true);
  try {
    const status = await postJson("/api/secrets/qwen", {
      api_key: qwenApiKey.value,
      model: qwenModel.value,
      base_url: qwenBaseUrl.value,
      enable_thinking: qwenThinking.checked,
    });
    qwenApiKey.value = "";
    renderQwenStatus(status);
    await loadStatus();
  } catch (error) {
    qwenKeyState.textContent = error.message;
  } finally {
    setBusy(saveQwenKeyButton, false);
  }
}

async function deleteQwenKey() {
  setBusy(deleteQwenKeyButton, true);
  try {
    const response = await fetch("/api/secrets/qwen", { method: "DELETE" });
    const status = await response.json();
    if (!response.ok) {
      throw new Error(status.error || "删除失败");
    }
    renderQwenStatus(status);
    await loadStatus();
  } catch (error) {
    qwenKeyState.textContent = error.message;
  } finally {
    setBusy(deleteQwenKeyButton, false);
  }
}

function renderQwenStatus(status) {
  if (!status) {
    qwenKeyState.textContent = "未配置";
    return;
  }
  qwenModel.value = status.model || qwenModel.value;
  qwenBaseUrl.value = status.base_url || qwenBaseUrl.value;
  qwenThinking.checked = Boolean(status.enable_thinking);
  qwenKeyState.textContent = status.configured
    ? `已配置：${status.model}`
    : "未配置，可用规则模式";
}

function setBusy(button, busy) {
  button.disabled = busy;
}

function renderProfile(profile) {
  if (!profile) {
    profileSummary.innerHTML = `<div class="empty">暂无数据概况。</div>`;
    dataState.textContent = "等待解析";
    return;
  }
  if (!state.intent && !state.result) {
    setWorkflowStage("data", "数据已读取");
  }
  dataState.textContent = `${profile.row_count} 行`;
  const columns = profile.columns
    .map((column) => {
      const type = column.numeric_ratio >= 0.9 ? "数值列" : "文本/分组";
      return `<div class="column-row"><strong>${escapeHtml(column.name)}</strong><span>${type}</span></div>`;
    })
    .join("");
  profileSummary.innerHTML = `
    <div class="profile-line"><strong>文件</strong><span>${escapeHtml(profile.path)}</span></div>
    <div class="profile-line"><strong>行数</strong><span>${profile.row_count}</span></div>
    <div class="columns">${columns}</div>
  `;
}

function renderIntent(intent) {
  if (!intent) {
    slotGrid.innerHTML = "";
    questions.innerHTML = "";
    assumptions.innerHTML = "";
    intentState.textContent = "未生成";
    return;
  }

  intentState.textContent = intent.ready_to_execute ? "可执行" : "需确认";
  setWorkflowStage(intent.ready_to_execute ? "confirm" : "intent", intent.ready_to_execute ? "等待生成" : "需要确认");
  const outputFormats = intent.output_formats.length ? intent.output_formats.join(", ") : "png";
  slotGrid.innerHTML = `
    <div class="slot readonly-slot"><span>意图</span><strong>${escapeHtml(intent.kind)}</strong></div>
    <div class="slot readonly-slot"><span>置信度</span><strong>${Math.round(intent.confidence * 100)}%</strong></div>
    <div class="slot editable-slot">
      <label for="slotPlotKind">图类型</label>
      <select id="slotPlotKind">${renderOptions(PLOT_KIND_OPTIONS, intent.plot_kind || "auto")}</select>
    </div>
    <div class="slot editable-slot">
      <label for="slotXColumn">横轴</label>
      <select id="slotXColumn">${renderColumnOptions(intent.x_column || "", true)}</select>
    </div>
    <div class="slot editable-slot">
      <label for="slotYColumn">纵轴</label>
      <select id="slotYColumn">${renderColumnOptions(intent.y_column || "", true)}</select>
    </div>
    <div class="slot editable-slot">
      <label for="slotGroupColumn">分组</label>
      <select id="slotGroupColumn">${renderGroupOptions(intent.group_column || "__none__")}</select>
    </div>
    <div class="slot editable-slot">
      <label for="slotTitle">图标题</label>
      <input id="slotTitle" placeholder="${escapeAttr(defaultTitle(intent))}" />
    </div>
    <div class="slot editable-slot">
      <label for="slotXTitle">横轴标题</label>
      <input id="slotXTitle" placeholder="${escapeAttr(intent.x_column || "")}" />
    </div>
    <div class="slot editable-slot">
      <label for="slotYTitle">纵轴标题</label>
      <input id="slotYTitle" placeholder="${escapeAttr(intent.y_column || "")}" />
    </div>
    <label class="slot toggle-slot" for="slotFitEnabled">
      <input id="slotFitEnabled" type="checkbox" ${defaultFitEnabled(intent) ? "checked" : ""} />
      线性拟合
    </label>
    <div class="slot editable-slot wide-slot">
      <label for="slotOutputFormats">输出格式</label>
      <input id="slotOutputFormats" value="${escapeAttr(outputFormats)}" />
    </div>
  `;

  questions.innerHTML = intent.clarifying_questions.length
    ? intent.clarifying_questions
        .map((question) => {
          const options = question.options.length ? ` 可选：${question.options.join(" / ")}` : "";
          return `<div class="notice warning">${escapeHtml(question.question + options)}</div>`;
        })
        .join("")
    : `<div class="notice">没有阻塞问题，可以直接执行。</div>`;

  assumptions.innerHTML = intent.assumptions.length
    ? intent.assumptions.map((item) => `<div class="notice">${escapeHtml(item)}</div>`).join("")
    : "";
}

function renderResult(data) {
  const result = data.result;
  if (!result) {
    renderEditPlan(data.edit_plan);
    return;
  }
  state.result = result;
  state.runId = data.run_id || state.runId;
  state.revision = data.revision ?? state.revision;
  state.manifest = data.manifest || state.manifest;
  state.plotSpec = data.plot_spec || state.plotSpec;
  runState.textContent = result.passed ? "检查通过" : "有问题";
  setWorkflowStage("render", result.passed ? "已生成" : "需处理");

  if (data.artifact_urls && data.artifact_urls.origin_figure) {
    previewFrame.innerHTML = `<img src="${data.artifact_urls.origin_figure}" alt="Origin 导出的图" />`;
  } else if (data.points && data.points.length) {
    previewFrame.innerHTML = renderSvgPlot(data.points, result.regression);
  } else {
    previewFrame.innerHTML = `<p>没有可预览的点数据。</p>`;
  }

  const regression = result.regression;
  resultSummary.innerHTML = regression
    ? `
      <div class="profile-line"><strong>斜率</strong><span>${formatNumber(regression.slope)}</span></div>
      <div class="profile-line"><strong>截距</strong><span>${formatNumber(regression.intercept)}</span></div>
      <div class="profile-line"><strong>R2</strong><span>${formatNumber(regression.r_squared)}</span></div>
      <div class="profile-line"><strong>样本数</strong><span>${regression.n}</span></div>
    `
    : `<div class="empty">本次没有回归结果。</div>`;

  const checks = result.checks
    .map((check) => {
      const cls = check.passed ? "pass" : "warn";
      return `<div class="check-line ${cls}"><strong>${check.passed ? "通过" : "注意"}</strong><span>${escapeHtml(check.message)}</span></div>`;
    })
    .join("");
  resultSummary.insertAdjacentHTML("beforeend", checks);

  const artifacts = Object.entries(data.artifact_urls || {})
    .map(([name, url]) => `<div class="artifact-row"><strong>${escapeHtml(name)}</strong><a href="${url}" target="_blank" rel="noreferrer">打开</a></div>`)
    .join("");
  artifactList.innerHTML = artifacts;
  renderEditPlan(data.edit_plan);
  renderModifyPanel();
  renderFeedbackPanel();
}

function renderEditPlan(editPlan) {
  if (!editPlan) {
    editPlanSummary.innerHTML = "";
    return;
  }
  if (!editPlan.ready_to_execute) {
    const questions = editPlan.clarifying_questions || [];
    editPlanSummary.innerHTML = questions.length
      ? questions.map((question) => `<div class="notice warning">${escapeHtml(question.question)}</div>`).join("")
      : `<div class="notice warning">这个修改请求还需要确认后才能执行。</div>`;
    return;
  }
  const operations = editPlan.operations || [];
  editPlanSummary.innerHTML = operations.length
    ? operations
        .map((operation) => {
          const props = Object.entries(operation.properties || {})
            .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : value}`)
            .join(" / ");
          return `<div class="edit-operation"><strong>${escapeHtml(operation.op)}</strong><span>${escapeHtml(props || operation.target || "")}</span></div>`;
        })
        .join("")
    : "";
}

function renderModifyPanel() {
  if (!state.runId || state.revision === null || state.revision === undefined) {
    modifyPanel.hidden = true;
    return;
  }
  modifyPanel.hidden = false;
  revisionState.textContent = `Revision ${state.revision}`;
  const revisions = (state.manifest && state.manifest.revisions) || [];
  revisionList.innerHTML = revisions.length
    ? revisions
        .map((revision) => {
          const selected = Number(revision.revision) === Number(state.revision);
          return `
            <div class="revision-row">
              <strong>Rev ${revision.revision}${selected ? " 当前" : ""}</strong>
              <span>${escapeHtml(revision.request || "")}</span>
              <button class="secondary" type="button" data-revision="${revision.revision}">查看</button>
            </div>
          `;
        })
        .join("")
    : "";
}

function renderFeedbackPanel() {
  if (!state.runId) {
    feedbackPanel.hidden = true;
    return;
  }
  feedbackPanel.hidden = false;
}

function renderSvgPlot(points, regression) {
  const width = 680;
  const height = 300;
  const pad = 42;
  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const scaleX = (value) => pad + ((value - minX) / Math.max(maxX - minX, 1)) * (width - pad * 2);
  const scaleY = (value) => height - pad - ((value - minY) / Math.max(maxY - minY, 1)) * (height - pad * 2);
  const dots = points
    .map((point) => `<circle cx="${scaleX(point[0])}" cy="${scaleY(point[1])}" r="4.5" />`)
    .join("");
  const fitLine = regression
    ? `<line x1="${scaleX(minX)}" y1="${scaleY(regression.slope * minX + regression.intercept)}" x2="${scaleX(maxX)}" y2="${scaleY(regression.slope * maxX + regression.intercept)}" />`
    : "";
  return `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="数据预览图">
      <rect x="0" y="0" width="${width}" height="${height}" fill="#fff" />
      <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#9aa8a0" />
      <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="#9aa8a0" />
      <g fill="#19755f">${dots}</g>
      <g stroke="#a35d22" stroke-width="2.2">${fitLine}</g>
      <text x="${pad}" y="24" fill="#1f2522" font-size="14" font-weight="700">Preview</text>
      <text x="${width - pad}" y="${height - 12}" fill="#63706a" font-size="12" text-anchor="end">X</text>
      <text x="18" y="${pad}" fill="#63706a" font-size="12">Y</text>
    </svg>
  `;
}

async function handleIntake() {
  setBusy(intakeButton, true);
  intentState.textContent = "解析中";
  setWorkflowStage("intent", "理解中");
  try {
    const data = await postJson("/api/intake", {
      request: requestText.value,
      dataset: datasetPath.value,
    });
    state.profile = data.profile;
    state.intent = data.intent;
    renderProfile(data.profile);
    renderIntent(data.intent);
  } catch (error) {
    intentState.textContent = "失败";
    setWorkflowStage("intent", "需要处理");
    questions.innerHTML = `<div class="notice warning">${escapeHtml(error.message)}</div>`;
  } finally {
    setBusy(intakeButton, false);
  }
}

async function handleRun() {
  setBusy(runButton, true);
  runState.textContent = "执行中";
  setWorkflowStage("render", "生成中");
  try {
    const data = await postJson("/api/analyze", {
      request: requestText.value,
      dataset: datasetPath.value,
      use_origin: useOrigin.checked,
      overrides: collectPlotOverrides(),
    });
    state.profile = data.profile;
    state.intent = data.intent;
    renderProfile(data.profile);
    renderIntent(data.intent);
    renderResult(data);
  } catch (error) {
    runState.textContent = "失败";
    setWorkflowStage("confirm", "需要处理");
    previewFrame.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
  } finally {
    setBusy(runButton, false);
  }
}

async function applySample(button) {
  requestText.value = button.dataset.request || requestText.value;
  datasetPath.value = button.dataset.dataset || datasetPath.value;
  state.profile = null;
  state.intent = null;
  state.result = null;
  state.runId = null;
  state.revision = null;
  state.manifest = null;
  state.plotSpec = null;
  runState.textContent = "未执行";
  resultSummary.innerHTML = "";
  artifactList.innerHTML = "";
  modifyPanel.hidden = true;
  feedbackPanel.hidden = true;
  previewFrame.innerHTML = `
    <div class="empty-preview">
      <strong>样例已载入</strong>
      <span>确认槽位后生成图与报告。</span>
    </div>
  `;
  setWorkflowStage("intent", "样例已载入");
  await handleIntake();
}

function setWorkflowStage(stage, label) {
  const order = ["data", "intent", "confirm", "render"];
  const currentIndex = Math.max(order.indexOf(stage), 0);
  flowSteps.forEach((item) => {
    const index = order.indexOf(item.dataset.step);
    item.classList.toggle("is-done", index >= 0 && index < currentIndex);
    item.classList.toggle("is-current", index === currentIndex);
  });
  if (workflowState) {
    workflowState.textContent = label;
  }
}

async function handleModify() {
  if (!state.runId) {
    editPlanSummary.innerHTML = `<div class="notice warning">请先生成一张图，再继续修改。</div>`;
    return;
  }
  const request = modifyText.value.trim();
  if (!request) {
    editPlanSummary.innerHTML = `<div class="notice warning">请输入修改要求。</div>`;
    return;
  }
  setBusy(modifyButton, true);
  revisionState.textContent = "修改中";
  try {
    const data = await postJson("/api/modify", {
      run_id: state.runId,
      revision: state.revision,
      request,
      use_origin: useOrigin.checked,
    });
    if (data.result) {
      modifyText.value = "";
      renderResult(data);
    } else {
      state.manifest = data.manifest || state.manifest;
      state.plotSpec = data.plot_spec || state.plotSpec;
      renderEditPlan(data.edit_plan);
      renderModifyPanel();
    }
  } catch (error) {
    editPlanSummary.innerHTML = `<div class="notice warning">${escapeHtml(error.message)}</div>`;
  } finally {
    setBusy(modifyButton, false);
  }
}

async function handleFeedback() {
  if (!state.runId) {
    feedbackState.innerHTML = `<div class="notice warning">请先生成一张图，再保存反馈。</div>`;
    return;
  }
  const feedback = feedbackText.value.trim();
  const correction = correctionText.value.trim();
  if (!feedback && !correction) {
    feedbackState.innerHTML = `<div class="notice warning">请至少写下问题或正确修改方向。</div>`;
    return;
  }
  setBusy(feedbackButton, true);
  try {
    await postJson("/api/feedback", {
      run_id: state.runId,
      revision: state.revision,
      request: requestText.value,
      feedback,
      correction,
      plot_spec: state.plotSpec,
      artifact_urls: state.result ? state.result.artifacts : {},
    });
    feedbackText.value = "";
    correctionText.value = "";
    feedbackState.innerHTML = `<div class="notice">已保存为后续评测样本。</div>`;
  } catch (error) {
    feedbackState.innerHTML = `<div class="notice warning">${escapeHtml(error.message)}</div>`;
  } finally {
    setBusy(feedbackButton, false);
  }
}

async function loadRevision(revision) {
  if (!state.runId) {
    return;
  }
  try {
    const response = await fetch(`/api/revision?run_id=${encodeURIComponent(state.runId)}&revision=${encodeURIComponent(revision)}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "加载 revision 失败");
    }
    renderResult(data);
  } catch (error) {
    editPlanSummary.innerHTML = `<div class="notice warning">${escapeHtml(error.message)}</div>`;
  }
}

function formatNumber(value) {
  return Number(value).toPrecision(6);
}

function collectPlotOverrides() {
  const plotKind = document.querySelector("#slotPlotKind");
  if (!plotKind) {
    return {};
  }
  return {
    plot_kind: valueOf("#slotPlotKind"),
    x_column: valueOf("#slotXColumn"),
    y_column: valueOf("#slotYColumn"),
    group_column: valueOf("#slotGroupColumn"),
    title: valueOf("#slotTitle"),
    x_title: valueOf("#slotXTitle"),
    y_title: valueOf("#slotYTitle"),
    fit_enabled: Boolean(document.querySelector("#slotFitEnabled")?.checked),
    output_formats: splitFormats(valueOf("#slotOutputFormats")),
  };
}

function valueOf(selector) {
  return document.querySelector(selector)?.value || "";
}

function splitFormats(value) {
  return value
    .split(/[,\s;]+/)
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function renderOptions(options, selected) {
  return options
    .map((option) => `<option value="${escapeAttr(option)}" ${option === selected ? "selected" : ""}>${escapeHtml(option)}</option>`)
    .join("");
}

function renderColumnOptions(selected, numericOnly) {
  const columns = (state.profile && state.profile.columns) || [];
  const usable = numericOnly ? columns.filter((column) => column.numeric_ratio >= 0.9) : columns;
  const options = [`<option value="">待确认</option>`].concat(
    usable.map((column) => {
      const name = column.name;
      return `<option value="${escapeAttr(name)}" ${name === selected ? "selected" : ""}>${escapeHtml(name)}</option>`;
    })
  );
  return options.join("");
}

function renderGroupOptions(selected) {
  const columns = (state.profile && state.profile.columns) || [];
  const options = [`<option value="__none__" ${selected === "__none__" ? "selected" : ""}>无</option>`].concat(
    columns.map((column) => {
      const name = column.name;
      return `<option value="${escapeAttr(name)}" ${name === selected ? "selected" : ""}>${escapeHtml(name)}</option>`;
    })
  );
  return options.join("");
}

function defaultTitle(intent) {
  if (intent.y_column && intent.x_column) {
    return `${intent.y_column} vs ${intent.x_column}`;
  }
  return "";
}

function defaultFitEnabled(intent) {
  const text = requestText.value.toLowerCase();
  const negative = ["不要拟合", "不需要拟合", "去掉拟合", "删除拟合", "不用拟合", "no fit", "without fit"];
  if (negative.some((item) => text.includes(item))) {
    return false;
  }
  const positive = ["线性拟合", "加拟合", "拟合线", "回归", "fit", "regression", "trend line"];
  if (positive.some((item) => text.includes(item))) {
    return true;
  }
  return intent && intent.plot_kind === "scatter" && text.includes("散点");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

intakeButton.addEventListener("click", handleIntake);
runButton.addEventListener("click", handleRun);
sampleButtons.forEach((button) => {
  button.addEventListener("click", () => {
    applySample(button);
  });
});
requestText.addEventListener("input", () => setWorkflowStage("data", "已编辑"));
datasetPath.addEventListener("input", () => setWorkflowStage("data", "已编辑"));
saveQwenKeyButton.addEventListener("click", saveQwenKey);
deleteQwenKeyButton.addEventListener("click", deleteQwenKey);
modifyButton.addEventListener("click", handleModify);
feedbackButton.addEventListener("click", handleFeedback);
revisionList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-revision]");
  if (button) {
    loadRevision(button.dataset.revision);
  }
});
loadStatus();

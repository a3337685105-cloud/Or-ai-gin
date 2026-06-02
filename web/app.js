const state = {
  workOrder: null,
  questionBank: [],
  answers: {},
  activeTab: "summary",
  error: "",
};

const SLOT_META = {
  intended_use: {
    label: "研究用途",
    placeholder: "例如：判断方向、设计实验、组会展示、论文插图",
  },
  system_description: {
    label: "研究对象",
    placeholder: "例如：5W 芯片贴在 50 mm 铝板中心",
  },
  geometry: {
    label: "几何 / 样品",
    placeholder: "例如：先用简化长方体，或已有 CAD 文件",
  },
  materials: {
    label: "材料参数",
    placeholder: "例如：铝 6061，导热垫 k=3 W/mK",
  },
  heat_sources: {
    label: "关键输入",
    placeholder: "例如：芯片总功率 5 W，作用在中心区域",
  },
  cooling_boundaries: {
    label: "边界 / 环境",
    placeholder: "例如：自然对流，环境 25°C，底面固定温度",
  },
  quantities_of_interest: {
    label: "关注指标",
    placeholder: "例如：最高温度、热点位置、升温时间",
  },
  constraints: {
    label: "判断标准",
    placeholder: "例如：最高温度不超过 80°C",
  },
  comparison_or_sweep: {
    label: "比较 / 扫描",
    placeholder: "例如：功率 1-10 W，风速 0-3 m/s",
  },
  validation_data: {
    label: "验证依据",
    placeholder: "例如：红外图、历史测试记录、文献 benchmark",
  },
  output_format: {
    label: "期望交付",
    placeholder: "例如：简短判断、实验方案、图、完整报告",
  },
};

const JOB_LABELS = {
  feasibility_screening: "可行性判断",
  experiment_planning: "实验规划",
  presentation: "展示材料",
  paper_evidence: "论文证据",
  validation_package: "可信证据包",
  exploratory_analysis: "探索分析",
};

const EVIDENCE_LABELS = {
  quick_screening: "快速判断",
  scoping: "范围界定",
  decision_support: "决策支持",
  publication_or_external_claim: "对外结论",
};

const OUTPUT_LABELS = {
  short_decision_memo: "简短判断备忘",
  assumptions: "假设清单",
  risk_flags: "风险标记",
  next_experiment_suggestions: "下一步实验建议",
  experiment_plan: "实验方案",
  parameter_matrix: "参数矩阵",
  probe_placement_suggestions: "测点建议",
  expected_ranges: "预期范围",
  annotated_figures: "带注释图",
  temperature_visual_package: "结果图像包",
  talking_points: "汇报要点",
  paper_figures: "论文图",
  methods_text: "方法描述",
  plot_data_csv: "绘图数据",
  limitations: "局限性",
  vv_report: "验证与确认报告",
  golden_case_comparison: "基准对比",
  mesh_convergence_plan: "收敛性计划",
  evidence_manifest: "证据清单",
  scoping_memo: "范围备忘",
  candidate_model_paths: "候选工作路径",
  blocking_questions: "阻塞问题",
  animation_package: "动态图包",
};

const goalInput = document.querySelector("#goalInput");
const contextNotes = document.querySelector("#contextNotes");
const filePaths = document.querySelector("#filePaths");
const intakeButton = document.querySelector("#intakeButton");
const updateSlotsButton = document.querySelector("#updateSlotsButton");
const clearSlotsButton = document.querySelector("#clearSlotsButton");
const tabContent = document.querySelector("#tabContent");
const serviceState = document.querySelector("#serviceState");
const workbenchState = document.querySelector("#workbenchState");
const resultState = document.querySelector("#resultState");
const contextState = document.querySelector("#contextState");
const readinessBadge = document.querySelector("#readinessBadge");
const understandingSnapshot = document.querySelector("#understandingSnapshot");
const slotFields = document.querySelector("#slotFields");
const tabButtons = Array.from(document.querySelectorAll("[data-tab]"));

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
    if (!response.ok) {
      throw new Error("status unavailable");
    }
    serviceState.textContent = "理解服务就绪";
  } catch (error) {
    serviceState.textContent = "服务未连接";
  }
}

async function submitResearchIntake(syncSlots = false) {
  if (syncSlots) {
    state.answers = collectSlotAnswers();
  }
  const goal = goalInput.value.trim();
  if (!goal) {
    state.error = "请先填写研究目标。";
    renderAll();
    goalInput.focus();
    return;
  }

  setBusy(intakeButton, true);
  setBusy(updateSlotsButton, true);
  state.error = "";
  setWorkbenchState("理解中", "working");
  resultState.textContent = "整理工作单中";
  try {
    const data = await postJson("/api/research-intake", {
      goal,
      context: contextNotes.value.trim(),
      files: parseFiles(filePaths.value),
      answers: state.answers,
    });
    state.workOrder = data.work_order;
    state.questionBank = data.question_bank || [];
    renderAll();
  } catch (error) {
    state.error = error.message;
    renderAll();
  } finally {
    setBusy(intakeButton, false);
    setBusy(updateSlotsButton, false);
  }
}

function renderAll() {
  renderStatus();
  renderSnapshot();
  renderSlots();
  renderTabs();
  renderContextState();
}

function renderStatus() {
  const workOrder = state.workOrder;
  if (state.error) {
    setWorkbenchState("需要处理", "warning");
    resultState.textContent = "发生错误";
    readinessBadge.textContent = "错误";
    readinessBadge.className = "warning";
    return;
  }
  if (!workOrder) {
    setWorkbenchState("等待目标", "");
    resultState.textContent = "尚未生成工作单";
    readinessBadge.textContent = "待理解";
    readinessBadge.className = "";
    return;
  }
  if (workOrder.ready_to_plan) {
    setWorkbenchState("可进入计划", "ready");
    resultState.textContent = "工作单已生成";
    readinessBadge.textContent = "信息可用";
    readinessBadge.className = "ready";
  } else {
    setWorkbenchState("缺少关键信息", "warning");
    resultState.textContent = "需要补充信息";
    readinessBadge.textContent = "需补充";
    readinessBadge.className = "warning";
  }
}

function setWorkbenchState(text, tone) {
  workbenchState.textContent = text;
  workbenchState.className = `state-pill ${tone || ""}`.trim();
}

function renderContextState() {
  const fileCount = parseFiles(filePaths.value).length;
  const hasContext = Boolean(contextNotes.value.trim());
  if (!fileCount && !hasContext) {
    contextState.textContent = "可选";
  } else if (fileCount && hasContext) {
    contextState.textContent = `${fileCount} 个文件线索`;
  } else if (fileCount) {
    contextState.textContent = `${fileCount} 个文件线索`;
  } else {
    contextState.textContent = "已有上下文";
  }
}

function renderSnapshot() {
  const workOrder = state.workOrder;
  if (!workOrder) {
    understandingSnapshot.innerHTML = `
      <div class="empty-state">
        <strong>等待研究目标</strong>
        <span>生成后会显示系统理解、证据强度和最小可行动工作单。</span>
      </div>
    `;
    return;
  }
  const core = workOrder.core_thread || {};
  understandingSnapshot.innerHTML = `
    <div class="snapshot-grid">
      ${snapshotItem("用途", humanJob(workOrder.user_job))}
      ${snapshotItem("证据", humanEvidence(workOrder.evidence_level))}
      ${snapshotItem("对象", core.primary_system || workOrder.raw_goal)}
      ${snapshotItem("指标", humanValue(core.primary_qoi))}
      ${snapshotItem("标准", humanValue(core.decision_criterion))}
    </div>
  `;
}

function snapshotItem(label, value) {
  return `
    <div class="snapshot-item">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value || "待确认")}</strong>
    </div>
  `;
}

function renderSlots() {
  const workOrder = state.workOrder;
  if (!workOrder) {
    slotFields.innerHTML = `
      <div class="slot-empty">
        <strong>核心槽位会在理解后出现</strong>
        <span>这里只保留当前任务最相关的字段。</span>
      </div>
    `;
    updateSlotsButton.disabled = true;
    clearSlotsButton.disabled = true;
    return;
  }
  updateSlotsButton.disabled = false;
  clearSlotsButton.disabled = false;
  const fields = relevantSlotFields(workOrder);
  slotFields.innerHTML = fields
    .map((field) => {
      const meta = SLOT_META[field];
      const value = fieldValue(field, workOrder);
      const isMissing = (workOrder.missing_blockers || []).includes(field);
      return `
        <label class="slot-field ${isMissing ? "is-missing" : ""}" for="slot-${escapeAttr(field)}">
          <span>${escapeHtml(meta.label)}${isMissing ? " · 缺失" : ""}</span>
          <textarea id="slot-${escapeAttr(field)}" data-slot-field="${escapeAttr(field)}" rows="2" placeholder="${escapeAttr(meta.placeholder)}">${escapeHtml(value)}</textarea>
        </label>
      `;
    })
    .join("");
}

function relevantSlotFields(workOrder) {
  const questionFields = (workOrder.next_questions || []).map((question) => question.field);
  const missingFields = workOrder.missing_blockers || [];
  const thick = workOrder.thick_context || {};
  const domainFields = thick.domain === "thermal_simulation"
    ? ["geometry", "heat_sources", "cooling_boundaries"]
    : [];
  const baseFields = ["system_description", "intended_use", "quantities_of_interest", "constraints", "output_format"];
  const candidateFields = unique([...missingFields, ...questionFields, ...domainFields, ...baseFields]);
  return candidateFields.filter((field) => SLOT_META[field]).slice(0, 7);
}

function fieldValue(field, workOrder) {
  if (Object.prototype.hasOwnProperty.call(state.answers, field)) {
    return state.answers[field];
  }
  const thick = workOrder.thick_context || {};
  const value = thick[field];
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  return value || "";
}

function collectSlotAnswers() {
  const answers = {};
  document.querySelectorAll("[data-slot-field]").forEach((input) => {
    const field = input.dataset.slotField;
    const value = input.value.trim();
    if (field && value) {
      answers[field] = value;
    }
  });
  return answers;
}

function renderTabs() {
  tabButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tab === state.activeTab);
  });
  if (state.error) {
    tabContent.innerHTML = `
      <section class="summary-section warning-section">
        <h3>错误</h3>
        <p>${escapeHtml(state.error)}</p>
      </section>
    `;
    return;
  }
  const renderer = {
    summary: renderSummaryTab,
    model: renderModelTab,
    results: renderResultsTab,
    figures: renderFiguresTab,
    validation: renderValidationTab,
    files: renderFilesTab,
  }[state.activeTab];
  tabContent.innerHTML = renderer ? renderer() : renderSummaryTab();
}

function renderSummaryTab() {
  const workOrder = state.workOrder;
  if (!workOrder) {
    return `
      <section class="summary-section empty-section">
        <h3>等待输入</h3>
        <p>提交研究目标后，这里会按 thick-to-thin 结构显示用户目标、系统理解、假设、缺失信息和下一步计划。</p>
      </section>
    `;
  }
  const core = workOrder.core_thread || {};
  const understanding = [
    ["研究用途", humanJob(workOrder.user_job)],
    ["证据强度", humanEvidence(workOrder.evidence_level)],
    ["主要对象", core.primary_system || workOrder.raw_goal],
    ["关注指标", humanValue(core.primary_qoi)],
    ["判断标准", humanValue(core.decision_criterion)],
  ];
  const missing = missingItems(workOrder);
  return `
    ${sectionBlock("用户目标", `<p class="goal-copy">${escapeHtml(workOrder.raw_goal)}</p>`)}
    ${sectionBlock("系统理解", keyValueList(understanding))}
    ${sectionBlock("假设", listBlock(workOrder.assumptions || [], "暂无默认假设。"))}
    ${sectionBlock("缺失信息", listBlock(missing, "暂无阻塞缺口。"))}
    ${sectionBlock("下一步计划", outputList(workOrder.planned_outputs || []))}
  `;
}

function renderModelTab() {
  const workOrder = state.workOrder;
  if (!workOrder) {
    return placeholderSection("模型区域", "理解完成后会保留系统、几何、参数、边界和后续模型产物。");
  }
  const thick = workOrder.thick_context || {};
  const rows = [
    ["研究对象", thick.system_description || (workOrder.core_thread || {}).primary_system],
    ["几何 / 样品", thick.geometry],
    ["材料参数", thick.materials],
    ["关键输入", thick.heat_sources],
    ["边界 / 环境", thick.cooling_boundaries],
    ["比较 / 扫描", thick.comparison_or_sweep],
  ];
  return `
    ${sectionBlock("当前模型线索", keyValueList(rows, "待补充"))}
    ${sectionBlock("后续模型产物", futureGrid(["参数表", "模型草案", "计算任务", "执行日志"]))}
  `;
}

function renderResultsTab() {
  const workOrder = state.workOrder;
  if (!workOrder) {
    return placeholderSection("结果区域", "这里会承接后续计算、分析、拟合和实验对比的摘要。");
  }
  const status = workOrder.ready_to_plan ? "已具备进入计划的最小信息" : "仍有阻塞信息需要补齐";
  return `
    ${sectionBlock("当前状态", `<p>${escapeHtml(status)}</p>`)}
    ${sectionBlock("预期结果", outputCards(workOrder.planned_outputs || []))}
  `;
}

function renderFiguresTab() {
  return `
    <section class="figure-stage">
      <div>
        <h3>图像结果区</h3>
        <p>后续生成的图、截图、动画帧和可导出图件会汇总在这里。</p>
      </div>
      <div class="figure-placeholder">
        <span>Figures</span>
      </div>
    </section>
  `;
}

function renderValidationTab() {
  const workOrder = state.workOrder;
  if (!workOrder) {
    return placeholderSection("验证区域", "这里会保留数值检查、对照数据、假设风险和验证证据。");
  }
  const thick = workOrder.thick_context || {};
  const validationRows = [
    ["验证依据", thick.validation_data],
    ["判断标准", thick.constraints || (workOrder.core_thread || {}).decision_criterion],
    ["缺失阻塞", (workOrder.missing_blockers || []).map(humanField).join(", ")],
  ];
  return `
    ${sectionBlock("验证线索", keyValueList(validationRows, "待补充"))}
    ${sectionBlock("假设风险", listBlock(workOrder.assumptions || [], "暂无假设风险。"))}
  `;
}

function renderFilesTab() {
  const files = parseFiles(filePaths.value);
  const context = contextNotes.value.trim();
  const workOrder = state.workOrder;
  const extra = workOrder && workOrder.thick_context ? workOrder.thick_context.extra_user_context || {} : {};
  const extraRows = Object.entries(extra)
    .filter(([key]) => !["files", "additional_context"].includes(key))
    .map(([key, value]) => [humanField(key), Array.isArray(value) ? value.join(", ") : value]);
  return `
    ${sectionBlock("文件线索", files.length ? fileList(files) : `<p class="muted-copy">暂无文件线索。</p>`)}
    ${sectionBlock("上下文摘录", context ? `<p>${escapeHtml(context)}</p>` : `<p class="muted-copy">暂无补充上下文。</p>`)}
    ${extraRows.length ? sectionBlock("额外上下文", keyValueList(extraRows)) : ""}
    ${sectionBlock("后续文件区域", futureGrid(["输入清单", "结果文件", "图件导出", "审计记录"]))}
  `;
}

function sectionBlock(title, innerHtml) {
  return `
    <section class="summary-section">
      <h3>${escapeHtml(title)}</h3>
      ${innerHtml}
    </section>
  `;
}

function placeholderSection(title, text) {
  return `
    <section class="summary-section empty-section">
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(text)}</p>
    </section>
  `;
}

function keyValueList(rows, emptyValue = "待确认") {
  const content = rows
    .filter(([label]) => label)
    .map(([label, value]) => `
      <div class="kv-row">
        <strong>${escapeHtml(label)}</strong>
        <span>${escapeHtml(humanValue(value) || emptyValue)}</span>
      </div>
    `)
    .join("");
  return `<div class="kv-list">${content}</div>`;
}

function listBlock(items, emptyText) {
  const normalized = (items || []).filter(Boolean);
  if (!normalized.length) {
    return `<p class="muted-copy">${escapeHtml(emptyText)}</p>`;
  }
  return `
    <ul class="clean-list">
      ${normalized.map((item) => `<li>${escapeHtml(humanValue(item))}</li>`).join("")}
    </ul>
  `;
}

function outputList(outputs) {
  const items = (outputs || []).map(humanOutput);
  return listBlock(items, "下一步计划会在理解后生成。");
}

function outputCards(outputs) {
  const items = (outputs || []).map(humanOutput);
  if (!items.length) {
    return `<p class="muted-copy">暂无预期结果。</p>`;
  }
  return `
    <div class="output-grid">
      ${items.map((item) => `<div class="output-card">${escapeHtml(item)}</div>`).join("")}
    </div>
  `;
}

function futureGrid(items) {
  return `
    <div class="future-grid">
      ${items.map((item) => `<div class="future-cell">${escapeHtml(item)}</div>`).join("")}
    </div>
  `;
}

function fileList(files) {
  return `
    <div class="file-list">
      ${files.map((file) => `<div class="file-row"><span>${escapeHtml(file)}</span></div>`).join("")}
    </div>
  `;
}

function missingItems(workOrder) {
  const missing = (workOrder.missing_blockers || []).map((field) => `${humanField(field)}：待补充`);
  const questions = (workOrder.next_questions || []).map((question) => {
    const options = question.options && question.options.length ? `（${question.options.map(humanValue).join(" / ")}）` : "";
    return `${humanField(question.field)}：${question.question}${options}`;
  });
  return unique([...missing, ...questions]);
}

function parseFiles(value) {
  return value
    .replaceAll(";", "\n")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function humanField(field) {
  return SLOT_META[field] ? SLOT_META[field].label : String(field).replaceAll("_", " ");
}

function humanJob(value) {
  return JOB_LABELS[value] || humanValue(value);
}

function humanEvidence(value) {
  return EVIDENCE_LABELS[value] || humanValue(value);
}

function humanOutput(value) {
  return OUTPUT_LABELS[value] || humanValue(value);
}

function humanValue(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  if (Array.isArray(value)) {
    return value.map(humanValue).filter(Boolean).join(", ");
  }
  const text = String(value);
  const known = OUTPUT_LABELS[text] || JOB_LABELS[text] || EVIDENCE_LABELS[text];
  return known || text.replaceAll("_", " ");
}

function unique(items) {
  const seen = new Set();
  return items.filter((item) => {
    if (!item || seen.has(item)) {
      return false;
    }
    seen.add(item);
    return true;
  });
}

function setBusy(button, busy) {
  if (button) {
    button.disabled = busy;
  }
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

intakeButton.addEventListener("click", () => submitResearchIntake(false));
updateSlotsButton.addEventListener("click", () => submitResearchIntake(true));
clearSlotsButton.addEventListener("click", () => {
  state.answers = {};
  renderSlots();
});

tabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    state.activeTab = button.dataset.tab || "summary";
    renderTabs();
  });
});

[goalInput, contextNotes, filePaths].forEach((input) => {
  input.addEventListener("input", () => {
    if (input === filePaths || input === contextNotes) {
      renderContextState();
      if (state.activeTab === "files") {
        renderTabs();
      }
    }
    if (input === goalInput && goalInput.value.trim()) {
      setWorkbenchState("已编辑", "");
    }
  });
});

loadStatus();
renderAll();

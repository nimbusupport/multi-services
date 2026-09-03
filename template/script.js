let loadedData = []; // {sheet_row, name, text, status, idnumber(hidden), domain, did, numbercgr, cgr_row, cgr_marked, checked}
let searchQuery = "";
let inforuSentNumbers = new Set();
let inforuLogEntries = [];
let inforuLogSearchQuery = "";
let manualNumberCgrState = {
  number: "",
  marked: false,
  row: null
};

const FIREBERRY_LOGO_URL = "https://app.fireberry.com/app/static/img/fireberry-logo-CIplsT_n.svg";
const SMS_GUIDE_STEPS = {
  1: "Fireberry Sync לטעינת לקוחות.",
  2: "יש לבחור את הלקוח או הלקוחות לביצוע SMS ולסמן ב-V. אפשר לבחור את כלל הלקוחות בלחיצה על Select All.",
  3: "Inforu Mail שולח בקשת אימות לספק SMS באמצעות מייל מ-support@nimbusip.com. שירות SMS יעבוד אחרי הוספת זיהוי שולח בצד הספק. אחרי הודעת \"נשלח ל-Inforu\" אפשר להתקדם לשלב הבא.",
  4: "Create SMS שולח בקשה למערכת VOIPAPPZ ליצירת לקוח. יצירה למספר לקוחות יכולה לקחת 2-5 דקות, יש להמתין להודעת סיום. חשוב: אם קיים לקוח עם אותו שם או אותו NumberCGRT במערכת VOIPAPPZ תתקבל שגיאה ויש לשנות את שם הלקוח או את המספר.",
  5: "Status Done שולח דוח יצירה לגוגל: NumberCGRT עם מספר דומיין, תאריך יצירה, ומסמן את המספר בשימוש."
};

/* Helpers */
function showAppNotice(message, type = "info", timeout = 30000){
  const region = document.getElementById("appNoticeRegion");
  if(!region){
    return;
  }

  const normalizedOptions =
    typeof timeout === "number"
      ? { timeout }
      : (timeout && typeof timeout === "object" ? timeout : {});
  const noticeTimeout = Number.isFinite(normalizedOptions.timeout) ? normalizedOptions.timeout : 30000;
  const actions = Array.isArray(normalizedOptions.actions) ? normalizedOptions.actions : [];

  const notice = document.createElement("section");
  notice.className = `app-notice is-${type}`;

  const titleByType = {
    success: "Success",
    error: "Error",
    info: "Notice"
  };
  const endSymbolByType = {
    success: "&#10003;",
    error: "&times;",
    info: "&times;"
  };
  const endLabelByType = {
    success: "Success",
    error: "Error",
    info: "Close"
  };

  notice.innerHTML = `
    <div class="app-notice-body">
      <p class="app-notice-title">${titleByType[type] || titleByType.info}</p>
      <p class="app-notice-message">${escapeHtml(String(message ?? ""))}</p>
      ${actions.length ? '<div class="app-notice-actions"></div>' : ""}
    </div>
    <button class="app-notice-close app-notice-endmark" type="button" aria-label="${endLabelByType[type] || endLabelByType.info}">${endSymbolByType[type] || endSymbolByType.info}</button>
  `;

  const close = () => {
    notice.remove();
  };

  notice.querySelector(".app-notice-close")?.addEventListener("click", close);
  const actionsWrap = notice.querySelector(".app-notice-actions");
  if(actionsWrap){
    actions.forEach((action, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "app-notice-action";
      button.textContent = action?.label || `Action ${index + 1}`;
      button.addEventListener("click", async () => {
        try{
          await action?.onClick?.(notice);
        }catch(error){
          showAppNotice(formatErrorMessage(error), "error");
        }
      });
      actionsWrap.appendChild(button);
    });
  }
  region.appendChild(notice);
  window.setTimeout(close, noticeTimeout);
}

function showAppSuccess(message){
  showAppNotice(message, "success");
}

function inferNoticeType(message){
  const text = String(message ?? "").toLowerCase();
  if(
    text.includes("שגיאה") ||
    text.includes("error") ||
    text.includes("failed") ||
    text.includes("unauthorized")
  ){
    return "error";
  }
  if(
    text.includes("נשלח") ||
    text.includes("עודכן") ||
    text.includes("created") ||
    text.includes("success")
  ){
    return "success";
  }
  return "info";
}

function formatErrorMessage(error){
  if(error instanceof Error){
    return error.message;
  }
  return String(error ?? "Unknown error");
}

async function readJsonResponse(res){
  const contentType = res.headers.get("content-type") || "";
  if(contentType.includes("application/json")){
    return res.json();
  }

  const text = await res.text();
  if(text && text.trim().startsWith("<")){
    throw new Error("Server returned an HTML error page instead of JSON. Check Vercel logs.");
  }
  throw new Error(text || "Server returned a non-JSON response.");
}

function setCounts(){
  document.getElementById("countPill").innerHTML =
    `<span class="dot dot-amber"></span> נטענו: ${loadedData.length}`;

  const selected = loadedData.filter(x => x.checked).length;
  document.getElementById("selectedPill").innerHTML =
    `<span class="dot dot-blue"></span> מסומנים: ${selected}`;
}

function escapeHtml(str){
  return (str ?? "").toString()
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

function setSearch(val){
  searchQuery = (val || "").trim().toLowerCase();
  renderTable();
}

function normalizeDidValue(value){
  return String(value ?? "").replace(/\D/g, "");
}

function setInforuSentNumbers(numbers){
  inforuSentNumbers = new Set(
    (Array.isArray(numbers) ? numbers : [])
      .map(normalizeDidValue)
      .filter(Boolean)
  );
}

function refreshInforuSentFlag(item){
  if(!item){
    return;
  }
  item.inforu_sent = inforuSentNumbers.has(normalizeDidValue(item.did));
}

function refreshAllInforuSentFlags(){
  loadedData.forEach(refreshInforuSentFlag);
}

function syncDidInputState(sheetRow){
  const item = loadedData.find(entry => entry.sheet_row === sheetRow);
  const input = document.querySelector(`input[data-did-row="${sheetRow}"]`);
  if(!item || !input){
    return;
  }
  input.classList.toggle("did-sent", !!item.inforu_sent);
}

function showSmsGuideStep(step){
  const textEl = document.getElementById("smsGuideText");
  if(textEl){
    textEl.textContent = SMS_GUIDE_STEPS[step] || "";
  }

  document.querySelectorAll(".guide-step").forEach(btn => {
    btn.classList.toggle("active", Number(btn.dataset.step) === Number(step));
  });
}

async function lookupSmsDomain(){
  const input = document.getElementById("smsDomainLookupInput");
  const result = document.getElementById("smsDomainLookupResult");
  const domain = (input?.value || "").trim();

  if(!domain){
    result.innerHTML = "";
    return;
  }

  result.innerHTML = "בודק...";

  try{
    const res = await fetch("/sms-domain-lookup", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({domain})
    });
    const data = await res.json();

    if(!res.ok || !data.ok){
      result.innerHTML = `<span class="lookup-missing">שגיאה בבדיקה</span>`;
      return;
    }

    if(!data.found){
      result.innerHTML = "";
      return;
    }

    result.innerHTML = `
      <span class="lookup-pill"><b>Domain:</b> ${escapeHtml(data.domain)}</span>
      <span class="lookup-pill"><b>תאריך יצירה:</b> ${escapeHtml(data.date || "-")}</span>
      <span class="lookup-pill"><b>DID:</b> ${escapeHtml(data.did || "-")}</span>
    `;
  }catch(e){
    result.innerHTML = `<span class="lookup-missing">שגיאה בבדיקה: ${escapeHtml(e.message)}</span>`;
  }
}

/* Load data */
async function loadData() {
    try{
      const res = await fetch('/load-data');
      const payload = await readJsonResponse(res);
      if(!res.ok || payload.ok === false){
        throw new Error(payload.message || res.statusText || "Load failed");
      }
      const data = Array.isArray(payload) ? payload : (payload.customers || []);
      setInforuSentNumbers(payload.inforu_sent_numbers || []);
  
      if(!Array.isArray(data) || data.length === 0){
        loadedData = [];
        renderTable();
        alert("אין לקוחות שממתינים לשירות סמס");
        return;
      }
  
      loadedData = data.map(x => ({
        ...x,
        domain: "",
        did: "",
        inforu_sent: false,
        checked: false,
        fbLoading: false
      }));

      refreshAllInforuSentFlags();
      renderTable();
    }catch(e){
      alert("שגיאה בטעינת נתונים: " + formatErrorMessage(e));
    }
  }

/* Render */
function renderTable(){
  const tbody = document.querySelector("#dataTable tbody");
  tbody.innerHTML = "";

  const filtered = loadedData
    .map((item, idx) => ({ item, idx }))
    .filter(({ item }) => {
      if(!searchQuery) return true;
      const name = (item.name || "").toLowerCase();
      const domain = (item.domain || "").toLowerCase();
      const did = (item.did || "").toLowerCase();
      return name.includes(searchQuery) || domain.includes(searchQuery) || did.includes(searchQuery);
    });

  filtered.forEach(({ item, idx }) => {
    const tr = document.createElement("tr");

    tr.innerHTML = `
      <td class="right">
        <input type="checkbox"
          ${item.checked ? "checked" : ""}
          onchange="toggleCheckedByRow(${item.sheet_row}, this.checked)" />
      </td>

      <td class="right">
        <div><b>${escapeHtml(item.name)}</b></div>
        <div class="small">לקוח</div>

        <button class="fb-mini ${item.fbLoading ? "disabled" : ""}"
          type="button"
          title="משוך Domain/DID מ-Fireberry"
          onclick="fireberryFill(${idx})"
          ${item.fbLoading ? "disabled" : ""}>
          <img class="fb-mini-img" src="${FIREBERRY_LOGO_URL}" alt="Fireberry" />
          <span>Fireberry</span>
        </button>
      </td>

      <td class="right">
        <div class="sms">${escapeHtml(item.text)}</div>
      </td>

      <td class="right">
        <input class="input" placeholder="לדוגמה: 5555"
          value="${escapeHtml(item.domain)}"
          oninput="updateField(${idx}, 'domain', this.value)" />
      </td>

      <td class="right">
       <input class="input ${item.inforu_sent ? 'did-sent' : ''}" data-did-row="${item.sheet_row}" placeholder="031234567"
         value="${escapeHtml(item.did)}"
         oninput="updateField(${idx}, 'did', this.value)" />
      </td>

      <td class="right">
        <span class="cgr-pill ${item.cgr_marked ? 'cgr-ok' : 'cgr-missing'}">
          <span class="dot ${item.cgr_marked ? 'dot-green' : 'dot-amber'}"></span>
          ${escapeHtml(item.numbercgr || "")}
        </span>
      </td>

      <td class="right">
        <span class="badge"><span class="dot dot-amber"></span> ${escapeHtml(item.status || "ממתין")}</span>
      </td>

      <td class="right">
        <span class="pill"><span class="dot dot-blue"></span> ${item.sheet_row}</span>
      </td>
    `;

    tbody.appendChild(tr);
  });

  setCounts();
}

/* Selection & updates */
function updateField(idx, field, value){
  loadedData[idx][field] = value;
  if(field === "did"){
    refreshInforuSentFlag(loadedData[idx]);
    syncDidInputState(loadedData[idx].sheet_row);
  }
}

function selectAll(val){
  loadedData.forEach(x => x.checked = val);

  document.querySelectorAll("#dataTable tbody input[type='checkbox']").forEach(cb => {
    cb.checked = val;
  });

  setCounts();
}

function getSelected(){
  return loadedData.filter(x => x.checked === true);
}

function toggleCheckedByRow(sheetRow, checked){
  const item = loadedData.find(x => x.sheet_row === sheetRow);
  if(!item) return;
  item.checked = checked;
  setCounts();
}

function validateSelectedForExport(selected){
  const missing = selected.filter(x =>
    !(x.domain || "").trim() ||
    !(x.did || "").trim() ||
    !(x.numbercgr || "").trim()
  );
  if(missing.length > 0){
    alert("יש לקוחות מסומנים בלי Domain/DID/NumberCGR. אנא מלא לפני יצוא.");
    return false;
  }
  return true;
}

function getSelectedSmsCustomers(){
  return loadedData.filter(x => x.checked);
}

function collectSelectedNumberCgrValues(selected){
  return selected
    .map(item => (item.numbercgr || "").trim())
    .filter(Boolean);
}

function getNumericDidValues(selected){
  return selected
    .map(item => normalizeDidValue(item.did))
    .filter(Boolean);
}

function normalizeSmsCustomerInput(customer){
  return {
    domain: (customer?.domain || "").trim(),
    did: String(customer?.did || "").trim(),
    numbercgr: normalizePhoneWithZero(customer?.numbercgr || ""),
    text: customer?.text || ""
  };
}

function getNumericDidValuesFromCustomers(customers){
  return customers
    .map(customer => normalizeDidValue(customer.did))
    .filter(Boolean);
}

function normalizePhoneWithZero(value){
  const digits = String(value ?? "").replace(/\D+/g, "");
  if(!digits){
    return "";
  }
  return digits.startsWith("0") ? digits : `0${digits}`;
}

function buildStartCreateHeader(selected){
  return selected.map(item => {
    const domain = (item.domain || "-").trim() || "-";
    const numberCgr = (item.numbercgr || "-").trim() || "-";
    return `Create Ring Group 410 in Domain ${domain} Add NumberCGRT ${numberCgr}`;
  }).join("\n");
}

async function copyTextToClipboard(text){
  await navigator.clipboard.writeText(String(text ?? ""));
}

function showStartCreateNotice(message, type, selected){
  const numberCgrValues = collectSelectedNumberCgrValues(selected);
  const actions = [];

  if(numberCgrValues.length){
    actions.push({
      label: "Copy NumberCGRT",
      onClick: async () => {
        await copyTextToClipboard(numberCgrValues.join("\n"));
        showAppSuccess("NumberCGRT copied");
      }
    });
  }

  actions.push({
    label: "Close",
    onClick: (notice) => {
      notice?.remove();
    }
  });

  showAppNotice(message, type, {
    timeout: 60000,
    actions
  });
}

function showCustomerFlowNotice(message, type, customers){
  const numberCgrValues = (Array.isArray(customers) ? customers : [])
    .map(customer => (customer?.numbercgr || "").trim())
    .filter(Boolean);
  const actions = [];

  if(numberCgrValues.length){
    actions.push({
      label: "Copy NumberCGRT",
      onClick: async () => {
        await copyTextToClipboard(numberCgrValues.join("\n"));
        showAppSuccess("NumberCGRT copied");
      }
    });
  }

  actions.push({
    label: "Close",
    onClick: (notice) => {
      notice?.remove();
    }
  });

  showAppNotice(message, type, {
    timeout: 60000,
    actions
  });
}

function buildCustomerFlowHeader(customers){
  return (Array.isArray(customers) ? customers : []).map(customer => {
    const domain = (customer?.domain || "-").trim() || "-";
    const numberCgr = (customer?.numbercgr || "-").trim() || "-";
    return `Create Ring Group 410 in Domain ${domain} Add NumberCGRT ${numberCgr}`;
  }).join("\n");
}

function renderManualNumberCgr(){
  const pill = document.getElementById("manual-numbercgr-pill");
  const dot = document.getElementById("manual-numbercgr-dot");
  const value = document.getElementById("manual-numbercgr-value");

  if(!pill || !dot || !value){
    return;
  }

  if(!manualNumberCgrState.number){
    pill.classList.remove("cgr-ok");
    pill.classList.add("cgr-missing");
    dot.classList.remove("dot-green");
    dot.classList.add("dot-amber");
    value.textContent = "No available NumberCGRT";
    return;
  }

  pill.classList.toggle("cgr-ok", !!manualNumberCgrState.marked);
  pill.classList.toggle("cgr-missing", !manualNumberCgrState.marked);
  dot.classList.toggle("dot-green", !!manualNumberCgrState.marked);
  dot.classList.toggle("dot-amber", !manualNumberCgrState.marked);
  value.textContent = manualNumberCgrState.number;
}

async function loadManualNumberCgr(showNotice = false){
  try{
    const res = await fetch("/available-numbercgr");
    const json = await readJsonResponse(res);

    if(!res.ok || !json.ok){
      throw new Error(json.message || "Failed to load NumberCGRT");
    }

    if(!json.found){
      manualNumberCgrState = { number: "", marked: false, row: null };
      renderManualNumberCgr();
      if(showNotice){
        showAppNotice("No available NumberCGRT in חיפ_סמס", "info");
      }
      return;
    }

    manualNumberCgrState = {
      number: normalizePhoneWithZero(json.number),
      marked: Boolean(json.marked),
      row: json.row || null
    };
    renderManualNumberCgr();

    if(showNotice){
      showAppSuccess(`Loaded NumberCGRT ${manualNumberCgrState.number}`);
    }
  }catch(e){
    manualNumberCgrState = { number: "", marked: false, row: null };
    renderManualNumberCgr();
    showAppNotice(formatErrorMessage(e), "error");
  }
}

/* Duplicate handling (auto-uncheck) */
function validateNoDuplicatesBeforeExport(selected){
  function autoUncheckDuplicates(fieldName){
    const firstByKey = new Map();
    const removed = [];

    selected.forEach(item => {
      const raw = (item[fieldName] || "").trim();
      const key = raw.toLowerCase();
      if(!key) return;

      if(!firstByKey.has(key)){
        firstByKey.set(key, item);
      }else{
        removed.push({ value: raw, item, first: firstByKey.get(key), field: fieldName });
      }
    });

    removed.forEach(d => { d.item.checked = false; });
    return removed;
  }

  const removedDomain = autoUncheckDuplicates("domain");
  const removedDid = autoUncheckDuplicates("did");
  const allRemoved = [...removedDomain, ...removedDid];

  if(allRemoved.length === 0) return true;

  let msg = `נמצאו כפילויות.\nביטלתי סימון אוטומטית לשורות הכפולות (השארתי את הראשונה מסומנת).\n\n`;
  allRemoved.slice(0, 12).forEach((d, i) => {
    msg += `${i+1}) ${d.field.toUpperCase()} "${d.value}"\n   נשאר: ${d.first.name} (row ${d.first.sheet_row})\n   הוסר סימון: ${d.item.name} (row ${d.item.sheet_row})\n\n`;
  });
  if(allRemoved.length > 12){
    msg += `...ועוד ${allRemoved.length - 12} כפילויות.\n`;
  }

  alert(msg);
  renderTable();
  return true;
}

/* Mark done */
async function markDoneSelected(){

    const selected = getSelected();
  
    if(selected.length === 0){
      alert("לא נבחרו לקוחות.");
      return;
    }
  
    const customers = selected.map(x => ({
      sheet_row: x.sheet_row,
      name: x.name || "",
      domain: (x.domain || "").trim(),
      did: (x.did || "").trim(),
      cgr_row: x.cgr_row   // ✅ THIS IS THE FIX
    }));
  
    try{
  
      const res = await fetch('/mark-done', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ customers })
      });

      const json = await readJsonResponse(res);
  
      if(!res.ok || !json.ok){
        alert("שגיאה בעדכון סטטוס: " + (json.message || "Unknown"));
        return;
      }

      showAppSuccess(`עודכן ל"בוצע": ${json.updated} לקוחות`);
  
      await loadData();
  
    }catch(e){

      alert("שגיאה בעדכון סטטוס: " + formatErrorMessage(e));
  
    }
  
  }

/* Export CSV */
async function exportSelected(){
  let selected = getSelected();
  if(selected.length === 0){
    alert("לא נבחרו לקוחות.");
    return;
  }

  if(!validateSelectedForExport(selected)) return;

  validateNoDuplicatesBeforeExport(selected);

  selected = getSelected();
  if(selected.length === 0){
    alert("לא נשארו לקוחות מסומנים אחרי טיפול בכפילויות.");
    return;
  }

  const exportData = selected.map(x => ({
    Domain: (x.domain || "").trim(),
    DID: (x.did || "").trim(),
    NumberCGR: (x.numbercgr || "").trim(),
    cgr_row: x.cgr_row,
    Text: x.text || "",
    Name: x.name || "",
    sheet_row: x.sheet_row
  }));

  try{
    const res = await fetch('/export', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(exportData)
    });

    if(!res.ok){
      const j = await res.json().catch(()=>null);
      alert("שגיאה ביצוא: " + (j?.message || res.statusText));
      return;
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = "sms_export.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();

    setTimeout(() => window.URL.revokeObjectURL(url), 1000);

  }catch(e){
    alert("שגיאה ביצוא: " + e);
  }
}

/* Fireberry per-row */
async function fireberryFill(idx){
  const item = loadedData[idx];
  if(!item) return;

  const idnumber = (item.idnumber || "").trim();
  if(!idnumber){
    alert("אין ח.פ (עמודה B) ללקוח הזה בגוגל-שיט.");
    return;
  }

  if(item.fbLoading) return;
  item.fbLoading = true;
  renderTable();

  try{
    const res = await fetch('/fireberry-by-id', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ idnumber })
    });

    const json = await res.json().catch(()=>null);

    if(!res.ok || !json?.ok){
      alert("שגיאה ב-Fireberry: " + (json?.message || res.statusText));
      return;
    }

    if(!json.found){
      alert("לא נמצא לקוח ב-Fireberry לפי ח.פ (עמודה B).");
      return;
    }

      if((json.domain || "").trim()) item.domain = (json.domain || "").trim();
      if((json.did || "").trim()) item.did = (json.did || "").trim();
      refreshInforuSentFlag(item);

  }catch(e){
    alert("שגיאה ב-Fireberry: " + e);
  }finally{
    item.fbLoading = false;
    renderTable();
  }
}

/* Fireberry for ALL loaded customers */
async function fireberryFillAll(){
  if(!loadedData || loadedData.length === 0){
    alert("אין לקוחות טעונים. לחץ קודם על 'טען לקוחות ממתין'.");
    return;
  }

  if(!confirm(`למשוך Domain/DID מ-Fireberry עבור ${loadedData.length} לקוחות?`)) return;

  let okCount = 0;
  let notFoundCount = 0;
  let errorCount = 0;

  for(let i = 0; i < loadedData.length; i++){
    const item = loadedData[i];
    const idnumber = (item.idnumber || "").trim();

    if(!idnumber){
      notFoundCount++;
      continue;
    }

    item.fbLoading = true;
    renderTable();

    try{
      const res = await fetch('/fireberry-by-id', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ idnumber })
      });

      const json = await res.json().catch(()=>null);

      if(!res.ok || !json?.ok){
        errorCount++;
        continue;
      }

      if(!json.found){
        notFoundCount++;
        continue;
      }

      if((json.domain || "").trim()) item.domain = (json.domain || "").trim();
      if((json.did || "").trim()) item.did = (json.did || "").trim();
      refreshInforuSentFlag(item);

      okCount++;

    }catch(e){
      errorCount++;
    }finally{
      item.fbLoading = false;
      renderTable();
    }
  }

  alert(`סיום משיכה מ-Fireberry:\n✅ עודכנו: ${okCount}\n❌ לא נמצאו/אין ח.פ: ${notFoundCount}\n⚠ שגיאות: ${errorCount}`);
}

/* ================================
   INFORU MAIL
================================ */

async function sendInforuMail(){

    const selected = loadedData.filter(x => x.checked);
  
    if(selected.length === 0){
      alert("לא נבחרו לקוחות");
      return;
    }
  
    let dids = selected
      .map(x => (x.did || "").trim())
      .filter(x => x !== "");
  
    if(dids.length === 0){
      alert("יש לייבא DID מ-Fireberry לפני שליחה");
      return;
    }
  
    // remove duplicates
    dids = [...new Set(dids)];
  
    try{
  
      const res = await fetch("/send-inforu-mail",{
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body:JSON.stringify({dids})
      });
      const json = await readJsonResponse(res);
  
      if(!json.ok){
        showAppNotice(json.message || "Failed to send Inforu mail.", "error");
        return;
      }

      const sentNumbers = Array.isArray(json.numbers) ? json.numbers : [];
      sentNumbers.forEach(number => inforuSentNumbers.add(normalizeDidValue(number)));
      refreshAllInforuSentFlags();
      inforuLogEntries = [];
  
      renderTable();

      if(document.getElementById("inforuLogCard")?.style.display !== "none"){
        await openInforuLog(true);
      }

      showAppSuccess("Mail sent to inforu");
  
    }catch(e){
      showAppNotice(formatErrorMessage(e), "error");
    }
  
  }

/* ================================
   OPEN INFORU LOG
================================ */

function getFilteredInforuLogEntries(){
  if(!inforuLogSearchQuery){
    return inforuLogEntries;
  }

  return inforuLogEntries.filter(entry => {
    const did = normalizeDidValue(entry.did);
    const sentDate = String(entry.sent_date || "").toLowerCase();
    const source = String(entry.source || "").toLowerCase();
    return did.includes(inforuLogSearchQuery) || sentDate.includes(inforuLogSearchQuery) || source.includes(inforuLogSearchQuery);
  });
}

function buildInforuLogText(entries){
  return entries.map(entry => {
    const sentDate = entry.sent_date || "-";
    const source = entry.source || "supabase";
    const did = normalizeDidValue(entry.did) || "";
    return `${sentDate}\t${did}\t${source}`;
  }).join("\n");
}

function renderInforuLog(){
  const logCard = document.getElementById("inforuLogCard");
  const logList = document.getElementById("inforuLogList");
  const logSummary = document.getElementById("inforuLogSummary");
  const logEmpty = document.getElementById("inforuLogEmpty");
  if(!logCard || !logList || !logSummary || !logEmpty){
    return;
  }

  const filteredEntries = getFilteredInforuLogEntries();
  logSummary.textContent = `Total: ${inforuLogEntries.length} | Result: ${filteredEntries.length}`;
  logList.innerHTML = "";
  logCard.style.display = "block";

  if(!filteredEntries.length){
    logEmpty.style.display = "block";
    return;
  }

  logEmpty.style.display = "none";
  filteredEntries.forEach(entry => {
    const row = document.createElement("div");
    row.className = "inforu-log-row";
    row.innerHTML = `
      <span class="inforu-log-date">${escapeHtml(entry.sent_date || "-")}</span>
      <span class="inforu-log-did">${escapeHtml(normalizeDidValue(entry.did))}</span>
      <span class="inforu-log-source">${escapeHtml(entry.source || "supabase")}</span>
    `;
    logList.appendChild(row);
  });
}

function setInforuLogSearch(value){
  inforuLogSearchQuery = String(value ?? "").trim().toLowerCase();
  renderInforuLog();
}

async function hydrateInforuLogData(forceRefresh = false){
  if(!forceRefresh && inforuLogEntries.length){
    return;
  }

  const res = await fetch("/inforu-log-data");
  const json = await readJsonResponse(res);
  if(!res.ok || !json.ok){
    throw new Error(json.message || "Failed to load Inforu log");
  }

  inforuLogEntries = Array.isArray(json.entries) ? json.entries : [];
  setInforuSentNumbers(json.sent_numbers || []);
  refreshAllInforuSentFlags();
  renderTable();
}

async function openInforuLog(forceRefresh = false){

    try{
      await hydrateInforuLogData(forceRefresh);
      renderInforuLog();
    }catch(e){
      alert("שגיאה בטעינת הלוג: " + formatErrorMessage(e));
    }
  
  }
// Close log
function closeInforuLog(){

    const logCard = document.getElementById("inforuLogCard");
  
    if(logCard){
      logCard.style.display = "none";
    }
  
  }

/* ================================
   COPY LOG
================================ */

function copyInforuLog(){
  const text = buildInforuLogText(getFilteredInforuLogEntries());

  navigator.clipboard.writeText(text);

  alert("הטקסט הועתק");

}
/* ================================
   CREATE SMS
================================ */
function formatSmsResponse(response){
  if(response === undefined || response === null || response === "" || response === "Created"){
    return "";
  }

  if(typeof response === "string"){
    return response;
  }

  return JSON.stringify(response);
}

function formatSmsResultLine(result){
  const domain = (result.domain || "UNKNOWN").trim() || "UNKNOWN";

  if(result.success){
    return `✅ ${domain} Created`;
  }

  const message =
    (typeof result.message === "string" && result.message.trim())
      ? result.message.trim()
      : formatSmsResponse(result.response) || "API Error";

  return `❌ ${domain} Failed: ${message}`;
}

async function createSMS(){

    const selected = loadedData.filter(x => x.checked);
  
    if(selected.length === 0){
      alert("לא נבחרו לקוחות");
      return;
    }
  
    const customers = selected.map(x => ({
      domain: (x.domain || "").trim(),
      did: (x.did || "").trim(),
      numbercgr: (x.numbercgr || "").trim(),
      text: x.text || ""
    }));
  
    try{
  
      const res = await fetch("/create-sms",{
        method:"POST",
        headers:{
          "Content-Type":"application/json"
        },
        body:JSON.stringify({customers})
      });
  
      const json = await readJsonResponse(res);
  
      if(!json.ok){
        alert("API Error");
        return;
      }
  
      const lines = (json.results || []).map(formatSmsResultLine).filter(Boolean);

      if(lines.length){
        showAppSuccess(lines.join("\n"));
      }
  
    }catch(e){
  
      alert("Connection error: " + formatErrorMessage(e));
  
    }
  
  }

async function runMarkDoneStep(){
  const selected = getSelected();

  if(selected.length === 0){
    return { ok: false, message: "לא נבחרו לקוחות." };
  }

  const customers = selected.map(x => ({
    sheet_row: x.sheet_row,
    name: x.name || "",
    domain: (x.domain || "").trim(),
    did: (x.did || "").trim(),
    cgr_row: x.cgr_row
  }));

  try{
    const res = await fetch("/mark-done", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ customers })
    });

    const json = await readJsonResponse(res);

    if(!res.ok || !json.ok){
      return {
        ok: false,
        message: `שגיאה בעדכון סטטוס: ${json.message || "Unknown"}`
      };
    }

    await loadData();

    return {
      ok: true,
      message: `עודכן ל"בוצע": ${json.updated} לקוחות`
    };
  }catch(e){
    return {
      ok: false,
      message: `שגיאה בעדכון סטטוס: ${formatErrorMessage(e)}`
    };
  }
}

async function runInforuMailStep(){
  const selected = getSelectedSmsCustomers();

  if(selected.length === 0){
    return { ok: false, message: "לא נבחרו לקוחות" };
  }

  let dids = getNumericDidValues(selected);

  if(dids.length === 0){
    return {
      ok: true,
      skipped: true,
      message: "Inforu Mail skipped: no numeric DID"
    };
  }

  dids = [...new Set(dids)];
  const skippedDidCount = selected.length - dids.length;

  try{
    const res = await fetch("/send-inforu-mail", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dids })
    });
    const json = await readJsonResponse(res);

    if(!res.ok || !json.ok){
      return {
        ok: false,
        message: json.message || "Failed to send Inforu mail."
      };
    }

    const sentNumbers = Array.isArray(json.numbers) ? json.numbers : [];
    sentNumbers.forEach(number => inforuSentNumbers.add(normalizeDidValue(number)));
    refreshAllInforuSentFlags();
    inforuLogEntries = [];

    renderTable();

    if(document.getElementById("inforuLogCard")?.style.display !== "none"){
      await openInforuLog(true);
    }

    const added = Number(json.added || sentNumbers.length || dids.length);
    const messageParts = [`Mail sent to Inforu (${added})`];
    if(skippedDidCount > 0){
      messageParts.push(`Skipped non-numeric DID: ${skippedDidCount}`);
    }
    if(json.warning){
      messageParts.push(`Warning: ${json.warning}`);
    }
    const message = messageParts.join("\n");

    return {
      ok: true,
      message,
      numbers: sentNumbers
    };
  }catch(e){
    return {
      ok: false,
      message: formatErrorMessage(e)
    };
  }
}

async function runInforuMailStepForCustomers(customers){
  const normalizedCustomers = (Array.isArray(customers) ? customers : []).map(normalizeSmsCustomerInput);

  if(normalizedCustomers.length === 0){
    return { ok: false, message: "לא הוזנו נתונים ליצירה ידנית" };
  }

  let dids = getNumericDidValuesFromCustomers(normalizedCustomers);

  if(dids.length === 0){
    return {
      ok: true,
      skipped: true,
      message: "Inforu Mail skipped: no numeric DID"
    };
  }

  dids = [...new Set(dids)];
  const skippedDidCount = normalizedCustomers.length - dids.length;

  try{
    const res = await fetch("/send-inforu-mail", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dids })
    });
    const json = await readJsonResponse(res);

    if(!res.ok || !json.ok){
      return {
        ok: false,
        message: json.message || "Failed to send Inforu mail."
      };
    }

    const sentNumbers = Array.isArray(json.numbers) ? json.numbers : [];
    sentNumbers.forEach(number => inforuSentNumbers.add(normalizeDidValue(number)));

    const added = Number(json.added || sentNumbers.length || dids.length);
    const messageParts = [`Mail sent to Inforu (${added})`];
    if(skippedDidCount > 0){
      messageParts.push(`Skipped non-numeric DID: ${skippedDidCount}`);
    }
    if(json.warning){
      messageParts.push(`Warning: ${json.warning}`);
    }

    return {
      ok: true,
      message: messageParts.join("\n"),
      numbers: sentNumbers
    };
  }catch(e){
    return {
      ok: false,
      message: formatErrorMessage(e)
    };
  }
}

async function runCreateSmsStep(){
  const selected = getSelectedSmsCustomers();

  if(selected.length === 0){
    return { ok: false, message: "לא נבחרו לקוחות", lines: [] };
  }

  const customers = selected.map(x => ({
    domain: (x.domain || "").trim(),
    did: (x.did || "").trim(),
    numbercgr: (x.numbercgr || "").trim(),
    text: x.text || ""
  }));

  try{
    const res = await fetch("/create-sms", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ customers })
    });

    const json = await readJsonResponse(res);

    if(!res.ok || !json.ok){
      return { ok: false, message: json.message || "API Error", lines: [] };
    }

    const results = Array.isArray(json.results) ? json.results : [];
    const lines = results.map(formatSmsResultLine).filter(Boolean);
    const allSuccessful = results.length > 0 && results.every(result => result?.success);

    return {
      ok: allSuccessful,
      message: allSuccessful ? "Create SMS completed successfully" : (lines.join("\n") || "Create SMS failed"),
      lines,
      results
    };
  }catch(e){
    return {
      ok: false,
      message: "Connection error: " + formatErrorMessage(e),
      lines: []
    };
  }
}

async function runCreateSmsStepForCustomers(customers){
  const normalizedCustomers = (Array.isArray(customers) ? customers : []).map(normalizeSmsCustomerInput);

  if(normalizedCustomers.length === 0){
    return { ok: false, message: "לא הוזנו נתונים ליצירה ידנית", lines: [] };
  }

  if(normalizedCustomers.some(customer => !customer.domain || !customer.numbercgr)){
    return {
      ok: false,
      message: "יש למלא Domain ו-NumberCGRT לפני יצירה ידנית",
      lines: []
    };
  }

  try{
    const res = await fetch("/create-sms", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ customers: normalizedCustomers })
    });

    const json = await readJsonResponse(res);

    if(!res.ok || !json.ok){
      return { ok: false, message: json.message || "API Error", lines: [] };
    }

    const results = Array.isArray(json.results) ? json.results : [];
    const lines = results.map(formatSmsResultLine).filter(Boolean);
    const allSuccessful = results.length > 0 && results.every(result => result?.success);

    return {
      ok: allSuccessful,
      message: allSuccessful ? "Create SMS completed successfully" : (lines.join("\n") || "Create SMS failed"),
      lines,
      results
    };
  }catch(e){
    return {
      ok: false,
      message: "Connection error: " + formatErrorMessage(e),
      lines: []
    };
  }
}

async function reserveNumberCgrStepForCustomers(customers){
  const normalizedCustomers = (Array.isArray(customers) ? customers : []).map(normalizeSmsCustomerInput);

  if(normalizedCustomers.length === 0){
    return { ok: false, message: "לא הוזנו נתונים ליצירה ידנית" };
  }

  try{
    const res = await fetch("/reserve-numbercgr", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ customers: normalizedCustomers })
    });

    const json = await readJsonResponse(res);

    if(!res.ok || !json.ok){
      return {
        ok: false,
        message: json.message || "Failed to update חיפ_סמס"
      };
    }

    const missingNumbers = Array.isArray(json.missing_numbers) ? json.missing_numbers : [];
    const messageParts = [`Updated חיפ_סמס: ${Number(json.updated || 0)}`];
    if(missingNumbers.length){
      messageParts.push(`Numbers not found: ${missingNumbers.join(", ")}`);
    }

    return {
      ok: missingNumbers.length === 0,
      message: messageParts.join("\n")
    };
  }catch(e){
    return {
      ok: false,
      message: "Failed to update חיפ_סמס: " + formatErrorMessage(e)
    };
  }
}

async function markDoneSelected(){
  const result = await runMarkDoneStep();
  if(result.ok){
    showAppSuccess(result.message);
    return;
  }

  showAppNotice(result.message, "error");
}

async function sendInforuMail(){
  const result = await runInforuMailStep();
  if(result.ok){
    showAppSuccess(result.message);
    return;
  }

  showAppNotice(result.message, "error");
}

async function createSMS(){
  const result = await runCreateSmsStep();
  if(result.ok){
    if(result.lines.length){
      showAppSuccess(result.lines.join("\n"));
    }
    return;
  }

  showAppNotice(result.message, "error");
}

async function startCreateFlow(){
  const selected = getSelectedSmsCustomers();

  if(selected.length === 0){
    showAppNotice("לא נבחרו לקוחות", "error");
    return;
  }

  const stepResults = [];

  const inforuResult = await runInforuMailStep();
  stepResults.push(`1. Inforu Mail\n${inforuResult.message}`);
  if(!inforuResult.ok){
    showStartCreateNotice(
      `${buildStartCreateHeader(selected)}\n\n${stepResults.join("\n\n")}`,
      "error",
      selected
    );
    return;
  }

  const createResult = await runCreateSmsStep();
  stepResults.push(`2. Create SMS\n${createResult.lines.length ? createResult.lines.join("\n") : createResult.message}`);
  if(!createResult.ok){
    showStartCreateNotice(
      `${buildStartCreateHeader(selected)}\n\n${stepResults.join("\n\n")}`,
      "error",
      selected
    );
    return;
  }

  const markDoneResult = await runMarkDoneStep();
  stepResults.push(`3. Status Done\n${markDoneResult.message}`);

  showStartCreateNotice(
    `${buildStartCreateHeader(selected)}\n\n${stepResults.join("\n\n")}`,
    markDoneResult.ok ? "success" : "error",
    selected
  );
}

function getManualCustomerInput(){
  return normalizeSmsCustomerInput({
    domain: document.getElementById("manual-domain")?.value,
    did: document.getElementById("manual-did")?.value,
    numbercgr: manualNumberCgrState.number,
    text: document.getElementById("manual-text")?.value
  });
}

function clearManualCustomerInput(){
  ["manual-domain", "manual-did", "manual-text"].forEach(id => {
    const input = document.getElementById(id);
    if(input){
      input.value = "";
    }
  });
}

async function startManualCreateFlow(){
  const customer = getManualCustomerInput();

  if(!customer.domain || !customer.numbercgr){
    showAppNotice("יש למלא Domain ולטעון NumberCGRT מתוך חיפ_סמס ליצירה ידנית", "error");
    return;
  }

  const customers = [customer];
  const stepResults = [];

  const inforuResult = await runInforuMailStepForCustomers(customers);
  stepResults.push(`1. Inforu Mail\n${inforuResult.message}`);
  if(!inforuResult.ok){
    showCustomerFlowNotice(
      `${buildCustomerFlowHeader(customers)}\n\n${stepResults.join("\n\n")}`,
      "error",
      customers
    );
    return;
  }

  const createResult = await runCreateSmsStepForCustomers(customers);
  stepResults.push(`2. Create SMS\n${createResult.lines.length ? createResult.lines.join("\n") : createResult.message}`);

  if(!createResult.ok){
    showCustomerFlowNotice(
      `${buildCustomerFlowHeader(customers)}\n\n${stepResults.join("\n\n")}`,
      "error",
      customers
    );
    return;
  }

  const reserveResult = await reserveNumberCgrStepForCustomers(customers);
  stepResults.push(`3. חיפ_סמס\n${reserveResult.message}`);

  showCustomerFlowNotice(
    `${buildCustomerFlowHeader(customers)}\n\n${stepResults.join("\n\n")}`,
    reserveResult.ok ? "success" : "error",
    customers
  );

  if(createResult.ok && reserveResult.ok){
    clearManualCustomerInput();
    await loadManualNumberCgr();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.alert = (message) => showAppNotice(message, inferNoticeType(message));
  loadData();
  loadManualNumberCgr();
});

let loadedData = []; // {sheet_row, name, text, status, idnumber(hidden), domain, did, numbercgr, cgr_row, cgr_marked, checked}
let searchQuery = "";

const FIREBERRY_LOGO_URL = "https://app.fireberry.com/app/static/media/fireberry-logo.ebef34ab.svg";
const SMS_GUIDE_STEPS = {
  1: "Fireberry Sync לטעינת לקוחות.",
  2: "יש לבחור את הלקוח או הלקוחות לביצוע SMS ולסמן ב-V. אפשר לבחור את כלל הלקוחות בלחיצה על Select All.",
  3: "Inforu Mail שולח בקשת אימות לספק SMS באמצעות מייל מ-support@nimbusip.com. שירות SMS יעבוד אחרי הוספת זיהוי שולח בצד הספק. אחרי הודעת \"נשלח ל-Inforu\" אפשר להתקדם לשלב הבא.",
  4: "Create SMS שולח בקשה למערכת VOIPAPPZ ליצירת לקוח. יצירה למספר לקוחות יכולה לקחת 2-5 דקות, יש להמתין להודעת סיום. חשוב: אם קיים לקוח עם אותו שם או אותו NumberCGRT במערכת VOIPAPPZ תתקבל שגיאה ויש לשנות את שם הלקוח או את המספר.",
  5: "Status Done שולח דוח יצירה לגוגל: NumberCGRT עם מספר דומיין, תאריך יצירה, ומסמן את המספר בשימוש."
};

/* Helpers */
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
      const payload = await res.json().catch(() => {
        throw new Error("Server returned non-JSON response");
      });
      if(!res.ok || payload.ok === false){
        throw new Error(payload.message || res.statusText || "Load failed");
      }
      const data = Array.isArray(payload) ? payload : (payload.customers || []);
  
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
        checked: false,
        fbLoading: false
      }));
  
      renderTable();
    }catch(e){
      alert("שגיאה בטעינת נתונים: " + e);
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
       <input class="input ${item.inforu_sent ? 'did-sent' : ''}" placeholder="031234567"
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
  
      const json = await res.json();
  
      if(!res.ok || !json.ok){
        alert("שגיאה בעדכון סטטוס: " + (json.message || "Unknown"));
        return;
      }
  
      alert(`עודכן ל"בוצע": ${json.updated} לקוחות\nנרשם לוג ב: log/created.log`);
  
      await loadData();
  
    }catch(e){
  
      alert("שגיאה בעדכון סטטוס: " + e);
  
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
  
      const json = await res.json();
  
      if(!json.ok){
        alert(json.message);
        return;
      }
  
      // mark sent
      selected.forEach(row=>{
        row.inforu_sent = true;
      });
  
      renderTable();
  
      alert("נשלח אימות Inforu️✅");
  
    }catch(e){
      alert("שגיאה בשליחה: " + e);
    }
  
  }

/* ================================
   OPEN INFORU LOG
================================ */

async function openInforuLog(){

    try{
  
      const res = await fetch("/inforu-log");
      const text = await res.text();
  
      const logText = document.getElementById("inforuLogText");
      const logCard = document.getElementById("inforuLogCard");
  
      logText.textContent = text;
      logText.style.display = "block";
      logCard.style.display = "block";
  
    }catch(e){
      alert("שגיאה בטעינת הלוג");
    }
  
  }
// Close log
function closeInforuLog(){

    const logText = document.getElementById("inforuLogText");
    const logCard = document.getElementById("inforuLogCard");
  
    if(logText){
      logText.style.display = "none";
    }
  
    if(logCard){
      logCard.style.display = "none";
    }
  
  }

/* ================================
   COPY LOG
================================ */

function copyInforuLog(){

  const text = document.getElementById("inforuLogText").textContent;

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
  
      const json = await res.json();
  
      if(!json.ok){
        alert("API Error");
        return;
      }
  
      let successMsg = "";
      let errorMsg = "";
  
      json.results.forEach(r => {
        const responseText = formatSmsResponse(r.response);

        if(r.success){
          successMsg += responseText
            ? `✅ ${r.domain} Created\n${responseText}\n\n`
            : `✅ ${r.domain} Created\n`;
        }else{
          errorMsg += `❌ ${r.domain}\n${responseText || "API Error"}\n\n`;
        }
  
      });
  
      if(successMsg){
        alert(successMsg);
      }
  
      if(errorMsg){
        alert(errorMsg);
      }
  
    }catch(e){
  
      alert("Connection error: " + e);
  
    }
  
  }

document.addEventListener("DOMContentLoaded", () => {
  loadData();
});

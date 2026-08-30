const SPREADSHEET_ID = '1uwtREvtWENPabibI5FSlhdYokIbBs_kuZmYVeL-BgCQ';
const SHEET_NAME = 'SMS';
const BOT_SHEET_NAME = 'שירות מענה - בוט';
const F2M_SHEET_NAME = 'm2f / f2m';
const RECORDING_STORAGE_SHEET_NAME = 'איחסון הקלטות';
const HUMAN_SERVICE_SHEET_NAME = 'שירות מענה - אנושי';
const RECORDING_OPENING_SHEET_NAME = 'הקלטת פתיח - אולפן';

const FEATURE_STATUS_SERVICES = [
  { key: 'sms', label: 'SMS', sheet: SHEET_NAME, statusCol: 8 },
  { key: 'recording_opening', label: 'הקלטת פתיח', sheet: RECORDING_OPENING_SHEET_NAME, statusCol: 9 },
  { key: 'bot', label: 'שירות מענה - בוט', sheet: BOT_SHEET_NAME, statusCol: 8 },
  { key: 'human_service', label: 'שירות מענה - אנושי', sheet: HUMAN_SERVICE_SHEET_NAME, statusCol: 8 },
  { key: 'f2m', label: 'm2f / f2m', sheet: F2M_SHEET_NAME, statusCol: 8 },
  { key: 'recording_storage', label: 'איחסון הקלטות', sheet: RECORDING_STORAGE_SHEET_NAME, statusCol: 8 },
];

function normalizeCustomerId(value) {
  const digitsOnly = String(value || '').replace(/\D/g, '');
  if (!digitsOnly) return '';
  return digitsOnly.replace(/^0+/, '') || digitsOnly;
}

function collapseFeatureStatusEntries(entries) {
  if (!entries || !entries.length) return [];

  const filtered = entries
    .map((entry) => ({
      business_name: String(entry.business_name || '').trim(),
      customer_id: String(entry.customer_id || '').trim(),
      status: String(entry.status || '').trim() || 'לא הוגדר',
    }))
    .filter((entry) => entry.status !== 'כפילות');

  const sourceEntries = filtered.length ? filtered : [{
    business_name: String(entries[0].business_name || '').trim(),
    customer_id: String(entries[0].customer_id || '').trim(),
    status: 'לא הוגדר',
  }];
  const statuses = sourceEntries.map((entry) => entry.status);

  let finalStatus = 'לא הוגדר';
  if (statuses.indexOf('בוצע') !== -1) {
    finalStatus = 'בוצע';
  } else {
    const firstMeaningful = statuses.find((status) => status !== 'לא הוגדר');
    if (firstMeaningful) {
      finalStatus = firstMeaningful;
    }
  }

  const primaryEntry = sourceEntries.find((entry) => entry.status === finalStatus) || sourceEntries[0];
  return [{
    business_name: primaryEntry.business_name,
    customer_id: primaryEntry.customer_id,
    status: finalStatus,
  }];
}

function lookupFeatureStatusByCustomerId(customerId) {
  const normalizedCustomerId = normalizeCustomerId(customerId);
  if (!normalizedCustomerId) {
    throw new Error('יש להזין מספר ח.פ של העסק');
  }

  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const services = [];
  const businessNames = [];

  FEATURE_STATUS_SERVICES.forEach((config) => {
    const ws = spreadsheet.getSheetByName(config.sheet);
    const rows = ws ? ws.getDataRange().getDisplayValues() : [];
    let entries = [];

    rows.slice(1).forEach((row) => {
      const rowCustomerId = normalizeCustomerId(row[1] || '');
      if (rowCustomerId !== normalizedCustomerId) {
        return;
      }

      const businessName = String(row[0] || '').trim();
      const statusValue = String(row[config.statusCol - 1] || '').trim();
      const rowCustomerDisplay = String(row[1] || '').trim();

      if (businessName && businessNames.indexOf(businessName) === -1) {
        businessNames.push(businessName);
      }

      entries.push({
        business_name: businessName,
        customer_id: rowCustomerDisplay,
        status: statusValue || 'לא הוגדר',
      });
    });

    entries = collapseFeatureStatusEntries(entries);
    services.push({
      key: config.key,
      label: config.label,
      found: entries.length > 0,
      entry_count: entries.length,
      entries: entries,
    });
  });

  const foundCount = services.filter((service) => service.found).length;
  return {
    ok: true,
    customer_id: normalizedCustomerId,
    business_names: businessNames,
    services: services,
    found_count: foundCount,
    missing_count: services.length - foundCount,
  };
}

function outputJson(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

function outputJsonp(callbackName, payload) {
  return ContentService
    .createTextOutput(`${callbackName}(${JSON.stringify(payload)});`)
    .setMimeType(ContentService.MimeType.JAVASCRIPT);
}

function doGet(e) {
  try {
    const customerId = e && e.parameter ? e.parameter.customer_id : '';
    const callbackName = e && e.parameter ? e.parameter.callback : '';
    const payload = lookupFeatureStatusByCustomerId(customerId);
    if (callbackName) {
      return outputJsonp(callbackName, payload);
    }
    return outputJson(payload);
  } catch (err) {
    const payload = { ok: false, message: String(err.message || err) };
    const callbackName = e && e.parameter ? e.parameter.callback : '';
    if (callbackName) {
      return outputJsonp(callbackName, payload);
    }
    return outputJson(payload);
  }
}


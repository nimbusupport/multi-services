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

const FIREBERRY_API_BASE_URL = 'https://api.fireberry.com/api';
const FIREBERRY_ORDER_OBJECT_TYPE = 13;
const FIREBERRY_TOKEN_PROPERTY = 'FIREBERRY_TOKEN';
const FIREBERRY_SMS_ORDER_FIELD_PROPERTY = 'FIREBERRY_SMS_ORDER_FIELD';
const FIREBERRY_SMS_ACTIVE_STATUS_NAME_PROPERTY = 'FIREBERRY_SMS_ACTIVE_STATUS_NAME';
const FIREBERRY_SMS_ACTIVE_STATUS_CODE_PROPERTY = 'FIREBERRY_SMS_ACTIVE_STATUS_CODE';
const FIREBERRY_SMS_ORDER_FIELD_CANDIDATES = ['ordernumber', 'name'];
const FIREBERRY_SMS_ACTIVE_STATUS_NAME = 'לקוח פעיל';

const SMS_ORDER_NUMBER_COL = 5; // E
const SMS_ORDER_DATE_COL = 7; // G
const SMS_INSTALLED_MARKER_COL = 11; // K
const SMS_INSTALLED_MARKER_VALUE = 'לקוח הותקן';

function normalizeCustomerId(value) {
  const digitsOnly = String(value || '').replace(/\D/g, '');
  if (!digitsOnly) return '';
  return digitsOnly.replace(/^0+/, '') || digitsOnly;
}

function normalizeTextCompare_(value) {
  return String(value || '').trim().replace(/\s+/g, ' ').toLowerCase();
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

function getFireberrySmsSyncConfig_() {
  const props = PropertiesService.getScriptProperties();
  const token = String(props.getProperty(FIREBERRY_TOKEN_PROPERTY) || '').trim();
  const configuredOrderField = String(props.getProperty(FIREBERRY_SMS_ORDER_FIELD_PROPERTY) || '').trim();
  const configuredActiveStatusName = String(props.getProperty(FIREBERRY_SMS_ACTIVE_STATUS_NAME_PROPERTY) || '').trim();
  const configuredActiveStatusCode = String(props.getProperty(FIREBERRY_SMS_ACTIVE_STATUS_CODE_PROPERTY) || '').trim();

  return {
    token: token,
    objectType: FIREBERRY_ORDER_OBJECT_TYPE,
    orderFields: configuredOrderField ? [configuredOrderField] : FIREBERRY_SMS_ORDER_FIELD_CANDIDATES.slice(),
    activeStatusName: configuredActiveStatusName || FIREBERRY_SMS_ACTIVE_STATUS_NAME,
    activeStatusCode: configuredActiveStatusCode,
  };
}

function parseSheetDate_(value) {
  if (value instanceof Date && !isNaN(value.getTime())) {
    return new Date(value.getFullYear(), value.getMonth(), value.getDate());
  }

  const raw = String(value || '').trim();
  if (!raw) return null;

  const isoDate = new Date(raw);
  if (!isNaN(isoDate.getTime())) {
    return new Date(isoDate.getFullYear(), isoDate.getMonth(), isoDate.getDate());
  }

  const datePart = raw.split(' ')[0];
  const parts = datePart.split(/[./-]/);
  if (parts.length !== 3) return null;

  const first = parseInt(parts[0], 10);
  const second = parseInt(parts[1], 10);
  let year = parseInt(parts[2], 10);
  if (!first || !second || !year) return null;
  if (year < 100) year += 2000;

  let day = first;
  let month = second;
  if (first <= 12 && second > 12) {
    month = first;
    day = second;
  }

  const parsed = new Date(year, month - 1, day);
  if (isNaN(parsed.getTime())) return null;
  return parsed;
}

function getStartOfCurrentMonth_() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), 1);
}

function buildFireberrySmsQueryPayload_(fieldName, orderNumber, objectType) {
  return {
    objectType: objectType,
    fields: [
      { name: fieldName },
      { name: 'statuscode' },
    ],
    filter: [
      {
        type: 'AND',
        conditions: [
          {
            fieldName: fieldName,
            operator: 'eq',
            value: String(orderNumber),
          },
        ],
      },
    ],
    pageSize: 10,
    pageNumber: 1,
  };
}

function queryFireberryOrdersByField_(fieldName, orderNumber, config) {
  const response = UrlFetchApp.fetch(`${FIREBERRY_API_BASE_URL}/v3/query`, {
    method: 'post',
    contentType: 'application/json',
    muteHttpExceptions: true,
    headers: {
      tokenid: config.token,
      accept: 'application/json',
    },
    payload: JSON.stringify(buildFireberrySmsQueryPayload_(fieldName, orderNumber, config.objectType)),
  });

  const statusCode = response.getResponseCode();
  const bodyText = response.getContentText() || '';
  let body = {};
  try {
    body = JSON.parse(bodyText);
  } catch (err) {
    body = {};
  }

  if (statusCode >= 200 && statusCode < 300) {
    return {
      invalidField: false,
      records: Array.isArray(body.data) ? body.data : [],
    };
  }

  const message = String(body.message || body.Message || body.error || bodyText || '').trim();
  if (statusCode === 400 && /invalid field/i.test(message)) {
    return {
      invalidField: true,
      records: [],
    };
  }

  throw new Error(`Fireberry query failed for field ${fieldName}: ${statusCode} ${message}`);
}

function findFireberryOrderByNumber_(orderNumber, config) {
  let invalidFieldCount = 0;

  for (let i = 0; i < config.orderFields.length; i += 1) {
    const fieldName = config.orderFields[i];
    const result = queryFireberryOrdersByField_(fieldName, orderNumber, config);
    if (result.invalidField) {
      invalidFieldCount += 1;
      continue;
    }

    if (result.records.length) {
      PropertiesService.getScriptProperties().setProperty(FIREBERRY_SMS_ORDER_FIELD_PROPERTY, fieldName);
      return {
        fieldName: fieldName,
        records: result.records,
      };
    }
  }

  if (invalidFieldCount === config.orderFields.length) {
    throw new Error('לא נמצא שדה תקין למספר הזמנה ב-Fireberry. יש להגדיר Script Property בשם FIREBERRY_SMS_ORDER_FIELD.');
  }

  return null;
}

function isFireberryRecordActive_(record, config) {
  const statusName = normalizeTextCompare_(record && record.statuscodename);
  const expectedStatusName = normalizeTextCompare_(config.activeStatusName);
  if (expectedStatusName && statusName === expectedStatusName) {
    return true;
  }

  const expectedStatusCode = String(config.activeStatusCode || '').trim();
  const statusCode = String(record && record.statuscode || '').trim();
  if (expectedStatusCode && statusCode === expectedStatusCode) {
    return true;
  }

  return false;
}

function syncSmsInstalledCustomersFromFireberry() {
  const config = getFireberrySmsSyncConfig_();
  if (!config.token) {
    throw new Error('חסר Fireberry token. יש להגדיר Script Property בשם FIREBERRY_TOKEN.');
  }

  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sheet = spreadsheet.getSheetByName(SHEET_NAME);
  if (!sheet) {
    throw new Error('גיליון SMS לא נמצא.');
  }

  const lastRow = sheet.getLastRow();
  if (lastRow <= 1) {
    return { ok: true, scanned: 0, updated: 0, skipped: 0 };
  }

  const startOfMonth = getStartOfCurrentMonth_();
  const numRows = lastRow - 1;
  const lastCol = Math.max(SMS_INSTALLED_MARKER_COL, SMS_ORDER_DATE_COL, SMS_ORDER_NUMBER_COL);
  const values = sheet.getRange(2, 1, numRows, lastCol).getValues();
  const installedValues = sheet.getRange(2, SMS_INSTALLED_MARKER_COL, numRows, 1).getValues();

  const pendingRows = [];
  const uniqueOrderNumbers = {};
  let skippedRows = 0;

  for (let index = 0; index < values.length; index += 1) {
    const row = values[index];
    const installedMarker = String(installedValues[index][0] || '').trim();
    if (installedMarker) {
      skippedRows += 1;
      continue;
    }

    const orderDate = parseSheetDate_(row[SMS_ORDER_DATE_COL - 1]);
    if (!orderDate || orderDate < startOfMonth) {
      skippedRows += 1;
      continue;
    }

    const orderNumber = String(row[SMS_ORDER_NUMBER_COL - 1] || '').trim();
    if (!orderNumber) {
      skippedRows += 1;
      continue;
    }

    pendingRows.push({
      rowIndex: index,
      sheetRow: index + 2,
      orderNumber: orderNumber,
    });
    uniqueOrderNumbers[orderNumber] = true;
  }

  const orderStatusCache = {};
  const orderNumbers = Object.keys(uniqueOrderNumbers);
  orderNumbers.forEach((orderNumber) => {
    orderStatusCache[orderNumber] = findFireberryOrderByNumber_(orderNumber, config);
  });

  let updatedRows = 0;
  pendingRows.forEach((entry) => {
    const lookupResult = orderStatusCache[entry.orderNumber];
    if (!lookupResult || !lookupResult.records || !lookupResult.records.length) {
      return;
    }

    const hasActiveRecord = lookupResult.records.some((record) => isFireberryRecordActive_(record, config));
    if (!hasActiveRecord) {
      return;
    }

    installedValues[entry.rowIndex][0] = SMS_INSTALLED_MARKER_VALUE;
    updatedRows += 1;
  });

  if (updatedRows > 0) {
    sheet.getRange(2, SMS_INSTALLED_MARKER_COL, numRows, 1).setValues(installedValues);
  }

  return {
    ok: true,
    scanned: pendingRows.length,
    updated: updatedRows,
    skipped: skippedRows,
    checked_orders: orderNumbers.length,
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

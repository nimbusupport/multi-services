const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, 'template/support_tickets.js'), 'utf8');
const start = source.indexOf('async function saveTicketDetailWithFeedback(');
const saveHandler = source.slice(start, source.indexOf('\nfunction showTicketDetail(', start));
const longSummary = ('\u05e1\u05d9\u05db\u05d5\u05dd \u05d1\u05d9\u05e7\u05d5\u05e8: WIFI 100/100 MB; RJ45\n').repeat(100).trim();

test('ticket searches load all months while the default view loads the current month', () => {
  const context = {};
  vm.createContext(context);
  const functionStart = source.indexOf('function shouldStageTicketLoading(');
  vm.runInContext(source.slice(functionStart, source.indexOf('\nasync function fetchTicketsPayload(', functionStart)), context);
  assert.equal(context.shouldStageTicketLoading({ search: 'terminal' }), false);
  assert.equal(context.shouldStageTicketLoading({ search: '  terminal  ' }), false);
  assert.equal(context.shouldStageTicketLoading({ search: '' }), true);
  assert.equal(context.shouldStageTicketLoading({ search: '  ' }), true);
  assert.equal(context.shouldStageTicketLoading({ date_from: '2026-10-01' }), false);
});

test('visit range selects two hours and preserves an existing visit until its start changes', () => {
  const startField = { value: '09:00' };
  const endField = { value: '' };
  const context = { document: { getElementById: id => id.endsWith('-from') ? startField : endField } };
  vm.createContext(context);
  const hoursStart = source.indexOf('function timeLabel(');
  const syncStart = source.indexOf('function syncPaisDetailVisitRange(');
  vm.runInContext(source.slice(hoursStart, source.indexOf('\nfunction priorityClass(', hoursStart)), context);
  vm.runInContext(source.slice(syncStart, source.indexOf('\nasync function savePaisDetail(', syncStart)), context);
  context.syncPaisDetailVisitRange();
  assert.equal(endField.value, '11:00');
  startField.value = '16:00';
  context.syncPaisDetailVisitRange(true);
  assert.equal(endField.value, '18:00');
  startField.value = '09:00';
  endField.value = '10:00';
  context.syncPaisDetailVisitRange();
  assert.equal(endField.value, '10:00');
  context.syncPaisDetailVisitRange(true);
  assert.equal(endField.value, '11:00');
  startField.value = '';
  context.syncPaisDetailVisitRange(true);
  assert.equal(endField.value, '');
  assert.match(context.hourOptions(11, 18, '10:00'), /value="10:00" selected/);
});

for (const board of ['pais', 'hot-kiryot', 'support']) {
  for (const status of ['תואם', 'נכשל']) {
    test(`${board}: Nastya replaces a technician directly and requests the new coordination email from ${status}`, async () => {
      let sentPayload;
      const ticket = { id: 2, board_slug: board, status, details: {
        coordinated_worker: 'גולן', visit_date: '2026-11-08', visit_hour_from: '09:00', visit_hour_to: '10:00',
      } };
      const fields = {
        'detail-coordinated-worker': { value: 'אסף' },
        'detail-visit-date': { value: '2026-11-09' },
        'detail-visit-hour-from': { value: '09:00' },
        'detail-visit-hour-to': { value: '11:00' },
        'detail-status-select': { value: status },
      };
      const context = {
        document: { getElementById: id => fields[id] || null },
        getTicket: () => ticket, ticketDetails: value => value.details,
        canEditExistingTickets: true, canAssignedTechnicianEditTicket: () => false,
        isHotTicket: value => value.board_slug === 'hot-kiryot',
        COORDINATION_FINAL_STATUSES: ['נכשל', 'בוצע', 'בוטל'],
        pageMode: 'nastia', ticketQueue: 'nastia', isNastyaQueuePage: true,
        selectedSupportServiceMode: () => '', selectedSupportCustomerType: () => '',
        clearCoordinationValidation() {}, setDetailSaveMessageState() {},
        normalizeLegacyHebrewData: value => value,
        async fetch(url, options) {
          sentPayload = JSON.parse(options.body);
          return { ok: true, json: async () => ({ ok: true, ticket: { notification_sent: true } }) };
        },
        showSendSuccessToast() {}, async waitForUi() {}, closeTicketDetail() {},
        async loadTickets() {}, async loadPaisReport() {},
        openNotificationErrorModal(message) { throw new Error(message); },
      };
      vm.createContext(context);
      vm.runInContext(saveHandler, context);
      await context.saveTicketDetailWithFeedback(2);
      assert.equal(sentPayload.status, 'תואם');
      assert.equal(sentPayload.details.coordinated_worker, 'אסף');
      assert.equal(sentPayload.details.visit_date, '2026-11-09');
      assert.equal(sentPayload.send_nastia_notification, true);
      assert.equal(sentPayload.send_nastia_cancellation_notification, undefined);
    });
  }
}

test('Nimbus dashboard offers coordination statuses and its card wires up saving and scheduling', () => {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      listeners: {}, dataset: {}, classList: { add() {}, remove() {} },
      addEventListener(event, handler) { this.listeners[event] = handler; },
      replaceChildren() {}, append() {}, closest() { return null; },
      querySelectorAll() { return []; }, reset() {}, setAttribute() {},
    });
    return elements.get(id);
  }
  let savedId;
  const context = {
    document: { getElementById: element, querySelectorAll: () => [] },
    canEditExistingTickets: true, isAssignedTechnicianMode: false,
    isNastyaQueuePage: false, pageMode: 'board',
    isAdmin: true, canUploadTicketAttachments: true,
    canManageExistingTicketAttachments: true, canDeleteTicketAttachments: true,
    paisStatuses: ['ממתין', 'ממתין לתיאום', 'תואם', 'בוצע'],
    supportStatuses: ['Waiting', 'Done'], technicianUsers: ['אסף'],
    canAssignedTechnicianEditTicket: () => false,
    canSetCancelledStatus: () => true, normalizePendingStatus: value => value,
    ticketDetails: ticket => ticket.details,
    isPaisTicket: () => false, isHotTicket: () => false,
    boardDisplayName: () => 'נימבוס', escapeHtml: value => String(value),
    detailItem: () => '', detailItemHtml: () => '', renderAddressValue: value => value,
    supportServiceModeEditor: () => '', coordinationCancelButton: () => '', hourOptions: () => '',
    clearCoordinationValidation() {}, setupServiceModeSelectors() {},
    syncPaisDetailStatusFields() {}, syncPaisDetailVisitRange() {},
    toggleSupportServiceDetails() {}, syncDetailAttachmentInputState() {},
    setInlineMessageState() {}, saveTicketDetailWithFeedback: id => { savedId = id; },
  };
  vm.createContext(context);
  for (const [name, nextName] of [
    ['boardSupportsCoordination', 'boardSupportsReport'],
    ['isCoordinationTicket', 'isPaisTicket'],
    ['availablePaisStatusesForCurrentUser', 'coordinationFinalStatusesForCurrentUser'],
    ['displayTicketStatus', 'statusOptionsForTicket'],
    ['statusOptionsForTicket', 'canNastyaEditPaisInlineStatus'],
    ['coordinationSchedulingEditor', 'renderHotDetailSections'],
    ['showTicketDetail', 'setTicketDetailLoading'],
  ]) {
    const functionStart = source.lastIndexOf(`function ${name}(`);
    vm.runInContext(source.slice(functionStart, source.indexOf(`\nfunction ${nextName}(`, functionStart)), context);
  }
  const ticket = { id: 12, board_slug: 'support', status: 'ממתין', details: {}, attachments: [] };
  const options = context.statusOptionsForTicket(ticket);
  assert.match(options, /value="ממתין" selected/);
  assert.match(options, /value="ממתין לתיאום"/);
  assert.match(options, /value="תואם"/);
  context.renderDetailSections = () => '';
  context.showTicketDetail(ticket);
  assert.equal(typeof element('detail-status-select').listeners.change, 'function');
  element('detail-save-btn').listeners.click();
  assert.equal(savedId, ticket.id);
  ticket.status = 'ממתין לתיאום';
  const scheduling = context.coordinationSchedulingEditor(ticket, ticket.details);
  assert.match(scheduling, /id="detail-coordinated-worker"/);
  assert.match(scheduling, /value="אסף"/);
  assert.match(scheduling, /id="detail-visit-date"/);
});

test('a response missing the saved summary keeps the editor open and preserves the text', async () => {
  let closed = false;
  let errorMessage = '';
  const field = { value: longSummary };
  const context = {
    document: { getElementById: id => id === 'detail-visit-summary' ? field : null },
    getTicket: () => ({ id: 2, board_slug: 'hot-kiryot', details: {} }),
    canEditExistingTickets: true, canAssignedTechnicianEditTicket: () => false,
    ticketDetails: ticket => ticket.details, isHotTicket: () => true,
    COORDINATION_FINAL_STATUSES: [], pageMode: '', ticketQueue: '', isNastyaQueuePage: false,
    clearCoordinationValidation() {}, setDetailSaveMessageState() {},
    normalizeLegacyHebrewData: value => value,
    async fetch() { return { ok: true, json: async () => ({ ok: true, ticket: { details: {} } }) }; },
    openNotificationErrorModal: message => { errorMessage = message; },
    async waitForUi() {}, closeTicketDetail: () => { closed = true; },
    async loadTickets() {}, async loadPaisReport() {},
  };
  vm.createContext(context);
  vm.runInContext(saveHandler, context);
  await context.saveTicketDetailWithFeedback(2);
  assert.equal(closed, false);
  assert.equal(field.value, longSummary);
  assert.match(errorMessage, /visit summary was not saved/);
});

for (const board of ['hot-kiryot', 'pais', 'support']) {
  for (const technicianMode of [false, true]) {
    for (const summary of [longSummary, '']) {
      test(`${board}: ${technicianMode ? 'technician' : 'editor'} saves ${summary ? 'long' : 'cleared'} visit summary`, async () => {
        let sentPayload;
        const ticket = { id: 2, board_slug: board, details: { visit_summary: 'previous summary' } };
        const fields = {
          'detail-visit-summary': { value: summary },
          'detail-status-select': { value: 'done' },
        };
        const context = {
          document: { getElementById: id => fields[id] || null },
          getTicket: () => ticket,
          canEditExistingTickets: !technicianMode,
          canAssignedTechnicianEditTicket: () => technicianMode,
          ticketDetails: value => value.details,
          isHotTicket: value => value.board_slug === 'hot-kiryot',
          COORDINATION_FINAL_STATUSES: ['done'],
          pageMode: '', ticketQueue: '', isNastyaQueuePage: false,
          selectedSupportServiceMode: () => '', selectedSupportCustomerType: () => '',
          clearCoordinationValidation() {}, setDetailSaveMessageState() {},
          normalizeLegacyHebrewData: value => value,
          async fetch(url, options) {
            assert.equal(url, '/support-tickets-update');
            sentPayload = JSON.parse(options.body);
            return { ok: true, json: async () => ({ ok: true, ticket: { details: { visit_summary: summary } } }) };
          },
          async waitForUi() {}, closeTicketDetail() {}, async loadTickets() {}, async loadPaisReport() {},
          openNotificationErrorModal(message) { throw new Error(message); },
        };
        vm.createContext(context);
        vm.runInContext(saveHandler, context);
        await context.saveTicketDetailWithFeedback(2);
        assert.equal(sentPayload.details.visit_summary, summary);
      });
    }
  }
}

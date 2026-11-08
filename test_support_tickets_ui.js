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

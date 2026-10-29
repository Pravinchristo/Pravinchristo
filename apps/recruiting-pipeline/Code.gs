/**
 * Recruiting Pipeline: Google Sheets + Gmail, run from the owner's Google account.
 *
 * Bind this script to the tracker spreadsheet (Extensions > Apps Script), paste this
 * file in, then run setup() once. Everything else runs on triggers that setup() installs.
 *
 * Ways records come in:
 *   1. Google Form "Log a candidate" (created by setup) -> handleFormSubmit
 *   2. Email to the owner's intake plus-address       -> processIntake (every 15 min)
 *   3. Typing or pasting straight into a requirement tab  -> handleEdit
 * Every path goes through the same duplicate check before a row is kept.
 */

const APP = {
  TEAM: 'Team',
  SETTINGS: 'Settings',
  REQS: 'Requirements',
  ALL: '_All Candidates',
  DASH: 'Dashboard',
  LOG: '_Log',
  FORM_RESPONSES: '_Form Responses',
  LABEL_ROOT: 'Recruiting',
  LABEL_INTAKE: 'Recruiting/Intake',
  LABEL_DONE: 'Recruiting/Logged',
  LABEL_FIX: 'Recruiting/Needs Fix',
};

// One column layout shared by every requirement tab. Add new columns at the end only.
const COLS = [
  'Candidate ID', 'Requirement', 'Date Sourced', 'Recruiter', 'Candidate Name',
  'Email', 'Phone', 'LinkedIn URL', 'Current Title', 'Current Company', 'Location',
  'Source', 'Status', 'Last Contacted', 'Next Action Date', 'Notes', 'Dedupe Key',
  'Entry Method',
];
const IX = {};
COLS.forEach((h, i) => { IX[h] = i; });
const col = h => IX[h] + 1;

const STATUSES = [
  'Sourced', 'Contacted', 'Replied', 'Screening', 'Submitted', 'Interviewing',
  'Offer', 'Hired', 'Not Interested', 'Rejected', 'On Hold',
];
const CONTACTED_PLUS = STATUSES.filter(s => s !== 'Sourced');
const REPLIED_PLUS = ['Replied', 'Screening', 'Submitted', 'Interviewing', 'Offer', 'Hired', 'Not Interested', 'Rejected'];
const CLOSED = ['Hired', 'Not Interested', 'Rejected'];
const SOURCES = ['LinkedIn', 'Naukri', 'Referral', 'GitHub', 'Job board', 'Internal database', 'Event', 'Other'];

const SET = {
  OWNER: 'Owner email',
  INTAKE: 'Intake address',
  FOLLOW_UP_DAYS: 'Follow-up after (days)',
  DIGEST_HOUR: 'Daily digest hour (0-23)',
  REMINDERS: 'Send recruiter reminders (Y/N)',
};

const FORM_Q = {
  recruiter: 'Recruiter', requirement: 'Requirement', name: 'Candidate name',
  email: 'Email', phone: 'Phone', linkedin: 'LinkedIn URL', title: 'Current title',
  company: 'Current company', location: 'Location', source: 'Source',
  status: 'Status', notes: 'Notes for Pravin',
};

// ---------------------------------------------------------------- menu & setup

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Recruiting')
    .addItem('Add requirement…', 'addRequirement')
    .addItem('Process Gmail intake now', 'processIntake')
    .addItem('Send digest and reminders now', 'dailyJobs')
    .addSeparator()
    .addItem('Run setup / repair', 'setup')
    .addToUi();
}

function setup() {
  const ss = SpreadsheetApp.getActive();
  ensureConfigSheets_(ss);
  syncRequirementTabs_(ss);
  rebuildAllCandidates_(ss);
  buildDashboard_(ss);
  ensureForm_(ss);
  ensureLabels_();
  installTriggers_(ss);
  removeBlankDefaultSheet_(ss);
  ss.setActiveSheet(ss.getSheetByName(APP.DASH));
  const form = FormApp.openById(PropertiesService.getScriptProperties().getProperty('FORM_ID'));
  toast_(ss, 'Setup complete. Form link for recruiters: ' + form.getPublishedUrl());
  Logger.log('Form link for recruiters: %s', form.getPublishedUrl());
}

function addRequirement() {
  const ss = SpreadsheetApp.getActive();
  const ui = SpreadsheetApp.getUi();
  const res = ui.prompt('New requirement', 'Requirement title (this becomes the tab name):', ui.ButtonSet.OK_CANCEL);
  if (res.getSelectedButton() !== ui.Button.OK) return;
  const title = res.getResponseText().trim();
  if (!title) return;
  const reqSheet = ss.getSheetByName(APP.REQS);
  const ids = getRequirements_(ss, true).map(r => parseInt(String(r.id).replace(/\D/g, ''), 10) || 0);
  const next = 'REQ-' + String((ids.length ? Math.max.apply(null, ids) : 0) + 1).padStart(2, '0');
  reqSheet.appendRow([next, title, '', '', 'Open', new Date()]);
  syncRequirementTabs_(ss);
  rebuildAllCandidates_(ss);
  refreshFormChoices_(ss);
  ui.alert(`Added ${next}: ${title}. Its tab, the form dropdown and the dashboard are updated.`);
}

function ensureConfigSheets_(ss) {
  const owner = Session.getEffectiveUser().getEmail();
  ensureSheet_(ss, APP.TEAM, ['Recruiter', 'Email', 'Active (Y/N)'], [
    ['John', 'john@example.com', 'Y'],
    ['Maria', 'maria@example.com', 'Y'],
    ['Izel', 'izel@example.com', 'Y'],
  ]);
  ensureSheet_(ss, APP.REQS, ['Req ID', 'Requirement Title', 'Tab Name', 'Hiring Manager', 'Status (Open/Closed)', 'Created'], [
    ['REQ-01', 'Client Partner - GCC', '', '', 'Open', new Date()],
    ['REQ-02', 'OTT Test Engineer', '', '', 'Open', new Date()],
    ['REQ-03', 'SDET - Automation', '', '', 'Open', new Date()],
  ]);
  ensureSheet_(ss, APP.SETTINGS, ['Setting', 'Value'], [
    [SET.OWNER, owner],
    [SET.INTAKE, owner.replace('@', '+intake@')],
    [SET.FOLLOW_UP_DAYS, 4],
    [SET.DIGEST_HOUR, 8],
    [SET.REMINDERS, 'Y'],
  ]);
  ensureSheet_(ss, APP.LOG, ['Timestamp', 'Event', 'Requirement', 'Recruiter', 'Candidate', 'Detail', 'Message ID'], []);
}

function ensureSheet_(ss, name, headers, seedRows) {
  let sh = ss.getSheetByName(name);
  if (sh) return sh;
  sh = ss.insertSheet(name);
  sh.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold').setBackground('#e8eaed');
  if (seedRows.length) sh.getRange(2, 1, seedRows.length, headers.length).setValues(seedRows);
  sh.setFrozenRows(1);
  sh.autoResizeColumns(1, headers.length);
  return sh;
}

function syncRequirementTabs_(ss) {
  const reqSheet = ss.getSheetByName(APP.REQS);
  const used = new Set(ss.getSheets().map(s => s.getName()));
  getRequirements_(ss, true).forEach(r => {
    let tab = r.tab;
    if (!tab) {
      tab = uniqueTabName_(r.title, used);
      reqSheet.getRange(r.row, 3).setValue(tab);
    }
    used.add(tab);
    if (!ss.getSheetByName(tab)) formatRequirementTab_(ss, ss.insertSheet(tab));
    if (!r.created) reqSheet.getRange(r.row, 6).setValue(new Date());
  });
}

function uniqueTabName_(title, used) {
  const base = String(title).replace(/[\[\]\*\?:\/\\']/g, '-').replace(/\s+/g, ' ').trim().slice(0, 90) || 'Requirement';
  let name = base;
  for (let n = 2; used.has(name) || name.startsWith('_') || Object.values(APP).includes(name); n++) name = `${base} (${n})`;
  return name;
}

function formatRequirementTab_(ss, sh) {
  const rows = sh.getMaxRows() - 1;
  sh.getRange(1, 1, 1, COLS.length).setValues([COLS])
    .setFontWeight('bold').setBackground('#1a73e8').setFontColor('#ffffff');
  sh.setFrozenRows(1);
  sh.setFrozenColumns(col('Candidate Name'));
  const team = ss.getSheetByName(APP.TEAM).getRange('A2:A100');
  sh.getRange(2, col('Recruiter'), rows).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInRange(team, true).setAllowInvalid(false).build());
  sh.getRange(2, col('Status'), rows).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(STATUSES, true).setAllowInvalid(false).build());
  sh.getRange(2, col('Source'), rows).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(SOURCES, true).setAllowInvalid(true).build());
  ['Date Sourced', 'Last Contacted', 'Next Action Date'].forEach(h => {
    sh.getRange(2, col(h), rows).setNumberFormat('dd mmm yyyy')
      .setDataValidation(SpreadsheetApp.newDataValidation().requireDate().setAllowInvalid(false).build());
  });
  const statusCol = colLetter_(col('Status'));
  const dim = SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied(`=OR($${statusCol}2="Not Interested",$${statusCol}2="Rejected")`)
    .setFontColor('#80868b').setRanges([sh.getRange(2, 1, rows, COLS.length)]).build();
  const won = SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied(`=OR($${statusCol}2="Offer",$${statusCol}2="Hired")`)
    .setBackground('#e6f4ea').setRanges([sh.getRange(2, 1, rows, COLS.length)]).build();
  sh.setConditionalFormatRules([dim, won]);
  sh.hideColumns(col('Dedupe Key'));
  sh.getRange(1, 1, 1, COLS.length).protect().setDescription('Header row: shared layout').setWarningOnly(true);
  sh.autoResizeColumns(1, COLS.length);
}

/** Stacks every requirement tab into one read-only view. The dashboard reads only this sheet. */
function rebuildAllCandidates_(ss) {
  const sh = ss.getSheetByName(APP.ALL) || ss.insertSheet(APP.ALL);
  sh.clear();
  sh.getRange(1, 1, 1, COLS.length).setValues([COLS]).setFontWeight('bold').setBackground('#e8eaed');
  sh.setFrozenRows(1);
  const last = colLetter_(COLS.length);
  const parts = getRequirements_(ss, true).map(r => `${quoteSheet_(r.tab)}!A2:${last}`);
  if (parts.length) {
    sh.getRange('A2').setFormula(
      `=IFERROR(QUERY({${parts.join(';')}},"select * where Col${col('Candidate Name')} is not null",0),"")`);
  }
  sh.getRange(2, col('Date Sourced'), sh.getMaxRows() - 1).setNumberFormat('dd mmm yyyy');
  sh.getRange(2, col('Last Contacted'), sh.getMaxRows() - 1, 2).setNumberFormat('dd mmm yyyy');
  const p = sh.protect().setDescription('Built automatically from the requirement tabs: edit those instead');
  p.setWarningOnly(true);
}

// ---------------------------------------------------------------- dashboard

function buildDashboard_(ss) {
  const sh = ss.getSheetByName(APP.DASH) || ss.insertSheet(APP.DASH, 0);
  sh.getCharts().forEach(c => sh.removeChart(c));
  sh.clear();
  const all = quoteSheet_(APP.ALL);
  const data = `${all}!A2:${colLetter_(COLS.length)}`;
  const r = h => `${all}!${colLetter_(col(h))}2:${colLetter_(col(h))}`;
  const L = h => colLetter_(col(h)); // QUERY over a plain range uses column letters
  const list = arr => '{' + arr.map(s => `"${s}"`).join(',') + '}';

  sh.getRange('A1').setValue('Recruiting Pipeline Dashboard').setFontSize(18).setFontWeight('bold');
  sh.getRange('A2').setValue('Live from every requirement tab. Re-run "Run setup / repair" after adding a recruiter.')
    .setFontColor('#5f6368');

  const kpis = [
    ['Candidates sourced (all time)', `=COUNTA(${r('Candidate Name')})`, '0'],
    ['Sourced in the last 7 days', `=COUNTIFS(${r('Date Sourced')},">="&(TODAY()-6))`, '0'],
    ['Active in pipeline', `=SUMPRODUCT((${r('Candidate Name')}<>"")*ISNA(MATCH(${r('Status')},${list(CLOSED)},0)))`, '0'],
    ['Submitted or further', `=SUMPRODUCT(--ISNUMBER(MATCH(${r('Status')},${list(['Submitted', 'Interviewing', 'Offer', 'Hired'])},0)))`, '0'],
    ['Candidate reply rate', `=IFERROR(SUMPRODUCT(--ISNUMBER(MATCH(${r('Status')},${list(REPLIED_PLUS)},0)))/SUMPRODUCT(--ISNUMBER(MATCH(${r('Status')},${list(CONTACTED_PLUS)},0))),0)`, '0%'],
    ['Duplicates blocked (last 30 days)', `=COUNTIFS(${quoteSheet_(APP.LOG)}!B2:B,"Duplicate blocked",${quoteSheet_(APP.LOG)}!A2:A,">="&(TODAY()-29))`, '0'],
  ];
  kpis.forEach((k, i) => {
    sh.getRange(4 + i, 1).setValue(k[0]);
    sh.getRange(4 + i, 2).setFormula(k[1]).setNumberFormat(k[2]).setFontWeight('bold');
  });

  const block = (row, title, formula) => {
    sh.getRange(row, 1).setValue(title).setFontWeight('bold').setFontSize(12);
    sh.getRange(row + 1, 1).setFormula(formula);
  };
  block(12, 'Sourced per recruiter',
    `=IFERROR(QUERY(${data},"select ${L('Recruiter')}, count(${L('Candidate Name')}) where ${L('Candidate Name')} is not null group by ${L('Recruiter')} order by count(${L('Candidate Name')}) desc label ${L('Recruiter')} 'Recruiter', count(${L('Candidate Name')}) 'Sourced'",0),"No data yet")`);
  block(26, 'Sourced per requirement',
    `=IFERROR(QUERY(${data},"select ${L('Requirement')}, count(${L('Candidate Name')}) where ${L('Candidate Name')} is not null group by ${L('Requirement')} order by count(${L('Candidate Name')}) desc label ${L('Requirement')} 'Requirement', count(${L('Candidate Name')}) 'Sourced'",0),"No data yet")`);
  block(40, 'Status breakdown',
    `=IFERROR(QUERY(${data},"select ${L('Status')}, count(${L('Candidate Name')}) where ${L('Candidate Name')} is not null group by ${L('Status')} label ${L('Status')} 'Status', count(${L('Candidate Name')}) 'Candidates'",0),"No data yet")`);

  // Weekly trend: Monday-start weeks, total plus one column per active recruiter.
  const team = getTeam_(ss).map(t => t.name);
  const trendRow = 56;
  sh.getRange(trendRow - 1, 1).setValue('Sourced per week (last 12 weeks)').setFontWeight('bold').setFontSize(12);
  const head = ['Week of', 'Total'].concat(team);
  sh.getRange(trendRow, 1, 1, head.length).setValues([head]).setFontWeight('bold');
  const rows = [];
  for (let i = 0; i < 12; i++) {
    const rr = trendRow + 1 + i;
    const line = [`=TODAY()-WEEKDAY(TODAY(),3)-7*${11 - i}`,
      `=COUNTIFS(${r('Date Sourced')},">="&$A${rr},${r('Date Sourced')},"<"&$A${rr}+7)`];
    team.forEach((_, j) => {
      const hc = colLetter_(3 + j) + '$' + trendRow;
      line.push(`=COUNTIFS(${r('Date Sourced')},">="&$A${rr},${r('Date Sourced')},"<"&$A${rr}+7,${r('Recruiter')},${hc})`);
    });
    rows.push(line);
  }
  sh.getRange(trendRow + 1, 1, 12, head.length).setFormulas(rows);
  sh.getRange(trendRow + 1, 1, 12, 1).setNumberFormat('dd mmm');

  block(72, 'Recruiter × status',
    `=IFERROR(QUERY(${data},"select ${L('Recruiter')}, count(${L('Candidate Name')}) where ${L('Candidate Name')} is not null group by ${L('Recruiter')} pivot ${L('Status')}",0),"No data yet")`);
  block(84, 'Requirement × status',
    `=IFERROR(QUERY(${data},"select ${L('Requirement')}, count(${L('Candidate Name')}) where ${L('Candidate Name')} is not null group by ${L('Requirement')} pivot ${L('Status')}",0),"No data yet")`);

  const chart = (type, range, row, title, extra) => {
    let b = sh.newChart().setChartType(type).addRange(sh.getRange(range))
      .setNumHeaders(1).setPosition(row, 5, 0, 0)
      .setOption('title', title).setOption('width', 520).setOption('height', 280);
    Object.keys(extra || {}).forEach(k => { b = b.setOption(k, extra[k]); });
    sh.insertChart(b.build());
  };
  chart(Charts.ChartType.BAR, 'A13:B23', 4, 'Sourced per recruiter', { legend: { position: 'none' } });
  chart(Charts.ChartType.BAR, 'A27:B37', 20, 'Sourced per requirement', { legend: { position: 'none' } });
  chart(Charts.ChartType.PIE, 'A41:B52', 36, 'Status breakdown', { pieHole: 0.4 });
  chart(Charts.ChartType.LINE, `A${trendRow}:${colLetter_(head.length)}${trendRow + 12}`, 54, 'Sourced per week', {});

  sh.setColumnWidth(1, 260);
  sh.setColumnWidth(2, 110);
}

// ---------------------------------------------------------------- form

function ensureForm_(ss) {
  const props = PropertiesService.getScriptProperties();
  let form = null;
  const id = props.getProperty('FORM_ID');
  if (id) { try { form = FormApp.openById(id); } catch (err) { form = null; } }
  if (!form) {
    form = FormApp.create('Log a candidate');
    form.setDescription('One candidate per submission. You need at least one of email, LinkedIn URL or phone, ' +
      'so the tracker can catch duplicates. If the candidate is already in the pipeline for that requirement, ' +
      'you will get an email saying who has them.');
    form.addListItem().setTitle(FORM_Q.recruiter).setRequired(true).setChoiceValues(['-']);
    form.addListItem().setTitle(FORM_Q.requirement).setRequired(true).setChoiceValues(['-']);
    form.addTextItem().setTitle(FORM_Q.name).setRequired(true);
    form.addTextItem().setTitle(FORM_Q.email)
      .setValidation(FormApp.createTextValidation().requireTextIsEmail().build());
    form.addTextItem().setTitle(FORM_Q.phone);
    form.addTextItem().setTitle(FORM_Q.linkedin);
    form.addTextItem().setTitle(FORM_Q.title);
    form.addTextItem().setTitle(FORM_Q.company);
    form.addTextItem().setTitle(FORM_Q.location);
    form.addListItem().setTitle(FORM_Q.source).setChoiceValues(SOURCES);
    form.addListItem().setTitle(FORM_Q.status).setChoiceValues(STATUSES.slice(0, 4));
    form.addParagraphTextItem().setTitle(FORM_Q.notes)
      .setHelpText('Why this person fits, what they said, and what you need from Pravin (2–3 lines).');
    form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
    props.setProperty('FORM_ID', form.getId());
    SpreadsheetApp.flush();
    const fresh = SpreadsheetApp.openById(ss.getId());
    fresh.getSheets().forEach(s => {
      const url = s.getFormUrl();
      if (url && FormApp.openByUrl(url).getId() === form.getId()) {
        s.setName(APP.FORM_RESPONSES);
        s.hideSheet();
      }
    });
  }
  refreshFormChoices_(ss);
}

function refreshFormChoices_(ss) {
  const id = PropertiesService.getScriptProperties().getProperty('FORM_ID');
  if (!id) return;
  const form = FormApp.openById(id);
  const team = getTeam_(ss).map(t => t.name);
  const reqs = getRequirements_(ss, false).map(r => r.title);
  form.getItems(FormApp.ItemType.LIST).forEach(item => {
    const li = item.asListItem();
    if (item.getTitle() === FORM_Q.recruiter && team.length) li.setChoiceValues(team);
    if (item.getTitle() === FORM_Q.requirement && reqs.length) li.setChoiceValues(reqs);
  });
}

function handleFormSubmit(e) {
  const nv = e.namedValues || {};
  const get = k => String((nv[FORM_Q[k]] || [''])[0] || '').trim();
  const rec = {};
  Object.keys(FORM_Q).forEach(k => { rec[k] = get(k); });
  const res = ingestCandidate_(rec, 'Form');
  if (res.status !== 'added' || (res.crossHits && res.crossHits.length)) notifyRecruiter_(rec.recruiter, [res]);
}

// ---------------------------------------------------------------- Gmail intake

/**
 * Recruiters email the owner's intake address (e.g. pravin+intake@gmail.com) using the
 * template in SETUP.md. A Gmail filter labels those messages "Recruiting/Intake"; this
 * job picks them up, files each candidate, then relabels the thread Logged or Needs Fix.
 */
function processIntake() {
  const ss = SpreadsheetApp.getActive();
  const intake = GmailApp.getUserLabelByName(APP.LABEL_INTAKE);
  if (!intake) return;
  const done = getOrCreateLabel_(APP.LABEL_DONE);
  const fix = getOrCreateLabel_(APP.LABEL_FIX);
  const team = getTeam_(ss);
  const owner = String(getSettings_(ss)[SET.OWNER] || '').toLowerCase();
  const seen = processedMessageIds_(ss);

  intake.getThreads(0, 50).forEach(thread => {
    let clean = true;
    thread.getMessages().forEach(msg => {
      const id = msg.getId();
      if (seen.has(id)) return;
      const from = extractEmail_(msg.getFrom());
      const member = team.find(t => t.email.toLowerCase() === from);
      if (!member && from !== owner) {
        log_(ss, 'Ignored sender', '', '', '', `Not in Team sheet: ${from}`, id);
        return;
      }
      const blocks = parseIntakeBody_(msg.getPlainBody());
      const results = blocks.map(b => {
        if (!b.recruiter && member) b.recruiter = member.name;
        return ingestCandidate_(b, 'Gmail');
      });
      if (!blocks.length) results.push({ status: 'error', message: 'No candidate fields found. Use the "Name: …" template.' });
      log_(ss, 'Email processed', '', member ? member.name : 'Owner', '', `${results.length} record(s)`, id);
      if (results.some(x => x.status !== 'added')) clean = false;
      if (results.some(x => x.status !== 'added' || (x.crossHits && x.crossHits.length))) {
        notifyRecruiter_(member ? member.name : null, results, from, msg.getSubject());
      }
    });
    thread.removeLabel(intake);
    thread.addLabel(clean ? done : fix);
  });
}

const FIELD_ALIASES = {
  requirement: ['requirement', 'req', 'role', 'position'],
  name: ['name', 'candidate', 'candidate name'],
  email: ['email', 'e-mail', 'mail'],
  phone: ['phone', 'mobile', 'phone number', 'contact number'],
  linkedin: ['linkedin', 'linkedin url', 'profile', 'profile url'],
  title: ['title', 'current title', 'current role', 'designation'],
  company: ['company', 'current company', 'employer'],
  location: ['location', 'city'],
  source: ['source'],
  status: ['status'],
  notes: ['notes', 'note', 'comments', 'why'],
  recruiter: ['recruiter', 'sourced by'],
};
const ALIAS_TO_FIELD = {};
Object.keys(FIELD_ALIASES).forEach(f => FIELD_ALIASES[f].forEach(a => { ALIAS_TO_FIELD[a] = f; }));

function parseIntakeBody_(body) {
  return stripQuoted_(String(body || ''))
    .split(/^\s*-{3,}\s*$/m)
    .map(parseBlock_)
    .filter(b => b.name || b.email || b.linkedin);
}

function parseBlock_(block) {
  const rec = {};
  block.split(/\r?\n/).forEach(line => {
    const m = line.match(/^\s*\*?([A-Za-z][A-Za-z \-]{0,30}?)\*?\s*:\s*(.*\S)\s*$/);
    if (!m) return;
    const field = ALIAS_TO_FIELD[m[1].trim().toLowerCase()];
    if (field && !rec[field]) rec[field] = m[2].trim();
  });
  if (!rec.linkedin) {
    const url = block.match(/https?:\/\/(?:[a-z]{2,3}\.)?linkedin\.com\/in\/[^\s<>"]+/i);
    if (url) rec.linkedin = url[0];
  }
  return rec;
}

function stripQuoted_(body) {
  const cut = body.search(/^On .{5,200}wrote:\s*$/m);
  const text = cut >= 0 ? body.slice(0, cut) : body;
  return text.split(/\r?\n/).filter(l => !/^\s*>/.test(l)).join('\n');
}

// ---------------------------------------------------------------- manual edits

/** Installable on-edit trigger: fills IDs and dates for rows typed or pasted into a requirement tab. */
function handleEdit(e) {
  if (!e || !e.range) return;
  const sh = e.range.getSheet();
  const ss = sh.getParent();
  const req = getRequirements_(ss, true).find(x => x.tab === sh.getName());
  if (!req) return;
  const r0 = Math.max(e.range.getRow(), 2);
  const r1 = e.range.getLastRow();
  if (r1 < r0) return;
  const c0 = e.range.getColumn();
  const c1 = e.range.getLastColumn();
  const watched = ['Candidate Name', 'Email', 'Phone', 'LinkedIn URL', 'Status'].map(col);
  if (!watched.some(c => c >= c0 && c <= c1)) return;
  const statusEdited = col('Status') >= c0 && col('Status') <= c1;

  const rng = sh.getRange(r0, 1, r1 - r0 + 1, COLS.length);
  const vals = rng.getValues();
  const index = buildIndex_(ss);
  const team = getTeam_(ss);
  vals.forEach((v, i) => {
    if (!String(v[IX['Candidate Name']]).trim()) return;
    const rowNum = r0 + i;
    if (!v[IX['Candidate ID']]) {
      v[IX['Candidate ID']] = nextId_(req.id);
      v[IX['Requirement']] = req.title;
      if (!v[IX['Date Sourced']]) v[IX['Date Sourced']] = new Date();
      if (!v[IX['Status']]) v[IX['Status']] = 'Sourced';
      if (!v[IX['Recruiter']]) {
        const me = team.find(t => t.email.toLowerCase() === String(Session.getActiveUser().getEmail()).toLowerCase());
        if (me) v[IX['Recruiter']] = me.name;
      }
      v[IX['Entry Method']] = 'Manual';
    }
    if (statusEdited && CONTACTED_PLUS.includes(v[IX['Status']]) && !v[IX['Last Contacted']]) {
      v[IX['Last Contacted']] = new Date();
    }
    const keys = dedupeKeys_({ email: v[IX['Email']], linkedin: v[IX['LinkedIn URL']], phone: v[IX['Phone']] });
    v[IX['Dedupe Key']] = keys.join('|');
    const hits = lookup_(index, keys, { tab: sh.getName(), row: rowNum });
    const cell = sh.getRange(rowNum, col('Candidate Name'));
    if (hits.length) {
      const sameReq = hits.some(h => h.tab === sh.getName());
      cell.setBackground(sameReq ? '#f4c7c3' : '#fce8b2').setNote(
        (sameReq ? 'DUPLICATE in this requirement. ' : 'Also in another requirement. ') +
        hits.map(describeHit_).join('\n'));
      if (sameReq) log_(ss, 'Duplicate flagged', req.title, v[IX['Recruiter']], v[IX['Candidate Name']], hits.map(describeHit_).join('; '), '');
    } else {
      cell.setBackground(null).clearNote();
    }
  });
  rng.setValues(vals);
}

// ---------------------------------------------------------------- shared ingest + dedupe

function ingestCandidate_(rec, method) {
  const ss = SpreadsheetApp.getActive();
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const req = findRequirement_(ss, rec.requirement);
    if (!req) {
      const open = getRequirements_(ss, false).map(r => r.title).join(', ');
      return { status: 'error', rec, message: `Unknown or closed requirement "${rec.requirement || ''}". Open requirements: ${open}.` };
    }
    if (!rec.name) return { status: 'error', rec, message: 'Candidate name is missing.' };
    const member = getTeam_(ss).find(t => t.name.toLowerCase() === String(rec.recruiter || '').trim().toLowerCase());
    if (!member) return { status: 'error', rec, message: `Recruiter "${rec.recruiter || ''}" is not in the Team sheet.` };
    const keys = dedupeKeys_(rec);
    if (!keys.length) return { status: 'error', rec, message: `${rec.name}: add an email, LinkedIn URL or phone so duplicates can be checked.` };

    const hits = lookup_(buildIndex_(ss), keys, null);
    const same = hits.filter(h => h.tab === req.tab);
    if (same.length) {
      log_(ss, 'Duplicate blocked', req.title, member.name, rec.name, same.map(describeHit_).join('; '), '');
      return { status: 'duplicate', rec, message: `${rec.name} is already in ${req.title}: ${same.map(describeHit_).join('; ')}. Not added.` };
    }

    const status = STATUSES.includes(rec.status) ? rec.status : 'Sourced';
    const row = new Array(COLS.length).fill('');
    row[IX['Candidate ID']] = nextId_(req.id);
    row[IX['Requirement']] = req.title;
    row[IX['Date Sourced']] = new Date();
    row[IX['Recruiter']] = member.name;
    row[IX['Candidate Name']] = rec.name;
    row[IX['Email']] = rec.email || '';
    row[IX['Phone']] = rec.phone || '';
    row[IX['LinkedIn URL']] = rec.linkedin || '';
    row[IX['Current Title']] = rec.title || '';
    row[IX['Current Company']] = rec.company || '';
    row[IX['Location']] = rec.location || '';
    row[IX['Source']] = rec.source || '';
    row[IX['Status']] = status;
    row[IX['Last Contacted']] = status === 'Sourced' ? '' : new Date();
    row[IX['Notes']] = (hits.length ? `[Also in: ${hits.map(h => `${h.requirement} (${h.recruiter})`).join('; ')}] ` : '') + (rec.notes || '');
    row[IX['Dedupe Key']] = keys.join('|');
    row[IX['Entry Method']] = method;
    ss.getSheetByName(req.tab).appendRow(row);
    log_(ss, 'Added', req.title, member.name, rec.name, method, '');
    return { status: 'added', rec, crossHits: hits, message: `${rec.name} added to ${req.title} as ${row[IX['Candidate ID']]}.` };
  } finally {
    lock.releaseLock();
  }
}

/** Email lowercased; LinkedIn reduced to the /in/<slug>; phone reduced to its last 10 digits. */
function dedupeKeys_(rec) {
  const keys = [];
  const email = String(rec.email || '').trim().toLowerCase();
  if (/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) keys.push('e:' + email);
  const li = String(rec.linkedin || '').toLowerCase().match(/linkedin\.com\/in\/([^\/?#\s]+)/);
  if (li) {
    let slug = li[1];
    try { slug = decodeURIComponent(slug); } catch (err) { /* keep raw slug */ }
    keys.push('l:' + slug);
  }
  const digits = String(rec.phone || '').replace(/\D/g, '');
  if (digits.length >= 10) keys.push('p:' + digits.slice(-10));
  return keys;
}

/** Reads every requirement tab directly (not the formula view) so new rows are seen at once. */
function buildIndex_(ss) {
  const index = {};
  getRequirements_(ss, true).forEach(req => {
    const sh = ss.getSheetByName(req.tab);
    if (!sh || sh.getLastRow() < 2) return;
    sh.getRange(2, 1, sh.getLastRow() - 1, COLS.length).getValues().forEach((v, i) => {
      if (!String(v[IX['Candidate Name']]).trim()) return;
      const hit = {
        tab: req.tab, row: i + 2, requirement: req.title, name: v[IX['Candidate Name']],
        recruiter: v[IX['Recruiter']], date: v[IX['Date Sourced']], status: v[IX['Status']],
      };
      dedupeKeys_({ email: v[IX['Email']], linkedin: v[IX['LinkedIn URL']], phone: v[IX['Phone']] })
        .forEach(k => { (index[k] = index[k] || []).push(hit); });
    });
  });
  return index;
}

function lookup_(index, keys, exclude) {
  const out = [];
  const seen = new Set();
  keys.forEach(k => (index[k] || []).forEach(h => {
    const id = h.tab + '#' + h.row;
    if (seen.has(id) || (exclude && exclude.tab === h.tab && exclude.row === h.row)) return;
    seen.add(id);
    out.push(h);
  }));
  return out;
}

function describeHit_(h) {
  return `${h.name} in ${h.requirement}, sourced by ${h.recruiter || 'unknown'} on ${fmtDate_(h.date)} (status: ${h.status || 'n/a'})`;
}

// ---------------------------------------------------------------- daily digest + reminders

function dailyJobs() {
  const ss = SpreadsheetApp.getActive();
  const settings = getSettings_(ss);
  const rows = allRows_(ss);
  sendOwnerDigest_(ss, settings, rows);
  if (String(settings[SET.REMINDERS] || 'Y').toUpperCase().startsWith('Y')) sendFollowUpReminders_(ss, settings, rows);
}

function sendOwnerDigest_(ss, settings, rows) {
  const owner = settings[SET.OWNER];
  if (!owner) return;
  const since = startOfDay_(new Date(Date.now() - 864e5));
  const fresh = rows.filter(r => r['Date Sourced'] instanceof Date && r['Date Sourced'] >= since);
  const count = (arr, key) => arr.reduce((m, r) => { m[r[key]] = (m[r[key]] || 0) + 1; return m; }, {});
  const byRec = count(fresh, 'Recruiter');
  const byReq = count(fresh, 'Requirement');
  const submitted = rows.filter(r => r.Status === 'Submitted');
  const logs = ss.getSheetByName(APP.LOG).getDataRange().getValues().slice(1)
    .filter(l => l[0] instanceof Date && l[0] >= since && l[1] === 'Duplicate blocked');
  const li = obj => Object.keys(obj).map(k => `<li>${esc_(k)}: <b>${obj[k]}</b></li>`).join('') || '<li>None</li>';
  const html =
    `<p>Since yesterday: <b>${fresh.length}</b> new candidates, <b>${logs.length}</b> duplicates blocked.</p>` +
    `<p><b>By recruiter</b></p><ul>${li(byRec)}</ul><p><b>By requirement</b></p><ul>${li(byReq)}</ul>` +
    `<p><b>Waiting on your review (status Submitted): ${submitted.length}</b></p><ul>` +
    submitted.slice(0, 15).map(r => `<li>${esc_(r['Candidate Name'])} · ${esc_(r.Requirement)} · ${esc_(r.Recruiter)}` +
      (r.Notes ? ` · <i>${esc_(String(r.Notes).slice(0, 140))}</i>` : '') + '</li>').join('') + '</ul>' +
    `<p><a href="${ss.getUrl()}">Open the tracker</a></p>`;
  MailApp.sendEmail({ to: owner, subject: `Recruiting digest: ${fresh.length} new, ${submitted.length} awaiting review`, htmlBody: html });
}

function sendFollowUpReminders_(ss, settings, rows) {
  const days = Number(settings[SET.FOLLOW_UP_DAYS]) || 4;
  const today = startOfDay_(new Date());
  const cutoff = new Date(today.getTime() - days * 864e5);
  getTeam_(ss).forEach(member => {
    if (!member.email || /example\.com$/i.test(member.email)) return;
    const due = rows.filter(r => r.Recruiter === member.name && !CLOSED.includes(r.Status) && (
      (r.Status === 'Contacted' && r['Last Contacted'] instanceof Date && r['Last Contacted'] <= cutoff) ||
      (r['Next Action Date'] instanceof Date && r['Next Action Date'] <= today)));
    if (!due.length) return;
    const html = `<p>Hi ${esc_(member.name)}, these candidates are due a follow-up today:</p><ul>` +
      due.slice(0, 30).map(r => `<li><b>${esc_(r['Candidate Name'])}</b> (${esc_(r.Requirement)}): ${esc_(r.Status)}, ` +
        `last contact ${fmtDate_(r['Last Contacted'])}` +
        (r['LinkedIn URL'] ? ` · <a href="${esc_(r['LinkedIn URL'])}">profile</a>` : '') + '</li>').join('') +
      '</ul><p>Send something specific to them, not "just checking in". Then update Status and Last Contacted.</p>' +
      `<p><a href="${ss.getUrl()}">Open the tracker</a></p>`;
    MailApp.sendEmail({ to: member.email, subject: `${due.length} follow-ups due today`, htmlBody: html });
  });
}

function notifyRecruiter_(recruiterName, results, fallbackEmail, subject) {
  const ss = SpreadsheetApp.getActive();
  const member = getTeam_(ss).find(t => t.name === recruiterName);
  const to = (member && !/example\.com$/i.test(member.email)) ? member.email : fallbackEmail;
  if (!to) return;
  const lines = results.map(r => {
    const tag = r.status === 'added' ? 'ADDED' : r.status === 'duplicate' ? 'DUPLICATE' : 'NEEDS FIX';
    const cross = r.crossHits && r.crossHits.length ? ` (also in ${r.crossHits.map(h => h.requirement).join(', ')})` : '';
    return `${tag}: ${r.message}${cross}`;
  });
  MailApp.sendEmail({ to, subject: subject ? `Re: ${subject}` : 'Candidate intake result', body: lines.join('\n') });
}

// ---------------------------------------------------------------- helpers

function getTeam_(ss) {
  const sh = ss.getSheetByName(APP.TEAM);
  if (!sh || sh.getLastRow() < 2) return [];
  return sh.getRange(2, 1, sh.getLastRow() - 1, 3).getValues()
    .filter(r => String(r[0]).trim() && String(r[2] || 'Y').toUpperCase() !== 'N')
    .map(r => ({ name: String(r[0]).trim(), email: String(r[1]).trim() }));
}

function getRequirements_(ss, includeClosed) {
  const sh = ss.getSheetByName(APP.REQS);
  if (!sh || sh.getLastRow() < 2) return [];
  return sh.getRange(2, 1, sh.getLastRow() - 1, 6).getValues()
    .map((r, i) => ({ row: i + 2, id: String(r[0]).trim(), title: String(r[1]).trim(), tab: String(r[2]).trim(), status: String(r[4]).trim(), created: r[5] }))
    .filter(r => r.title && (includeClosed || r.status.toLowerCase() !== 'closed'));
}

function findRequirement_(ss, text) {
  const t = String(text || '').trim().toLowerCase();
  if (!t) return null;
  return getRequirements_(ss, false).find(r => [r.id, r.title, r.tab].some(x => x.toLowerCase() === t)) || null;
}

function getSettings_(ss) {
  const out = {};
  const sh = ss.getSheetByName(APP.SETTINGS);
  if (!sh || sh.getLastRow() < 2) return out;
  sh.getRange(2, 1, sh.getLastRow() - 1, 2).getValues().forEach(r => { out[String(r[0]).trim()] = r[1]; });
  return out;
}

function allRows_(ss) {
  const out = [];
  getRequirements_(ss, true).forEach(req => {
    const sh = ss.getSheetByName(req.tab);
    if (!sh || sh.getLastRow() < 2) return;
    sh.getRange(2, 1, sh.getLastRow() - 1, COLS.length).getValues().forEach(v => {
      if (!String(v[IX['Candidate Name']]).trim()) return;
      const o = {};
      COLS.forEach((h, i) => { o[h] = v[i]; });
      out.push(o);
    });
  });
  return out;
}

function nextId_(reqId) {
  const props = PropertiesService.getScriptProperties();
  const key = 'SEQ_' + reqId;
  const n = (parseInt(props.getProperty(key), 10) || 0) + 1;
  props.setProperty(key, String(n));
  return `${reqId}-${String(n).padStart(4, '0')}`;
}

function log_(ss, event, requirement, recruiter, candidate, detail, messageId) {
  ss.getSheetByName(APP.LOG).appendRow([new Date(), event, requirement || '', recruiter || '', candidate || '', detail || '', messageId || '']);
}

function processedMessageIds_(ss) {
  const sh = ss.getSheetByName(APP.LOG);
  if (sh.getLastRow() < 2) return new Set();
  return new Set(sh.getRange(2, 7, sh.getLastRow() - 1, 1).getValues().map(r => String(r[0])).filter(Boolean));
}

function installTriggers_(ss) {
  const handlers = ['handleEdit', 'handleFormSubmit', 'processIntake', 'dailyJobs'];
  ScriptApp.getProjectTriggers()
    .filter(t => handlers.includes(t.getHandlerFunction()))
    .forEach(t => ScriptApp.deleteTrigger(t));
  const hour = Math.min(23, Math.max(0, Number(getSettings_(ss)[SET.DIGEST_HOUR]) || 8));
  ScriptApp.newTrigger('handleEdit').forSpreadsheet(ss).onEdit().create();
  ScriptApp.newTrigger('handleFormSubmit').forSpreadsheet(ss).onFormSubmit().create();
  ScriptApp.newTrigger('processIntake').timeBased().everyMinutes(15).create();
  ScriptApp.newTrigger('dailyJobs').timeBased().everyDays(1).atHour(hour).create();
}

function ensureLabels_() {
  [APP.LABEL_ROOT, APP.LABEL_INTAKE, APP.LABEL_DONE, APP.LABEL_FIX].forEach(getOrCreateLabel_);
}

function getOrCreateLabel_(name) {
  return GmailApp.getUserLabelByName(name) || GmailApp.createLabel(name);
}

function removeBlankDefaultSheet_(ss) {
  const s = ss.getSheetByName('Sheet1');
  if (s && s.getLastRow() === 0 && ss.getSheets().length > 1) ss.deleteSheet(s);
}

function toast_(ss, msg) {
  try { ss.toast(msg, 'Recruiting', 15); } catch (err) { /* no UI when run from a trigger */ }
}

function extractEmail_(from) {
  const m = String(from).match(/<([^>]+)>/);
  return (m ? m[1] : String(from)).trim().toLowerCase();
}

function quoteSheet_(name) { return "'" + String(name).replace(/'/g, "''") + "'"; }

function colLetter_(n) {
  let s = '';
  for (; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
  return s;
}

function startOfDay_(d) { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; }

function fmtDate_(d) {
  if (!(d instanceof Date)) return d ? String(d) : 'n/a';
  return Utilities.formatDate(d, SpreadsheetApp.getActive().getSpreadsheetTimeZone(), 'dd MMM yyyy');
}

function esc_(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

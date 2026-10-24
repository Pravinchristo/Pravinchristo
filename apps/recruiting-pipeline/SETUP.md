# Recruiting Pipeline — setup

A Google Sheet + Apps Script that runs in your Google account. Recruiters log candidates
by form, by email, or by typing into the sheet; every path is checked for duplicates; a
dashboard and a daily Gmail digest read from the same data.

## One-time steps you do by hand (about 15 minutes)

1. **Create the sheet.** In Google Drive, create a blank spreadsheet named
   `Recruiting Tracker`. Keep the spreadsheet locale as English (India or US):
   File > Settings.
2. **Add the script.** Open Extensions > Apps Script. Replace `Code.gs` with this
   folder's `Code.gs`. Then open Project Settings, tick "Show appsscript.json manifest
   file in editor", and paste in `appsscript.json`. Save.
3. **Run `setup`.** Pick `setup` in the function dropdown and click Run. Google asks for
   permission to use Sheets, Forms, Gmail and triggers. Because the app is your own and
   unverified, you'll see a warning screen: click Advanced, then "Go to … (unsafe)".
   This is normal for a personal script.
4. **Fill in the config tabs**, then use **Recruiting > Run setup / repair** again:
   - `Team`: real names and Gmail addresses for John, Maria and Izel.
   - `Requirements`: your three real requirement titles. Edit the seeded titles
     *before* the first rerun of setup, because the tab name is fixed once created.
   - `Settings`: confirm the owner email, the intake address, the follow-up days and
     the digest hour.
5. **Make the Gmail filter.** In Gmail, go to Settings > Filters > Create new filter.
   Set To: `yourname+intake@gmail.com` (the intake address from Settings). Choose
   "Apply the label: Recruiting/Intake" and "Skip the Inbox". Gmail delivers
   plus-addresses to your normal inbox without any further setup.
6. **Share access.**
   - Share the spreadsheet with the three recruiters as **Editor**.
   - Send them the form link (shown in the setup toast and in Apps Script > Executions
     logs).
   - Send them the intake address and the email template below.

## Adding a requirement later

Use **Recruiting > Add requirement…** in the sheet menu. It does three things:
- creates the new tab with the standard columns,
- adds the tab to `_All Candidates` (so the dashboard picks it up),
- adds the title to the form's dropdown.

To close a requirement, set its Status to `Closed` in `Requirements` and run setup /
repair. Its tab and history stay; it drops out of the form and the email intake.

After adding or removing a recruiter in `Team`, run setup / repair so the dashboard's
weekly trend gets a column for them.

## Email template for recruiters

Send to the intake address. To log several candidates in one email, separate them with
a line of `---`.

```
Requirement: OTT Test Engineer
Name: Asha Rao
Email: asha.rao@gmail.com
Phone: +91 98450 12345
LinkedIn: https://www.linkedin.com/in/asha-rao-qa
Title: Senior QA Engineer
Company: Zee5
Location: Bengaluru
Source: LinkedIn
Status: Contacted
Notes: Roku + Fire TV automation; 30-day notice; asked about hybrid. Need your call on band.
```

You only need Requirement, Name, and one of Email, LinkedIn or Phone. Recruiter is taken
from the sender's address. If anything is wrong (a duplicate, an unknown requirement, a
missing contact), the sender gets a reply saying what happened, and the Gmail thread is
labelled `Recruiting/Needs Fix`.

## How duplicates are stopped

- Each candidate gets keys: lowercased email, the LinkedIn `/in/<slug>`, and the last 10
  digits of the phone number. A match on any key counts as the same person.
- **Same requirement:** Form and email submissions are *blocked*. The recruiter is told
  who already has the candidate, the date, and the current status. Rows typed straight
  into the sheet can't be blocked, so they are highlighted red with a note instead.
- **Different requirement:** the row is allowed (one person can fit two roles), but it
  is tagged `[Also in: …]` in Notes and highlighted amber.
- A script lock serializes writes, so two recruiters submitting the same person at the
  same moment cannot both get through.
- The dashboard shows "Duplicates blocked (last 30 days)", and every block is recorded in
  `_Log`.

Team rule to agree on: the first recruiter on the sheet owns the candidate for that
requirement. Anyone else who has a warm relationship with them adds a note, rather than
reaching out separately.

## Limits to know

- Consumer Gmail: Apps Script can send about 100 emails a day. The digest plus reminders
  uses at most 4 emails a day.
- The intake job runs every 15 minutes, and the digest runs once a day at the hour you
  set.
- Triggers run as you, so the script only reads *your* mailbox. Recruiters must send to
  your intake address; the script cannot see their own inboxes.

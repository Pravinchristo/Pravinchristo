"""CSV and Excel (.xlsx) export of the candidate dashboard, standard library only."""
import csv
import io
import zipfile
from xml.sax.saxutils import escape

COLUMNS = [("id", "Record ID"), ("requirement_title", "Requirement"), ("full_name", "Candidate"), ("current_company", "Current company"),
           ("current_designation", "Designation"), ("total_exp_years", "Experience (yrs)"), ("relevant_exp_years", "Relevant exp (yrs)"),
           ("location", "Location"), ("skills_text", "Skills (evidence level)"), ("notice_period_days", "Notice (days)"),
           ("availability", "Availability"), ("linkedin_url", "LinkedIn URL"), ("resume_link", "Resume link"),
           ("source_channel", "Source channel"), ("source_url", "Source URL"), ("match_score", "Match score"),
           ("classification", "Classification"), ("joe_text", "JOE's assessment"), ("status", "Status"), ("recruiter_remarks", "Recruiter remarks")]


def flat(rows):
    out = []
    for r in rows:
        r = dict(r)
        r["skills_text"] = "; ".join(f"{s['skill']} ({s['level']})" for s in r.get("skills", []))
        a = r.get("joe_assessment") or {}
        parts = [a.get("recommendation") or ""]
        if a.get("critical_gaps"):
            parts.append("Critical gaps: " + ", ".join(a["critical_gaps"]))
        if a.get("missing"):
            parts.append("Missing: " + ", ".join(a["missing"]))
        r["joe_text"] = " | ".join(p for p in parts if p)
        out.append([r.get(k) if r.get(k) is not None else "" for k, _ in COLUMNS])
    return out


def to_csv(rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([h for _, h in COLUMNS])
    for row in flat(rows):
        # guard against spreadsheet formula injection from scraped text
        w.writerow(["'" + v if isinstance(v, str) and v[:1] in "=+-@" else v for v in row])
    return buf.getvalue().encode("utf-8-sig")


def _col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def to_xlsx(rows, sheet="Candidates"):
    data = [[h for _, h in COLUMNS]] + flat(rows)
    xml_rows = []
    for ri, row in enumerate(data, 1):
        cells = []
        for ci, v in enumerate(row):
            ref = f"{_col(ci)}{ri}"
            style = ' s="1"' if ri == 1 else ""
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                cells.append(f'<c r="{ref}"{style}><v>{v}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{escape(str(v))}</t></is></c>')
        xml_rows.append(f'<row r="{ri}">{"".join(cells)}</row>')
    sheet_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                 '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
                 f'<sheetData>{"".join(xml_rows)}</sheetData>'
                 f'<autoFilter ref="A1:{_col(len(COLUMNS) - 1)}{len(data)}"/></worksheet>')
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{sheet}" sheetId="1" r:id="rId1"/></sheets><definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">{sheet}!$A$1:${_col(len(COLUMNS) - 1)}${len(data)}</definedName></definedNames></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        "xl/styles.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>',
        "xl/worksheets/sheet1.xml": sheet_xml,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buf.getvalue()

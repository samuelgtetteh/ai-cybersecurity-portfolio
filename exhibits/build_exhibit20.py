"""Generate "Exhibit 20 - Testing Infrastructure: Target Labs for Continuous Validation.docx"."""
from docx import Document
from docx.shared import Pt

RUN_DATE = "July 17, 2026"
REPO = "https://github.com/samuelgtetteh/ai-cybersecurity-portfolio"

doc = Document()
doc.styles["Normal"].font.name = "Calibri"
doc.styles["Normal"].font.size = Pt(11)


def para(t, bold=False, italic=False):
    p = doc.add_paragraph(); r = p.add_run(t); r.bold = bold; r.italic = italic; return p


def bullet(t):
    doc.add_paragraph(t, style="List Bullet")


def table(headers, rows):
    tb = doc.add_table(rows=1, cols=len(headers)); tb.style = "Light Grid Accent 1"
    for j, h in enumerate(headers):
        tb.rows[0].cells[j].paragraphs[0].add_run(h).bold = True
    for row in rows:
        c = tb.add_row().cells
        for j, v in enumerate(row):
            c[j].text = str(v)
    return tb


t = doc.add_paragraph()
r = t.add_run("Exhibit 20: Testing Infrastructure — Target Labs for Continuous Validation")
r.bold = True; r.font.size = Pt(15)
para("Petitioner: Samuel Gbli Tetteh", bold=True)
para("NIW Proposed Endeavor — the purpose-built test harnesses I created to continuously and "
     "reproducibly validate the detection and scanning systems, now themselves released as open, "
     "standalone tools.", italic=True)

doc.add_heading("1. Purpose", level=1)
para(
    "Building detectors is only half of credible security engineering; you must also prove they "
    "work, continuously and against realistic activity. To do that I built two disposable 'target "
    "labs' — controlled environments that generate realistic malicious and benign activity for the "
    "systems to detect. This exhibit documents them and their current phase: both are complete, in "
    "use, and now published as open tools so the validation is reproducible by anyone.")

doc.add_heading("2. The two labs", level=1)
table(["Lab", "What it does", "Validates"],
      [["Live Target Lab", "Two standing services that continuously stream synthetic-but-realistic "
        "identity login events and OT/ICS sensor readings to the live detection APIs (~15% "
        "intentionally malicious), and report the KNOWN injected label back through the feedback "
        "channel.", "The identity + OT/ICS detectors and the decision layer — end to end, live."],
       ["Cloud Target Lab", "Stands up a disposable fake-AWS (LocalStack) seeded with a deliberate "
        "mix of correctly-configured and intentionally-insecure resources (public S3 bucket, "
        "SSH-open security group, admin-* IAM user, etc.).", "The cloud security scanner / control "
        "auditing — with known ground-truth findings to detect."]])

doc.add_heading("3. Why this is rigorous validation", level=1)
bullet("Continuous, not one-shot: the live lab runs forever and generates fresh data each tick, "
       "closer to a real SIEM/SCADA stream than replaying a fixed dataset.")
bullet("Ground-truth feedback loop: because each generator knows the label it injected, it reports "
       "that label back, so the platform can compute LIVE precision/recall/specificity from its own "
       "trail (the same channel a real analyst or SOAR tool would use).")
bullet("Known-answer cloud fixtures: the cloud lab seeds a mix of secure and insecure resources, so "
       "a scanner is measured against genuine, varied findings — not an all-or-nothing fixture.")
bullet("Safe and disposable: everything runs in throwaway containers against emulated/synthetic "
       "targets — no real accounts, no third-party systems.")

doc.add_heading("4. Published as open, standalone tools", level=1)
para("Both labs are released so the validation is fully reproducible:")
table(["Lab", "GitHub", "Docker (GHCR)", "Hugging Face"],
      [["Live Target Lab", "github.com/samuelgtetteh/live-target-lab (Release v0.1)",
        "ghcr.io/samuelgtetteh/live-target-lab", "dataset stetteh/live-target-lab-events; "
        "Space stetteh/live-target-lab"],
       ["Cloud Target Lab", "github.com/samuelgtetteh/cloud-target-lab (Release v0.1)",
        "ghcr.io/samuelgtetteh/cloud-target-lab", "dataset stetteh/cloud-target-lab-scenarios; "
        "Space stetteh/cloud-target-lab"]])

doc.add_heading("5. Significance", level=1)
para("Purpose-built, continuously-running, ground-truth-labelled test harnesses — released openly "
     "alongside the systems they validate — demonstrate the engineering and scientific maturity to "
     "not only build security capabilities but to prove and reproduce their effectiveness. This "
     "supports both the credibility of the results in Exhibits 11–19 and that the petitioner is well "
     "positioned to advance the endeavor to a rigorous, verifiable standard.")
p = doc.add_paragraph(); p.add_run(REPO).bold = True
para(""); para("Date: " + RUN_DATE); para("Prepared by: Samuel Gbli Tetteh")

out = r"c:\Users\User\ai-cybersecurity-portfolio\exhibits\Exhibit 20 Testing Infrastructure Target Labs.docx"
doc.save(out); print("saved:", out, "| paras", len(doc.paragraphs), "| tables", len(doc.tables))

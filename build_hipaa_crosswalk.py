"""
Build the full NIST SP 800-53 Rev 5 -> HIPAA Security Rule crosswalk CSV.

- Fetches official NIST control text from the OSCAL JSON published on GitHub.
- HIPAA provision texts are from 45 CFR Part 164 (SP 800-66r2 Appendix D).
- Mapping table covers all control families that have HIPAA relevance.
- Output format matches the notebook column expectations exactly.

Run from the project root:
    python build_hipaa_crosswalk.py
"""

import json
import re
from pathlib import Path

import pandas as pd
import requests

OSCAL_URL = (
    "https://raw.githubusercontent.com/usnistgov/oscal-content/"
    "main/nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json"
)

OUTPUT_PATH = Path("data/raw/nist_800_53_rev5_hipaa_crosswalk_full.csv")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# HIPAA Security Rule provisions (45 CFR Part 164, SP 800-66r2 Appendix D)
# ---------------------------------------------------------------------------
HIPAA = {
    # --- Administrative Safeguards (164.308) ---
    "164.308(a)(1)": (
        "Security Management Process: Implement policies and procedures to prevent, "
        "detect, contain, and correct security violations."
    ),
    "164.308(a)(1)(ii)(A)": (
        "Risk Analysis (R): Conduct an accurate and thorough assessment of the potential "
        "risks and vulnerabilities to the confidentiality, integrity, and availability of "
        "electronic protected health information held by the covered entity or business associate."
    ),
    "164.308(a)(1)(ii)(B)": (
        "Risk Management (R): Implement security measures sufficient to reduce risks and "
        "vulnerabilities to a reasonable and appropriate level to comply with §164.306(a)."
    ),
    "164.308(a)(1)(ii)(C)": (
        "Sanction Policy (R): Apply appropriate sanctions against workforce members who fail "
        "to comply with the security policies and procedures of the covered entity or business associate."
    ),
    "164.308(a)(1)(ii)(D)": (
        "Information System Activity Review (R): Implement procedures to regularly review records "
        "of information system activity, such as audit logs, access reports, and security incident "
        "tracking reports."
    ),
    "164.308(a)(2)": (
        "Assigned Security Responsibility: Identify the security official who is responsible for "
        "the development and implementation of the policies and procedures required by this subpart."
    ),
    "164.308(a)(3)": (
        "Workforce Security: Implement policies and procedures to ensure that all members of its "
        "workforce have appropriate access to electronic protected health information, as provided "
        "under paragraph (a)(4) of this section, and to prevent those workforce members who do not "
        "have access under paragraph (a)(4) from obtaining access to electronic protected health information."
    ),
    "164.308(a)(3)(ii)(A)": (
        "Authorization and/or Supervision (A): Implement procedures for the authorization and/or "
        "supervision of workforce members who work with electronic protected health information or "
        "in locations where it might be accessed."
    ),
    "164.308(a)(3)(ii)(B)": (
        "Workforce Clearance Procedure (A): Implement procedures to determine that the access of a "
        "workforce member to electronic protected health information is appropriate."
    ),
    "164.308(a)(3)(ii)(C)": (
        "Termination Procedures (A): Implement procedures for terminating access to electronic "
        "protected health information when the employment of, or other arrangement with, a workforce "
        "member ends or as required by determinations made as specified in paragraph (a)(3)(ii)(B)."
    ),
    "164.308(a)(4)": (
        "Information Access Management: Implement policies and procedures for authorizing access to "
        "electronic protected health information that are consistent with the applicable requirements "
        "of subpart E of this part."
    ),
    "164.308(a)(4)(ii)(A)": (
        "Isolating Healthcare Clearinghouse Functions (R): If a health care clearinghouse is part of "
        "a larger organization, the clearinghouse must implement policies and procedures that protect "
        "the electronic protected health information of the clearinghouse from unauthorized access by "
        "the larger organization."
    ),
    "164.308(a)(4)(ii)(B)": (
        "Access Authorization (A): Implement policies and procedures for granting access to electronic "
        "protected health information, for example, through access to a workstation, transaction, "
        "program, process, or other mechanism."
    ),
    "164.308(a)(4)(ii)(C)": (
        "Access Establishment and Modification (A): Implement policies and procedures that, based upon "
        "the covered entity's or business associate's access authorization policies, establish, document, "
        "review, and modify a user's right of access to a workstation, transaction, program, or process."
    ),
    "164.308(a)(5)": (
        "Security Awareness and Training: Implement a security awareness and training program for all "
        "members of its workforce (including management)."
    ),
    "164.308(a)(5)(ii)(A)": (
        "Security Reminders (A): Periodic security updates."
    ),
    "164.308(a)(5)(ii)(B)": (
        "Protection from Malicious Software (A): Procedures for guarding against, detecting, and "
        "reporting malicious software."
    ),
    "164.308(a)(5)(ii)(C)": (
        "Log-in Monitoring (A): Procedures for monitoring log-in attempts and reporting discrepancies."
    ),
    "164.308(a)(5)(ii)(D)": (
        "Password Management (A): Procedures for creating, changing, and safeguarding passwords."
    ),
    "164.308(a)(6)": (
        "Security Incident Procedures: Implement policies and procedures to address security incidents."
    ),
    "164.308(a)(6)(ii)": (
        "Response and Reporting (R): Identify and respond to suspected or known security incidents; "
        "mitigate, to the extent practicable, harmful effects of security incidents that are known to "
        "the covered entity or business associate; and document security incidents and their outcomes."
    ),
    "164.308(a)(7)": (
        "Contingency Plan: Establish (and implement as needed) policies and procedures for responding "
        "to an emergency or other occurrence (for example, fire, vandalism, system failure, and natural "
        "disaster) that damages systems that contain electronic protected health information."
    ),
    "164.308(a)(7)(ii)(A)": (
        "Data Backup Plan (R): Establish and implement procedures to create and maintain retrievable "
        "exact copies of electronic protected health information."
    ),
    "164.308(a)(7)(ii)(B)": (
        "Disaster Recovery Plan (R): Establish (and implement as needed) procedures to restore any "
        "loss of data."
    ),
    "164.308(a)(7)(ii)(C)": (
        "Emergency Mode Operation Plan (R): Establish (and implement as needed) procedures to enable "
        "continuation of critical business processes for protection of the security of electronic "
        "protected health information while operating in emergency mode."
    ),
    "164.308(a)(7)(ii)(D)": (
        "Testing and Revision Procedures (A): Implement procedures for periodic testing and revision "
        "of contingency plans."
    ),
    "164.308(a)(7)(ii)(E)": (
        "Applications and Data Criticality Analysis (A): Assess the relative criticality of specific "
        "applications and data in support of other contingency plan components."
    ),
    "164.308(a)(8)": (
        "Evaluation: Perform a periodic technical and nontechnical evaluation, based initially upon "
        "the standards implemented under this rule and, subsequently, in response to environmental or "
        "operational changes affecting the security of electronic protected health information, that "
        "establishes the extent to which a covered entity's or business associate's security policies "
        "and procedures meet the requirements of this subpart."
    ),
    "164.308(b)(1)": (
        "Business Associate Contracts and Other Arrangements: A covered entity may permit a business "
        "associate to create, receive, maintain, or transmit electronic protected health information on "
        "the covered entity's behalf only if the covered entity obtains satisfactory assurances that the "
        "business associate will appropriately safeguard the information."
    ),
    # --- Physical Safeguards (164.310) ---
    "164.310(a)(1)": (
        "Facility Access Controls: Implement policies and procedures to limit physical access to its "
        "electronic information systems and the facility or facilities in which they are housed, while "
        "ensuring that properly authorized access is allowed."
    ),
    "164.310(a)(2)(i)": (
        "Contingency Operations (A): Establish (and implement as needed) procedures that allow facility "
        "access in support of restoration of lost data under the disaster recovery plan and emergency mode "
        "operations plan in the event of an emergency."
    ),
    "164.310(a)(2)(ii)": (
        "Facility Security Plan (A): Implement policies and procedures to safeguard the facility and the "
        "equipment therein from unauthorized physical access, tampering, and theft."
    ),
    "164.310(a)(2)(iii)": (
        "Access Control and Validation Procedures (A): Implement procedures to control and validate a "
        "person's access to facilities based on their role or function, including visitor control, and "
        "control of access to software programs for testing and revision."
    ),
    "164.310(a)(2)(iv)": (
        "Maintenance Records (A): Implement policies and procedures to document repairs and modifications "
        "to the physical components of a facility which are related to security (for example, hardware, "
        "walls, doors, and locks)."
    ),
    "164.310(b)": (
        "Workstation Use: Implement policies and procedures that specify the proper functions to be "
        "performed, the manner in which those functions are to be performed, and the physical attributes "
        "of the surroundings of a specific workstation or class of workstation that can access electronic "
        "protected health information."
    ),
    "164.310(c)": (
        "Workstation Security: Implement physical safeguards for all workstations that access electronic "
        "protected health information, to restrict access to authorized users."
    ),
    "164.310(d)(1)": (
        "Device and Media Controls: Implement policies and procedures that govern the receipt and removal "
        "of hardware and electronic media that contain electronic protected health information into and "
        "out of a facility, and the movement of these items within the facility."
    ),
    "164.310(d)(2)(i)": (
        "Disposal (R): Implement policies and procedures to address the final disposition of electronic "
        "protected health information, and/or the hardware or electronic media on which it is stored."
    ),
    "164.310(d)(2)(ii)": (
        "Media Re-use (R): Implement procedures for removal of electronic protected health information "
        "from electronic media before the media are made available for re-use."
    ),
    "164.310(d)(2)(iii)": (
        "Accountability (A): Maintain a record of the movements of hardware and electronic media and "
        "any person responsible therefore."
    ),
    "164.310(d)(2)(iv)": (
        "Data Backup and Storage (A): Create a retrievable, exact copy of electronic protected health "
        "information, when needed, before movement of equipment."
    ),
    # --- Technical Safeguards (164.312) ---
    "164.312(a)": (
        "Access Control: Implement technical policies and procedures for electronic information systems "
        "that maintain electronic protected health information to allow access only to those persons or "
        "software programs that have been granted access rights as specified in §164.308(a)(4)."
    ),
    "164.312(a)(2)(i)": (
        "Unique User Identification (R): Assign a unique name and/or number for identifying and "
        "tracking user identity."
    ),
    "164.312(a)(2)(ii)": (
        "Emergency Access Procedure (R): Establish (and implement as needed) procedures for obtaining "
        "necessary electronic protected health information during an emergency."
    ),
    "164.312(a)(2)(iii)": (
        "Automatic Logoff (A): Implement electronic procedures that terminate an electronic session "
        "after a predetermined time of inactivity."
    ),
    "164.312(a)(2)(iv)": (
        "Encryption and Decryption (A): Implement a mechanism to encrypt and decrypt electronic "
        "protected health information."
    ),
    "164.312(b)": (
        "Audit Controls: Implement hardware, software, and/or procedural mechanisms that record and "
        "examine activity in information systems that contain or use electronic protected health information."
    ),
    "164.312(c)(1)": (
        "Integrity: Implement policies and procedures to protect electronic protected health information "
        "from improper alteration or destruction."
    ),
    "164.312(c)(2)": (
        "Mechanism to Authenticate Electronic Protected Health Information (A): Implement electronic "
        "mechanisms to corroborate that electronic protected health information has not been altered or "
        "destroyed in an unauthorized manner."
    ),
    "164.312(d)": (
        "Person or Entity Authentication: Implement procedures to verify that a person or entity "
        "seeking access to electronic protected health information is the one claimed."
    ),
    "164.312(e)(1)": (
        "Transmission Security: Implement technical security measures to guard against unauthorized "
        "access to electronic protected health information that is being transmitted over an electronic "
        "communications network."
    ),
    "164.312(e)(2)(i)": (
        "Integrity Controls (A): Implement security measures to ensure that electronically transmitted "
        "electronic protected health information is not improperly modified without detection until "
        "disposed of."
    ),
    "164.312(e)(2)(ii)": (
        "Encryption (A): Implement a mechanism to encrypt electronic protected health information "
        "whenever deemed appropriate."
    ),
    # --- Organizational Requirements (164.314) ---
    "164.314(a)(1)": (
        "Business Associate Contracts: The contract or other arrangement between the covered entity "
        "and its business associate required by §164.308(b)(3) must meet the requirements of "
        "§164.314(a)(2)(i) or (a)(2)(ii), as applicable."
    ),
    "164.314(a)(2)(i)": (
        "Business Associate Contracts (R): The covered entity must enter into a contract with the "
        "business associate that establishes the permitted and required uses and disclosures of such "
        "information, and provides that the business associate will appropriately safeguard the information."
    ),
    "164.314(b)(1)": (
        "Requirements for Group Health Plans: A group health plan must ensure that its plan documents "
        "provide that the plan sponsor will reasonably and appropriately safeguard electronic protected "
        "health information created, received, maintained, or transmitted to or by the plan sponsor on "
        "behalf of the group health plan."
    ),
    # --- Policies, Procedures and Documentation (164.316) ---
    "164.316(a)": (
        "Policies and Procedures: Implement reasonable and appropriate policies and procedures to "
        "comply with the standards, implementation specifications, or other requirements of this subpart."
    ),
    "164.316(b)(1)": (
        "Documentation: Maintain the policies and procedures implemented to comply with this subpart "
        "in written (which may be electronic) form."
    ),
    "164.316(b)(2)(i)": (
        "Time Limit (R): Retain the documentation required by paragraph (b)(1) of this section for "
        "6 years from the date of its creation or the date when it last was in effect, whichever is later."
    ),
    "164.316(b)(2)(ii)": (
        "Availability (R): Make documentation available to those persons responsible for implementing "
        "the procedures to which the documentation pertains."
    ),
    "164.316(b)(2)(iii)": (
        "Updates (R): Review documentation periodically, and update as needed, in response to "
        "environmental or operational changes affecting the security of the electronic protected "
        "health information."
    ),
}

# ---------------------------------------------------------------------------
# NIST SP 800-53 Rev 5 -> HIPAA mapping table (based on SP 800-66r2 App. D)
# Each entry: (nist_control_id, [hipaa_citations], baseline)
# ---------------------------------------------------------------------------
NIST_TO_HIPAA = [
    # Access Control (AC)
    ("AC-1",  ["164.308(a)(3)", "164.308(a)(4)", "164.312(a)", "164.316(b)(2)(ii)", "164.316(b)(2)(iii)"], "Low"),
    ("AC-2",  ["164.308(a)(3)", "164.308(a)(3)(ii)(A)", "164.308(a)(3)(ii)(B)",
               "164.308(a)(4)", "164.308(a)(4)(ii)(B)", "164.308(a)(4)(ii)(C)",
               "164.312(a)(2)(i)", "164.312(a)(2)(ii)"], "Low"),
    ("AC-3",  ["164.308(a)(3)", "164.308(a)(3)(ii)(A)", "164.308(a)(4)(ii)(B)",
               "164.310(b)", "164.312(a)", "164.312(a)(2)(i)", "164.312(a)(2)(ii)"], "Low"),
    ("AC-4",  ["164.308(a)(3)(ii)(A)", "164.308(a)(4)(ii)(B)", "164.310(b)"], "Moderate"),
    ("AC-5",  ["164.308(a)(3)", "164.308(a)(4)", "164.308(a)(4)(ii)(A)", "164.312(a)"], "Moderate"),
    ("AC-6",  ["164.308(a)(3)", "164.308(a)(4)", "164.308(a)(4)(ii)(A)", "164.312(a)"], "Moderate"),
    ("AC-7",  ["164.308(a)(5)(ii)(C)"], "Low"),
    ("AC-11", ["164.310(b)", "164.312(a)(2)(iii)"], "Moderate"),
    ("AC-12", ["164.310(b)", "164.312(a)(2)(iii)"], "Moderate"),
    ("AC-16", ["164.310(b)"], "Not Selected"),
    ("AC-17", ["164.310(b)"], "Low"),
    ("AC-19", ["164.310(b)"], "Low"),

    # Awareness and Training (AT)
    ("AT-1",  ["164.308(a)(5)"], "Low"),
    ("AT-2",  ["164.308(a)(5)", "164.308(a)(5)(ii)(A)", "164.308(a)(5)(ii)(B)",
               "164.308(a)(5)(ii)(C)", "164.308(a)(5)(ii)(D)"], "Low"),
    ("AT-3",  ["164.308(a)(5)", "164.308(a)(5)(ii)(A)", "164.308(a)(5)(ii)(B)",
               "164.308(a)(5)(ii)(C)", "164.308(a)(5)(ii)(D)"], "Low"),
    ("AT-4",  ["164.308(a)(5)"], "Low"),

    # Audit and Accountability (AU)
    ("AU-1",  ["164.308(a)(1)(ii)(D)"], "Low"),
    ("AU-2",  ["164.308(a)(1)(ii)(D)", "164.308(a)(5)(ii)(C)", "164.312(b)"], "Low"),
    ("AU-3",  ["164.312(b)"], "Low"),
    ("AU-4",  ["164.312(b)"], "Moderate"),
    ("AU-5",  ["164.312(b)"], "Moderate"),
    ("AU-6",  ["164.308(a)(1)(ii)(D)", "164.308(a)(5)(ii)(C)"], "Low"),
    ("AU-7",  ["164.308(a)(1)(ii)(D)"], "Moderate"),
    ("AU-8",  ["164.312(b)"], "Low"),
    ("AU-9",  ["164.308(a)(1)(ii)(D)", "164.312(b)"], "Low"),
    ("AU-11", ["164.316(b)(2)(i)"], "Low"),
    ("AU-12", ["164.308(a)(1)(ii)(D)", "164.312(b)"], "Low"),

    # Assessment, Authorization, and Monitoring (CA)
    ("CA-1",  ["164.308(a)(1)", "164.308(a)(8)"], "Low"),
    ("CA-2",  ["164.308(a)(1)", "164.308(a)(8)"], "Low"),
    ("CA-3",  ["164.308(b)(1)"], "Low"),
    ("CA-5",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("CA-6",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("CA-7",  ["164.308(a)(1)", "164.308(a)(8)"], "Low"),
    ("CA-9",  ["164.308(b)(1)"], "Low"),

    # Configuration Management (CM)
    ("CM-1",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("CM-2",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("CM-6",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("CM-7",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("CM-8",  ["164.308(a)(1)(ii)(A)"], "Low"),

    # Contingency Planning (CP)
    ("CP-1",  ["164.308(a)(7)"], "Low"),
    ("CP-2",  ["164.308(a)(7)", "164.308(a)(7)(ii)(B)", "164.308(a)(7)(ii)(C)",
               "164.308(a)(7)(ii)(E)", "164.310(a)(2)(i)"], "Low"),
    ("CP-3",  ["164.308(a)(7)(ii)(D)"], "Moderate"),
    ("CP-4",  ["164.308(a)(7)(ii)(D)"], "Low"),
    ("CP-6",  ["164.308(a)(7)(ii)(A)", "164.310(d)(2)(iv)"], "Moderate"),
    ("CP-7",  ["164.308(a)(7)(ii)(C)"], "Moderate"),
    ("CP-8",  ["164.308(a)(7)(ii)(C)"], "Moderate"),
    ("CP-9",  ["164.308(a)(7)(ii)(A)", "164.310(d)(2)(iv)"], "Low"),
    ("CP-10", ["164.308(a)(7)(ii)(B)", "164.308(a)(7)(ii)(C)"], "Low"),

    # Identification and Authentication (IA)
    ("IA-1",  ["164.308(a)(5)(ii)(D)"], "Low"),
    ("IA-2",  ["164.308(a)(5)(ii)(C)", "164.308(a)(5)(ii)(D)",
               "164.312(a)(2)(i)", "164.312(a)(2)(ii)", "164.312(d)"], "Low"),
    ("IA-3",  ["164.312(d)"], "Moderate"),
    ("IA-4",  ["164.312(a)(2)(i)"], "Low"),
    ("IA-5",  ["164.308(a)(5)(ii)(D)", "164.312(d)"], "Low"),
    ("IA-6",  ["164.312(d)"], "Low"),
    ("IA-7",  ["164.312(d)"], "Low"),
    ("IA-8",  ["164.312(d)"], "Low"),

    # Incident Response (IR)
    ("IR-1",  ["164.308(a)(6)"], "Low"),
    ("IR-2",  ["164.308(a)(6)"], "Low"),
    ("IR-4",  ["164.308(a)(6)", "164.308(a)(6)(ii)"], "Low"),
    ("IR-5",  ["164.308(a)(6)(ii)"], "Low"),
    ("IR-6",  ["164.308(a)(6)", "164.308(a)(6)(ii)"], "Low"),
    ("IR-7",  ["164.308(a)(6)"], "Low"),
    ("IR-8",  ["164.308(a)(6)(ii)"], "Low"),

    # Maintenance (MA)
    ("MA-1",  ["164.310(a)(2)(iv)"], "Low"),
    ("MA-2",  ["164.310(a)(2)(iv)"], "Low"),
    ("MA-3",  ["164.310(a)(2)(iv)"], "Moderate"),
    ("MA-4",  ["164.310(a)(2)(iv)"], "Low"),
    ("MA-5",  ["164.310(a)(2)(iv)"], "Low"),
    ("MA-6",  ["164.310(a)(2)(iv)"], "Moderate"),

    # Media Protection (MP)
    ("MP-1",  ["164.310(d)(1)"], "Low"),
    ("MP-2",  ["164.310(d)(1)", "164.310(d)(2)(iii)"], "Low"),
    ("MP-3",  ["164.310(d)(1)"], "Moderate"),
    ("MP-4",  ["164.310(d)(2)(iii)", "164.310(d)(2)(iv)"], "Moderate"),
    ("MP-5",  ["164.310(d)(1)"], "Moderate"),
    ("MP-6",  ["164.310(d)(1)", "164.310(d)(2)(i)", "164.310(d)(2)(ii)"], "Low"),
    ("MP-7",  ["164.310(d)(1)"], "Low"),

    # Physical and Environmental Protection (PE)
    ("PE-1",  ["164.310(a)(1)"], "Low"),
    ("PE-2",  ["164.310(a)(1)", "164.310(a)(2)(i)", "164.310(a)(2)(ii)",
               "164.310(a)(2)(iii)", "164.310(a)(2)(iv)"], "Low"),
    ("PE-3",  ["164.310(a)(1)", "164.310(a)(2)(ii)", "164.310(a)(2)(iii)", "164.310(c)"], "Low"),
    ("PE-5",  ["164.310(a)(2)(iii)"], "Low"),
    ("PE-6",  ["164.310(a)(2)(iii)"], "Low"),
    ("PE-8",  ["164.310(a)(2)(iv)"], "Low"),
    ("PE-9",  ["164.310(a)(2)(ii)"], "Low"),
    ("PE-13", ["164.310(a)(2)(ii)"], "Low"),
    ("PE-14", ["164.310(a)(2)(ii)"], "Low"),
    ("PE-15", ["164.310(a)(2)(ii)"], "Low"),
    ("PE-16", ["164.310(d)(1)"], "Low"),
    ("PE-17", ["164.310(b)"], "Low"),
    ("PE-18", ["164.310(c)"], "Moderate"),

    # Planning (PL)
    ("PL-1",  ["164.316(a)", "164.316(b)(2)(i)", "164.316(b)(2)(iii)"], "Low"),
    ("PL-2",  ["164.308(a)(7)(ii)(E)", "164.316(b)(1)", "164.316(b)(2)(ii)"], "Low"),
    ("PL-4",  ["164.308(a)(3)(ii)(A)"], "Low"),

    # Program Management (PM)
    ("PM-1",  ["164.316(a)"], "Low"),
    ("PM-2",  ["164.308(a)(2)"], "Low"),
    ("PM-4",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("PM-9",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("PM-10", ["164.308(a)(1)(ii)(B)"], "Low"),

    # Personnel Security (PS)
    ("PS-1",  ["164.308(a)(3)"], "Low"),
    ("PS-3",  ["164.308(a)(3)", "164.308(a)(3)(ii)(A)", "164.308(a)(3)(ii)(B)"], "Low"),
    ("PS-4",  ["164.308(a)(3)(ii)(B)", "164.308(a)(3)(ii)(C)"], "Low"),
    ("PS-5",  ["164.308(a)(3)(ii)(B)", "164.308(a)(3)(ii)(C)"], "Low"),
    ("PS-6",  ["164.308(b)(1)"], "Low"),
    ("PS-7",  ["164.308(b)(1)"], "Low"),
    ("PS-8",  ["164.308(a)(1)(ii)(C)"], "Low"),

    # Risk Assessment (RA)
    ("RA-1",  ["164.308(a)(1)"], "Low"),
    ("RA-2",  ["164.308(a)(1)(ii)(A)"], "Low"),
    ("RA-3",  ["164.308(a)(1)", "164.308(a)(1)(ii)(A)", "164.308(a)(1)(ii)(B)"], "Low"),
    ("RA-5",  ["164.308(a)(1)", "164.308(a)(1)(ii)(A)", "164.308(a)(1)(ii)(B)"], "Low"),
    ("RA-7",  ["164.308(a)(1)(ii)(B)"], "Moderate"),

    # System and Services Acquisition (SA)
    ("SA-1",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("SA-2",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("SA-3",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("SA-4",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("SA-5",  ["164.316(b)(1)"], "Low"),
    ("SA-8",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("SA-9",  ["164.308(b)(1)", "164.314(a)(1)", "164.314(a)(2)(i)"], "Low"),

    # System and Communications Protection (SC)
    ("SC-1",  ["164.312(e)(1)"], "Low"),
    ("SC-5",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("SC-7",  ["164.312(e)(1)"], "Low"),
    ("SC-8",  ["164.312(e)(1)", "164.312(e)(2)(i)", "164.312(e)(2)(ii)"], "Moderate"),
    ("SC-12", ["164.312(a)(2)(iv)", "164.312(e)(2)(ii)"], "Low"),
    ("SC-13", ["164.312(a)(2)(iv)", "164.312(e)(2)(ii)"], "Low"),
    ("SC-15", ["164.310(b)"], "Low"),
    ("SC-28", ["164.312(a)(2)(iv)"], "Moderate"),

    # System and Information Integrity (SI)
    ("SI-1",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("SI-2",  ["164.308(a)(1)(ii)(B)"], "Low"),
    ("SI-3",  ["164.308(a)(5)(ii)(B)"], "Low"),
    ("SI-4",  ["164.308(a)(1)(ii)(D)", "164.308(a)(5)(ii)(B)"], "Low"),
    ("SI-5",  ["164.308(a)(5)(ii)(A)"], "Low"),
    ("SI-6",  ["164.308(a)(1)(ii)(D)"], "Moderate"),
    ("SI-7",  ["164.312(c)(1)", "164.312(c)(2)", "164.312(e)(2)(i)"], "Moderate"),
    ("SI-10", ["164.308(a)(1)(ii)(B)"], "Low"),
    ("SI-12", ["164.308(a)(1)"], "Low"),
]


# ---------------------------------------------------------------------------
# Helpers to parse OSCAL JSON
# ---------------------------------------------------------------------------

def _collect_prose(parts):
    """Recursively collect prose from OSCAL part objects."""
    texts = []
    for part in parts or []:
        if part.get("name") in ("statement", "item"):
            if "prose" in part:
                texts.append(part["prose"].strip())
            texts.extend(_collect_prose(part.get("parts", [])))
    return texts


def _control_text(ctrl):
    """Return a clean single-string statement for one OSCAL control object."""
    title = ctrl.get("title", "").strip()
    parts = ctrl.get("parts", [])
    prose_chunks = _collect_prose(parts)
    body = " ".join(prose_chunks).strip()
    # Remove OSCAL parameter placeholders like {{ insert: param, ac-1_prm_1 }}
    body = re.sub(r"\{\{[^}]+\}\}", "[Assignment: org-defined]", body)
    if body:
        return f"{title}: {body}"
    return title


def fetch_nist_controls():
    """Download and index NIST SP 800-53 Rev 5 control texts from OSCAL JSON."""
    print(f"Downloading NIST OSCAL catalog from GitHub …")
    resp = requests.get(OSCAL_URL, timeout=60)
    resp.raise_for_status()
    catalog = resp.json().get("catalog", {})

    index = {}
    for group in catalog.get("groups", []):
        for ctrl in group.get("controls", []):
            ctrl_id = ctrl["id"].upper()          # e.g. ac-1 -> AC-1
            index[ctrl_id] = _control_text(ctrl)
            for enh in ctrl.get("controls", []):
                enh_id = enh["id"].upper()
                index[enh_id] = _control_text(enh)

    print(f"  Loaded {len(index)} controls/enhancements.")
    return index


# ---------------------------------------------------------------------------
# Build crosswalk DataFrame
# ---------------------------------------------------------------------------

def build_crosswalk(nist_index):
    rows = []
    missing = []
    for nist_id, hipaa_citations, baseline in NIST_TO_HIPAA:
        nist_text = nist_index.get(nist_id, "")
        if not nist_text:
            missing.append(nist_id)
        for citation in hipaa_citations:
            hipaa_text = HIPAA.get(citation, "")
            if not hipaa_text:
                print(f"  WARNING: no HIPAA text found for {citation}")
            rows.append({
                "Focal Document Element": nist_id,
                "Focal Document Element Description": nist_text,
                "Security Control Baseline": baseline,
                "Reference Document Element": citation,
                "Reference Document Element Description": hipaa_text,
                "Fulfilled By (Y/N)": "",
                "Group Identifier (optional)": "",
                "Comments (optional)": "",
                "Strength of Relationship (optional)": "",
            })
    if missing:
        print(f"  WARNING: NIST text not found for: {missing}")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    nist_index = fetch_nist_controls()
    df = build_crosswalk(nist_index)

    # Drop rows where both NIST and HIPAA text are empty
    df = df[
        df["Focal Document Element Description"].str.strip().astype(bool) |
        df["Reference Document Element Description"].str.strip().astype(bool)
    ]

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(df)} crosswalk rows to {OUTPUT_PATH}")

    # Summary
    unique_nist   = df["Focal Document Element"].nunique()
    unique_hipaa  = df["Reference Document Element"].nunique()
    print(f"  Unique NIST controls : {unique_nist}")
    print(f"  Unique HIPAA provisions: {unique_hipaa}")
    print("\nDone. Update the notebook path to use this file:")
    print(f"  DATA_RAW / 'nist_800_53_rev5_hipaa_crosswalk_full.csv'")


if __name__ == "__main__":
    main()

"""Quick start: map a few NIST SP 800-53 controls to HIPAA provisions with RegMap."""
from regmap_map import map_control

CONTROLS = [
    "The organization enforces multi-factor authentication for remote access.",
    "Employ integrity verification tools to detect unauthorized changes to software and firmware.",
    "Retain audit records for a defined period to support after-the-fact investigations.",
]

for control in CONTROLS:
    print("\nNIST control:", control)
    for r in map_control(control, top_k=3):
        print(f"  {r['score']:.3f}  {r['hipaa_citation']}")

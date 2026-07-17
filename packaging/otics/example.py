"""Quick start: score a normal sensor reading, then a tampered one."""
from otics_score import score_reading, BASELINE_READING

print("normal reading:", score_reading(BASELINE_READING))
tampered = dict(BASELINE_READING)
tampered["P1_B2004"] = 8.0      # manipulate a sensor
tampered["P1_FT01"] = 900.0
print("tampered reading:", score_reading(tampered))

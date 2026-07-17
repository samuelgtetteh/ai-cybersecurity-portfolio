"""Quick start: score a normal login, then a burst of anomalous logins from one account."""
from identity_score import score_event

print("normal login:")
print(" ", score_event({"src_user": "alice@DOM", "src_pc": "PC-ALICE", "auth_type": "Kerberos",
                        "logon_type": "Network", "orientation": "LogOn", "success": "Success"}))

print("\nsuspicious burst (one account hitting many machines with failed remote logons):")
for i in range(12):
    r = score_event({"src_user": "ANONYMOUS@DOM", "src_pc": f"SRV-{i:02d}",
                     "auth_type": "TotallyUnknownAuth", "logon_type": "RemoteInteractive",
                     "orientation": "LogOn", "success": "Fail"})
print("  final:", r)

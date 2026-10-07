"""Pulse nRESET via the probe. Note: the nRESET pad (tp-back-23) is user-asserted, not verified;
a full power-cycle is the reliable way to apply an erase/unlock."""
import time
from pyocd.core.helpers import ConnectHelper
sess = ConnectHelper.session_with_chosen_probe(auto_open=False, blocking=False, options={"target_override": "cortex_m"})
p = sess.probe
p.open()
p.assert_reset(True); time.sleep(0.2); p.assert_reset(False); time.sleep(1.0)
p.close()
print("reset pulsed")

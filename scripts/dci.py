# SPDX-License-Identifier: GPL-2.0-or-later
"""Series 2 (EFR32FG22) debug-lock status / device erase over the DCI access port, via a pyOCD CMSIS-DAP probe.

usage: dci.py status|erase [swd_clock_hz]     (default 20000)

'erase' is DESTRUCTIVE (wipes flash); power-cycle the tag afterwards. See docs/debug-unlock.md.
"""
import sys,time
from pyocd.core.helpers import ConnectHelper
from pyocd.probe.debug_probe import DebugProbe
sess=ConnectHelper.session_with_chosen_probe(auto_open=False,blocking=False,options={"target_override":"cortex_m"})
p=sess.probe
p.open(); p.set_clock(int(sys.argv[2]) if len(sys.argv)>2 else 20000); p.connect(DebugProbe.Protocol.SWD)
ones=(1<<51)-1
for attempt in range(8):
    try:
        p.swj_sequence(51,ones); p.swj_sequence(16,0xE79E); p.swj_sequence(51,ones); p.swj_sequence(8,0)
        print('DPIDR',hex(p.read_dp(0x0))); break
    except Exception as e:
        print('retry',attempt,str(e)[:40]); p.swj_sequence(8,0)
else: sys.exit('no DP')
p.write_dp(0x0,0x1e); p.write_dp(0x4,0x50000000)
p.write_dp(0x8,0x01000000)          # APSEL=1 (DCI), bank 0
p.write_ap(0x00,0x22000002)         # CSW
def ap_read(tar):
    p.write_ap(0x04,tar)
    p.read_ap(0x0C)                  # posted
    return p.read_dp(0x0C)           # RDBUFF
def status(): return ap_read(0x1008)
def wcmd(w):
    for i in range(100):
        s=status()
        if s&1: time.sleep(.01); continue
        if s&0x100: raise Exception('RDATAVALID set, cannot write')
        p.write_ap(0x04,0x1000); p.write_ap(0x0C,w); return
    raise Exception('write timeout')
def rresp():
    for i in range(100):
        s=status()
        if s&0x100: return ap_read(0x1004)
        time.sleep(.01)
    raise Exception('read timeout')
print('DCIID',hex(ap_read(0x10FC)),'(expect 0xdc11d)')
mode=sys.argv[1]
if mode=='status':
    wcmd(8); wcmd(0xFE010000)
    n=rresp(); print('resp len word',hex(n))
    if n&0xFFFF0000: sys.exit('bad response')
    words=[]; rem=n-4
    while rem>0:
        rem-=4; words.append(rresp())
    print('SESTATUS words',[hex(w) for w in words])
    idx=7 if n==0x28 else 3
    d=words[idx]
    print('debug lock config   :', 'ENABLED' if d&1 else 'disabled')
    print('device erase allowed:', 'yes' if d&2 else 'no')
    print('secure debug        :', 'ENABLED' if d&4 else 'disabled')
    print('debug lock hw status:', 'LOCKED' if d&0x20 else 'unlocked')
elif mode=='erase':
    wcmd(8); wcmd(0x430F0000); print('erase cmd written')
    try:
        r=rresp(); print('SE response length word',hex(r)); r2=rresp(); print('SE status word',hex(r2),'(0 = OK)')
    except Exception as e: print('no response:',e)
    time.sleep(2)
p.disconnect(); p.close()

"""Fast repeated writes to ONE target address over SWD (for bit-banging a GPIO port from the host).

pyOCD's write_memory_block32 auto-increments the address; here the MEM-AP address auto-increment is switched off so a whole list of
values lands on the same register (e.g. GPIO DOUT) in a few probe transactions instead of one USB round trip per write.
"""
from pyocd.coresight.ap import MEM_AP_CSW, MEM_AP_TAR, MEM_AP_DRW, CSW_ADDRINC, CSW_SIZE32

CHUNK = 256

def burst(target, addr, values):
    ap = target.selected_core.ap
    ap.write_reg(ap._reg_offset + MEM_AP_CSW, (ap._csw & ~CSW_ADDRINC) | CSW_SIZE32)     # address increment off
    ap.write_reg(ap._reg_offset + MEM_AP_TAR, addr)
    drw = ap.address.address + ap._reg_offset + MEM_AP_DRW
    for i in range(0, len(values), CHUNK):
        ap.dp.write_ap_multiple(drw, values[i:i + CHUNK])
    ap.write_reg(ap._reg_offset + MEM_AP_CSW, ap._csw | CSW_SIZE32)                       # restore normal access

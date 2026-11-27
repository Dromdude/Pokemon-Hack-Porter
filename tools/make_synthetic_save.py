"""Writes a synthetic Lazarus-format save with Gen 8/9 edge cases (regional forms,
unusable moves, a Legends: Arceus Pokemon) into an existing Lazarus save:
    python3 tools/make_synthetic_save.py tests/saves/lazarus.sav out.sav"""
import struct,sys
src,dst=sys.argv[1],sys.argv[2]
raw=bytearray(open(src,'rb').read())
ORD=["GAEM","GAME","GEAM","GEMA","GMAE","GMEA","AGEM","AGME","AEGM","AEMG","AMGE","AMEG","EGAM","EGMA","EAGM","EAMG","EMGA","EMAG","MGAE","MGEA","MAGE","MAEG","MEGA","MEAG"]
CH={' ':0}
for i in range(26): CH[chr(65+i)]=0xBB+i; CH[chr(97+i)]=0xD5+i
def enc(t,n): b=bytes(CH[c] for c in t[:n]); return b+b'\xff'*(n-len(b))
def mon(pid,species,moves,level,exp,nick,abil=0,egg=0,hn=0,ball=1):
    otid=(51005<<16)|13469
    n12=enc(nick,12)
    G=struct.pack('<HHI',species,0,exp|(n12[10]<<21))+bytes([0,70])+struct.pack('<H',ball|(n12[11]<<6))
    A=struct.pack('<4H',*moves)+bytes([10,10,10,10])
    E=bytes([1,2,3,4,5,6]+[0]*6)
    iv=sum(v<<(5*i) for i,v in enumerate([31,30,29,28,27,26]))|(egg<<30)
    M=bytes([0,5])+struct.pack('<H',5|(3<<7))+struct.pack('<II',iv,abil<<29)
    sub={'G':G,'A':A,'E':E,'M':M}; o=ORD[pid%24]
    dec=b''.join(sub[c] for c in o)
    chk=sum(struct.unpack('<24H',dec))&0xffff
    key=pid^otid
    encd=b''.join(struct.pack('<I',struct.unpack_from('<I',dec,i)[0]^key) for i in range(0,48,4))
    hdr=struct.pack('<II',pid,otid)+n12[:10]+bytes([2|(hn<<3), 2|(4 if egg else 0)])+enc('N',7)+bytes([0])+struct.pack('<HH',chk,0)
    b=hdr+encd+struct.pack('<I',0)+bytes([level,0])+struct.pack('<7H',*([20]*7))
    assert len(b)==100; return b
# find newest slot section 1
best=None
for base in (0,14*4096):
    for i in range(14):
        o=base+i*4096; sid,chk,sig,idx=struct.unpack_from('<HHII',raw,o+0xFF4)
        if sid==1 and (best is None or idx>best[1]): best=(o,idx)
o=best[0]
mons_old=[
 mon(0x12345671,7,[664,0,0,0],20,8000,'Squirtle'),
 mon(0x12345672,95,[704,0,0,0],20,8000,'Onix'),
 mon(0x12345673,1289,[33,0,0,0],10,1000,'Sprigatito'),               # Gen 9 -> blocked
 mon(0x12345674,25,[33,0,0,0],5,125,'Egg',egg=1),                    # egg -> skipped
 mon(0x12345675,1700,[33,0,0,0],10,1000,'Mystery'),                  # unknown -> blocked
 mon(0x12345676,198,[64,0,0,0],13,1542,'Crowbarsssss',hn=5),         # 12-char nick + mint -> pk6
]
mons=[
 mon(0x22345671,974,[10,0,0,0],10,1000,'Meowth'),                 # Galarian Meowth -> pk8 form 2
 mon(0x22345672,993,[52,0,0,0],10,1250,'Growlithe'),              # Hisuian Growlithe -> pk9
 mon(0x22345673,1405,[39,0,0,0],10,1000,'Wooper'),                # Paldean Wooper -> pk9
 mon(0x22345674,1093,[33,0,0,0],30,27000,'Darmanitan'),           # Galarian Darmanitan (Zen) -> form 2
 mon(0x22345675,824,[228,522,0,0],10,1000,'Blipbug'),             # Pursuit can't be used in SwSh/SV
 mon(0x22345676,899,[33,0,0,0],10,1250,'Wyrdeer'),                # Legends: Arceus only -> blocked
]
struct.pack_into('<I',raw,o+0x234,6)
for i,b in enumerate(mons): raw[o+0x238+i*100:o+0x238+(i+1)*100]=b
t=sum(struct.unpack_from('<992I',raw,o))&0xffffffff
struct.pack_into('<H',raw,o+0xFF6,((t>>16)+(t&0xffff))&0xffff)
open(dst,'wb').write(raw)

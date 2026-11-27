# Builds data.json (the reference tables embedded in pokemon_hack_porter.py) from
# local checkouts of PKHeX, pokeemerald-expansion and OpenHome. Set the paths with
# environment variables, then run:  python3 tools/gen_data.py && python3 tools/build.py
#   PKHEX_CORE  path to PKHeX/PKHeX.Core          (https://github.com/kwsch/PKHeX)
#   EXPANSION   path to pokeemerald-expansion     (https://github.com/rh-hideout/pokeemerald-expansion)
#   OPENHOME    path to OpenHome/src/core/save    (https://github.com/andrewbenington/OpenHome)
import os, re, struct, json, unicodedata
EXP = os.environ.get('EXPANSION', 'ref/exp'); PK = os.environ.get('PKHEX_CORE', 'ref/pkhex/PKHeX.Core')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')
def lines(p): return open(p,encoding='utf-8').read().split('\n')
species=lines(PK+'/Resources/text/other/en/text_Species_en.txt')[:1026]
moves=lines(PK+'/Resources/text/other/en/text_Moves_en.txt')[:920]
abil=lines(PK+'/Resources/text/other/en/text_Abilities_en.txt')[:311]
assert species[1025]=='Pecharunt' and moves[919]=='Malignant Chain' and abil[310]=='Poison Puppeteer', (species[1025],moves[919],abil[310])
def norm(s):
    s=s.replace('♀','F').replace('♂','M')
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode()
    return re.sub(r'[^A-Z0-9]','',s.upper())
# national dex constants
nd={}; n=0
for l in lines(EXP+'/include/constants/pokedex.h'):
    m=re.match(r'\s*(NATIONAL_DEX_\w+)\s*,',l)
    if m:
        if m.group(1)=='NATIONAL_DEX_NONE': n=0
        nd[m.group(1)]=n; n+=1
assert nd['NATIONAL_DEX_PECHARUNT']==1025 and nd['NATIONAL_DEX_SPRIGATITO']==906
# expansion species constants
sp={}
for l in lines(EXP+'/include/constants/species.h'):
    m=re.match(r'\s*(SPECIES_\w+)\s*=\s*(\d+)\s*,',l)
    if m: sp[m.group(1)]=int(m.group(2))
# species_info: species -> natdex
sp_nat={}
cur=None
import glob
for f in sorted(glob.glob(EXP+'/src/data/pokemon/species_info/gen_*_families.h')):
    for l in lines(f):
        m=re.match(r'\s*\[(SPECIES_\w+)\]\s*=',l)
        if m: cur=m.group(1)
        m=re.search(r'\.natDexNum\s*=\s*(NATIONAL_DEX_\w+)',l)
        if m and cur and cur not in sp_nat: sp_nat[cur]=nd[m.group(1)]
# expansion id -> (natdex, kind, constname) for ids > 905 (ids <=905 are national dex)
forms={}
for name,i in sp.items():
    if i<=905: assert sp_nat.get(name,i)==i, (name,i,sp_nat.get(name)); continue
    nat=sp_nat.get(name)
    if nat is None:   # macro-generated entries (e.g. Unown letters): match by constant-name prefix
        parts=name[len('SPECIES_'):].split('_')
        for k in range(len(parts)-1,0,-1):
            cand=norm('_'.join(parts[:k]))
            hit=[j for j in range(1,1026) if norm(species[j])==cand]
            if hit: nat=hit[0]; break
    if nat is None: continue
    base=species[nat]
    suf=name[len('SPECIES_'):]
    kind='form'
    for k in ('MEGA','GMAX','PRIMAL','ULTRA','ETERNAMAX','TOTEM'):
        if re.search(r'(^|_)'+k+r'(_|$)',suf): kind='battle'
    for k,v in (('ALOLA','alola'),('GALAR','galar'),('HISUI','hisui'),('PALDEA','paldea')):
        if re.search(r'(^|_)'+k+r'(_|$)',suf): kind=v
    if i>=1289 and nat>=906 and norm(base)==norm(suf): kind='base'   # Gen 9 base species live at 1289+
    if norm(base)==norm(suf): kind='base'
    if nat==25 and kind=='alola': kind='form'   # Pikachu's Alola Cap is not a regional form
    forms[i]=(nat,kind,suf)
# moves: expansion id -> official id for ids > 621
emoves={}
for l in lines(EXP+'/include/constants/moves.h'):
    m=re.match(r'\s*MOVE_(\w+)\s*=\s*(\d+)\s*,',l)
    if m: emoves[int(m.group(2))]=m.group(1)
offnorm={}
for i,nm in enumerate(moves):
    offnorm.setdefault(norm(nm),i)
fix={'VISEGRIP':'VISEGRIP'}
mmap={}; miss=[]
for i,nm in sorted(emoves.items()):
    o=offnorm.get(norm(nm))
    if i<=621:
        if o!=i: miss.append(('LOW',i,nm,o))
        continue
    if o is None: miss.append((i,nm)); continue
    mmap[i]=o
# personal tables
def ptab(path,size):
    d=open(path,'rb').read(); return [d[i:i+size] for i in range(0,len(d),size)]
ao=ptab(PK+'/Resources/byte/personal/personal_ao',0x50)
uu=ptab(PK+'/Resources/byte/personal/personal_uu',0x54)
em=ptab(PK+'/Resources/byte/personal/personal_e',0x1C)
def p6(e): return [e[0x12],e[0x15],e[0x18],e[0x19],e[0x1A]]
AO=[None]+[p6(ao[i]) for i in range(1,722)]
UU=[None]+[p6(uu[i]) for i in range(1,810)]
ALOLA={}
for i,(nat,kind,suf) in forms.items():
    if kind=='alola':
        fsi=struct.unpack_from('<H',uu[nat],0x1C)[0]
        ALOLA[nat]=p6(uu[fsi])   # form 1 entry
# gen3 national->internal
src=open(PK+'/PKM/Util/Conversion/SpeciesConverter.cs').read()
body=re.search(r'Table3NationalToInternal =>\s*\[(.*?)\];',src,re.S).group(1)
shift=[int(x) for x in re.findall(r'-?\d+',body)]
assert len(shift)==135
G3INT=[0]+[i if i<252 else i+shift[i-252] for i in range(1,387)]
G3GROW=[None]+[em[i][0x13] for i in range(1,387)]
G3AB=[None]+[[em[i][0x16],em[i][0x17]] for i in range(1,387)]
assert G3INT[285]==306
# --- base PP per official move (from expansion moves_info.h)
ppsrc=open(EXP+'/src/data/moves_info.h').read()
cur=None; ppc={}
for l in ppsrc.split('\n'):
    mm=re.match(r'\s*\[(MOVE_\w+)\]\s*=',l)
    if mm: cur=mm.group(1)
    mm=re.search(r'\.pp\s*=\s*(?:[^?,]*\?\s*)?(\d+)',l)
    if mm and cur and cur not in ppc: ppc[cur]=int(mm.group(1))
const_id={}
for l in lines(EXP+'/include/constants/moves.h'):
    mm=re.match(r'\s*(MOVE_\w+)\s*=\s*(\d+)\s*,',l)
    if mm: const_id.setdefault(mm.group(1),int(mm.group(2)))
PP=[0]*920
for c,v in ppc.items():
    e=const_id.get(c)
    if e is None: continue
    o=e if e<=621 else mmap.get(e)
    if o and o<920 and not PP[o]: PP[o]=v
# --- Dynamic Pokemon Expansion (CFRU) species numbering, from OpenHome's Unbound map (GPL-3.0)
OH=os.environ.get('OPENHOME', 'ref/oh/src/core/save')
dpe={}
for l in open(OH+'/unbound/conversion/UnboundSpeciesMap.ts',encoding='utf-8'):
    mm=re.match(r"\s*'(\d+)':\s*\{\s*nationalDex:\s*(\d+),\s*formIndex:\s*(\d+)(,\s*extraFormIndex:[^}]*)?\s*\}\s*,?\s*(?://\s*(.*))?",l)
    if not mm: continue
    idx,nat,form,extra,cm=int(mm.group(1)),int(mm.group(2)),int(mm.group(3)),mm.group(4),(mm.group(5) or '')
    kind='base' if form==0 and not extra else 'form'
    if extra or re.search(r'Mega|Giga|Primal|Gmax|Totem',cm): kind='battle'
    for k,v in (('Alola','alola'),('Galar','galar'),('Hisui','hisui'),('Paldea','paldea')):
        if '-'+k in cm: kind=v
    if nat==25 and kind=='alola': kind='form'
    dpe[idx]=[nat,form,kind,cm.strip()]
for i in range(413,440): dpe[i]=[201,0,'base','Unown']
# CFRU move list (index -> name) -> official move ids
msrc=open(OH+'/cfru/conversion/Gen3CFRUMovesIndex/index.ts').read()
lst=re.search(r'const Gen3CFRUMoves = \[(.*?)\]',msrc,re.S).group(1)
cn=[a or b for a,b in re.findall(r"'((?:[^'\\]|\\.)*)'|\"([^\"]*)\"",lst)]
CFRUMOVES=[offnorm.get(norm(n)) for n in cn]
print('dpe',len(dpe),'cfru moves',len(CFRUMOVES),'unmapped',sum(1 for x in CFRUMOVES[1:] if x is None),'PP zero',[i for i in range(1,920) if not PP[i]][:10])

# --- v1.1: Sword/Shield + Scarlet/Violet personal data, form numbers, unusable moves
def ptab_info(path, size, off):
    rows = ptab(path, size)
    out = []
    for e in rows:
        g = e[off['gender']]; gr = e[off['growth']]
        a = [struct.unpack_from('<H', e, off['ab'] + 2*k)[0] for k in range(3)]
        fsi = struct.unpack_from('<H', e, off['fsi'])[0]; fc = e[off['fc']]
        present = off['present'](e)
        out.append([int(present), g, gr, a[0], a[1], a[2], fsi, fc, e[6]] + list(e[0:6]))
    return out
SWSH_RAW = ptab_info(PK+'/Resources/byte/personal/personal_swsh', 0xB0,
    dict(gender=0x12, growth=0x15, ab=0x18, fsi=0x1E, fc=0x20, present=lambda e: (e[0x21] >> 6) & 1))
SV_RAW = ptab_info(PK+'/Resources/byte/personal/personal_sv', 0x50,
    dict(gender=0x0C, growth=0x0F, ab=0x12, fsi=0x18, fc=0x1A, present=lambda e: e[0x1C] != 0))
def by_form(raw, maxsp):
    """{ 'nat' or 'nat:form' : [present, gender, growth, a1, a2, ah, type1] }"""
    t = {}
    for nat in range(1, maxsp + 1):
        r = raw[nat]
        t[str(nat)] = r[:6] + [r[8]] + r[9:15]
        fsi, fc = r[6], r[7]
        for f in range(1, fc):
            if fsi:
                rr = raw[fsi + f - 1]
                t['%d:%d' % (nat, f)] = rr[:6] + [rr[8]] + rr[9:15]
    return t
SWSH = by_form(SWSH_RAW, 898)
SV = by_form(SV_RAW, 1025)
assert SWSH['824'][0] == 1 and SV['906'][0] == 1 and SWSH['52:2'][0] == 1, (SWSH['824'], SV['906'])
def dummied(fname):
    s = open(PK + '/Moves/' + fname).read()
    body = re.search(r'DummiedMoves =>[^\[]*\[(.*?)\];', s, re.S).group(1)
    b = [int(x, 16) for x in re.findall(r'0x[0-9A-F]{2}', body)]
    return [m for m in range(len(b) * 8) if b[m >> 3] >> (m & 7) & 1]
DUMMY8, DUMMY9 = dummied('MoveInfo8.cs'), dummied('MoveInfo9.cs')
# Gen 9 internal species numbers (PKHeX SpeciesConverter)
scsrc = open(PK + '/PKM/Util/Conversion/SpeciesConverter.cs').read()
t9 = [int(x) for x in re.findall(r'-?\d+', re.search(r'Table9NationalToInternal =>\s*\[(.*?)\];', scsrc, re.S).group(1))]
G9INT = {str(917 + i): 917 + i + d for i, d in enumerate(t9) if d}
# expansion form numbers: position in each species' form table (G-Max entries aren't real forms)
FORMNUM = {}
fsrc = open(EXP + '/src/data/pokemon/form_species_tables.h').read()
for body in re.findall(r'FormSpeciesIdTable\[\]\s*=\s*\{(.*?)\};', fsrc, re.S):
    names = [n for n in re.findall(r'\b(SPECIES_\w+)\b', body) if n != 'SPECIES_NONE' and '_GMAX' not in n]
    seen = []
    for n in names:
        if n not in seen:
            seen.append(n)
    for k, n in enumerate(seen):
        if n in sp and k:
            FORMNUM[str(sp[n])] = k

data=dict(SWSH=SWSH,SV=SV,DUMMY8=DUMMY8,DUMMY9=DUMMY9,G9INT=G9INT,FORMNUM=FORMNUM,PP=PP,DPE={str(k):v for k,v in dpe.items()},CFRUMOVES=CFRUMOVES,SPECIES=species,MOVES=moves,ABILITIES=abil,FORMS={str(k):v for k,v in forms.items()},
          MOVEMAP={str(k):v for k,v in mmap.items()},AO=AO,UU=UU,ALOLA={str(k):v for k,v in ALOLA.items()},G3INT=G3INT,G3AB=G3AB,G3GROW=G3GROW,MAXEXP=max(sp.values()))
json.dump(data,open(OUT,'w'),separators=(',',':'),ensure_ascii=False)
print('forms',len(forms),'kinds',{k:sum(1 for v in forms.values() if v[1]==k) for k in set(v[1] for v in forms.values())})
print('movemap',len(mmap),'missing',miss[:40], len(miss))
print('unmapped species ids >905:',[ (n,i) for n,i in sp.items() if i>905 and i not in forms][:20])

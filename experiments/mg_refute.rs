// WEERLEGGINGSMOTOR voor de maxgame-klasse (triplet + slotmaskers vast).
//
// DE IDENTITEIT (bewezen in experiments/SCHEDULEPROOF.md, numeriek geijkt):
//     score = SOM over de maximale EINDruns L van g_L(geschiedenis van L)
//     g_L   = alle woordscores op L + 50 * (aantal 7-tegelzetten met L als hoofdlijn)
// Elke gescoorde run ligt in precies EEN maximale eindrun (span-vulregel) en elke bingo hoort
// bij precies EEN hoofdlijn.  Daarmee valt de score uiteen in per-lijn-termen, en een
// bovengrens per lijn sommeert tot een geldige bovengrens op de totaalscore.
//
// SUBCOMMANDO'S
//   tables  SHARD NSHARD   per lijnsleutel de exacte per-lijn-DP over ALLE passende woorden
//                          -> (Umax, top-K (U, letterprofiel), staartgrens)
//   merge                  shards samenvoegen tot tables.bin
//   eval    OCCFILE        bovengrens per bezetting (ijking)
//   maxcol                 GLOBALE maximalisatie van de bovengrens over ALLE bezettingen
//                          (kolom-separabele relaxatie + rugzak op het tegelbudget)
//   enum                   uitputtende opsomming van de kolom-parameterfamilie + weerlegging
//
// Bouwen:  rustc -O -C target-cpu=native experiments/mg_refute.rs -o experiments/mg_refute_bin

use std::collections::HashMap;
use std::env;
use std::fs::File;
use std::io::{BufRead, BufReader, Read, Write, BufWriter};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};

const NEG: i64 = -(1i64 << 40);
const ANCHOR_ROWS: [usize; 3] = [0, 7, 14];

// ------------------------------------------------------------------ eigen hash-set voor woorden
struct WordSet {
    keys: Vec<u128>,
    mask: usize,
}
impl WordSet {
    fn new(cap: usize) -> Self {
        let mut n = 16usize;
        while n < cap * 2 {
            n <<= 1;
        }
        WordSet { keys: vec![0u128; n], mask: n - 1 }
    }
    #[inline]
    fn hash(k: u128) -> usize {
        let a = (k as u64) ^ ((k >> 64) as u64).wrapping_mul(0x9E3779B97F4A7C15);
        let mut h = a.wrapping_mul(0xff51afd7ed558ccd);
        h ^= h >> 33;
        h as usize
    }
    fn insert(&mut self, k: u128) {
        let mut i = Self::hash(k) & self.mask;
        loop {
            if self.keys[i] == 0 {
                self.keys[i] = k;
                return;
            }
            if self.keys[i] == k {
                return;
            }
            i = (i + 1) & self.mask;
        }
    }
    #[inline]
    fn contains(&self, k: u128) -> bool {
        let mut i = Self::hash(k) & self.mask;
        loop {
            let v = self.keys[i];
            if v == 0 {
                return false;
            }
            if v == k {
                return true;
            }
            i = (i + 1) & self.mask;
        }
    }
}

#[inline]
fn wkey(w: &[u8]) -> u128 {
    let mut k: u128 = 1;
    for &c in w {
        k = k * 27 + c as u128;
    }
    k
}

// ------------------------------------------------------------------ gegevens
struct Data {
    bylen: Vec<Vec<u8>>, // bylen[L] = aaneengesloten woorden van lengte L
    nwords: Vec<usize>,
    set: WordSet,
    lm: [[i64; 15]; 15], // [y][x]
    wm: [[i64; 15]; 15],
    val: [i64; 27],
    bag: [i64; 27],
    rest: [i64; 27],
    nblank: i64,
    trip: [[u8; 15]; 3],
}

fn load(dir: &str) -> Data {
    let mut f = File::open(format!("{}/dict.bin", dir)).expect("dict.bin");
    let mut buf = Vec::new();
    f.read_to_end(&mut buf).unwrap();
    let mut p = 0usize;
    let rd_u32 = |b: &[u8], p: &mut usize| -> u32 {
        let v = u32::from_le_bytes([b[*p], b[*p + 1], b[*p + 2], b[*p + 3]]);
        *p += 4;
        v
    };
    let magic = rd_u32(&buf, &mut p);
    assert_eq!(magic, 0x52454644);
    let mut bylen: Vec<Vec<u8>> = vec![Vec::new(); 16];
    let mut nwords = vec![0usize; 16];
    let mut total = 0usize;
    for l in 1..16usize {
        let n = rd_u32(&buf, &mut p) as usize;
        nwords[l] = n;
        bylen[l] = buf[p..p + n * l].to_vec();
        p += n * l;
        total += n;
    }
    let mut set = WordSet::new(total + 16);
    for l in 1..16usize {
        for i in 0..nwords[l] {
            set.insert(wkey(&bylen[l][i * l..(i + 1) * l]));
        }
    }
    // board.txt
    let br = BufReader::new(File::open(format!("{}/board.txt", dir)).expect("board.txt"));
    let lines: Vec<String> = br.lines().map(|x| x.unwrap()).collect();
    let nums = |s: &str| -> Vec<i64> { s.split_whitespace().map(|t| t.parse().unwrap()).collect() };
    let mut lm = [[0i64; 15]; 15];
    let mut wm = [[0i64; 15]; 15];
    for y in 0..15 {
        let v = nums(&lines[y]);
        for x in 0..15 {
            lm[y][x] = v[x];
        }
    }
    for y in 0..15 {
        let v = nums(&lines[15 + y]);
        for x in 0..15 {
            wm[y][x] = v[x];
        }
    }
    let mut val = [0i64; 27];
    for (i, v) in nums(&lines[30]).iter().enumerate() {
        val[i + 1] = *v;
    }
    let mut bag = [0i64; 27];
    for (i, v) in nums(&lines[31]).iter().enumerate() {
        bag[i + 1] = *v;
    }
    let mut rest = [0i64; 27];
    for (i, v) in nums(&lines[32]).iter().enumerate() {
        rest[i + 1] = *v;
    }
    let nblank = nums(&lines[33])[0];
    let mut trip = [[0u8; 15]; 3];
    for k in 0..3 {
        let v = nums(&lines[34 + k]);
        for x in 0..15 {
            trip[k][x] = v[x] as u8;
        }
    }
    Data { bylen, nwords, set, lm, wm, val, bag, rest, nblank, trip }
}

// ------------------------------------------------------------------ lijnsleutel + profiel
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
struct Prof {
    n: usize,
    wm: Vec<i64>,
    lm: Vec<i64>,
    anch: Vec<(usize, u8)>, // (positie, lettercode)
    sup: u16,               // posities met LOODRECHTE steun in het eindbord (aanraakregel)
}

#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
enum Key {
    V(usize, usize, usize), // kolom, a, b
    H(usize, usize, usize), // rij, x0, x1
}

/// variant 0 = volle steun (altijd geldig, ruimste); variant 1 = alleen de posities waarvan
/// we ZEKER weten dat ze loodrechte steun hebben (ankerrijcellen resp. cellen naast een
/// ankerrij).  Variant 1 mag alleen gebruikt worden als de bezetting werkelijk geen enkele
/// andere loodrechte buur geeft -- dan is het de scherpe grens.
fn prof_of(d: &Data, k: Key, variant: u8) -> Prof {
    match k {
        Key::V(x, a, b) => {
            let n = b - a + 1;
            let mut wm = Vec::with_capacity(n);
            let mut lm = Vec::with_capacity(n);
            let mut anch = Vec::new();
            for i in 0..n {
                let y = a + i;
                wm.push(d.wm[y][x]);
                lm.push(d.lm[y][x]);
                for (j, &ay) in ANCHOR_ROWS.iter().enumerate() {
                    if ay == y {
                        anch.push((i, d.trip[j][x]));
                    }
                }
            }
            let sup = if variant == 0 {
                (1u16 << n) - 1
            } else {
                let mut m = 0u16;
                for i in 0..n {
                    if ANCHOR_ROWS.contains(&(a + i)) {
                        m |= 1 << i;
                    }
                }
                m
            };
            Prof { n, wm, lm, anch, sup }
        }
        Key::H(y, x0, x1) => {
            let n = x1 - x0 + 1;
            let mut wm = Vec::with_capacity(n);
            let mut lm = Vec::with_capacity(n);
            for i in 0..n {
                wm.push(d.wm[y][x0 + i]);
                lm.push(d.lm[y][x0 + i]);
            }
            // rijen 1/6/8/13 grenzen aan een VOLLE ankerrij: elke cel heeft daar altijd
            // loodrechte steun.  In de overige vrije rijen komt steun alleen van kolommen.
            let sup = if variant == 0 || y == 1 || y == 6 || y == 8 || y == 13 {
                (1u16 << n) - 1
            } else {
                0
            };
            Prof { n, wm, lm, anch: Vec::new(), sup }
        }
    }
}

// ------------------------------------------------------------------ DE EXACTE PER-LIJN-DP
// max_h g_L(h) voor gegeven letters.  Toestand = deelverzameling gelegde posities.
// Een groep is een interval [a..e] minus S met a,e nieuw (<=7 nieuwe cellen); het gevormde
// maximale blok moet een woord zijn.  Dit is precies de zetvorm-regel: alle nieuwe tegels op
// een lijn, span volledig gevuld.
struct Dp {
    best: Vec<i64>,
    stamp: Vec<u32>,
    gen: u32,
    order: Vec<u32>,
}
impl Dp {
    fn new() -> Self {
        Dp { best: vec![NEG; 1 << 15], stamp: vec![0; 1 << 15], gen: 0, order: Vec::with_capacity(1 << 15) }
    }
}

fn maxg(dp: &mut Dp, prof: &Prof, val: &[i64], isw: &[u16; 16]) -> i64 {
    let n = prof.n;
    let full: usize = (1usize << n) - 1;
    dp.gen += 1;
    let g = dp.gen;
    dp.best[0] = 0;
    dp.stamp[0] = g;
    // iteratief over toestanden in oplopende volgorde; alleen bereikbare tellen
    for s in 0..=full {
        if dp.stamp[s] != g {
            continue;
        }
        let b = dp.best[s];
        for a in 0..n {
            if s >> a & 1 != 0 {
                continue;
            }
            let mut cnt = 0usize;
            let mut w: i64 = 1;
            for e in a..n {
                if s >> e & 1 != 0 {
                    continue;
                }
                cnt += 1;
                if cnt > 7 {
                    break;
                }
                w *= prof.wm[e];
                let span = ((1usize << (e + 1)) - 1) ^ ((1usize << a) - 1);
                let gg = span & !s;
                let t = s | gg;
                // AANRAAKREGEL: de zet moet het bord raken.  Dat kan doordat een van zijn
                // cellen loodrechte steun heeft (prof.sup) of doordat de zet binnen deze lijn
                // aan al gelegde cellen grenst / eroverheen spant.
                if (gg as u16 & prof.sup) == 0 {
                    let inline = (span & s) != 0
                        || (a > 0 && (s >> (a - 1)) & 1 != 0)
                        || (e + 1 < n && (s >> (e + 1)) & 1 != 0);
                    if !inline {
                        continue;
                    }
                }
                let mut lo = a;
                while lo > 0 && (t >> (lo - 1)) & 1 != 0 {
                    lo -= 1;
                }
                let mut hi = e;
                while hi + 1 < n && (t >> (hi + 1)) & 1 != 0 {
                    hi += 1;
                }
                let inc;
                if hi - lo + 1 < 2 {
                    inc = 0;
                } else {
                    if isw[lo] >> (hi + 1) & 1 == 0 {
                        continue;
                    }
                    let mut acc = 0i64;
                    for k in lo..=hi {
                        acc += if gg >> k & 1 != 0 { val[k] * prof.lm[k] } else { val[k] };
                    }
                    acc *= w;
                    inc = acc + if cnt == 7 { 50 } else { 0 };
                }
                let nv = b + inc;
                if dp.stamp[t] != g {
                    dp.stamp[t] = g;
                    dp.best[t] = nv;
                } else if nv > dp.best[t] {
                    dp.best[t] = nv;
                }
            }
        }
    }
    if dp.stamp[full] == g {
        dp.best[full]
    } else {
        NEG
    }
}

// isw[i] = bitmasker over j: W[i..j] is een woord (j > i+1)
fn build_isw(d: &Data, w: &[u8]) -> [u16; 16] {
    let n = w.len();
    let mut out = [0u16; 16];
    for i in 0..n {
        let mut k: u128 = 1;
        k = k * 27 + w[i] as u128;
        for j in (i + 1)..n {
            k = k * 27 + w[j] as u128;
            if j - i + 1 >= 2 && d.set.contains(k) {
                out[i] |= 1 << (j + 1);
            }
        }
    }
    out
}

// ------------------------------------------------------------------ tabel per lijnsleutel
fn topk() -> usize {
    env::var("TOPK").ok().and_then(|s| s.parse().ok()).unwrap_or(384)
}

struct Tab {
    umax: i32,
    tail: i32,               // bovengrens op U van alle woorden BUITEN de bewaarde selectie
    ent: Vec<(i32, [u8; 15])>, // (U, het woord zelf -- zo is elk eigendomspatroon te beprijzen)
    n: u8,
    nw: u32,
}

fn build_tab(d: &Data, dp: &mut Dp, prof: &Prof, lam0: &[i64; 26]) -> Tab {
    let n = prof.n;
    let nw = d.nwords[n];
    let words = &d.bylen[n];
    let mut all: Vec<(i32, [u8; 15])> = Vec::new();
    let mut umax = NEG as i32;
    let mut cnt_ok = 0u32;
    let mut valv = vec![0i64; n];
    let freepos: Vec<usize> = (0..n).filter(|i| !prof.anch.iter().any(|a| a.0 == *i)).collect();
    'w: for wi in 0..nw {
        let w = &words[wi * n..(wi + 1) * n];
        for &(p, c) in prof.anch.iter() {
            if w[p] != c {
                continue 'w;
            }
        }
        // ZAK-LEXICALE toets op runniveau: de VRIJE posities van deze lijn moeten uit de
        // restzak (55 tegels na aftrek van de 45 ankerletters) te bouwen zijn, op ten
        // hoogste NBLANK blanco's na.  Sound: in elk echt bord komen de letters op vrije
        // cellen uit precies die restzak.  (Blanco's houden hier hun volle letterwaarde --
        // een overschatting, dus in de veilige richting.)
        {
            let mut need = [0i64; 27];
            for &i in freepos.iter() {
                need[w[i] as usize] += 1;
            }
            let mut short = 0i64;
            for c in 1..27usize {
                if need[c] > d.rest[c] {
                    short += need[c] - d.rest[c];
                }
            }
            if short > d.nblank {
                continue 'w;
            }
        }
        cnt_ok += 1;
        for i in 0..n {
            valv[i] = d.val[w[i] as usize];
        }
        let isw = build_isw(d, w);
        let u = maxg(dp, prof, &valv, &isw);
        if u <= NEG {
            continue;
        }
        let ui = u as i32;
        if ui > umax {
            umax = ui;
        }
        let mut ww = [0u8; 15];
        ww[..n].copy_from_slice(w);
        all.push((ui, ww));
    }
    if all.is_empty() {
        return Tab { umax: NEG as i32, tail: NEG as i32, ent: Vec::new(), n: n as u8, nw: cnt_ok };
    }
    let kk = topk();
    // selectie 1: hoogste U  -> bepaalt de STAARTGRENS (geldig voor elke lambda >= 0)
    all.sort_unstable_by(|a, b| b.0.cmp(&a.0));
    let tail = if all.len() > kk { all[kk].0 } else { NEG as i32 };
    let mut sel: Vec<(i32, [u8; 15])> = all[..all.len().min(kk)].to_vec();
    // selectie 2: hoogste U - lambda0.cnt (goedkope letters) -> betere max, zelfde staart
    let nz = lam0.iter().any(|v| *v != 0);
    if nz && all.len() > kk {
        let mut sc: Vec<(i64, usize)> = all
            .iter()
            .enumerate()
            .map(|(i, (u, w))| {
                let mut c = 0i64;
                for &j in freepos.iter() {
                    c += lam0[(w[j] - 1) as usize];
                }
                (*u as i64 * SCALE - c, i)
            })
            .collect();
        sc.sort_unstable_by(|a, b| b.0.cmp(&a.0));
        let mut seen: std::collections::HashSet<usize> = (0..all.len().min(kk)).collect();
        for (_v, i) in sc.into_iter().take(kk) {
            if seen.insert(i) {
                sel.push(all[i]);
            }
        }
    }
    Tab { umax, tail, ent: sel, n: n as u8, nw: cnt_ok }
}

// ------------------------------------------------------------------ sleutels
fn all_keys() -> Vec<Key> {
    let mut keys = Vec::new();
    let aok = |a: usize| a != 1 && a != 8;
    let bok = |b: usize| b != 6 && b != 13;
    for x in 0..15 {
        for a in 0..15 {
            if !aok(a) {
                continue;
            }
            for b in (a + 1)..15 {
                if !bok(b) {
                    continue;
                }
                keys.push(Key::V(x, a, b));
            }
        }
    }
    for y in 0..15 {
        if ANCHOR_ROWS.contains(&y) {
            continue;
        }
        for x0 in 0..15 {
            for x1 in (x0 + 1)..15 {
                keys.push(Key::H(y, x0, x1));
            }
        }
    }
    keys
}

// ------------------------------------------------------------------ serialisatie
fn write_tabs(path: &str, items: &[((Key, u8), Tab)]) {
    let mut f = BufWriter::new(File::create(path).unwrap());
    f.write_all(&(items.len() as u32).to_le_bytes()).unwrap();
    for ((k, var), t) in items {
        let (tag, a, b, c) = match *k {
            Key::V(x, a, b) => (0u8 + 2 * var, x as u8, a as u8, b as u8),
            Key::H(y, a, b) => (1u8 + 2 * var, y as u8, a as u8, b as u8),
        };
        f.write_all(&[tag, a, b, c]).unwrap();
        f.write_all(&t.umax.to_le_bytes()).unwrap();
        f.write_all(&t.tail.to_le_bytes()).unwrap();
        f.write_all(&t.nw.to_le_bytes()).unwrap();
        f.write_all(&[t.n]).unwrap();
        f.write_all(&(t.ent.len() as u32).to_le_bytes()).unwrap();
        for (u, p) in t.ent.iter() {
            f.write_all(&u.to_le_bytes()).unwrap();
            f.write_all(&p[..t.n as usize]).unwrap();
        }
    }
}

fn read_tabs(path: &str) -> HashMap<(Key, u8), Tab> {
    let mut f = File::open(path).expect(path);
    let mut b = Vec::new();
    f.read_to_end(&mut b).unwrap();
    let mut p = 0usize;
    let n = u32::from_le_bytes([b[0], b[1], b[2], b[3]]) as usize;
    p += 4;
    let mut out = HashMap::new();
    for _ in 0..n {
        let tag = b[p];
        let a = b[p + 1] as usize;
        let c = b[p + 2] as usize;
        let e = b[p + 3] as usize;
        p += 4;
        let var = tag / 2;
        let k = if tag % 2 == 0 { Key::V(a, c, e) } else { Key::H(a, c, e) };
        let umax = i32::from_le_bytes([b[p], b[p + 1], b[p + 2], b[p + 3]]);
        p += 4;
        let tail = i32::from_le_bytes([b[p], b[p + 1], b[p + 2], b[p + 3]]);
        p += 4;
        let nw = u32::from_le_bytes([b[p], b[p + 1], b[p + 2], b[p + 3]]);
        p += 4;
        let ln = b[p] as usize;
        p += 1;
        let ne = u32::from_le_bytes([b[p], b[p + 1], b[p + 2], b[p + 3]]) as usize;
        p += 4;
        let mut ent = Vec::with_capacity(ne);
        for _ in 0..ne {
            let u = i32::from_le_bytes([b[p], b[p + 1], b[p + 2], b[p + 3]]);
            p += 4;
            let mut pr = [0u8; 15];
            pr[..ln].copy_from_slice(&b[p..p + ln]);
            p += ln;
            ent.push((u, pr));
        }
        out.insert((k, var), Tab { umax, tail, ent, n: ln as u8, nw });
    }
    out
}

// ------------------------------------------------------------------ lijnen van een bezetting
// kolommasker: bit y gezet = (x,y) bezet.  Rijen 0/7/14 zijn ALTIJD bezet.
#[inline]
fn full_col(m: u16) -> u16 {
    m | (1 << 0) | (1 << 7) | (1 << 14)
}

fn vruns(m: u16) -> Vec<(usize, usize)> {
    let f = full_col(m);
    let mut out = Vec::new();
    let mut y = 0usize;
    while y < 15 {
        if f >> y & 1 == 0 {
            y += 1;
            continue;
        }
        let mut y1 = y;
        while y1 + 1 < 15 && f >> (y1 + 1) & 1 != 0 {
            y1 += 1;
        }
        if y1 > y {
            out.push((y, y1));
        }
        y = y1 + 1;
    }
    out
}

fn hruns_of(cols: &[u16; 15], y: usize) -> Vec<(usize, usize)> {
    let mut out = Vec::new();
    let mut x = 0usize;
    while x < 15 {
        if cols[x] >> y & 1 == 0 {
            x += 1;
            continue;
        }
        let mut x1 = x;
        while x1 + 1 < 15 && cols[x1 + 1] >> y & 1 != 0 {
            x1 += 1;
        }
        if x1 > x {
            out.push((x, x1));
        }
        x = x1 + 1;
    }
    out
}

// ------------------------------------------------------------------ Lagrange-relaxatie zak
// De VERTICALEN bezitten al hun vrije cellen (verticalen zijn onderling disjunct), dus
//     SOM_V cnt_V(W_V) <= restzak + 2 blanco   (componentsgewijs, blanco's 2 vrije tegels)
// en daarmee is voor elke lambda >= 0
//     SOM_V U_V(W_V) <= SOM_V max_W [U_V(W) - lambda.cnt_V(W)] + lambda.REST + 2*max(lambda).
// De horizontalen krijgen GEEN lambda-krediet (ze bezitten niets) -> ze tellen met hun kale
// Umax.  Dat is een verruiming, dus gezond.
// Alles in vaste-komma-eenheden van 1/SCALE punt.  De eindgrens wordt naar beneden
// afgerond: de echte score is geheel, dus floor(x/SCALE) blijft een geldige bovengrens.
const SCALE: i64 = 64;

/// R(lambda, own) = max_W [ U(W) - lambda . (letters van W op de posities in `own`) ].
/// `own` = de posities waarvan DEZE lijn de zaktegel voor zijn rekening neemt.  Elke vrije cel
/// wordt door precies een lijn geclaimd (verticaal heeft voorrang), dus de som van alle
/// geclaimde letters is precies de bezetting van de vrije cellen -- die uit de restzak komt.
fn r_lambda_own(t: &Tab, lam: &[i64; 26], own: u16) -> i64 {
    let mut best = t.tail as i64 * SCALE;
    for (u, w) in t.ent.iter() {
        let mut c = 0i64;
        let mut m = own;
        while m != 0 {
            let i = m.trailing_zeros() as usize;
            m &= m - 1;
            c += lam[(w[i] - 1) as usize];
        }
        let v = *u as i64 * SCALE - c;
        if v > best {
            best = v;
        }
    }
    best
}

/// het gekozen woord bij R(lambda,own) -- subgradiënt-informatie; None = staartgrens bindt
fn r_arg_own(t: &Tab, lam: &[i64; 26], own: u16) -> Option<([u8; 15], u16)> {
    let mut best = t.tail as i64 * SCALE;
    let mut arg = None;
    for (u, w) in t.ent.iter() {
        let mut c = 0i64;
        let mut m = own;
        while m != 0 {
            let i = m.trailing_zeros() as usize;
            m &= m - 1;
            c += lam[(w[i] - 1) as usize];
        }
        let v = *u as i64 * SCALE - c;
        if v > best {
            best = v;
            arg = Some((*w, own));
        }
    }
    arg
}

fn lam_const(d: &Data, lam: &[i64; 26]) -> i64 {
    let mut s = 0i64;
    let mut mx = 0i64;
    for i in 0..26 {
        s += lam[i] * d.rest[i + 1];
        if lam[i] > mx {
            mx = lam[i];
        }
    }
    s + d.nblank * mx
}

/// mu = min lambda over de letters die nog in de restzak zitten.  Een LAAN-cel die niet op een
/// verticale run ligt wordt door geen enkele verticaal geteld; hem met mu belasten blijft
/// gezond omdat mu <= lambda_ch voor elke restletter (zie REFUTE.md, lemma ZAK-SPLITSING).
fn lam_mu(d: &Data, lam: &[i64; 26]) -> i64 {
    let mut mu = i64::MAX;
    for i in 0..26 {
        if d.rest[i + 1] > 0 && lam[i] < mu {
            mu = lam[i];
        }
    }
    if mu == i64::MAX { 0 } else { mu }
}


/// eigendomsmasker van een VERTICALE run [a,b]: alle niet-ankerposities (die letters komen uit
/// de restzak).  De ankerletters van rijen 0/7/14 liggen vast en zijn al afgetrokken.
#[inline]
fn own_v(a: usize, b: usize) -> u16 {
    let mut m = 0u16;
    for (i, y) in (a..=b).enumerate() {
        if !ANCHOR_ROWS.contains(&y) {
            m |= 1 << i;
        }
    }
    m
}

/// eigendomsmasker van een HORIZONTALE run [x0,x1] in rij y: alleen de cellen die NIET op een
/// verticale run (>=2) liggen -- die worden al door hun verticaal geclaimd.
#[inline]
fn own_h(cols: &[u16; 15], y: usize, x0: usize, x1: usize) -> u16 {
    let mut m = 0u16;
    for (i, x) in (x0..=x1).enumerate() {
        let f = full_col(cols[x]);
        let up = y > 0 && f >> (y - 1) & 1 != 0;
        let dn = y < 14 && f >> (y + 1) & 1 != 0;
        if !up && !dn {
            m |= 1 << i;
        }
    }
    m
}

// ------------------------------------------------------------------ ankerrij-tabel
// A_y[sup] = exacte bovengrens van ankerrij y gegeven WELKE pre-cellen loodrechte steun
// hebben.  -1 = niet legbaar (eiland-lemma).  Geschreven door mg_refute.py MODE=anchtab.
struct AnchTab {
    pre: Vec<Vec<usize>>,  // per ankerrij de pre-kolommen
    val: Vec<Vec<i64>>,    // per ankerrij 2^|pre| waarden
}

fn read_anchtab(dir: &str) -> AnchTab {
    let br = BufReader::new(File::open(format!("{}/anchtab.txt", dir)).expect("anchtab.txt"));
    let mut pre = Vec::new();
    let mut val = Vec::new();
    for line in br.lines() {
        let s = line.unwrap();
        let mut it = s.split_whitespace();
        let _y: usize = it.next().unwrap().parse().unwrap();
        let p: Vec<usize> = it.next().unwrap().split(',').map(|t| t.parse().unwrap()).collect();
        let v: Vec<i64> = it.map(|t| t.parse().unwrap()).collect();
        pre.push(p);
        val.push(v);
    }
    AnchTab { pre, val }
}

impl AnchTab {
    // steunpatroon uit de kolommaskers halen en de exacte ankerbijdrage opzoeken
    fn cap(&self, cols: &[u16; 15]) -> i64 {
        let mut tot = 0i64;
        for (k, &y) in ANCHOR_ROWS.iter().enumerate() {
            let mut s = 0usize;
            for (i, &x) in self.pre[k].iter().enumerate() {
                let ok = match y {
                    0 => cols[x] >> 1 & 1 != 0,
                    7 => (cols[x] >> 6 & 1 != 0) || (cols[x] >> 8 & 1 != 0),
                    _ => cols[x] >> 13 & 1 != 0,
                };
                if ok {
                    s |= 1 << i;
                }
            }
            let v = self.val[k][s];
            if v < 0 {
                return NEG;
            }
            tot += v;
        }
        tot
    }
    fn maxcap(&self) -> i64 {
        self.val.iter().map(|v| *v.iter().max().unwrap()).sum()
    }
}

// ------------------------------------------------------------------ per-paar horizontale grens
// p(y,x) = max over runs r in rij y die het PAAR (x,x+1) bevatten van Umax(r)/(|r|-1).
// Dan geldt voor elke run r:  SOM over de |r|-1 paren in r van p >= Umax(r).  Dus de
// horizontale bijdrage is te bovengrenzen als een som over aangrenzende KOLOMPAREN --
// precies wat een kolom-voor-kolom-DP nodig heeft.
fn pair_weights(tabs: &HashMap<(Key, u8), Tab>) -> [[i64; 14]; 15] {
    let mut p = [[0i64; 14]; 15];
    for y in 0..15 {
        if ANCHOR_ROWS.contains(&y) {
            continue;
        }
        for x0 in 0..15 {
            for x1 in (x0 + 1)..15 {
                if let Some(t) = tabs.get(&(Key::H(y, x0, x1), 0u8)) {
                    if t.umax <= 0 {
                        continue;
                    }
                    let per = ((t.umax as i64 * SCALE) as f64 / (x1 - x0) as f64).ceil() as i64;
                    for x in x0..x1 {
                        if per > p[y][x] {
                            p[y][x] = per;
                        }
                    }
                }
            }
        }
    }
    p
}

// ------------------------------------------------------------------ kolomwaarden
const FREEROWS: [usize; 12] = [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13];

#[inline]
fn mask12_to_col(m: u32) -> u16 {
    let mut c = 0u16;
    for (i, &y) in FREEROWS.iter().enumerate() {
        if m >> i & 1 != 0 {
            c |= 1 << y;
        }
    }
    c
}

// colv[x][m] = (tegels, SOM_V R_V(lambda))  of None als een verticale run geen woord toelaat
fn col_values(tabs: &HashMap<(Key, u8), Tab>, lam: &[i64; 26], var: u8) -> Vec<Vec<Option<(u8, i64)>>> {
    // STRATIFICATIE: MAXVLEN begrenst de lengte van elke verticale run.  Zo is de bovengrens
    // uit te rekenen als functie van "hoe lang mag de langste verticaal zijn", en levert het
    // kleinste L waarbij de grens de drempel haalt een STRUCTUURSTELLING op:
    // elk bord boven de drempel heeft een verticale run van minstens die lengte.
    let maxv: usize = env::var("MAXVLEN").ok().and_then(|s| s.parse().ok()).unwrap_or(15);
    let mut out = Vec::with_capacity(15);
    for x in 0..15 {
        let mut v = Vec::with_capacity(1 << 12);
        for m in 0..(1u32 << 12) {
            let cm = mask12_to_col(m);
            let mut val = 0i64;
            let mut ok = true;
            for (a, b) in vruns(cm) {
                if b - a + 1 > maxv {
                    ok = false;
                    break;
                }
                match tabs.get(&(Key::V(x, a, b), var)) {
                    Some(t) if t.umax > NEG as i32 / 2 => val += r_lambda_own(t, lam, own_v(a, b)),
                    _ => {
                        ok = false;
                        break;
                    }
                }
            }
            v.push(if ok { Some((m.count_ones() as u8, val)) } else { None });
        }
        out.push(v);
    }
    out
}

// ------------------------------------------------------------------ eilandvlaggen
// rij 0 pre-eilanden (kolommen): {1,2} {4,5,6} {9,10} {12}   -> steun = bit rij 1
// rij 14 pre-eilanden:           {4,5,6} {8,9,10,11,12}      -> steun = bit rij 13
const ISL0: [(usize, usize); 4] = [(1, 2), (4, 6), (9, 10), (12, 12)];
const ISL14: [(usize, usize); 2] = [(4, 6), (8, 12)];

fn isl_of(x: usize, isl: &[(usize, usize)]) -> Option<(bool, bool)> {
    for &(a, b) in isl {
        if x >= a && x <= b {
            return Some((x == a, x == b));
        }
    }
    None
}

// ------------------------------------------------------------------ GLOBALE DP over bezettingen
// Kolom-voor-kolom-DP die de bovengrens MAXIMALISEERT over alle bezettingen tegelijk.
// Toestand na kolom x-1: (masker van kolom x-1, resterende tegels, eilandvlaggen).
//
// Horizontale runs: de verzameling vrije RIJEN waarin horizontale aangrenzing is toegestaan
// (`active`) is een parameter.  In een niet-actieve rij mogen twee naast elkaar liggende
// kolommen niet allebei bezet zijn (harde beperking); in een actieve rij wordt de horizontale
// bijdrage van boven begrensd met PAARGEWICHTEN
//     p(y,x) = max over runs r in rij y die het paar (x,x+1) bevatten van Umax(r)/(|r|-1),
// zodat SOM over de paren van r van p >= Umax(r) voor ELKE run r in die rij.  Dat is een
// verruiming, dus gezond, en het dekt ELKE runstructuur binnen de actieve rijen.
//
// Door over alle deelverzamelingen `active` van grootte <= K te lopen, dekt de sweep ALLE
// bezettingen waarin hoogstens K vrije rijen uberhaupt een horizontale run bevatten.
const MINF: i32 = -1 << 28;
const HARD: i64 = -1 << 20;

/// eilandvlag-overgang voor kolom x: (nieuwe vlaggen, of None als de kolom hier faalt)
#[inline]
fn flag_step(x: usize, m: u32, f: usize) -> Option<usize> {
    let mut nf0 = f & 1;
    let mut nf14 = f >> 1;
    if let Some((s0, e0)) = isl_of(x, &ISL0) {
        if s0 {
            nf0 = 0;
        }
        if m >> 0 & 1 != 0 {
            nf0 = 1;
        }
        if e0 && nf0 == 0 {
            return None;
        }
    }
    if let Some((s14, e14)) = isl_of(x, &ISL14) {
        if s14 {
            nf14 = 0;
        }
        if m >> 11 & 1 != 0 {
            nf14 = 1;
        }
        if e14 && nf14 == 0 {
            return None;
        }
    }
    Some(nf0 | (nf14 << 1))
}

/// B[pm] = max_m ( A[m] + SOM_i w[i]*[pm_i & m_i] ) -- 12-staps bit-transformatie, O(12*4096)
fn maxplus_and(a: &mut [i32; 4096], w: &[i64; 12]) {
    for i in 0..12 {
        let bit = 1usize << i;
        let wi = w[i];
        for s in 0..4096usize {
            if s & bit != 0 {
                continue;
            }
            let v0 = a[s];
            let v1 = a[s | bit];
            let n0 = if v1 > v0 { v1 } else { v0 };
            let n1 = if v1 > MINF {
                let c = v1 as i64 + wi;
                if c > v0 as i64 { c as i32 } else { v0 }
            } else {
                v0
            };
            a[s] = n0;
            a[s | bit] = n1;
        }
    }
}

struct Gdp {
    suf: Vec<Vec<i32>>, // suf[x][((pm*2 + pi)*nt + t)*4 + f]
    nt: usize,
    pw: Vec<[i64; 12]>,
}

/// De kolom-DP met een ISOLATIE-VLAG per kolom.
///
/// Een kolom mag zich ISOLEREN: dan eisen we dat geen van zijn vrije cellen een horizontale
/// buur heeft (mask[x-1] & mask[x] = 0 EN mask[x] & mask[x+1] = 0), en in ruil daarvoor telt
/// die kolom met de SCHERPE steunvariant (variant 1: alleen de ankerrijcellen kunnen een zet
/// laten aanraken).  Isoleert hij zich niet, dan telt hij met de ruime variant 0.  Beide
/// richtingen zijn gezond: variant 0 is altijd een geldige bovengrens, en variant 1 is precies
/// geldig onder de eis die de vlag afdwingt.
///
/// Dat verschil is enorm: een volle TWS-kolom haalt met volle steun 1132 en met alleen
/// ankersteun 477.  Zonder deze vlag is de globale grens onbruikbaar los.
fn gdp_build(colv0: &Vec<Vec<Option<(u8, i64)>>>, colv1: &Vec<Vec<Option<(u8, i64)>>>,
             pwr: &[[i64; 14]; 15], active: u16, nmax: usize) -> Gdp {
    let mut pw: Vec<[i64; 12]> = Vec::new();
    for x in 0..15 {
        let mut a = [HARD; 12];
        for (i, &y) in FREEROWS.iter().enumerate() {
            if active >> i & 1 != 0 {
                a[i] = if x > 0 { pwr[y][x - 1] } else { 0 };
            }
        }
        pw.push(a);
    }
    let whard = [HARD; 12];
    let nt = nmax + 1;
    let sz = 4096 * 2 * nt * 4;
    let mut suf: Vec<Vec<i32>> = vec![Vec::new(); 16];
    suf[15] = vec![0i32; sz];
    for x in (0..15).rev() {
        let mut cur = vec![MINF; sz];
        for t in 0..nt {
            for f in 0..4usize {
                let mut a0 = [MINF; 4096];
                let mut a1 = [MINF; 4096];
                for m in 0..4096usize {
                    let nf = match flag_step(x, m as u32, f) {
                        Some(v) => v,
                        None => continue,
                    };
                    // Als geen enkele bezette rij van deze kolom een ACTIEVE rij is, kan geen
                    // enkele vrije cel ooit een horizontale buur hebben: de kolom is dan
                    // AUTOMATISCH geisoleerd en de scherpe steunvariant is verplicht.
                    let forced_iso = (m as u16 & active) == 0;
                    if !forced_iso {
                    if let Some((tiles, val)) = colv0[x][m] {
                        let tiles = tiles as usize;
                        if tiles <= t {
                            let nv = suf[x + 1][(((m * 2 + 0) * nt) + (t - tiles)) * 4 + nf];
                            if nv > MINF {
                                a0[m] = nv + val as i32;
                            }
                        }
                    }
                    }
                    if let Some((tiles, val)) = colv1[x][m] {
                        let tiles = tiles as usize;
                        if tiles <= t {
                            let nv = suf[x + 1][(((m * 2 + 1) * nt) + (t - tiles)) * 4 + nf];
                            if nv > MINF {
                                a1[m] = nv + val as i32;
                            }
                        }
                    }
                }
                let mut b0 = a0;
                maxplus_and(&mut b0, &pw[x]);
                let mut b0h = a0;
                maxplus_and(&mut b0h, &whard);
                let mut b1h = a1;
                maxplus_and(&mut b1h, &whard);
                for pm in 0..4096usize {
                    let v0 = if b1h[pm] > b0[pm] { b1h[pm] } else { b0[pm] };
                    let v1 = if b1h[pm] > b0h[pm] { b1h[pm] } else { b0h[pm] };
                    cur[(((pm * 2 + 0) * nt) + t) * 4 + f] = v0;
                    cur[(((pm * 2 + 1) * nt) + t) * 4 + f] = v1;
                }
            }
        }
        suf[x] = cur;
    }
    Gdp { suf, nt, pw }
}

fn subsets_upto(k: usize) -> Vec<u16> {
    let mut out = Vec::new();
    for m in 0..(1u16 << 12) {
        if m.count_ones() as usize <= k {
            out.push(m);
        }
    }
    out.sort_by_key(|m| m.count_ones());
    out
}

fn cmd_gmax(dir: &str) {
    let d = load(dir);
    let tabs = read_tabs(&format!("{}/tables.bin", dir));
    let at = read_anchtab(dir);
    let lam = read_lam();
    let konst = lam_const(&d, &lam);
    let nmax: usize = env::var("NFREE").ok().and_then(|s| s.parse().ok()).unwrap_or(56);
    let target: i64 = env::var("TARGET").ok().and_then(|s| s.parse().ok()).unwrap_or(4819);
    let kmax: usize = env::var("KACT").ok().and_then(|s| s.parse().ok()).unwrap_or(12);
    calib_assert(dir, &tabs, &at, &d, &lam);
    let anch = at.maxcap();
    let colv = col_values(&tabs, &lam, 0);
    let colv1 = col_values(&tabs, &lam, 1);
    let pwr = pair_weights(&tabs);
    let nlive: Vec<usize> =
        (0..15).map(|x| colv[x].iter().filter(|o| o.is_some()).count()).collect();
    eprintln!("legbare kolommaskers per kolom (van 4096): {:?}", nlive);
    let subs = subsets_upto(kmax);
    eprintln!("{} actieve-rij-deelverzamelingen (|A| <= {})", subs.len(), kmax);
    let t0 = std::time::Instant::now();
    let mut worst = i64::MIN;
    let mut worst_a = 0u16;
    let mut nref = 0usize;
    for (i, &a) in subs.iter().enumerate() {
        let g = gdp_build(&colv, &colv1, &pwr, a, nmax);
        let best = g.suf[0][((0 * 2 + 0) * g.nt + nmax) * 4 + 0] as i64;
        let ub = anch + (best + konst).div_euclid(SCALE);
        if ub < target {
            nref += 1;
        }
        if ub > worst {
            worst = ub;
            worst_a = a;
            eprintln!("  nieuw maximum {} bij actieve rijen {:012b} ({}/{}, {:.0}s)",
                      ub, a, i + 1, subs.len(), t0.elapsed().as_secs_f64());
        }
    }
    println!("SWEEP over actieve-rij-deelverzamelingen |A| <= {}", kmax);
    println!("  ANCH(max) {}   drempel {}   tegelbudget {}", anch, target, nmax);
    println!("  deelfamilies WEERLEGD: {} van {}", nref, subs.len());
    println!("  hoogste bovengrens: {}  bij actieve rijen {:012b}", worst, worst_a);
    println!("  ({:.0}s)", t0.elapsed().as_secs_f64());
}


// ------------------------------------------------------------------ SWEEP + overlevenden
#[inline]
fn pairsum(pw: &[i64; 12], pm: u32, m: u32) -> i64 {
    let mut b = pm & m;
    let mut s = 0i64;
    while b != 0 {
        let i = b.trailing_zeros() as usize;
        b &= b - 1;
        s += pw[i];
    }
    s
}

/// telt hoeveel bezettingen deze deelfamilie bevat.  De verenigbaarheidseis is
/// m & pm & ~active == 0, dus m ligt in de DEELVERZAMELING ~(pm & ~active): een zeta-transform
/// (subset-som) doet de hele kolomovergang in O(12*4096) in plaats van O(4096^2).
fn count_family(colv: &Vec<Vec<Option<(u8, i64)>>>, active: u16, nmax: usize) -> f64 {
    let nt = nmax + 1;
    let mut cnt: Vec<f64> = vec![1.0; 4096 * nt * 4];
    for x in (0..15).rev() {
        let mut cur = vec![0.0f64; 4096 * nt * 4];
        for t in 0..nt {
            for f in 0..4usize {
                let mut a = [0.0f64; 4096];
                for m in 0..4096usize {
                    let (tiles, _v) = match colv[x][m] {
                        Some(v) => v,
                        None => continue,
                    };
                    let tiles = tiles as usize;
                    if tiles > t {
                        continue;
                    }
                    let nf = match flag_step(x, m as u32, f) {
                        Some(v) => v,
                        None => continue,
                    };
                    a[m] = cnt[(m * nt + (t - tiles)) * 4 + nf];
                }
                // subset-som over de bits die NIET actief zijn wordt hieronder per pm gebruikt;
                // we hebben Z[u] = som over m deelverzameling van u nodig, dus volledige zeta
                for i in 0..12 {
                    let bit = 1usize << i;
                    for u in 0..4096usize {
                        if u & bit != 0 {
                            a[u] += a[u ^ bit];
                        }
                    }
                }
                for pm in 0..4096usize {
                    let u = !(pm & !(active as usize)) & 0xfff;
                    cur[(pm * nt + t) * 4 + f] = a[u];
                }
            }
        }
        cnt = cur;
    }
    cnt[(0 * nt + nmax) * 4 + 0]
}

struct SurvCtx<'a> {
    g: &'a Gdp,
    colv0: &'a Vec<Vec<Option<(u8, i64)>>>,
    colv1: &'a Vec<Vec<Option<(u8, i64)>>>,
    active: u16,
    need: i64,
    nodes: u64,
    found: u64,
    cap: u64,
    cols: [u16; 15],
    out: Vec<[u16; 15]>,
}

fn dfs(c: &mut SurvCtx, x: usize, pm: u32, pi: usize, t: usize, f: usize, acc: i64) {
    if c.found >= c.cap {
        return;
    }
    c.nodes += 1;
    if x == 15 {
        c.found += 1;
        if c.out.len() < 400000 {
            c.out.push(c.cols);
        }
        return;
    }
    let nt = c.g.nt;
    for m in 0..4096usize {
        let forced_iso = (m as u16 & c.active) == 0;
        for i in 0..2usize {
            if forced_iso && i == 0 {
                continue;
            }
            let cv = if i == 0 { &c.colv0[x][m] } else { &c.colv1[x][m] };
            let (tiles, val) = match cv {
                Some(v) => *v,
                None => continue,
            };
            let hard = pi == 1 || i == 1;
            if hard {
                if (pm & m as u32) != 0 {
                    continue;
                }
            } else if (pm & m as u32 & !(c.active as u32)) != 0 {
                continue;
            }
            let tiles = tiles as usize;
            if tiles > t {
                continue;
            }
            let nf = match flag_step(x, m as u32, f) {
                Some(v) => v,
                None => continue,
            };
            let nv = c.g.suf[x + 1][(((m * 2 + i) * nt) + (t - tiles)) * 4 + nf];
            if nv <= MINF {
                continue;
            }
            let ps = if hard { 0 } else { pairsum(&c.g.pw[x], pm, m as u32) };
            let na = acc + val + ps;
            if na + (nv as i64) < c.need {
                continue;
            }
            c.cols[x] = mask12_to_col(m as u32);
            dfs(c, x + 1, m as u32, i, t - tiles, nf, na);
            c.cols[x] = 0;
            if c.found >= c.cap {
                return;
            }
        }
    }
}

fn cmd_sweep(dir: &str) {
    let d = Arc::new(load(dir));
    let tabs = Arc::new(read_tabs(&format!("{}/tables.bin", dir)));
    let at = Arc::new(read_anchtab(dir));
    let lam = read_lam();
    let konst = lam_const(&d, &lam);
    let nmax: usize = env::var("NFREE").ok().and_then(|s| s.parse().ok()).unwrap_or(56);
    let target: i64 = env::var("TARGET").ok().and_then(|s| s.parse().ok()).unwrap_or(4819);
    let kmax: usize = env::var("KACT").ok().and_then(|s| s.parse().ok()).unwrap_or(2);
    let cap: u64 = env::var("MAXSURV").ok().and_then(|s| s.parse().ok()).unwrap_or(400_000);
    let docount = env::var("COUNT").is_ok();
    calib_assert(dir, &tabs, &at, &d, &lam);
    let anch = at.maxcap();
    let colv = Arc::new(col_values(&tabs, &lam, 0));
    let colv1 = Arc::new(col_values(&tabs, &lam, 1));
    let pwr = Arc::new(pair_weights(&tabs));
    let nlive: Vec<usize> =
        (0..15).map(|x| colv[x].iter().filter(|o| o.is_some()).count()).collect();
    eprintln!("legbare kolommaskers per kolom (van 4096): {:?}", nlive);
    let subs = Arc::new(subsets_upto(kmax));
    eprintln!("{} actieve-rij-deelverzamelingen (|A| <= {}), drempel {}", subs.len(), kmax, target);
    let outp = env::var("SURVOUT").unwrap_or_else(|_| format!("{}/surv.txt", dir));
    let t0 = std::time::Instant::now();
    let idx = Arc::new(AtomicUsize::new(0));
    type Res = (u16, i64, u64, u64, f64, Vec<[u16; 15]>);
    let res: Arc<Mutex<Vec<Res>>> = Arc::new(Mutex::new(Vec::new()));
    let mut hs = Vec::new();
    for _ in 0..nthreads() {
        let (d, tabs, at, colv, colv1, pwr, subs, idx, res) =
            (d.clone(), tabs.clone(), at.clone(), colv.clone(), colv1.clone(), pwr.clone(),
             subs.clone(), idx.clone(), res.clone());
        hs.push(std::thread::spawn(move || loop {
            let i = idx.fetch_add(1, Ordering::SeqCst);
            if i >= subs.len() {
                break;
            }
            let a = subs[i];
            let g = gdp_build(&colv, &colv1, &pwr, a, nmax);
            let best = g.suf[0][((0 * 2 + 0) * g.nt + nmax) * 4 + 0] as i64;
            let ub = anch + (best + konst).div_euclid(SCALE);
            let nc = if docount { count_family(&colv, a, nmax) } else { 0.0 };
            if ub < target {
                res.lock().unwrap().push((a, ub, 0, 0, nc, Vec::new()));
                continue;
            }
            let need = (target - anch) * SCALE - konst;
            let mut c = SurvCtx { g: &g, colv0: &colv, colv1: &colv1, active: a, need,
                                  nodes: 0, found: 0, cap, cols: [0u16; 15], out: Vec::new() };
            dfs(&mut c, 0, 0, 0, nmax, 0, 0);
            let mut keep = Vec::new();
            for cols in c.out.iter() {
                let b = bound_of(cols, &tabs, &at, &d, &lam);
                if b.feasible && b.ub >= target {
                    keep.push(*cols);
                }
            }
            eprintln!("  A={:012b} UB={} ruw {} scherp {} ({:.0}s)", a, ub, c.found, keep.len(),
                      t0.elapsed().as_secs_f64());
            res.lock().unwrap().push((a, ub, c.found, keep.len() as u64, nc, keep));
        }));
    }
    for h in hs {
        h.join().unwrap();
    }
    let r = res.lock().unwrap();
    let mut fo = BufWriter::new(File::create(&outp).unwrap());
    let mut nref = 0usize;
    let mut nover = 0usize;
    let mut tot_surv = 0u64;
    let mut tot_sharp = 0u64;
    let mut ncfg = 0.0f64;
    let mut worst = i64::MIN;
    let mut worst_a = 0u16;
    let mut sid = 0usize;
    let mut hist: HashMap<i64, usize> = HashMap::new();
    for (a, ub, found, sharp, nc, keep) in r.iter() {
        ncfg += nc;
        *hist.entry((ub / 50) * 50).or_insert(0) += 1;
        if *ub < target {
            nref += 1;
        } else {
            nover += 1;
            tot_surv += found;
            tot_sharp += sharp;
            for cols in keep {
                sid += 1;
                write!(fo, "s{}", sid).unwrap();
                for x in 0..15 {
                    write!(fo, " {}", cols[x]).unwrap();
                }
                writeln!(fo, "  # A={:012b}", a).unwrap();
            }
        }
        if *ub > worst {
            worst = *ub;
            worst_a = *a;
        }
    }
    fo.flush().unwrap();
    println!("SWEEP |A| <= {}   drempel {}   tegelbudget {}", kmax, target, nmax);
    println!("  deelfamilies: {} totaal, {} IN BULK WEERLEGD, {} met overlevenden",
             subs.len(), nref, nover);
    if docount {
        println!("  bezettingen in de familie: {:.4e}", ncfg);
    }
    println!("  ruwe overlevenden {}   na scherpe grens {}  -> {}", tot_surv, tot_sharp, outp);
    println!("  hoogste bovengrens {} bij A={:012b}", worst, worst_a);
    let mut hk: Vec<_> = hist.into_iter().collect();
    hk.sort();
    println!("  histogram van de deelfamilie-bovengrenzen:");
    for (b, n) in hk {
        println!("    {:5}..{:5}  {}", b, b + 49, n);
    }
    println!("  ({:.0}s)", t0.elapsed().as_secs_f64());
}

// ------------------------------------------------------------------ hulp: bezettingen
/// welke steunvariant is voor deze lijn GELDIG in deze bezetting?
/// 1 = scherp (geen enkele vrije cel heeft een loodrechte buur), 0 = ruim (altijd geldig)
#[inline]
fn var_v(cols: &[u16; 15], x: usize, a: usize, b: usize) -> u8 {
    for y in a..=b {
        if ANCHOR_ROWS.contains(&y) {
            continue;
        }
        let l = x > 0 && full_col(cols[x - 1]) >> y & 1 != 0;
        let r = x < 14 && full_col(cols[x + 1]) >> y & 1 != 0;
        if l || r {
            return 0;
        }
    }
    1
}

#[inline]
fn var_h(cols: &[u16; 15], y: usize, x0: usize, x1: usize) -> u8 {
    for x in x0..=x1 {
        let f = full_col(cols[x]);
        let up = y > 0 && f >> (y - 1) & 1 != 0;
        let dn = y < 14 && f >> (y + 1) & 1 != 0;
        if up || dn {
            return 0;
        }
    }
    1
}

fn occ_lines(cols: &[u16; 15]) -> (Vec<(Key, u8)>, Vec<(Key, u8)>) {
    let mut vs = Vec::new();
    let mut hs = Vec::new();
    for x in 0..15 {
        for (a, b) in vruns(cols[x]) {
            vs.push((Key::V(x, a, b), var_v(cols, x, a, b)));
        }
    }
    for y in 0..15 {
        if ANCHOR_ROWS.contains(&y) {
            continue;
        }
        for (x0, x1) in hruns_of(cols, y) {
            hs.push((Key::H(y, x0, x1), var_h(cols, y, x0, x1)));
        }
    }
    (vs, hs)
}

struct Bound {
    ub: i64,
    anch: i64,
    sv: i64,
    sh: i64,
    feasible: bool,
}

/// DE SCHERPE BOVENGRENS van een concrete bezetting:
///   ANCH(steunpatroon)  +  SOM_lijnen R_L(lambda, eigendom)  +  lambda-constante
/// met exacte maximale runs (dus geen paar-relaxatie) en de exacte ankersteun.
fn bound_of(cols: &[u16; 15], tabs: &HashMap<(Key, u8), Tab>, at: &AnchTab, d: &Data,
            lam: &[i64; 26]) -> Bound {
    // TEGELBUDGET: zak 100 letters + 2 blanco, de tegenstander houdt >= 1 tegel vast, dus
    // hoogstens 101 tegels op het bord; 45 daarvan zijn ankercellen -> <= 56 vrije cellen.
    let nmax: usize = env::var("NFREE").ok().and_then(|s| s.parse().ok()).unwrap_or(56);
    let mut nfree = 0usize;
    for x in 0..15 {
        nfree += (cols[x] & !((1 << 0) | (1 << 7) | (1 << 14))).count_ones() as usize;
    }
    if nfree > nmax {
        return Bound { ub: NEG, anch: NEG, sv: 0, sh: 0, feasible: false };
    }
    let anch = at.cap(cols);
    if anch <= NEG / 2 {
        return Bound { ub: NEG, anch: NEG, sv: 0, sh: 0, feasible: false };
    }
    let konst = lam_const(d, lam);
    let (vs, hs) = occ_lines(cols);
    let mut sv = 0i64;
    for (k, var) in vs {
        let (a, b) = match k {
            Key::V(_, a, b) => (a, b),
            _ => unreachable!(),
        };
        match tabs.get(&(k, var)) {
            Some(t) if t.umax > NEG as i32 / 2 => sv += r_lambda_own(t, lam, own_v(a, b)),
            _ => return Bound { ub: NEG, anch, sv: 0, sh: 0, feasible: false },
        }
    }
    let mut sh = 0i64;
    for (k, var) in hs {
        let (y, x0, x1) = match k {
            Key::H(y, a, b) => (y, a, b),
            _ => unreachable!(),
        };
        match tabs.get(&(k, var)) {
            Some(t) if t.umax > NEG as i32 / 2 => {
                sh += r_lambda_own(t, lam, own_h(cols, y, x0, x1));
            }
            _ => return Bound { ub: NEG, anch, sv: 0, sh: 0, feasible: false },
        }
    }
    let ub = anch + (sv + sh + konst).div_euclid(SCALE);
    Bound { ub, anch, sv, sh, feasible: true }
}

fn read_occs(path: &str) -> Vec<(String, [u16; 15])> {
    let br = BufReader::new(File::open(path).unwrap());
    let mut out = Vec::new();
    for line in br.lines() {
        let line = line.unwrap();
        let t = line.trim();
        if t.is_empty() || t.starts_with('#') {
            continue;
        }
        let mut it = t.split_whitespace();
        let name = it.next().unwrap().to_string();
        let mut cols = [0u16; 15];
        for x in 0..15 {
            cols[x] = it.next().unwrap().parse::<u16>().unwrap();
        }
        out.push((name, cols));
    }
    out
}

/// IJKING die bij ELKE run draait: op de recordbezetting moet de motor een grens >= 4793
/// geven (de arbiter-geverifieerde score van experiments/results/maxgame_BEST.json).  Een
/// lagere waarde zou betekenen dat de grens onsound is.
fn calib_assert(dir: &str, tabs: &HashMap<(Key, u8), Tab>, at: &AnchTab, d: &Data,
                lam: &[i64; 26]) {
    let path = format!("{}/occ_record.txt", dir);
    if !std::path::Path::new(&path).exists() {
        eprintln!("IJKING OVERGESLAGEN: {} ontbreekt", path);
        return;
    }
    let rec: i64 = env::var("RECORD").ok().and_then(|s| s.parse().ok()).unwrap_or(4793);
    for (name, cols) in read_occs(&path) {
        let b = bound_of(&cols, tabs, at, d, lam);
        if !b.feasible || b.ub < rec {
            panic!("IJKING GEFAALD: {} krijgt grens {} < {} -- de motor is ONSOUND",
                   name, b.ub, rec);
        }
        eprintln!("IJKING OK: {} -> grens {} >= record {}", name, b.ub, rec);
    }
}

// ------------------------------------------------------------------ eval
fn cmd_eval(dir: &str, occfile: &str) {
    let d = load(dir);
    let tabs = read_tabs(&format!("{}/tables.bin", dir));
    let at = read_anchtab(dir);
    let lam = read_lam();
    let target: i64 = env::var("TARGET").ok().and_then(|s| s.parse().ok()).unwrap_or(4819);
    let verbose = env::var("V").is_ok();
    calib_assert(dir, &tabs, &at, &d, &lam);
    let mut nref = 0;
    let mut nsur = 0;
    for (name, cols) in read_occs(occfile) {
        let mut nfree = 0;
        for x in 0..15 {
            nfree += (cols[x] & !((1 << 0) | (1 << 7) | (1 << 14))).count_ones();
        }
        let b = bound_of(&cols, &tabs, &at, &d, &lam);
        if verbose {
            println!("--- {}  ({} vrije cellen)", name, nfree);
            let (vs, hs) = occ_lines(&cols);
            for (k, var) in vs {
                if let (Key::V(x, a, bb), Some(t)) = (k, tabs.get(&(k, var))) {
                    println!("  V x={:2} {:2}..{:<2} n={:2} var={} w={:6} Umax={:5} ent={:6} R={:8.2}",
                             x, a, bb, bb - a + 1, var, t.nw, t.umax, t.ent.len(),
                             r_lambda_own(t, &lam, own_v(a, bb)) as f64 / SCALE as f64);
                }
            }
            for (k, var) in hs {
                if let (Key::H(y, x0, x1), Some(t)) = (k, tabs.get(&(k, var))) {
                    println!("  H y={:2} {:2}..{:<2} n={:2} var={} w={:6} Umax={:5} ent={:6} eigen={:2} R={:8.2}",
                             y, x0, x1, x1 - x0 + 1, var, t.nw, t.umax, t.ent.len(),
                             own_h(&cols, y, x0, x1).count_ones(),
                             r_lambda_own(t, &lam, own_h(&cols, y, x0, x1)) as f64 / SCALE as f64);
                }
            }
        }
        if !b.feasible {
            nref += 1;
            if verbose {
                println!("  ONMOGELIJK (ankersteun of lexicaal lege lijn) -> WEERLEGD");
            }
            continue;
        }
        if b.ub < target {
            nref += 1;
        } else {
            nsur += 1;
        }
        if verbose {
            println!("  ANCH={}  SOM_V={:.2}  SOM_H={:.2}  lam-konst={:.2}  ->  UB={}  ({})",
                     b.anch, b.sv as f64 / SCALE as f64, b.sh as f64 / SCALE as f64,
                     lam_const(&d, &lam) as f64 / SCALE as f64, b.ub,
                     if b.ub < target { "WEERLEGD" } else { "overleeft" });
        } else {
            println!("{} {} {}", name, b.ub, if b.ub < target { "WEERLEGD" } else { "OVERLEEFT" });
        }
    }
    eprintln!("weerlegd {}  overleeft {}", nref, nsur);
}

// ------------------------------------------------------------------ lamopt
// Elke lambda >= 0 geeft een GELDIGE bovengrens (Lagrange-relaxatie van de zakbeperking),
// dus optimaliseren over lambda mag vrij: het minimum van geldige grenzen is geldig.
fn cmd_lamopt(dir: &str, occfile: &str) {
    let d = load(dir);
    let tabs = read_tabs(&format!("{}/tables.bin", dir));
    let at = read_anchtab(dir);
    let occs = read_occs(occfile);
    let iters: usize = env::var("ITERS").ok().and_then(|s| s.parse().ok()).unwrap_or(3000);
    let mut lam = read_lam();
    let mut best = i64::MAX;
    let mut bestlam = lam;
    let step: f64 = env::var("STEP").ok().and_then(|s| s.parse().ok()).unwrap_or(24.0);
    for it in 0..iters {
        let mut worst = i64::MIN;
        let mut wcols = [0u16; 15];
        for (_n, c) in occs.iter() {
            let b = bound_of(c, &tabs, &at, &d, &lam);
            if b.feasible && b.ub > worst {
                worst = b.ub;
                wcols = *c;
            }
        }
        if worst < best {
            best = worst;
            bestlam = lam;
        }
        let mut use_ = [0i64; 26];
        let (vs, hs) = occ_lines(&wcols);
        for (k, var) in vs {
            if let (Key::V(_, a, b), Some(t)) = (k, tabs.get(&(k, var))) {
                if let Some((w, own)) = r_arg_own(t, &lam, own_v(a, b)) {
                    let mut m = own;
                    while m != 0 {
                        let i = m.trailing_zeros() as usize;
                        m &= m - 1;
                        use_[(w[i] - 1) as usize] += 1;
                    }
                }
            }
        }
        for (k, var) in hs {
            if let (Key::H(y, x0, x1), Some(t)) = (k, tabs.get(&(k, var))) {
                let ow = own_h(&wcols, y, x0, x1);
                if let Some((w, own)) = r_arg_own(t, &lam, ow) {
                    let mut m = own;
                    while m != 0 {
                        let i = m.trailing_zeros() as usize;
                        m &= m - 1;
                        use_[(w[i] - 1) as usize] += 1;
                    }
                }
            }
        }
        let mut mxi = 0usize;
        for i in 0..26 {
            if lam[i] > lam[mxi] {
                mxi = i;
            }
        }
        let s = step / ((it as f64 / 200.0) + 1.0).sqrt();
        for i in 0..26 {
            let mut g = d.rest[i + 1] - use_[i];
            if i == mxi {
                g += d.nblank;
            }
            let nv = lam[i] as f64 - s * g as f64;
            lam[i] = if nv < 0.0 { 0 } else { nv.round() as i64 };
        }
        if it % 500 == 0 {
            eprintln!("  it {:5}  worst {}  best {}", it, worst, best);
        }
    }
    println!("LAM={}", bestlam.iter().map(|v| v.to_string()).collect::<Vec<_>>().join(","));
    println!("  -> slechtste bovengrens over {} bezettingen: {}", occs.len(), best);
}

// ------------------------------------------------------------------ lambda / anker uit env
fn read_lam() -> [i64; 26] {
    let mut lam = [0i64; 26];
    if let Ok(s) = env::var("LAM") {
        for (i, t) in s.split(',').enumerate() {
            if i < 26 {
                lam[i] = t.trim().parse().unwrap_or(0);
            }
        }
    }
    lam
}

fn nthreads() -> usize {
    env::var("THREADS").ok().and_then(|s| s.parse().ok()).unwrap_or(12)
}

// ------------------------------------------------------------------ tables
fn cmd_tables(dir: &str) {
    let d = Arc::new(load(dir));
    let lam0 = read_lam();
    let keys = all_keys();
    let mut pmap: HashMap<Prof, Vec<(Key, u8)>> = HashMap::new();
    for k in keys.iter() {
        for var in 0..2u8 {
            pmap.entry(prof_of(&d, *k, var)).or_default().push((*k, var));
        }
    }
    let mut profs: Vec<(Prof, Vec<(Key, u8)>)> = pmap.into_iter().collect();
    profs.sort_by_key(|(p, _)| std::cmp::Reverse(d.nwords[p.n] >> (3 * p.anch.len())));
    eprintln!("{} lijnsleutels -> {} unieke profielen", keys.len(), profs.len());
    let profs = Arc::new(profs);
    let idx = Arc::new(AtomicUsize::new(0));
    let res: Arc<Mutex<Vec<((Key, u8), Tab)>>> = Arc::new(Mutex::new(Vec::new()));
    let t0 = std::time::Instant::now();
    let done = Arc::new(AtomicUsize::new(0));
    let mut hs = Vec::new();
    for _ in 0..nthreads() {
        let d = d.clone();
        let profs = profs.clone();
        let idx = idx.clone();
        let res = res.clone();
        let done = done.clone();
        let lam0 = lam0;
        hs.push(std::thread::spawn(move || {
            let mut dp = Dp::new();
            loop {
                let i = idx.fetch_add(1, Ordering::SeqCst);
                if i >= profs.len() {
                    break;
                }
                let (prof, ks) = &profs[i];
                let t = build_tab(&d, &mut dp, prof, &lam0);
                let mut g = res.lock().unwrap();
                for k in ks.iter() {
                    g.push((*k, Tab { umax: t.umax, tail: t.tail, ent: t.ent.clone(),
                                      n: t.n, nw: t.nw }));
                }
                drop(g);
                let n = done.fetch_add(1, Ordering::SeqCst) + 1;
                if n % 50 == 0 {
                    eprintln!("  {}/{} profielen  {:.0}s", n, profs.len(),
                              t0.elapsed().as_secs_f64());
                }
            }
        }));
    }
    for h in hs {
        h.join().unwrap();
    }
    let g = res.lock().unwrap();
    write_tabs(&format!("{}/tables.bin", dir), &g);
    eprintln!("{} tabellen -> {}/tables.bin  ({:.0}s)", g.len(), dir,
              t0.elapsed().as_secs_f64());
}

// ------------------------------------------------------------------ lamdp
// Subgradiënt-minimalisatie van de GLOBALE DP-grens over lambda, per stratum.
// Elke lambda >= 0 levert een geldige bovengrens; we zoeken de lambda die de grens van dit
// stratum zo laag mogelijk maakt.  Iteratie: bouw de DP, haal de maximaliserende bezetting
// eruit, kijk welke letters die vraagt, en verhoog de prijs van de letters die overvraagd
// worden.
fn cmd_lamdp(dir: &str) {
    let d = load(dir);
    let tabs = read_tabs(&format!("{}/tables.bin", dir));
    let at = read_anchtab(dir);
    let mut lam = read_lam();
    let nmax: usize = env::var("NFREE").ok().and_then(|s| s.parse().ok()).unwrap_or(56);
    let active: u16 = env::var("ACT").ok().and_then(|s| u16::from_str_radix(&s, 2).ok())
        .unwrap_or(0);
    let iters: usize = env::var("ITERS").ok().and_then(|s| s.parse().ok()).unwrap_or(60);
    let step: f64 = env::var("STEP").ok().and_then(|s| s.parse().ok()).unwrap_or(40.0);
    calib_assert(dir, &tabs, &at, &d, &lam);
    let anch = at.maxcap();
    let pwr = pair_weights(&tabs);
    let mut best = i64::MAX;
    let mut bestlam = lam;
    for it in 0..iters {
        let colv0 = col_values(&tabs, &lam, 0);
        let colv1 = col_values(&tabs, &lam, 1);
        let konst = lam_const(&d, &lam);
        let g = gdp_build(&colv0, &colv1, &pwr, active, nmax);
        let bv = g.suf[0][((0 * 2 + 0) * g.nt + nmax) * 4 + 0] as i64;
        let ub = anch + (bv + konst).div_euclid(SCALE);
        if ub < best {
            best = ub;
            bestlam = lam;
        }
        // maximaliserende bezetting ophalen
        let mut c = SurvCtx { g: &g, colv0: &colv0, colv1: &colv1, active, need: bv,
                              nodes: 0, found: 0, cap: 1, cols: [0u16; 15], out: Vec::new() };
        dfs(&mut c, 0, 0, 0, nmax, 0, 0);
        if c.out.is_empty() {
            eprintln!("  it {} ub {} (geen bezetting gevonden)", it, ub);
            break;
        }
        let cols = c.out[0];
        let mut use_ = [0i64; 26];
        let (vs, hs) = occ_lines(&cols);
        for (k, var) in vs {
            if let (Key::V(_, a, b), Some(t)) = (k, tabs.get(&(k, var))) {
                if let Some((w, own)) = r_arg_own(t, &lam, own_v(a, b)) {
                    let mut m = own;
                    while m != 0 {
                        let i = m.trailing_zeros() as usize;
                        m &= m - 1;
                        use_[(w[i] - 1) as usize] += 1;
                    }
                }
            }
        }
        for (k, var) in hs {
            if let (Key::H(y, x0, x1), Some(t)) = (k, tabs.get(&(k, var))) {
                let ow = own_h(&cols, y, x0, x1);
                if let Some((w, own)) = r_arg_own(t, &lam, ow) {
                    let mut m = own;
                    while m != 0 {
                        let i = m.trailing_zeros() as usize;
                        m &= m - 1;
                        use_[(w[i] - 1) as usize] += 1;
                    }
                }
            }
        }
        let mut mxi = 0usize;
        for i in 0..26 {
            if lam[i] > lam[mxi] {
                mxi = i;
            }
        }
        let sstep = step / ((it as f64 / 10.0) + 1.0).sqrt();
        for i in 0..26 {
            let mut gr = d.rest[i + 1] - use_[i];
            if i == mxi {
                gr += d.nblank;
            }
            let nv = lam[i] as f64 - sstep * gr as f64;
            lam[i] = if nv < 0.0 { 0 } else { nv.round() as i64 };
        }
        eprintln!("  it {:3}  ub {}  best {}", it, ub, best);
    }
    println!("LAM={}", bestlam.iter().map(|v| v.to_string()).collect::<Vec<_>>().join(","));
    println!("STRATUM ACT={:012b} MAXVLEN={} -> BOVENGRENS {}", active,
             env::var("MAXVLEN").unwrap_or_else(|_| "15".into()), best);
}

// ------------------------------------------------------------------ sharp
// De EXACTE steunversie: in plaats van de twee grove varianten (volle steun / alleen
// ankersteun) wordt hier per lijn het WERKELIJKE steunpatroon uit de bezetting gehaald en de
// per-lijn-DP opnieuw gedraaid over de opgeslagen woordtabel.  Dat is de scherpste
// zetvolgorde-vrije per-lijn-grens die we kunnen berekenen.  Voor de woorden die bij het
// afkappen zijn weggevallen geldt nog steeds de staartgrens (U <= tail met VOLLE steun >=
// U met de echte steun), dus het blijft sound.
fn sup_mask_v(cols: &[u16; 15], x: usize, a: usize, b: usize) -> u16 {
    let mut m = 0u16;
    for (i, y) in (a..=b).enumerate() {
        if ANCHOR_ROWS.contains(&y) {
            m |= 1 << i;
            continue;
        }
        let l = x > 0 && full_col(cols[x - 1]) >> y & 1 != 0;
        let r = x < 14 && full_col(cols[x + 1]) >> y & 1 != 0;
        if l || r {
            m |= 1 << i;
        }
    }
    m
}

fn sup_mask_h(cols: &[u16; 15], y: usize, x0: usize, x1: usize) -> u16 {
    let mut m = 0u16;
    for (i, x) in (x0..=x1).enumerate() {
        let f = full_col(cols[x]);
        let up = y > 0 && f >> (y - 1) & 1 != 0;
        let dn = y < 14 && f >> (y + 1) & 1 != 0;
        if up || dn {
            m |= 1 << i;
        }
    }
    m
}

fn sharp_line(d: &Data, dp: &mut Dp, t: &Tab, mut prof: Prof, sup: u16,
              lam: &[i64; 26], own: u16) -> i64 {
    prof.sup = sup;
    let n = prof.n;
    let mut best = t.tail as i64 * SCALE;
    let mut valv = vec![0i64; n];
    for (_u, w) in t.ent.iter() {
        for i in 0..n {
            valv[i] = d.val[w[i] as usize];
        }
        let isw = build_isw(d, &w[..n]);
        let u = maxg(dp, &prof, &valv, &isw);
        if u <= NEG {
            continue;
        }
        let mut c = 0i64;
        let mut mm = own;
        while mm != 0 {
            let i = mm.trailing_zeros() as usize;
            mm &= mm - 1;
            c += lam[(w[i] - 1) as usize];
        }
        let v = u * SCALE - c;
        if v > best {
            best = v;
        }
    }
    best
}

fn cmd_sharp(dir: &str, occfile: &str) {
    let d = load(dir);
    let tabs = read_tabs(&format!("{}/tables.bin", dir));
    let at = read_anchtab(dir);
    let lam = read_lam();
    let konst = lam_const(&d, &lam);
    let target: i64 = env::var("TARGET").ok().and_then(|s| s.parse().ok()).unwrap_or(4819);
    let nmax: usize = env::var("NFREE").ok().and_then(|s| s.parse().ok()).unwrap_or(56);
    calib_assert(dir, &tabs, &at, &d, &lam);
    let mut dp = Dp::new();
    let mut cache: HashMap<(Key, u16, u16), i64> = HashMap::new();
    for (name, cols) in read_occs(occfile) {
        let mut nfree = 0usize;
        for x in 0..15 {
            nfree += (cols[x] & !((1 << 0) | (1 << 7) | (1 << 14))).count_ones() as usize;
        }
        if nfree > nmax {
            println!("{}  te veel tegels ({}) -> WEERLEGD", name, nfree);
            continue;
        }
        let anch = at.cap(&cols);
        if anch <= NEG / 2 {
            println!("{}  ankersteun onmogelijk -> WEERLEGD", name);
            continue;
        }
        let (vs, hs) = occ_lines(&cols);
        let mut tot = 0i64;
        let mut dead = false;
        println!("--- {}  ({} vrije cellen, ANCH={})", name, nfree, anch);
        for (k, _var) in vs.into_iter().chain(hs.into_iter()) {
            let (sup, own) = match k {
                Key::V(x, a, b) => (sup_mask_v(&cols, x, a, b), own_v(a, b)),
                Key::H(y, x0, x1) => (sup_mask_h(&cols, y, x0, x1), own_h(&cols, y, x0, x1)),
            };
            let t = match tabs.get(&(k, 0u8)) {
                Some(t) if t.umax > NEG as i32 / 2 => t,
                _ => {
                    dead = true;
                    break;
                }
            };
            let ck = (k, sup, own);
            let v = match cache.get(&ck) {
                Some(v) => *v,
                None => {
                    let prof = prof_of(&d, k, 0);
                    let v = sharp_line(&d, &mut dp, t, prof, sup, &lam, own);
                    cache.insert(ck, v);
                    v
                }
            };
            let ruw = r_lambda_own(t, &lam, own);
            match k {
                Key::V(x, a, b) => println!(
                    "  V x={:2} {:2}..{:<2} steun={:015b} ruw={:8.2} SCHERP={:8.2}",
                    x, a, b, sup, ruw as f64 / SCALE as f64, v as f64 / SCALE as f64),
                Key::H(y, x0, x1) => println!(
                    "  H y={:2} {:2}..{:<2} steun={:015b} ruw={:8.2} SCHERP={:8.2}",
                    y, x0, x1, sup, ruw as f64 / SCALE as f64, v as f64 / SCALE as f64),
            }
            tot += v;
        }
        if dead {
            println!("  lexicaal lege lijn -> WEERLEGD");
            continue;
        }
        let ub = anch + (tot + konst).div_euclid(SCALE);
        println!("  SCHERPE BOVENGRENS = {}   ({})", ub,
                 if ub < target { "WEERLEGD" } else { "overleeft" });
    }
}

// ==================================================================================
// VERSCHERPING 1 -- FIJNE STEUNGRANULARITEIT PER STRATUM
// ==================================================================================
//
// De oude relaxatie kent per lijn maar TWEE steunvarianten: volle steun (variant 0, altijd
// geldig) en alleen-ankersteun (variant 1, alleen geldig als de kolom horizontaal volledig
// geisoleerd is).  In de kolom-DP mocht een kolom variant 1 gebruiken zodra hij GEEN cel in
// een actieve rij had; had hij er wel een, dan kreeg hij variant 0 voor AL zijn runs -- ook
// voor runs die kilometers van die actieve rij liggen.  Dat is de grootste verliespost: de
// stratumgrens springt daardoor van 4777 (A = leeg) naar ~5100 zodra er een actieve rij is.
//
// LEMMA 3 (steunmasker per stratum).  Zij A de verzameling vrije rijen waarin de bezetting
// een horizontale run heeft (de stratumparameter).  Dan heeft een bezette cel (x,y) een
// bezette HORIZONTALE buur alleen als y in {0,7,14} u A.
//   Bewijs.  Rijen 0/7/14 zijn volle ankerrijen: elke cel daar heeft altijd een bezette
//   horizontale buur (bij x=0 is dat (1,y), bij x=14 is dat (13,y)).  Zij y een vrije rij
//   buiten A.  Per definitie van het stratum bevat rij y geen enkele horizontale run, dus er
//   zijn geen twee horizontaal aangrenzende bezette cellen in rij y; is (x,y) bezet, dan zijn
//   (x-1,y) en (x+1,y) leeg.  QED
//
// Gevolg: voor een verticale run [a,b] in kolom x is
//       sup = ({0,7,14} u A) n [a,b]
// een BOVENverzameling van de werkelijke steunverzameling, dus Lemma 2 (aanraakregel) mag er
// mee worden toegepast en de per-lijn-DP blijft een geldige bovengrens.  Dit masker hangt
// NIET van x en NIET van het kolommasker af -- alleen van (a,b) en A.  Daarmee is het per
// stratum eenmalig uit te rekenen.
//
// Twee randgevallen vallen samen met de bestaande tabellen:
//   * A n [a,b] bevat alle vrije rijen van [a,b]  -> sup = vol      -> variant 0 is exact;
//   * A n [a,b] = leeg                            -> sup = ankers   -> variant 1 is exact.
// Het tweede geval GENERALISEERT de oude `forced_iso`-vlag: een kolom zonder cel in een
// actieve rij heeft geen enkele run die een rij van A raakt, dus krijgt overal variant 1 --
// precies wat de vlag deed -- maar nu krijgt een kolom die WEL een actieve rij raakt de
// scherpe variant voor al zijn overige runs.
//
// SOUNDNESS.  sup is een bovenverzameling van de echte steun => de DP staat minstens alle
// echte geschiedenissen toe => de waarde is een bovengrens.  De staartgrens `tail` uit de
// variant-0-tabel blijft geldig: voor elk weggelaten woord geldt U(sup) <= U(vol) <= tail.

#[derive(Clone)]
enum SupSrc {
    Var0,           // steunmasker = volle steun -> de bestaande variant-0-tabel is exact
    Var1,           // steunmasker = alleen ankerrijen -> de variant-1-tabel is exact
    Cust(Vec<i32>), // U per entry van de variant-0-tabel, herrekend met het echte steunmasker
    Dead,           // geen enkel woord is met dit steunmasker legbaar
}

const UDEAD: i32 = i32::MIN / 2;

/// de rijen waarin een bezette cel loodrechte (horizontale) steun KAN hebben -- Lemma 3
fn suprows_of(active: u16) -> u16 {
    let mut m = (1u16 << 0) | (1 << 7) | (1 << 14);
    for (i, &y) in FREEROWS.iter().enumerate() {
        if active >> i & 1 != 0 {
            m |= 1 << y;
        }
    }
    m
}

fn anch_sup_mask(a: usize, b: usize) -> u16 {
    let mut m = 0u16;
    for (i, y) in (a..=b).enumerate() {
        if ANCHOR_ROWS.contains(&y) {
            m |= 1 << i;
        }
    }
    m
}

/// per verticale lijnsleutel het steunmasker van dit stratum toepassen
fn build_sharp_v(d: &Arc<Data>, tabs: &Arc<HashMap<(Key, u8), Tab>>, suprows: u16)
                 -> HashMap<Key, SupSrc> {
    let mut keys: Vec<Key> = Vec::new();
    for (k, var) in tabs.keys() {
        if *var == 0 {
            if let Key::V(..) = k {
                keys.push(*k);
            }
        }
    }
    keys.sort_by_key(|k| match k {
        Key::V(x, a, b) => (*b - *a, *x, *a),
        _ => (0, 0, 0),
    });
    keys.reverse();
    let keys = Arc::new(keys);
    let idx = Arc::new(AtomicUsize::new(0));
    let res: Arc<Mutex<Vec<(Key, SupSrc)>>> = Arc::new(Mutex::new(Vec::new()));
    let mut hs = Vec::new();
    for _ in 0..nthreads() {
        let (d, tabs, keys, idx, res) = (d.clone(), tabs.clone(), keys.clone(), idx.clone(),
                                         res.clone());
        hs.push(std::thread::spawn(move || {
            let mut dp = Dp::new();
            let mut local: Vec<(Key, SupSrc)> = Vec::new();
            loop {
                let i = idx.fetch_add(1, Ordering::SeqCst);
                if i >= keys.len() {
                    break;
                }
                let k = keys[i];
                let (a, b) = match k {
                    Key::V(_, a, b) => (a, b),
                    _ => unreachable!(),
                };
                let n = b - a + 1;
                let full = ((1u32 << n) - 1) as u16;
                let sup = ((suprows >> a) as u16) & full;
                let asup = anch_sup_mask(a, b);
                if sup == full {
                    local.push((k, SupSrc::Var0));
                    continue;
                }
                if sup == asup {
                    local.push((k, SupSrc::Var1));
                    continue;
                }
                let t = &tabs[&(k, 0u8)];
                if t.umax <= NEG as i32 / 2 {
                    local.push((k, SupSrc::Dead));
                    continue;
                }
                let mut prof = prof_of(&d, k, 0);
                prof.sup = sup;
                let mut us: Vec<i32> = Vec::with_capacity(t.ent.len());
                let mut valv = vec![0i64; n];
                let mut live = false;
                for (_u, w) in t.ent.iter() {
                    for j in 0..n {
                        valv[j] = d.val[w[j] as usize];
                    }
                    let isw = build_isw(&d, &w[..n]);
                    let u = maxg(&mut dp, &prof, &valv, &isw);
                    if u <= NEG {
                        us.push(UDEAD);
                    } else {
                        us.push(u as i32);
                        live = true;
                    }
                }
                if !live && t.tail <= NEG as i32 / 2 {
                    local.push((k, SupSrc::Dead));
                } else {
                    local.push((k, SupSrc::Cust(us)));
                }
            }
            res.lock().unwrap().extend(local);
        }));
    }
    for h in hs {
        h.join().unwrap();
    }
    let g = res.lock().unwrap();
    g.iter().cloned().collect()
}

/// de woordtabel die bij het stratum-steunmasker van deze lijn hoort:
/// (tabel, eventueel herrekende U per entry).  None = deze run is lexicaal onmogelijk.
fn sharp_ent<'a>(tabs: &'a HashMap<(Key, u8), Tab>, sharp: &'a HashMap<Key, SupSrc>, k: Key)
                 -> Option<(&'a Tab, Option<&'a Vec<i32>>)> {
    match sharp.get(&k) {
        None | Some(SupSrc::Dead) => None,
        Some(SupSrc::Var0) => match tabs.get(&(k, 0u8)) {
            Some(t) if t.umax > NEG as i32 / 2 => Some((t, None)),
            _ => None,
        },
        Some(SupSrc::Var1) => match tabs.get(&(k, 1u8)) {
            Some(t) if t.umax > NEG as i32 / 2 => Some((t, None)),
            _ => None,
        },
        Some(SupSrc::Cust(us)) => Some((&tabs[&(k, 0u8)], Some(us))),
    }
}

/// R(lambda, own) met het stratum-steunmasker; None = deze run is lexicaal onmogelijk
fn r_sharp(tabs: &HashMap<(Key, u8), Tab>, sharp: &HashMap<Key, SupSrc>, lam: &[i64; 26],
           k: Key, own: u16) -> Option<i64> {
    let (t, us) = sharp_ent(tabs, sharp, k)?;
    let mut best = i64::MIN;
    if t.tail > NEG as i32 / 2 {
        best = t.tail as i64 * SCALE;
    }
    for (i, (u0, w)) in t.ent.iter().enumerate() {
        let u = match us {
            None => *u0,
            Some(v) => v[i],
        };
        if u <= UDEAD {
            continue;
        }
        let mut c = 0i64;
        let mut m = own;
        while m != 0 {
            let j = m.trailing_zeros() as usize;
            m &= m - 1;
            c += lam[(w[j] - 1) as usize];
        }
        let v = u as i64 * SCALE - c;
        if v > best {
            best = v;
        }
    }
    if best == i64::MIN { None } else { Some(best) }
}

// ---------------------------------------------------------------- VERSCHERPING 4: FRAME-klasse
// De maskers maken van kolom 0, 7 en 14 volledige TWS-kolommen: hun cellen in rij 0, 7 EN 14
// zitten alle drie in het slotmasker.  Een verticaal 15-letterwoord daar wordt door alle drie
// de slotzetten opnieuw gescoord.  Zo'n VOLLE kolom is een verticale run [0,14] van lengte 15
// en valt dus alleen in het stratum MAXVLEN = 15 -- waar de grens (5415) nietszeggend is.
//
// De FRAME-parameter F = de verzameling kolommen die VOL zijn (masker = alle 12 vrije rijen).
// Elke bezetting heeft precies een F, dus stratificeren op (F, A, MAXVLEN) is uitputtend, met
// dien verstande dat MAXVLEN dan alleen op de kolommen BUITEN F slaat: een kolom in F heeft
// per definitie een run van 15.  Zo krijgt de FRAME-klasse haar eigen, scherpe grens en houdt
// de rest van de stratificatie een bruikbare MAXVLEN.
fn full_cols_env() -> Option<u16> {
    let s = env::var("FULL").ok()?;
    let s = s.trim().to_string();
    if s.is_empty() {
        return Some(0);
    }
    let mut m = 0u16;
    for t in s.split(',') {
        m |= 1 << t.trim().parse::<usize>().unwrap();
    }
    Some(m)
}

/// kolomwaarden met de scherpe steunmaskers (verscherping 1) + FRAME-parameter (verscherping 4)
fn col_values_sharp(tabs: &HashMap<(Key, u8), Tab>, sharp: &HashMap<Key, SupSrc>,
                    lam: &[i64; 26]) -> Vec<Vec<Option<(u8, i64)>>> {
    let maxv: usize = env::var("MAXVLEN").ok().and_then(|s| s.parse().ok()).unwrap_or(15);
    let fullm = full_cols_env();
    let mut out = Vec::with_capacity(15);
    for x in 0..15 {
        // een kolom in F is VERPLICHT vol, een kolom buiten F is verboden vol te zijn
        let must_full = fullm.map_or(false, |f| f >> x & 1 != 0);
        let no_full = fullm.map_or(false, |f| f >> x & 1 == 0);
        // eerst de 70 mogelijke runs van deze kolom een keer beprijzen
        let mut rv = [[None::<i64>; 15]; 15];
        for a in 0..15 {
            for b in (a + 1)..15 {
                // MAXVLEN geldt alleen voor de kolommen BUITEN F
                if !must_full && b - a + 1 > maxv {
                    continue;
                }
                rv[a][b] = r_sharp(tabs, sharp, lam, Key::V(x, a, b), own_v(a, b));
            }
        }
        let mut v = Vec::with_capacity(1 << 12);
        for m in 0..(1u32 << 12) {
            if (must_full && m != 0xfff) || (no_full && m == 0xfff) {
                v.push(None);
                continue;
            }
            let cm = mask12_to_col(m);
            let mut val = 0i64;
            let mut ok = true;
            for (a, b) in vruns(cm) {
                if !must_full && b - a + 1 > maxv {
                    ok = false;
                    break;
                }
                match rv[a][b] {
                    Some(r) => val += r,
                    None => {
                        ok = false;
                        break;
                    }
                }
            }
            v.push(if ok { Some((m.count_ones() as u8, val)) } else { None });
        }
        out.push(v);
    }
    out
}

// ---------------------------------------------------------------- VERSCHERPING 3: bingoplafond
// U_L telt +50 voor elke groep van 7 nieuwe tegels op L, zonder globaal maximum.  Er liggen
// hoogstens 101 tegels op het bord (zak 100 + 2 blanco, tegenstander houdt >= 1 tegel vast) en
// elke bingo legt er precies 7, op onderling DISJUNCTE cellen (zetten zijn disjunct).  Dus
//      SOM over ALLE lijnen L van b_L  <=  floor(101/7) = 14.
// Een lijn van lengte n kan er hoogstens floor(n/7) herbergen (elke bingo legt 7 NIEUWE cellen
// op die lijn).  De vraag is of de relaxatie dat plafond uberhaupt overschrijdt.  Daarom eerst
// een RIGOUREUZE meting: maximaliseer met dezelfde kolom-DP de SLOTTELLING
//      SOM_L floor(len(L)/7)
// over het stratum (zelfde tegelbudget, zelfde eilandvlaggen, zelfde steunmaskers).  Komt daar
// een getal <= 14 uit, dan kan het bingoplafond in dit stratum NOOIT bijten en is verscherping
// 3 daar bewijsbaar nul waard.
fn col_bingoslots(colv: &Vec<Vec<Option<(u8, i64)>>>) -> Vec<Vec<Option<(u8, i64)>>> {
    let mut out = Vec::with_capacity(15);
    for x in 0..15 {
        let mut v = Vec::with_capacity(1 << 12);
        for m in 0..(1u32 << 12) {
            match colv[x][m as usize] {
                None => v.push(None),
                Some((tiles, _)) => {
                    let cm = mask12_to_col(m);
                    let mut s = 0i64;
                    for (a, b) in vruns(cm) {
                        s += ((b - a + 1) / 7) as i64;
                    }
                    v.push(Some((tiles, s * SCALE)));
                }
            }
        }
        out.push(v);
    }
    out
}

// ---------------------------------------------------------------- kolom-DP zonder isolatievlag
// Met de scherpe steunmaskers is de isolatievlag overbodig geworden: een kolom zonder cel in
// een actieve rij krijgt automatisch het ankersteunmasker (zie Lemma 3), en een kolom die wel
// een actieve rij raakt krijgt de scherpe variant voor al zijn overige runs.  Daarmee valt de
// toestandsdimensie `pi` weg en is de DP twee keer zo snel.
struct Gdp2 {
    suf: Vec<Vec<i32>>, // suf[x][(pm*nt + t)*4 + f]
    nt: usize,
    pw: Vec<[i64; 12]>,
}

fn gdp2_build(colv: &Vec<Vec<Option<(u8, i64)>>>, pwr: &[[i64; 14]; 15], active: u16,
              nmax: usize) -> Gdp2 {
    let mut pw: Vec<[i64; 12]> = Vec::new();
    for x in 0..15 {
        let mut a = [HARD; 12];
        for (i, &y) in FREEROWS.iter().enumerate() {
            if active >> i & 1 != 0 {
                a[i] = if x > 0 { pwr[y][x - 1] } else { 0 };
            }
        }
        pw.push(a);
    }
    let nt = nmax + 1;
    let sz = 4096 * nt * 4;
    let mut suf: Vec<Vec<i32>> = vec![Vec::new(); 16];
    suf[15] = vec![0i32; sz];
    for x in (0..15).rev() {
        let mut cur = vec![MINF; sz];
        for t in 0..nt {
            for f in 0..4usize {
                let mut a = [MINF; 4096];
                for m in 0..4096usize {
                    let nf = match flag_step(x, m as u32, f) {
                        Some(v) => v,
                        None => continue,
                    };
                    if let Some((tiles, val)) = colv[x][m] {
                        let tiles = tiles as usize;
                        if tiles <= t {
                            let nv = suf[x + 1][((m * nt) + (t - tiles)) * 4 + nf];
                            if nv > MINF {
                                a[m] = nv + val as i32;
                            }
                        }
                    }
                }
                maxplus_and(&mut a, &pw[x]);
                for pm in 0..4096usize {
                    cur[((pm * nt) + t) * 4 + f] = a[pm];
                }
            }
        }
        suf[x] = cur;
    }
    Gdp2 { suf, nt, pw }
}

struct Surv2<'a> {
    g: &'a Gdp2,
    colv: &'a Vec<Vec<Option<(u8, i64)>>>,
    active: u16,
    need: i64,
    found: u64,
    cap: u64,
    cols: [u16; 15],
    out: Vec<[u16; 15]>,
}

fn dfs2(c: &mut Surv2, x: usize, pm: u32, t: usize, f: usize, acc: i64) {
    if c.found >= c.cap {
        return;
    }
    if x == 15 {
        c.found += 1;
        if c.out.len() < 400000 {
            c.out.push(c.cols);
        }
        return;
    }
    let nt = c.g.nt;
    for m in 0..4096usize {
        let (tiles, val) = match c.colv[x][m] {
            Some(v) => v,
            None => continue,
        };
        if (pm & m as u32 & !(c.active as u32)) != 0 {
            continue;
        }
        let tiles = tiles as usize;
        if tiles > t {
            continue;
        }
        let nf = match flag_step(x, m as u32, f) {
            Some(v) => v,
            None => continue,
        };
        let nv = c.g.suf[x + 1][((m * nt) + (t - tiles)) * 4 + nf];
        if nv <= MINF {
            continue;
        }
        let ps = pairsum(&c.g.pw[x], pm, m as u32);
        let na = acc + val + ps;
        if na + (nv as i64) < c.need {
            continue;
        }
        c.cols[x] = mask12_to_col(m as u32);
        dfs2(c, x + 1, m as u32, t - tiles, nf, na);
        c.cols[x] = 0;
        if c.found >= c.cap {
            return;
        }
    }
}

/// IJKING voor verscherping 1: neem de recordbezetting, bepaal HAAR stratum (A = de vrije
/// rijen waarin ze werkelijk een horizontale run heeft), bouw daarmee de steunmaskers volgens
/// Lemma 3, en eis dat de per-lijn-som nog steeds >= de recordscore blijft.  Zou een van de
/// steunmaskers te klein zijn, dan zakt deze som onder 4793 en panic't de ijking.
fn calib_assert_sharp(dir: &str, tabs: &HashMap<(Key, u8), Tab>, sharp: &HashMap<Key, SupSrc>,
                      at: &AnchTab, d: &Data, lam: &[i64; 26], active: u16) {
    let path = format!("{}/occ_record.txt", dir);
    if !std::path::Path::new(&path).exists() {
        eprintln!("IJKING(scherp) OVERGESLAGEN: {} ontbreekt", path);
        return;
    }
    let rec: i64 = env::var("RECORD").ok().and_then(|s| s.parse().ok()).unwrap_or(4793);
    for (name, cols) in read_occs(&path) {
        // het stratum van deze bezetting
        let mut a = 0u16;
        for (i, &y) in FREEROWS.iter().enumerate() {
            if !hruns_of(&cols, y).is_empty() {
                a |= 1 << i;
            }
        }
        if a & !active != 0 {
            eprintln!("IJKING(scherp) n.v.t.: {} ligt in stratum {:012b}, niet in {:012b}",
                      name, a, active);
            continue;
        }
        let konst = lam_const(d, lam);
        let (vs, hs) = occ_lines(&cols);
        let mut tot = 0i64;
        for (k, _var) in vs {
            let (aa, bb) = match k {
                Key::V(_, aa, bb) => (aa, bb),
                _ => unreachable!(),
            };
            match r_sharp(tabs, sharp, lam, k, own_v(aa, bb)) {
                Some(v) => tot += v,
                None => panic!("IJKING(scherp) GEFAALD: {} heeft een DODE verticale lijn {:?}",
                               name, k),
            }
        }
        for (k, _var) in hs {
            let (y, x0, x1) = match k {
                Key::H(y, x0, x1) => (y, x0, x1),
                _ => unreachable!(),
            };
            match tabs.get(&(k, 0u8)) {
                Some(t) if t.umax > NEG as i32 / 2 =>
                    tot += r_lambda_own(t, lam, own_h(&cols, y, x0, x1)),
                _ => panic!("IJKING(scherp) GEFAALD: {} heeft een dode horizontale lijn", name),
            }
        }
        let anch = at.cap(&cols);
        let ub = anch + (tot + konst).div_euclid(SCALE);
        if anch <= NEG / 2 || ub < rec {
            panic!("IJKING(scherp) GEFAALD: {} krijgt met stratum-steunmaskers grens {} < {} \
                    -- verscherping 1 is ONSOUND", name, ub, rec);
        }
        eprintln!("IJKING(scherp) OK: {} (stratum {:012b}) -> grens {} >= record {}",
                  name, a, ub, rec);
    }
}

// ---------------------------------------------------------- VERSCHERPING 2 IN DE KOLOM-DP
// De kruispunt-Lagrange (zie boven) in de kolom-DP.  De horizontale lijnen zitten daar als
// PAARGEWICHTEN in, dus zonder letters; de theta-term moet daarom in het paargewicht worden
// meegebakken, en de verticale kant moet weten OF de cel wel echt een kruispunt is.
//
// NORMALISATIE-LEMMA.  Voor een echt kruispunt c verandert het optellen van een constante bij
// theta(c,.) de grens niet: de V-kant trekt -delta af en de H-kant telt +delta op.  We mogen
// dus WLOG normaliseren op min_k theta(c,k) = 0, en daarmee is theta >= 0.
//
// Daaruit volgt de soundness van de asymmetrie die de DP nodig heeft:
//  * de V-kant trekt theta(c, letter) af PRECIES als de cel een bezette linkerbuur heeft
//    (dat is in de DP bekend: het is de bit pm_y & m_y) EN op een verticale run (>=2) ligt
//    (dat is bekend uit het kolommasker m: alleen dan bevat een run die cel);
//  * de H-kant telt theta(c, letter) op voor ALLE cellen van de run behalve de meest linkse
//    (dat is dezelfde 'linkerbuur bezet'-voorwaarde).
// Ligt de cel wel op een horizontale maar niet op een verticale run, dan telt de H-kant +theta
// op zonder compensatie -- en omdat theta >= 0 is dat een VERRUIMING, dus sound.
//
// De DP-toestand krijgt er niets bij: per kolomovergang wordt over de deelverzamelingen
// S van de actieve rijen gelopen waarvoor pm_y & m_y = 1, en elke S krijgt zijn eigen
// kolomwaarde (met theta) en zijn eigen paargewichten.  Dat zijn 2^|A| maxplus-passes.

/// lettertabel van een run: de beste waarde per lettercombinatie op de gemarkeerde posities
struct LetTab {
    npos: usize,
    v: Vec<i64>, // 26^npos
}

impl LetTab {
    fn idx(&self, ls: &[usize]) -> usize {
        let mut i = 0usize;
        for j in 0..self.npos {
            i = i * 26 + ls[j];
        }
        i
    }
}

/// R per lettercombinatie op de posities `pos` (indices binnen de run)
fn run_lettab(tabs: &HashMap<(Key, u8), Tab>, sharp: &HashMap<Key, SupSrc>, lam: &[i64; 26],
              k: Key, own: u16, pos: &[usize]) -> Option<LetTab> {
    let (t, us) = sharp_ent(tabs, sharp, k)?;
    let npos = pos.len();
    let sz = 26usize.pow(npos as u32);
    let base = if t.tail > NEG as i32 / 2 { t.tail as i64 * SCALE } else { i64::MIN };
    let mut lt = LetTab { npos, v: vec![base; sz] };
    let mut any = base > i64::MIN;
    for (i, (u0, w)) in t.ent.iter().enumerate() {
        let u = match us {
            None => *u0,
            Some(vv) => vv[i],
        };
        if u <= UDEAD {
            continue;
        }
        let mut c = 0i64;
        let mut m = own;
        while m != 0 {
            let j = m.trailing_zeros() as usize;
            m &= m - 1;
            c += lam[(w[j] - 1) as usize];
        }
        let val = u as i64 * SCALE - c;
        let mut ix = 0usize;
        for &p in pos.iter() {
            ix = ix * 26 + (w[p] - 1) as usize;
        }
        if val > lt.v[ix] {
            lt.v[ix] = val;
        }
        any = true;
    }
    if !any { None } else { Some(lt) }
}

/// R_S = max over lettercombinaties van [ R(combi) - SOM_{j in S} theta_j(letter_j) ]
fn lettab_reduce(lt: &LetTab, th: &Vec<&[i64; 26]>, sset: u32) -> i64 {
    let n = lt.npos;
    let mut best = i64::MIN;
    let mut ls = vec![0usize; n];
    let total = lt.v.len();
    for ix in 0..total {
        if lt.v[ix] == i64::MIN {
            continue;
        }
        let mut r = ix;
        for j in (0..n).rev() {
            ls[j] = r % 26;
            r /= 26;
        }
        let mut v = lt.v[ix];
        for j in 0..n {
            if sset >> j & 1 != 0 {
                v -= th[j][ls[j]];
            }
        }
        if v > best {
            best = v;
        }
    }
    let _ = ls;
    best
}

/// kolomwaarden per deelverzameling S van de actieve rijen (verscherping 1 + 2 + 4)
/// out[x][S][m] = (tegels, waarde) ; None = onmogelijk
fn col_values_x(tabs: &HashMap<(Key, u8), Tab>, sharp: &HashMap<Key, SupSrc>, lam: &[i64; 26],
                arows: &[usize], theta: &Vec<Vec<[i64; 26]>>)
                -> Vec<Vec<Vec<Option<(u8, i64)>>>> {
    let maxv: usize = env::var("MAXVLEN").ok().and_then(|s| s.parse().ok()).unwrap_or(15);
    let fullm = full_cols_env();
    let ka = arows.len();
    let nsub = 1usize << ka;
    let mut out = Vec::with_capacity(15);
    for x in 0..15 {
        let must_full = fullm.map_or(false, |f| f >> x & 1 != 0);
        let no_full = fullm.map_or(false, |f| f >> x & 1 == 0);
        // per run: de waarde onder elke deelverzameling van de erin liggende actieve rijen
        let mut rv: Vec<Vec<Option<i64>>> = vec![vec![None; 15 * 15]; nsub];
        for a in 0..15 {
            for b in (a + 1)..15 {
                if !must_full && b - a + 1 > maxv {
                    continue;
                }
                // welke actieve rijen liggen in deze run?
                let js: Vec<usize> = (0..ka).filter(|&j| arows[j] >= a && arows[j] <= b).collect();
                let pos: Vec<usize> = js.iter().map(|&j| arows[j] - a).collect();
                let lt = match run_lettab(tabs, sharp, lam, Key::V(x, a, b), own_v(a, b), &pos) {
                    Some(l) => l,
                    None => continue,
                };
                let th: Vec<&[i64; 26]> = js.iter().map(|&j| &theta[j][x]).collect();
                for s in 0..nsub {
                    // alleen de actieve rijen die IN deze run liggen doen mee
                    let mut sub = 0u32;
                    for (q, &j) in js.iter().enumerate() {
                        if s >> j & 1 != 0 {
                            sub |= 1 << q;
                        }
                    }
                    let v = lettab_reduce(&lt, &th, sub);
                    if v > i64::MIN {
                        rv[s][a * 15 + b] = Some(v);
                    }
                }
            }
        }
        let mut per_s = Vec::with_capacity(nsub);
        for s in 0..nsub {
            let mut v = Vec::with_capacity(1 << 12);
            for m in 0..(1u32 << 12) {
                if (must_full && m != 0xfff) || (no_full && m == 0xfff) {
                    v.push(None);
                    continue;
                }
                let cm = mask12_to_col(m);
                // S mag alleen rijen bevatten die in deze kolom BEZET zijn
                let mut ok = true;
                for j in 0..ka {
                    if s >> j & 1 != 0 && cm >> arows[j] & 1 == 0 {
                        ok = false;
                    }
                }
                if !ok {
                    v.push(None);
                    continue;
                }
                let mut val = 0i64;
                for (a, b) in vruns(cm) {
                    if !must_full && b - a + 1 > maxv {
                        ok = false;
                        break;
                    }
                    match rv[s][a * 15 + b] {
                        Some(r) => val += r,
                        None => {
                            ok = false;
                            break;
                        }
                    }
                }
                v.push(if ok { Some((m.count_ones() as u8, val)) } else { None });
            }
            per_s.push(v);
        }
        out.push(per_s);
    }
    out
}

/// paargewichten met theta erin gebakken (H-kant): voor run r geldt nog steeds
/// SOM over de |r|-1 paren van p >= U(r) + SOM_{cellen met linkerbuur} theta
fn pair_weights_x(tabs: &HashMap<(Key, u8), Tab>, arows: &[usize],
                  theta: &Vec<Vec<[i64; 26]>>) -> Vec<[[i64; 14]; 15]> {
    let ka = arows.len();
    let mut out = vec![[[0i64; 14]; 15]; ka];
    for j in 0..ka {
        let y = arows[j];
        for x0 in 0..15 {
            for x1 in (x0 + 1)..15 {
                let t = match tabs.get(&(Key::H(y, x0, x1), 0u8)) {
                    Some(t) if t.umax > 0 => t,
                    _ => continue,
                };
                let n = x1 - x0 + 1;
                let mut u = i64::MIN;
                if t.tail > NEG as i32 / 2 {
                    let mut v = t.tail as i64 * SCALE;
                    for i in 1..n {
                        v += theta[j][x0 + i].iter().cloned().max().unwrap();
                    }
                    u = v;
                }
                for (uu, w) in t.ent.iter() {
                    let mut v = *uu as i64 * SCALE;
                    for i in 1..n {
                        v += theta[j][x0 + i][(w[i] - 1) as usize];
                    }
                    if v > u {
                        u = v;
                    }
                }
                if u <= 0 {
                    continue;
                }
                let per = ((u as f64) / (x1 - x0) as f64).ceil() as i64;
                for x in x0..x1 {
                    if per > out[j][y][x] {
                        out[j][y][x] = per;
                    }
                }
            }
        }
    }
    out
}

/// kolom-DP met de kruispunt-Lagrange: per overgang 2^|A| deelverzamelingen
struct Gdp3 {
    suf: Vec<Vec<i32>>,
    nt: usize,
    pw: Vec<Vec<[i64; 12]>>, // pw[S][x]
}

fn gdp3_build(colv: &Vec<Vec<Vec<Option<(u8, i64)>>>>, pwr0: &[[i64; 14]; 15],
              pwx: &Vec<[[i64; 14]; 15]>, arows: &[usize], active: u16, nmax: usize) -> Gdp3 {
    let ka = arows.len();
    let nsub = 1usize << ka;
    // index in FREEROWS van elke actieve rij
    let ai: Vec<usize> = arows.iter()
        .map(|y| FREEROWS.iter().position(|z| z == y).unwrap()).collect();
    // paargewichten per deelverzameling S: rijen in S krijgen het theta-gewicht, rijen in
    // A\S en alle niet-actieve rijen krijgen HARD (aangrenzing daar is in deze tak verboden)
    let mut pw: Vec<Vec<[i64; 12]>> = Vec::with_capacity(nsub);
    for s in 0..nsub {
        let mut per_x = Vec::with_capacity(15);
        for x in 0..15 {
            let mut a = [HARD; 12];
            for (q, &j) in ai.iter().enumerate() {
                if s >> q & 1 != 0 {
                    a[j] = if x > 0 { pwx[q][arows[q]][x - 1] } else { HARD };
                }
            }
            per_x.push(a);
        }
        pw.push(per_x);
    }
    let _ = (pwr0, active);
    let nt = nmax + 1;
    let sz = 4096 * nt * 4;
    let mut suf: Vec<Vec<i32>> = vec![Vec::new(); 16];
    suf[15] = vec![0i32; sz];
    for x in (0..15).rev() {
        let mut cur = vec![MINF; sz];
        for t in 0..nt {
            for f in 0..4usize {
                let mut acc = [MINF; 4096];
                for s in 0..nsub {
                    let mut a = [MINF; 4096];
                    for m in 0..4096usize {
                        let nf = match flag_step(x, m as u32, f) {
                            Some(v) => v,
                            None => continue,
                        };
                        if let Some((tiles, val)) = colv[x][s][m] {
                            let tiles = tiles as usize;
                            if tiles <= t {
                                let nv = suf[x + 1][((m * nt) + (t - tiles)) * 4 + nf];
                                if nv > MINF {
                                    a[m] = nv + val as i32;
                                }
                            }
                        }
                    }
                    maxplus_and(&mut a, &pw[s][x]);
                    // deze tak is alleen geldig voor pm die ALLE rijen van S bezet heeft
                    let need: u32 = ai.iter().enumerate()
                        .filter(|(q, _)| s >> q & 1 != 0).map(|(_, &j)| 1u32 << j).sum();
                    for pm in 0..4096usize {
                        if (pm as u32 & need) != need {
                            continue;
                        }
                        if a[pm] > acc[pm] {
                            acc[pm] = a[pm];
                        }
                    }
                }
                for pm in 0..4096usize {
                    cur[((pm * nt) + t) * 4 + f] = acc[pm];
                }
            }
        }
        suf[x] = cur;
    }
    Gdp3 { suf, nt, pw }
}

/// het argmax-woord van een verticale run onder (lambda, theta)
fn arg_run(tabs: &HashMap<(Key, u8), Tab>, sharp: &HashMap<Key, SupSrc>, lam: &[i64; 26],
           k: Key, own: u16, pens: &[(usize, [i64; 26])]) -> Option<[u8; 15]> {
    let (t, us) = sharp_ent(tabs, sharp, k)?;
    let mut best = i64::MIN;
    let mut arg = None;
    for (i, (u0, w)) in t.ent.iter().enumerate() {
        let u = match us {
            None => *u0,
            Some(v) => v[i],
        };
        if u <= UDEAD {
            continue;
        }
        let mut v = u as i64 * SCALE;
        let mut m = own;
        while m != 0 {
            let j = m.trailing_zeros() as usize;
            m &= m - 1;
            v -= lam[(w[j] - 1) as usize];
        }
        for (p, th) in pens.iter() {
            v -= th[(w[*p] - 1) as usize];
        }
        if v > best {
            best = v;
            arg = Some(*w);
        }
    }
    arg
}

/// het argmax-woord van een horizontale run onder theta (H-kant: theta wordt OPGETELD)
fn arg_hrun(tabs: &HashMap<(Key, u8), Tab>, y: usize, x0: usize, x1: usize,
            th: &Vec<[i64; 26]>) -> Option<[u8; 15]> {
    let t = tabs.get(&(Key::H(y, x0, x1), 0u8))?;
    let n = x1 - x0 + 1;
    let mut best = i64::MIN;
    let mut arg = None;
    for (u, w) in t.ent.iter() {
        let mut v = *u as i64 * SCALE;
        for i in 1..n {
            v += th[x0 + i][(w[i] - 1) as usize];
        }
        if v > best {
            best = v;
            arg = Some(*w);
        }
    }
    arg
}

/// de maximaliserende bezetting uit een Gdp3 terugrekenen
fn recon3(g: &Gdp3, colv: &Vec<Vec<Vec<Option<(u8, i64)>>>>, arows: &[usize], nmax: usize)
          -> Option<[u16; 15]> {
    let ka = arows.len();
    let nsub = 1usize << ka;
    let ai: Vec<usize> = arows.iter()
        .map(|y| FREEROWS.iter().position(|z| z == y).unwrap()).collect();
    let nt = g.nt;
    let mut cols = [0u16; 15];
    let (mut pm, mut t, mut f) = (0u32, nmax, 0usize);
    for x in 0..15 {
        let tgt = g.suf[x][((pm as usize * nt) + t) * 4 + f];
        let mut hit = false;
        'outer: for s in 0..nsub {
            let need: u32 = ai.iter().enumerate()
                .filter(|(q, _)| s >> q & 1 != 0).map(|(_, &j)| 1u32 << j).sum();
            if (pm & need) != need {
                continue;
            }
            for m in 0..4096usize {
                let (tiles, val) = match colv[x][s][m] {
                    Some(v) => v,
                    None => continue,
                };
                let tiles = tiles as usize;
                if tiles > t {
                    continue;
                }
                let nf = match flag_step(x, m as u32, f) {
                    Some(v) => v,
                    None => continue,
                };
                let nv = g.suf[x + 1][((m * nt) + (t - tiles)) * 4 + nf];
                if nv <= MINF {
                    continue;
                }
                let ps = pairsum(&g.pw[s][x], pm, m as u32);
                if nv as i64 + val + ps == tgt as i64 {
                    cols[x] = mask12_to_col(m as u32);
                    pm = m as u32;
                    t -= tiles;
                    f = nf;
                    hit = true;
                    break 'outer;
                }
            }
        }
        if !hit {
            return None;
        }
    }
    Some(cols)
}

fn cmd_stratx(dir: &str) {
    let d = Arc::new(load(dir));
    let tabs = Arc::new(read_tabs(&format!("{}/tables.bin", dir)));
    let at = read_anchtab(dir);
    let mut lam = read_lam();
    let nmax: usize = env::var("NFREE").ok().and_then(|s| s.parse().ok()).unwrap_or(56);
    let active: u16 = env::var("ACT").ok().and_then(|s| u16::from_str_radix(&s, 2).ok())
        .unwrap_or(0);
    let iters: usize = env::var("ITERS").ok().and_then(|s| s.parse().ok()).unwrap_or(120);
    let step: f64 = env::var("STEP").ok().and_then(|s| s.parse().ok()).unwrap_or(40.0);
    let xstep: f64 = env::var("XSTEP").ok().and_then(|s| s.parse().ok()).unwrap_or(64.0);
    let target: i64 = env::var("TARGET").ok().and_then(|s| s.parse().ok()).unwrap_or(4819);
    let arows: Vec<usize> = FREEROWS.iter().enumerate()
        .filter(|(i, _)| active >> i & 1 != 0).map(|(_, &y)| y).collect();
    assert!(arows.len() <= 3, "kruispunt-DP is voor |A| <= 3 gebouwd");
    calib_assert(dir, &tabs, &at, &d, &lam);
    let t0 = std::time::Instant::now();
    let sharp = build_sharp_v(&d, &tabs, suprows_of(active));
    calib_assert_sharp(dir, &tabs, &sharp, &at, &d, &lam, active);
    let anch = at.maxcap();
    let pwr0 = pair_weights(&tabs);
    let ka = arows.len();
    let mut theta: Vec<Vec<[i64; 26]>> = vec![vec![[0i64; 26]; 15]; ka];
    let mut best = i64::MAX;
    let mut base = i64::MAX;
    for it in 0..iters {
        let colv = col_values_x(&tabs, &sharp, &lam, &arows, &theta);
        let pwx = pair_weights_x(&tabs, &arows, &theta);
        let konst = lam_const(&d, &lam);
        let g = gdp3_build(&colv, &pwr0, &pwx, &arows, active, nmax);
        let bv = g.suf[0][(0 * g.nt + nmax) * 4 + 0] as i64;
        let ub = anch + (bv + konst).div_euclid(SCALE);
        if it == 0 {
            base = ub;
        }
        if ub < best {
            best = ub;
        }
        let cols = match recon3(&g, &colv, &arows, nmax) {
            Some(c) => c,
            None => {
                eprintln!("  it {} ub {} (reconstructie mislukt)", it, ub);
                break;
            }
        };
        // ---- subgradienten
        let mut use_ = [0i64; 26];
        let (vs, hs) = occ_lines(&cols);
        // welke cellen zijn 'afgedwongen': bezet, in een actieve rij, met bezette linkerbuur
        let enforced = |x: usize, y: usize| -> bool {
            x > 0 && full_col(cols[x]) >> y & 1 != 0 && full_col(cols[x - 1]) >> y & 1 != 0
        };
        let mut vlet: HashMap<(usize, usize), usize> = HashMap::new();
        for (k, _v) in vs.iter() {
            if let Key::V(x, a, b) = k {
                let pens: Vec<(usize, [i64; 26])> = (0..ka)
                    .filter(|&j| arows[j] >= *a && arows[j] <= *b && enforced(*x, arows[j]))
                    .map(|j| (arows[j] - *a, theta[j][*x])).collect();
                if let Some(w) = arg_run(&tabs, &sharp, &lam, *k, own_v(*a, *b), &pens) {
                    let mut m = own_v(*a, *b);
                    while m != 0 {
                        let i = m.trailing_zeros() as usize;
                        m &= m - 1;
                        use_[(w[i] - 1) as usize] += 1;
                    }
                    for j in 0..ka {
                        if arows[j] >= *a && arows[j] <= *b {
                            vlet.insert((*x, arows[j]), (w[arows[j] - *a] - 1) as usize);
                        }
                    }
                }
            }
        }
        for (k, _v) in hs.iter() {
            if let Key::H(y, x0, x1) = k {
                let j = match arows.iter().position(|z| z == y) {
                    Some(j) => j,
                    None => continue,
                };
                if let Some(w) = arg_hrun(&tabs, *y, *x0, *x1, &theta[j]) {
                    let s = (xstep / ((it as f64 / 25.0) + 1.0).sqrt()) as i64;
                    for i in 1..=(*x1 - *x0) {
                        let x = *x0 + i;
                        if !enforced(x, *y) {
                            continue;
                        }
                        let ch = (w[i] - 1) as usize;
                        let cv = match vlet.get(&(x, *y)) {
                            Some(v) => *v,
                            None => continue,
                        };
                        if cv == ch {
                            continue;
                        }
                        theta[j][x][cv] += s;
                        theta[j][x][ch] -= s;
                        // NORMALISATIE: min_k theta = 0 (vrij voor echte kruispunten, en
                        // noodzakelijk voor de soundness bij niet-kruispunten)
                        let mn = *theta[j][x].iter().min().unwrap();
                        for kk in 0..26 {
                            theta[j][x][kk] -= mn;
                        }
                    }
                }
            }
        }
        let mut mxi = 0usize;
        for i in 0..26 {
            if lam[i] > lam[mxi] {
                mxi = i;
            }
        }
        let sstep = step / ((it as f64 / 10.0) + 1.0).sqrt();
        for i in 0..26 {
            let mut gr = d.rest[i + 1] - use_[i];
            if i == mxi {
                gr += d.nblank;
            }
            let nv = lam[i] as f64 - sstep * gr as f64;
            lam[i] = if nv < 0.0 { 0 } else { nv.round() as i64 };
        }
        if it % 10 == 0 {
            eprintln!("  it {:3}  ub {}  best {}  ({:.0}s)", it, ub, best,
                      t0.elapsed().as_secs_f64());
        }
    }
    println!("STRATUM(v3, +kruispunt-Lagrange) ACT={:012b} MAXVLEN={} FULL={} -> \
              BOVENGRENS {}  (zonder theta {}, winst {})  ({})",
             active, env::var("MAXVLEN").unwrap_or_else(|_| "15".into()),
             env::var("FULL").unwrap_or_else(|_| "-".into()), best, base, base - best,
             if best < target { "WEERLEGD" } else { "open" });
    println!("  ({:.0}s)", t0.elapsed().as_secs_f64());
}

/// paargewichten voor de SLOTTELLING: SOM over de |r|-1 paren van r >= floor(|r|/7)
fn pair_slots() -> [[i64; 14]; 15] {
    let mut p = [[0i64; 14]; 15];
    for y in 0..15 {
        if ANCHOR_ROWS.contains(&y) {
            continue;
        }
        for x0 in 0..15 {
            for x1 in (x0 + 1)..15 {
                let n = x1 - x0 + 1;
                let per = ((((n / 7) as i64 * SCALE) as f64) / (x1 - x0) as f64).ceil() as i64;
                for x in x0..x1 {
                    if per > p[y][x] {
                        p[y][x] = per;
                    }
                }
            }
        }
    }
    p
}

/// hoeveel BINGO-SLOTS kan dit stratum maximaal hebben?  (verscherping 3, meting)
fn cmd_slots(dir: &str) {
    let d = Arc::new(load(dir));
    let tabs = Arc::new(read_tabs(&format!("{}/tables.bin", dir)));
    let lam = read_lam();
    let nmax: usize = env::var("NFREE").ok().and_then(|s| s.parse().ok()).unwrap_or(56);
    let active: u16 = env::var("ACT").ok().and_then(|s| u16::from_str_radix(&s, 2).ok())
        .unwrap_or(0);
    let sharp = build_sharp_v(&d, &tabs, suprows_of(active));
    let colv = col_values_sharp(&tabs, &sharp, &lam);
    let slots = col_bingoslots(&colv);
    let pwr = pair_slots();
    let g = gdp2_build(&slots, &pwr, active, nmax);
    let bv = g.suf[0][(0 * g.nt + nmax) * 4 + 0] as i64;
    let free = bv.div_euclid(SCALE);
    // LEMMA 4 (bingobudget van de vrije lijnen).
    //  (a) Er liggen hoogstens 101 tegels op het bord (zak 100 + 2 blanco, de tegenstander
    //      houdt >= 1 tegel vast).  Elke bingo legt precies 7 tegels en zetten zijn onderling
    //      disjunct, dus SOM over ALLE lijnen L van b_L <= floor(101/7) = 14.
    //  (b) De maskerregel zegt dat de 7 maskercellen van elke ankerrij samen de LAATSTE groep
    //      van die rij vormen: een zet die precies die 7 cellen legt.  Een zet legt al zijn
    //      tegels op een lijn, dus die zet legt precies 7 tegels -- een bingo.  De drie
    //      slotzetten zijn dus DRIE bingo's, en die horen bij de ankerrijen.
    //  => SOM over de VRIJE lijnen van b_L <= 14 - 3 = 11.
    // b_L <= floor(len(L)/7) per lijn, en het maximum daarvan over het stratum is `free`.
    println!("BINGOSLOTS ACT={:012b} MAXVLEN={} FULL={}: vrije lijnen <= {} bingo's   \
              (budget vrije lijnen = 14 - 3 = 11 -> {})",
             active, env::var("MAXVLEN").unwrap_or_else(|_| "15".into()),
             env::var("FULL").unwrap_or_else(|_| "-".into()), free,
             if free <= 11 { "BIJT NOOIT, verscherping 3 is hier bewijsbaar 0 waard" }
             else { "kan bijten" });
}

/// welke kolommen KUNNEN vol zijn (verscherping 4)?  Voor elke kolom de volle-run-tabel.
fn cmd_framediag(dir: &str) {
    let d = load(dir);
    let tabs = read_tabs(&format!("{}/tables.bin", dir));
    println!("VOLLE KOLOMMEN (verticale run [0,14], lengte 15):");
    let mut cands = Vec::new();
    for x in 0..15 {
        let pat: String = (0..3).map(|k| (b'a' + d.trip[k][x] - 1) as char).collect();
        let t0 = tabs.get(&(Key::V(x, 0, 14), 0u8));
        let t1 = tabs.get(&(Key::V(x, 0, 14), 1u8));
        let (nw, u0) = match t0 {
            Some(t) => (t.nw, t.umax),
            None => (0, NEG as i32),
        };
        let u1 = t1.map(|t| t.umax).unwrap_or(NEG as i32);
        let f = |v: i32| if v > NEG as i32 / 2 { v.to_string() } else { "-".into() };
        println!("  kolom {:2}  patroon {}..{}..{}  zak-bouwbare woorden {:5}  \
                  Umax(vol) {:>6}  Umax(ankersteun) {:>6}",
                 x, &pat[0..1], &pat[1..2], &pat[2..3], nw, f(u0), f(u1));
        if nw > 0 && u1 > NEG as i32 / 2 {
            cands.push(x);
        }
    }
    println!("  -> kolommen die vol KUNNEN zijn: {:?}", cands);
    println!("  -> FRAME-deelstrata: alle 2^{} deelverzamelingen daarvan", cands.len());
}

// ------------------------------------------------------------------ strat: stratumgrens v2
fn cmd_strat(dir: &str) {
    let d = Arc::new(load(dir));
    let tabs = Arc::new(read_tabs(&format!("{}/tables.bin", dir)));
    let at = read_anchtab(dir);
    let mut lam = read_lam();
    let nmax: usize = env::var("NFREE").ok().and_then(|s| s.parse().ok()).unwrap_or(56);
    let active: u16 = env::var("ACT").ok().and_then(|s| u16::from_str_radix(&s, 2).ok())
        .unwrap_or(0);
    let iters: usize = env::var("ITERS").ok().and_then(|s| s.parse().ok()).unwrap_or(60);
    let step: f64 = env::var("STEP").ok().and_then(|s| s.parse().ok()).unwrap_or(40.0);
    let target: i64 = env::var("TARGET").ok().and_then(|s| s.parse().ok()).unwrap_or(4819);
    calib_assert(dir, &tabs, &at, &d, &lam);
    let t0 = std::time::Instant::now();
    let sharp = build_sharp_v(&d, &tabs, suprows_of(active));
    let nv0 = sharp.values().filter(|s| matches!(s, SupSrc::Var0)).count();
    let nv1 = sharp.values().filter(|s| matches!(s, SupSrc::Var1)).count();
    let nc = sharp.values().filter(|s| matches!(s, SupSrc::Cust(_))).count();
    let nd = sharp.values().filter(|s| matches!(s, SupSrc::Dead)).count();
    eprintln!("steunmaskers ACT={:012b}: {} vol / {} anker / {} scherp-herrekend / {} dood \
               ({:.0}s)", active, nv0, nv1, nc, nd, t0.elapsed().as_secs_f64());
    calib_assert_sharp(dir, &tabs, &sharp, &at, &d, &lam, active);
    let anch = at.maxcap();
    let pwr = pair_weights(&tabs);
    let mut best = i64::MAX;
    let mut bestlam = lam;
    for it in 0..iters {
        let colv = col_values_sharp(&tabs, &sharp, &lam);
        let konst = lam_const(&d, &lam);
        let g = gdp2_build(&colv, &pwr, active, nmax);
        let bv = g.suf[0][(0 * nt_of(&g) + nmax) * 4 + 0] as i64;
        let ub = anch + (bv + konst).div_euclid(SCALE);
        if ub < best {
            best = ub;
            bestlam = lam;
        }
        let mut c = Surv2 { g: &g, colv: &colv, active, need: bv, found: 0, cap: 1,
                            cols: [0u16; 15], out: Vec::new() };
        dfs2(&mut c, 0, 0, nmax, 0, 0);
        if c.out.is_empty() {
            eprintln!("  it {} ub {} (geen bezetting gevonden)", it, ub);
            break;
        }
        let cols = c.out[0];
        let mut use_ = [0i64; 26];
        let (vs, hs) = occ_lines(&cols);
        for (k, _var) in vs {
            if let Key::V(_, a, b) = k {
                let own = own_v(a, b);
                let src = sharp.get(&k);
                let tk = match src {
                    Some(SupSrc::Var1) => tabs.get(&(k, 1u8)),
                    _ => tabs.get(&(k, 0u8)),
                };
                if let Some(t) = tk {
                    if let Some((w, ow)) = r_arg_own(t, &lam, own) {
                        let mut m = ow;
                        while m != 0 {
                            let i = m.trailing_zeros() as usize;
                            m &= m - 1;
                            use_[(w[i] - 1) as usize] += 1;
                        }
                    }
                }
            }
        }
        for (k, _var) in hs {
            if let (Key::H(y, x0, x1), Some(t)) = (k, tabs.get(&(k, 0u8))) {
                let ow = own_h(&cols, y, x0, x1);
                if let Some((w, own)) = r_arg_own(t, &lam, ow) {
                    let mut m = own;
                    while m != 0 {
                        let i = m.trailing_zeros() as usize;
                        m &= m - 1;
                        use_[(w[i] - 1) as usize] += 1;
                    }
                }
            }
        }
        let mut mxi = 0usize;
        for i in 0..26 {
            if lam[i] > lam[mxi] {
                mxi = i;
            }
        }
        let sstep = step / ((it as f64 / 10.0) + 1.0).sqrt();
        for i in 0..26 {
            let mut gr = d.rest[i + 1] - use_[i];
            if i == mxi {
                gr += d.nblank;
            }
            let nv = lam[i] as f64 - sstep * gr as f64;
            lam[i] = if nv < 0.0 { 0 } else { nv.round() as i64 };
        }
        eprintln!("  it {:3}  ub {}  best {}", it, ub, best);
    }
    if let Ok(p) = env::var("BESTOUT") {
        let colv = col_values_sharp(&tabs, &sharp, &bestlam);
        let konst = lam_const(&d, &bestlam);
        let g = gdp2_build(&colv, &pwr, active, nmax);
        let bv = g.suf[0][(0 * g.nt + nmax) * 4 + 0] as i64;
        let mut c = Surv2 { g: &g, colv: &colv, active, need: bv, found: 0, cap: 1,
                            cols: [0u16; 15], out: Vec::new() };
        dfs2(&mut c, 0, 0, nmax, 0, 0);
        let mut fo = BufWriter::new(File::create(&p).unwrap());
        for cols in c.out.iter() {
            write!(fo, "argmax_A{:012b}", active).unwrap();
            for x in 0..15 {
                write!(fo, " {}", cols[x] & !((1 << 0) | (1 << 7) | (1 << 14))).unwrap();
            }
            writeln!(fo).unwrap();
            // per-lijn-uitsplitsing van de DP-waarde: hoeveel zit er in de PAARGEWICHTEN?
            let (vs, hs) = occ_lines(cols);
            let mut sv = 0i64;
            for (k, _v) in vs.iter() {
                if let Key::V(_, a, b) = k {
                    sv += r_sharp(&tabs, &sharp, &bestlam, *k, own_v(*a, *b)).unwrap_or(0);
                }
            }
            let mut sh = 0i64;
            for (k, _v) in hs.iter() {
                if let Key::H(y, x0, x1) = k {
                    if let Some(t) = tabs.get(&(*k, 0u8)) {
                        sh += r_lambda_own(t, &bestlam, own_h(cols, *y, *x0, *x1));
                    }
                }
            }
            let mut nfree = 0usize;
            for x in 0..15 {
                nfree += (cols[x] & !((1 << 0) | (1 << 7) | (1 << 14))).count_ones() as usize;
            }
            eprintln!("ARGMAX {} vrije cellen | DP-waarde {} | SOM_V {} | SOM_H(echte runs) {} \
                       | PAARSURPLUS {}",
                      nfree, anch + (bv + konst).div_euclid(SCALE),
                      (sv + konst).div_euclid(SCALE), sh / SCALE, (bv - sv - sh) / SCALE);
            eprintln!("ARGMAX exacte per-lijn-grens = {}",
                      anch + (sv + sh + konst).div_euclid(SCALE));
        }
    }
    let mut ncnt = String::from("-");
    if env::var("COUNT").is_ok() {
        let colv = col_values_sharp(&tabs, &sharp, &bestlam);
        ncnt = format!("{:.4e}", count_family(&colv, active, nmax));
    }
    println!("LAM={}", bestlam.iter().map(|v| v.to_string()).collect::<Vec<_>>().join(","));
    println!("STRATUM(v2) ACT={:012b} MAXVLEN={} FULL={} -> BOVENGRENS {}  ({})  bezettingen {}",
             active, env::var("MAXVLEN").unwrap_or_else(|_| "15".into()),
             env::var("FULL").unwrap_or_else(|_| "-".into()), best,
             if best < target { "WEERLEGD" } else { "open" }, ncnt);
    println!("  ({:.0}s)", t0.elapsed().as_secs_f64());
}

#[inline]
fn nt_of(g: &Gdp2) -> usize {
    g.nt
}

// ==================================================================================
// VERSCHERPING 2 -- KRUISPUNTCONSISTENTIE ALS LAGRANGE-TERM
// ==================================================================================
//
// De per-lijn-ontbinding laat elke lijn onafhankelijk haar beste woord kiezen.  In een echt
// bord draagt een cel die op EEN verticale en EEN horizontale run ligt in beide woorden
// DEZELFDE letter.  Dat is de enige koppeling die de CP-SAT-narekening extra heeft, en ze is
// duur: op de recordbezetting 4993 -> 4867 (126 punten), en op de argmax-bezetting van de
// stratum-DP zelfs van 5104 naar INFEASIBLE.
//
// LAGRANGE.  Zij X de verzameling KRUISPUNTEN: cellen die op een verticale run (>=2) EN op een
// horizontale run (>=2) liggen.  Voor c in X noteren we V(c) resp. H(c) voor die twee lijnen.
// De consistentie-eis is  letter_{V(c)}(c) = letter_{H(c)}(c).  Voor WILLEKEURIGE reele
// getallen theta(c, k) (k = letter) geldt daarom voor elk LEGAAL bord
//
//     0  =  SOM_{c in X} [ theta(c, letter_H(c)) - theta(c, letter_V(c)) ] ,
//
// en dus
//
//     SOM_L U_L  =  SOM_L U_L + 0
//                <= SOM_{V-lijnen} max_W [ U_V(W) - lam.cnt - SOM_{c in V n X} theta(c,W_c) ]
//                 + SOM_{H-lijnen} max_W [ U_H(W) - lam.cnt + SOM_{c in H n X} theta(c,W_c) ].
//
// Elke theta geeft dus een geldige bovengrens; we minimaliseren met subgradient-afdaling.
// De subgradient in theta(c,k) is  -1{k = letter_V gekozen} + 1{k = letter_H gekozen}, dus de
// afdalingsstap verhoogt theta(c, letter_V) en verlaagt theta(c, letter_H): precies zolang de
// twee lijnen het oneens zijn blijft de prijs oplopen.
//
// STAARTGRENS.  Voor de bij het afkappen weggelaten woorden geldt nog steeds U <= tail, maar de
// theta-term is voor hen onbekend; daarom wordt de staartgrens verhoogd met
// SOM_{c in L n X} max_k (-/+ theta(c,k)) -- de gunstigste letter per kruispunt.  Dat is een
// verruiming en dus sound.  (In de praktijk is de staart bij de meeste lijnen dood: dan zijn
// ALLE woorden bewaard en speelt de correctie niet.)
//
// SOUNDNESS: de identiteit hierboven geldt voor elk legaal bord en elke theta; de DP-waarden
// U_L blijven per-lijn-bovengrenzen.  De ijking (calib_assert_x) eist dat de recordbezetting
// ook met theta nog >= 4793 uitkomt.

struct XLine {
    key: Key,
    ent: Arc<Vec<(i32, [u8; 15])>>, // (U met het EXACTE steunmasker, woord)
    tail: i32,                 // staartgrens uit de variant-0-tabel (NEG = dood)
    n: usize,
    own: u16,                  // posities waarvan deze lijn de zaktegel claimt
    xp: Vec<i32>,              // per positie de kruispuntindex, -1 = geen kruispunt
    isv: bool,                 // verticaal (theta aftrekken) of horizontaal (optellen)
}

impl XLine {
    /// waarde van deze lijn onder (lambda, theta) + het gekozen woord
    fn value(&self, lam: &[i64; 26], th: &Vec<[i64; 26]>) -> (i64, Option<[u8; 15]>) {
        let sgn: i64 = if self.isv { -1 } else { 1 };
        let mut best = i64::MIN;
        let mut arg = None;
        if self.tail > NEG as i32 / 2 {
            let mut t = self.tail as i64 * SCALE;
            for i in 0..self.n {
                if self.xp[i] >= 0 {
                    let c = &th[self.xp[i] as usize];
                    let mut mx = i64::MIN;
                    for k in 0..26 {
                        let v = sgn * c[k];
                        if v > mx {
                            mx = v;
                        }
                    }
                    t += mx;
                }
            }
            best = t;
        }
        for (u, w) in self.ent.iter() {
            if *u <= UDEAD {
                continue;
            }
            let mut v = *u as i64 * SCALE;
            let mut m = self.own;
            while m != 0 {
                let i = m.trailing_zeros() as usize;
                m &= m - 1;
                v -= lam[(w[i] - 1) as usize];
            }
            for i in 0..self.n {
                if self.xp[i] >= 0 {
                    v += sgn * th[self.xp[i] as usize][(w[i] - 1) as usize];
                }
            }
            if v > best {
                best = v;
                arg = Some(*w);
            }
        }
        (best, arg)
    }
}

/// alle lijnen van een bezetting klaarzetten met hun EXACTE steunmasker en kruispuntindices
fn xlines_of(d: &Data, dp: &mut Dp, tabs: &HashMap<(Key, u8), Tab>, cols: &[u16; 15],
             cache: &mut HashMap<(Key, u16), Option<Arc<Vec<(i32, [u8; 15])>>>>)
             -> Option<(Vec<XLine>, usize)> {
    let (vs, hs) = occ_lines(cols);
    // kruispunten nummeren: cellen die op een V-run EN een H-run liggen
    let mut xidx: HashMap<(usize, usize), usize> = HashMap::new();
    let mut vcells: std::collections::HashSet<(usize, usize)> = Default::default();
    for (k, _v) in vs.iter() {
        if let Key::V(x, a, b) = k {
            for y in *a..=*b {
                vcells.insert((*x, y));
            }
        }
    }
    for (k, _v) in hs.iter() {
        if let Key::H(y, x0, x1) = k {
            for x in *x0..=*x1 {
                if vcells.contains(&(x, *y)) && !ANCHOR_ROWS.contains(y) {
                    let n = xidx.len();
                    xidx.entry((x, *y)).or_insert(n);
                }
            }
        }
    }
    let nx = xidx.len();
    let mut out = Vec::new();
    for (k, _v) in vs.into_iter().chain(hs.into_iter()) {
        let (sup, own, cells): (u16, u16, Vec<(usize, usize)>) = match k {
            Key::V(x, a, b) => (sup_mask_v(cols, x, a, b), own_v(a, b),
                                (a..=b).map(|y| (x, y)).collect()),
            Key::H(y, x0, x1) => (sup_mask_h(cols, y, x0, x1), own_h(cols, y, x0, x1),
                                  (x0..=x1).map(|x| (x, y)).collect()),
        };
        let t = match tabs.get(&(k, 0u8)) {
            Some(t) if t.umax > NEG as i32 / 2 => t,
            _ => return None,
        };
        let n = cells.len();
        let ent = match cache.get(&(k, sup)) {
            Some(v) => v.clone()?,
            None => {
                let mut prof = prof_of(d, k, 0);
                prof.sup = sup;
                let mut ent: Vec<(i32, [u8; 15])> = Vec::with_capacity(t.ent.len());
                let mut valv = vec![0i64; n];
                for (_u, w) in t.ent.iter() {
                    for i in 0..n {
                        valv[i] = d.val[w[i] as usize];
                    }
                    let isw = build_isw(d, &w[..n]);
                    let u = maxg(dp, &prof, &valv, &isw);
                    if u <= NEG {
                        continue;
                    }
                    ent.push((u as i32, *w));
                }
                let r = if ent.is_empty() && t.tail <= NEG as i32 / 2 {
                    None
                } else {
                    Some(Arc::new(ent))
                };
                cache.insert((k, sup), r.clone());
                r?
            }
        };
        let xp: Vec<i32> = cells.iter()
            .map(|c| xidx.get(c).map(|v| *v as i32).unwrap_or(-1)).collect();
        let isv = matches!(k, Key::V(..));
        out.push(XLine { key: k, ent, tail: t.tail, n, own, xp, isv });
    }
    Some((out, nx))
}

/// bovengrens van een bezetting met kruispunt-Lagrange (verscherping 2)
fn xbound(lines: &Vec<XLine>, nx: usize, d: &Data, at: &AnchTab, cols: &[u16; 15],
          lam0: &[i64; 26], iters: usize, step: f64) -> (i64, i64) {
    let anch = at.cap(cols);
    let mut lam = *lam0;
    let mut th: Vec<[i64; 26]> = vec![[0i64; 26]; nx];
    let mut best = i64::MAX;
    let mut base = i64::MAX;
    for it in 0..iters {
        let mut tot = 0i64;
        let mut use_ = [0i64; 26];
        let mut pick: Vec<[i32; 2]> = vec![[-1, -1]; nx]; // [V-letter, H-letter] per kruispunt
        for l in lines.iter() {
            let (v, arg) = l.value(&lam, &th);
            tot += v;
            if let Some(w) = arg {
                let mut m = l.own;
                while m != 0 {
                    let i = m.trailing_zeros() as usize;
                    m &= m - 1;
                    use_[(w[i] - 1) as usize] += 1;
                }
                for i in 0..l.n {
                    if l.xp[i] >= 0 {
                        pick[l.xp[i] as usize][if l.isv { 0 } else { 1 }] = (w[i] - 1) as i32;
                    }
                }
            }
        }
        let ub = anch + (tot + lam_const(d, &lam)).div_euclid(SCALE);
        if it == 0 {
            base = ub;
        }
        if ub < best {
            best = ub;
        }
        // subgradient: theta omhoog bij de V-letter, omlaag bij de H-letter
        let s = (step / ((it as f64 / 20.0) + 1.0).sqrt()) as i64;
        for c in 0..nx {
            let (cv, ch) = (pick[c][0], pick[c][1]);
            if cv < 0 || ch < 0 || cv == ch {
                continue;
            }
            th[c][cv as usize] += s;
            th[c][ch as usize] -= s;
            // normaliseren (een constante verschuiving per kruispunt valt weg tegen elkaar,
            // maar houdt de staartcorrectie klein)
            let mn = *th[c].iter().min().unwrap();
            let mx = *th[c].iter().max().unwrap();
            let mid = (mn + mx) / 2;
            for k in 0..26 {
                th[c][k] -= mid;
            }
        }
        // lambda-subgradient (zak) blijft meelopen
        let mut mxi = 0usize;
        for i in 0..26 {
            if lam[i] > lam[mxi] {
                mxi = i;
            }
        }
        let ls = 8.0 / ((it as f64 / 40.0) + 1.0).sqrt();
        for i in 0..26 {
            let mut g = d.rest[i + 1] - use_[i];
            if i == mxi {
                g += d.nblank;
            }
            let nv = lam[i] as f64 - ls * g as f64;
            lam[i] = if nv < 0.0 { 0 } else { nv.round() as i64 };
        }
    }
    (base, best)
}

fn cmd_xsharp(dir: &str, occfile: &str) {
    let d = load(dir);
    let tabs = read_tabs(&format!("{}/tables.bin", dir));
    let at = read_anchtab(dir);
    let lam = read_lam();
    let target: i64 = env::var("TARGET").ok().and_then(|s| s.parse().ok()).unwrap_or(4819);
    let iters: usize = env::var("XITERS").ok().and_then(|s| s.parse().ok()).unwrap_or(400);
    let step: f64 = env::var("XSTEP").ok().and_then(|s| s.parse().ok()).unwrap_or(96.0);
    calib_assert(dir, &tabs, &at, &d, &lam);
    let mut dp = Dp::new();
    let mut cache: HashMap<(Key, u16), Option<Arc<Vec<(i32, [u8; 15])>>>> = HashMap::new();
    let t0 = std::time::Instant::now();
    for (name, cols) in read_occs(occfile) {
        match xlines_of(&d, &mut dp, &tabs, &cols, &mut cache) {
            None => println!("{}  lexicaal lege lijn -> WEERLEGD", name),
            Some((lines, nx)) => {
                let (base, best) = xbound(&lines, nx, &d, &at, &cols, &lam, iters, step);
                println!("{}  kruispunten {:3}  scherp(zonder theta) {}  MET KRUISPUNT-LAGRANGE \
                          {}   winst {}   ({})",
                         name, nx, base, best, base - best,
                         if best < target { "WEERLEGD" } else { "overleeft" });
            }
        }
    }
    eprintln!("({:.0}s)", t0.elapsed().as_secs_f64());
}

// ------------------------------------------------------------------ dumptab
/// Schrijft voor alle lijnen die in de gegeven bezettingen voorkomen de VOLLEDIGE
/// (woord, U)-tabel weg, zodat de Python-zijde er een zak- en kruispuntbewust CP-SAT-model
/// van kan maken (de scherpste zetvolgorde-VRIJE toets die we hebben).
fn cmd_dumptab(dir: &str, occfile: &str) {
    let tabs = read_tabs(&format!("{}/tables.bin", dir));
    let occs = read_occs(occfile);
    let mut need: Vec<(Key, u8)> = Vec::new();
    for (_n, cols) in occs.iter() {
        let (vs, hs) = occ_lines(cols);
        for kv in vs.into_iter().chain(hs.into_iter()) {
            if !need.contains(&kv) {
                need.push(kv);
            }
        }
    }
    let out = env::var("TABOUT").unwrap_or_else(|_| format!("{}/tabdump.txt", dir));
    let mut f = BufWriter::new(File::create(&out).unwrap());
    for (k, var) in need.iter() {
        let (tag, a, b, c) = match *k {
            Key::V(x, a, b) => ("V", x, a, b),
            Key::H(y, a, b) => ("H", y, a, b),
        };
        let t = match tabs.get(&(*k, *var)) {
            Some(t) => t,
            None => continue,
        };
        writeln!(f, "# {} {} {} {} {} {} {}", tag, a, b, c, var, t.ent.len(), t.umax).unwrap();
        for (u, w) in t.ent.iter() {
            write!(f, "{}", u).unwrap();
            for i in 0..t.n as usize {
                write!(f, " {}", w[i]).unwrap();
            }
            writeln!(f).unwrap();
        }
    }
    eprintln!("{} lijntabellen -> {}", need.len(), out);
}

// ------------------------------------------------------------------ coldiag
fn cmd_coldiag(dir: &str) {
    let tabs = read_tabs(&format!("{}/tables.bin", dir));
    let lam = read_lam();
    let colv = col_values(&tabs, &lam, env::var("VAR").ok().and_then(|s| s.parse().ok()).unwrap_or(0));
    for x in 0..15 {
        let mut best = vec![(i64::MIN, 0usize); 13];
        for m in 0..4096usize {
            if let Some((t, v)) = colv[x][m] {
                if v > best[t as usize].0 {
                    best[t as usize] = (v, m);
                }
            }
        }
        print!("kolom {:2}:", x);
        for t in 0..13 {
            if best[t].0 > i64::MIN {
                print!("  {}t={:.1}", t, best[t].0 as f64 / SCALE as f64);
            }
        }
        println!();
        let (v, m) = best[12];
        if v > i64::MIN {
            eprintln!("   x={} beste 12-tegelmasker {:012b} -> {:.1}", x, m, v as f64 / SCALE as f64);
        }
        // beste waarde per tegel
        let mut bt = (0.0f64, 0usize, 0usize);
        for t in 1..13 {
            if best[t].0 > i64::MIN {
                let r = best[t].0 as f64 / SCALE as f64 / t as f64;
                if r > bt.0 { bt = (r, t, best[t].1); }
            }
        }
        eprintln!("   x={} beste rendement {:.2}/tegel bij {} tegels, masker {:012b}", x, bt.0, bt.1, bt.2);
    }
}

// ------------------------------------------------------------------ main
fn main() {
    let args: Vec<String> = env::args().collect();
    let dir = env::var("REFDIR")
        .unwrap_or_else(|_| "/home/bob/programming/scrabble4/experiments/results/refute".into());
    let cmd = args.get(1).map(|s| s.as_str()).unwrap_or("help");
    match cmd {
        "tables" => cmd_tables(&dir),
        "eval" => cmd_eval(&dir, &args[2]),
        "lamopt" => cmd_lamopt(&dir, &args[2]),
        "gmax" => cmd_gmax(&dir),
        "sweep" => cmd_sweep(&dir),
        "lamdp" => cmd_lamdp(&dir),
        "strat" => cmd_strat(&dir),
        "slots" => cmd_slots(&dir),
        "stratx" => cmd_stratx(&dir),
        "xsharp" => cmd_xsharp(&dir, &args[2]),
        "framediag" => cmd_framediag(&dir),
        "coldiag" => cmd_coldiag(&dir),
        "dumptab" => cmd_dumptab(&dir, &args[2]),
        "sharp" => cmd_sharp(&dir, &args[2]),
        _ => eprintln!("gebruik: mg_refute_bin tables|eval|lamopt|gmax|sweep"),
    }
}

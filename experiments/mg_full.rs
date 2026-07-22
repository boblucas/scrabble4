// Rust joint-solver hot loop (port van mg_solver3.attempt): component-DFS op het PRE-bord.
// Python doet precompute (woorden, maskers) + validatie (score_game). Rust doet de zware zoektocht:
// probeer per (mask-combo) VEEL random restarts om een 1-component pre-bord te sluiten (vooral de
// hoog-finals maskers die Python niet kan brute-forcen). Output: gesloten bord als JSON-achtige regel.
//
// stdin: regel1 = R0 R7 R14 (3 woorden, spatie-gescheiden, 15 letters lowercase)
//        regel2 = NRESTARTS TIMEOUT_MS
//        daarna N regels: M0csv M14csv M7csv  (elk 7 ints, komma-gescheiden) in finals-prioriteit
// woorden: env WORDS_ALL (2-15) en WORDS_CONN (2-8); meta via env VALS (26 komma) BAG (26 komma)
use std::collections::{HashSet,HashMap,VecDeque};
use std::io::{self,Read,BufRead};
use std::time::Instant;

fn code(c:u8)->u8{ c-b'a'+1 }
fn key(w:&[u8])->u128{ let mut k:u128=0; for &c in w { k=k*27+ c as u128; } k }

struct Rng(u64);
impl Rng{ fn next(&mut self)->u64{ let mut x=self.0; x^=x<<13; x^=x>>7; x^=x<<17; self.0=x; x }
    fn below(&mut self,n:usize)->usize{ if n==0 {0} else {(self.next()%(n as u64)) as usize} } }

struct Solver{
    words:HashSet<u128>,                         // 2-15 voor run-validatie
    byfl:HashMap<(u8,u8,u8),Vec<Vec<u8>>>,       // (first,last,len)->words  (rungs/bridges)
    byfirst:HashMap<(u8,u8),Vec<Vec<u8>>>,       // (first,len)->words       (down-stubs)
    bylast:HashMap<(u8,u8),Vec<Vec<u8>>>,        // (last,len)->words         (up-stubs)
    c8:HashMap<(u8,u8),Vec<Vec<u8>>>,            // (w[0],w[7]) len8 bruggen
    len7:Vec<Vec<u8>>,                           // len7 voor opening
    val:[i64;27], bag:[i64;27],
    r0:[u8;15], r7:[u8;15], r14:[u8;15],
}
impl Solver{
    fn isw(&self,w:&[u8])->bool{ w.len()<2 || self.words.contains(&key(w)) }
}

// per-attempt mutabele staat
struct St{ g:[[u8;15];15], free:[i64;27], m0:Vec<usize>, m7:Vec<usize>, m14:Vec<usize>,
           inm0:[bool;15], inm7:[bool;15], inm14:[bool;15] }

fn is_free_row(y:usize)->bool{ (1..=6).contains(&y) || (8..=13).contains(&y) }

fn runs_valid(s:&Solver,g:&[[u8;15];15], cells:&[(usize,usize)])->bool{
    let mut rows=HashSet::new(); let mut cols=HashSet::new();
    for &(x,y) in cells { rows.insert(y); cols.insert(x); }
    for &y in &rows {
        let mut x=0;
        while x<15 {
            if g[y][x]==0 { x+=1; continue; }
            let mut x2=x; while x2<15 && g[y][x2]!=0 { x2+=1; }
            if x2-x>=2 { let w:Vec<u8>=(x..x2).map(|k| g[y][k]).collect(); if !s.isw(&w){return false;} }
            x=x2;
        }
    }
    for &x in &cols {
        let mut y=0;
        while y<15 {
            if g[y][x]==0 { y+=1; continue; }
            let mut y2=y; while y2<15 && g[y2][x]!=0 { y2+=1; }
            if y2-y>=2 { let w:Vec<u8>=(y..y2).map(|k| g[k][x]).collect(); if !s.isw(&w){return false;} }
            y=y2;
        }
    }
    true
}
fn mask_vert_ok(s:&Solver, st:&St)->bool{
    let anch=[(0usize,&st.m0,&s.r0),(7,&st.m7,&s.r7),(14,&st.m14,&s.r14)];
    for (y,ms,ar) in anch {
        for &c in ms.iter() {
            let mut up=Vec::new(); if y>0 { let mut yy=y as i32-1; while yy>=0 && st.g[yy as usize][c]!=0 { up.push(st.g[yy as usize][c]); yy-=1; } }
            let mut dn=Vec::new(); { let mut yy=y+1; while yy<15 && st.g[yy][c]!=0 { dn.push(st.g[yy][c]); yy+=1; } }
            if !up.is_empty() || !dn.is_empty() {
                let mut w=Vec::new(); for &ch in up.iter().rev(){w.push(ch);} w.push(ar[c]); for &ch in dn.iter(){w.push(ch);}
                if !s.isw(&w){ return false; }
            }
        }
    }
    true
}
fn components(g:&[[u8;15];15])->Vec<Vec<(usize,usize)>>{
    let mut seen=[[false;15];15]; let mut comps=Vec::new();
    for y in 0..15 { for x in 0..15 {
        if g[y][x]!=0 && !seen[y][x] {
            let mut cells=Vec::new(); let mut dq=VecDeque::new(); dq.push_back((x,y)); seen[y][x]=true;
            while let Some((cx,cy))=dq.pop_front(){ cells.push((cx,cy));
                let nb:[(i32,i32);4]=[(1,0),(-1,0),(0,1),(0,-1)];
                for (a,b) in nb { let nx=cx as i32+a; let ny=cy as i32+b;
                    if nx>=0&&nx<15&&ny>=0&&ny<15 && g[ny as usize][nx as usize]!=0 && !seen[ny as usize][nx as usize]{
                        seen[ny as usize][nx as usize]=true; dq.push_back((nx as usize,ny as usize)); } }
            }
            comps.push(cells);
        }
    }}
    comps
}
// place: geeft de nieuwe cellen terug (of None). h=true horizontaal.
fn place(s:&Solver, st:&mut St, word:&[u8], x:i32, y:i32, h:bool)->Option<Vec<(usize,usize)>>{
    let (dx,dy)=if h {(1i32,0i32)} else {(0,1)};
    let l=word.len() as i32;
    if x<0||y<0||x+dx*(l-1)>14||y+dy*(l-1)>14 { return None; }
    let (px,py)=(x-dx,y-dy);
    if px>=0&&px<15&&py>=0&&py<15 && st.g[py as usize][px as usize]!=0 { return None; }
    let (ex,ey)=(x+dx*l,y+dy*l);
    if ex>=0&&ex<15&&ey>=0&&ey<15 && st.g[ey as usize][ex as usize]!=0 { return None; }
    let mut newc=Vec::new(); let mut need=[0i64;27];
    for i in 0..word.len() {
        let cx=(x+dx*i as i32) as usize; let cy=(y+dy*i as i32) as usize; let ch=word[i];
        if st.g[cy][cx]!=0 {
            if st.g[cy][cx]!=ch { return None; }
        } else {
            if cy==0||cy==7||cy==14 { return None; }
            if !is_free_row(cy) { return None; }
            newc.push((cx,cy)); need[ch as usize]+=1;
        }
    }
    if newc.is_empty() { return None; }
    for c in 1..27 { if need[c]>st.free[c] { return None; } }
    for &(cx,cy) in &newc { let ch=word[ if h {cx as i32-x} else {cy as i32-y} as usize]; st.g[cy][cx]=ch; }
    if !(runs_valid(s,&st.g,&newc) && mask_vert_ok(s,st)) {
        for &(cx,cy) in &newc { st.g[cy][cx]=0; } return None;
    }
    for c in 1..27 { st.free[c]-=need[c]; }
    Some(newc)
}
fn unplace(st:&mut St, newc:&[(usize,usize)]){
    for &(cx,cy) in newc { let ch=st.g[cy][cx] as usize; st.free[ch]+=1; st.g[cy][cx]=0; }
}
const MAXV:usize=40;
fn connectors_for(s:&Solver, st:&St, tx:usize, ty:usize, rng:&mut Rng, out:&mut Vec<(Vec<u8>,i32,i32,bool)>){
    let sample=|v:&Vec<Vec<u8>>, rng:&mut Rng, out:&mut Vec<(Vec<u8>,i32,i32,bool)>, x:i32, y:i32|{
        if v.len()<=MAXV { for w in v { out.push((w.clone(),x,y,false)); } }
        else { for _ in 0..MAXV { let w=&v[rng.below(v.len())]; out.push((w.clone(),x,y,false)); } }
    };
    if ty==0 {
        if st.g[1][tx]==0 {
            if !st.inm0[tx] { if let Some(v)=s.c8.get(&(s.r0[tx],s.r7[tx])){ for w in v { out.push((w.clone(),tx as i32,0,false)); } } }
            for l in 2..8u8 { if let Some(v)=s.byfirst.get(&(s.r0[tx],l)){ sample(v,rng,out,tx as i32,0); } }
        }
    } else if ty==14 {
        if st.g[13][tx]==0 {
            if !st.inm14[tx] { if let Some(v)=s.c8.get(&(s.r7[tx],s.r14[tx])){ for w in v { out.push((w.clone(),tx as i32,7,false)); } } }
            for l in 2..8u8 { if let Some(v)=s.bylast.get(&(s.r14[tx],l)){ sample(v,rng,out,tx as i32,14-l as i32+1); } }
        }
    } else if ty==7 {
        if st.g[6][tx]==0 { for l in 2..8u8 { if let Some(v)=s.bylast.get(&(s.r7[tx],l)){ sample(v,rng,out,tx as i32,7-l as i32+1); } } }
        if st.g[8][tx]==0 { for l in 2..8u8 { if let Some(v)=s.byfirst.get(&(s.r7[tx],l)){ sample(v,rng,out,tx as i32,7); } } }
    } else {
        let la=st.g[ty][tx];
        for b in 0..15usize {
            if b==tx || st.g[ty][b]==0 { continue; }
            let (a,c)=if tx<b {(tx,b)} else {(b,tx)};
            if !(2..=7).contains(&(c-a)) { continue; }
            if (a+1..c).any(|k| st.g[ty][k]!=0) { continue; }
            let l0=st.g[ty][a]; let l1=st.g[ty][c];
            if let Some(v)=s.byfl.get(&(l0,l1,(c-a+1) as u8)){ for w in v { out.push((w.clone(),a as i32,ty as i32,true)); } }
        }
        if ty>0 && st.g[ty-1][tx]==0 { for l in 2..6u8 { if let Some(v)=s.bylast.get(&(la,l)){ sample(v,rng,out,tx as i32,ty as i32-l as i32+1); } } }
        if ty<14 && st.g[ty+1][tx]==0 { for l in 2..6u8 { if let Some(v)=s.byfirst.get(&(la,l)){ sample(v,rng,out,tx as i32,ty as i32); } } }
    }
}
fn gen_moves(s:&Solver, st:&St, rng:&mut Rng)->Vec<(Vec<u8>,i32,i32,bool)>{
    let comps=components(&st.g);
    if comps.len()<=1 { return Vec::new(); }
    let main=comps.iter().enumerate().max_by_key(|(_,c)| c.len()).unwrap().0;
    let mut others:Vec<&Vec<(usize,usize)>>=comps.iter().enumerate().filter(|(i,_)| *i!=main).map(|(_,c)| c).collect();
    others.sort_by_key(|c| c.len());
    let mut out=Vec::new();
    for &(tx,ty) in others[0] { connectors_for(s,st,tx,ty,rng,&mut out); }
    // shuffle
    for i in (1..out.len()).rev(){ let j=rng.below(i+1); out.swap(i,j); }
    out.truncate(500);
    out
}
fn build_backbone(s:&Solver, st:&mut St, rng:&mut Rng){
    let mut order:Vec<usize>=(0..15).collect();
    for i in (1..15).rev(){ let j=rng.below(i+1); order.swap(i,j); }
    for &c in &order { if !st.inm0[c] && st.g[1][c]==0 {
        if let Some(v)=s.c8.get(&(s.r0[c],s.r7[c])){ let mut cs=v.clone(); for i in (1..cs.len()).rev(){let j=rng.below(i+1);cs.swap(i,j);} for w in &cs { if place(s,st,w,c as i32,0,false).is_some(){break;} } }
    }}
    for &c in &order { if !st.inm14[c] && st.g[13][c]==0 {
        if let Some(v)=s.c8.get(&(s.r7[c],s.r14[c])){ let mut cs=v.clone(); for i in (1..cs.len()).rev(){let j=rng.below(i+1);cs.swap(i,j);} for w in &cs { if place(s,st,w,c as i32,7,false).is_some(){break;} } }
    }}
}
fn dfs(s:&Solver, st:&mut St, rng:&mut Rng, depth:i32, t0:&Instant, tl_ms:u128, best:&mut usize, bestb:&mut Option<[[u8;15];15]>)->bool{
    if t0.elapsed().as_millis()>tl_ms { return false; }
    let comps=components(&st.g); let cm=comps.len();
    if cm<*best { *best=cm; *bestb=Some(st.g); }
    if cm==1 { return true; }
    if depth>30 { return false; }
    let moves=gen_moves(s,st,rng);
    for (w,x,y,h) in moves {
        if let Some(newc)=place(s,st,&w,x,y,h){
            if dfs(s,st,rng,depth+1,t0,tl_ms,best,bestb){ return true; }
            unplace(st,&newc);
        }
    }
    false
}
fn attempt(s:&Solver, m0:&[usize], m14:&[usize], m7:&[usize], seed:u64, tl_ms:u128)->Option<[[u8;15];15]>{
    let mut st=St{ g:[[0u8;15];15], free:[0i64;27], m0:m0.to_vec(),m7:m7.to_vec(),m14:m14.to_vec(),
        inm0:[false;15],inm7:[false;15],inm14:[false;15] };
    for &c in m0 {st.inm0[c]=true;} for &c in m7 {st.inm7[c]=true;} for &c in m14 {st.inm14[c]=true;}
    // pre-cellen
    for c in 0..15 { if !st.inm0[c]{st.g[0][c]=s.r0[c];} if !st.inm7[c]{st.g[7][c]=s.r7[c];} if !st.inm14[c]{st.g[14][c]=s.r14[c];} }
    for c in 1..27 { st.free[c]=s.bag[c]; }
    for c in 0..15 { st.free[s.r0[c] as usize]-=1; st.free[s.r7[c] as usize]-=1; st.free[s.r14[c] as usize]-=1; }
    let mut rng=Rng(seed.wrapping_mul(2862933555777941757).wrapping_add(3037000493));
    // opening: random len7 met w[3]==r7[7]
    let tgt=s.r7[7];
    let mut ops:Vec<&Vec<u8>>=s.len7.iter().filter(|w| w[3]==tgt).collect();
    for i in (1..ops.len()).rev(){ let j=rng.below(i+1); ops.swap(i,j); }
    for w in ops {
        let mut nd=[0i64;27]; for &ch in w.iter(){nd[ch as usize]+=1;} nd[tgt as usize]-=1;
        let mut ok=true; for c in 1..27 { if st.free[c]<nd[c]{ok=false;break;} }
        if ok { for i in 0..7 { st.g[4+i][7]=w[i]; } for c in 1..27 { st.free[c]-=nd[c]; } break; }
    }
    build_backbone(s,&mut st,&mut rng);
    let t0=Instant::now(); let mut best=999usize; let mut bestb=None;
    let closed=dfs(s,&mut st,&mut rng,0,&t0,tl_ms,&mut best,&mut bestb);
    if closed { Some(st.g) } else { None }
}
fn load_words(path:&str)->Vec<Vec<u8>>{
    let f=std::fs::File::open(path).unwrap(); let r=io::BufReader::new(f);
    let mut v=Vec::new();
    for line in r.lines(){ let l=line.unwrap(); let w:Vec<u8>=l.bytes().map(code).collect(); if !w.is_empty(){v.push(w);} }
    v
}
fn parse_csv(s:&str)->Vec<usize>{ s.split(',').filter(|t|!t.is_empty()).map(|t| t.trim().parse().unwrap()).collect() }

// ---------- Rust score_game + beam-decompose ----------
struct Scorer{ lm:[[i64;15];15], wm:[[i64;15];15], sc:[i64;27], bonus:i64, hand:usize }
fn runs_through(cur:&[[u8;15];15], x:usize, y:usize, h:bool)->Vec<(usize,usize)>{
    let (dx,dy)=if h {(1i32,0i32)} else {(0,1)};
    let (mut x0,mut y0)=(x as i32,y as i32);
    while x0-dx>=0 && x0-dx<15 && y0-dy>=0 && y0-dy<15 && cur[(y0-dy) as usize][(x0-dx) as usize]!=0 { x0-=dx; y0-=dy; }
    let mut cells=Vec::new(); let (mut xx,mut yy)=(x0,y0);
    while xx>=0&&xx<15&&yy>=0&&yy<15 && cur[yy as usize][xx as usize]!=0 { cells.push((xx as usize,yy as usize)); xx+=dx; yy+=dy; }
    cells
}
// score van EEN zet gegeven cur (bord NA het plaatsen van de nieuwe cellen). cset=nieuw, blanks=blank-cellen.
fn move_score(sco:&Scorer, s:&Solver, cur:&[[u8;15];15], cells:&[(usize,usize)],
              cset:&HashSet<(usize,usize)>, blanks:&HashSet<(usize,usize)>)->Option<i64>{
    let mut seen:HashSet<((usize,usize),bool,usize)>=HashSet::new(); let mut mscore=0i64;
    for &(x,y) in cells {
        for h in [true,false] {
            let run=runs_through(cur,x,y,h);
            if run.len()<2 { continue; }
            let k=(run[0],h,run.len());
            if seen.contains(&k) { continue; }
            if !run.iter().any(|c| cset.contains(c)) { continue; }
            seen.insert(k);
            let word:Vec<u8>=run.iter().map(|&(cx,cy)| cur[cy][cx]).collect();
            if !s.words.contains(&key(&word)) { return None; }
            let mut score=0i64; let mut wm=1i64; let mut np=0i64;
            for (i,&(cx,cy)) in run.iter().enumerate() {
                let mut v= if blanks.contains(&(cx,cy)) {0} else { sco.sc[word[i] as usize] };
                if cset.contains(&(cx,cy)) { v*=sco.lm[cy][cx]; wm*=sco.wm[cy][cx]; np+=1; }
                score+=v;
            }
            mscore += score*wm + if (np as usize)==sco.hand { sco.bonus } else {0};
        }
    }
    Some(mscore)
}
type Bits=[u64;4];
fn bset(b:&mut Bits, x:usize, y:usize){ let i=y*15+x; b[i/64]|=1u64<<(i%64); }
fn bget(b:&Bits, x:usize, y:usize)->bool{ let i=y*15+x; (b[i/64]>>(i%64))&1==1 }
// beam-decompose van het PRE-bord (pre = volledig bord met masker-cellen op 0). finals apart.
fn beam_decompose(sco:&Scorer, s:&Solver, full:&[[u8;15];15], maskset:&HashSet<(usize,usize)>,
                  blanks:&HashSet<(usize,usize)>, beam_w:usize)->Option<(i64,Vec<Vec<(usize,usize)>>)>{
    // pre-bord lijnen (segmenten van niet-masker cellen)
    let mut pre=[[0u8;15];15];
    for y in 0..15 { for x in 0..15 { if full[y][x]!=0 && !maskset.contains(&(x,y)) { pre[y][x]=full[y][x]; } } }
    let mut lines:Vec<Vec<(usize,usize)>>=Vec::new();
    for y in 0..15 { let mut x=0; while x<15 { if pre[y][x]==0 {x+=1;continue;} let mut x2=x; while x2<15&&pre[y][x2]!=0{x2+=1;} if x2-x>=2 { lines.push((x..x2).map(|k|(k,y)).collect()); } x=x2; } }
    for x in 0..15 { let mut y=0; while y<15 { if pre[y][x]==0 {y+=1;continue;} let mut y2=y; while y2<15&&pre[y2][x]!=0{y2+=1;} if y2-y>=2 { lines.push((y..y2).map(|k|(x,k)).collect()); } y=y2; } }
    let npre:usize=(0..15).map(|y| (0..15).filter(|&x| pre[y][x]!=0).count()).sum();
    // state: (cum, placed_grid, bits, moves)
    struct S{ cum:i64, pl:[[bool;15];15], moves:Vec<Vec<(usize,usize)>> }
    let mut beam:Vec<S>=vec![S{cum:0,pl:[[false;15];15],moves:Vec::new()}];
    let mut complete:Vec<S>=Vec::new();
    loop {
        let mut nxt:HashMap<Bits,S>=HashMap::new();
        let mut any=false;
        for st in &beam {
            let placed_cnt:usize=(0..15).map(|y|(0..15).filter(|&x| st.pl[y][x]).count()).sum();
            if placed_cnt>=npre { continue; }
            any=true;
            for line in &lines {
                let n=line.len();
                for i in 0..n { for j in i..n {
                    let seg=&line[i..=j];
                    let newc:Vec<(usize,usize)>=seg.iter().cloned().filter(|&(x,y)| !st.pl[y][x]).collect();
                    if newc.is_empty()||newc.len()>7 { continue; }
                    if st.moves.is_empty() {
                        if !newc.contains(&(7,7)) { continue; }
                    } else {
                        let touch=seg.iter().any(|&(x,y)| st.pl[y][x]) || newc.iter().any(|&(x,y)|{
                            let nb:[(i32,i32);4]=[(1,0),(-1,0),(0,1),(0,-1)];
                            nb.iter().any(|&(a,b)|{ let nx=x as i32+a; let ny=y as i32+b; nx>=0&&nx<15&&ny>=0&&ny<15 && st.pl[ny as usize][nx as usize] })
                        });
                        if !touch { continue; }
                    }
                    // cur = pre-tiles placed so far + newc
                    let mut cur=[[0u8;15];15];
                    for y in 0..15 { for x in 0..15 { if st.pl[y][x] { cur[y][x]=full[y][x]; } } }
                    for &(x,y) in &newc { cur[y][x]=full[y][x]; }
                    let cset:HashSet<(usize,usize)>=newc.iter().cloned().collect();
                    let mg=match move_score(sco,s,&cur,&newc,&cset,blanks){ Some(v)=>v, None=>continue };
                    let mut npl=st.pl; for &(x,y) in &newc { npl[y][x]=true; }
                    let mut bits:Bits=[0;4]; for y in 0..15 { for x in 0..15 { if npl[y][x]{ bset(&mut bits,x,y);} } }
                    let e=nxt.entry(bits).or_insert(S{cum:i64::MIN,pl:npl,moves:Vec::new()});
                    if st.cum+mg>e.cum { e.cum=st.cum+mg; e.pl=npl; let mut nm=st.moves.clone(); nm.push(newc.clone()); e.moves=nm; }
                }}
            }
        }
        if !any { for st in beam.drain(..){ complete.push(st);} break; }
        let mut cand:Vec<S>=nxt.into_values().collect();
        // splits voltooide
        let mut nb=Vec::new();
        for st in cand.drain(..) {
            let pc:usize=(0..15).map(|y|(0..15).filter(|&x| st.pl[y][x]).count()).sum();
            if pc>=npre { complete.push(st); } else { nb.push(st); }
        }
        nb.sort_by(|a,b| b.cum.cmp(&a.cum));
        nb.truncate(beam_w);
        if nb.is_empty() { break; }
        beam=nb;
    }
    let best=complete.into_iter().max_by_key(|s| s.cum)?;
    Some((best.cum,best.moves))
}
fn assign_blanks(sco:&Scorer, full:&[[u8;15];15], bag:&[i64;27])->HashSet<(usize,usize)>{
    let mut cnt=[0i64;27]; for y in 0..15 { for x in 0..15 { if full[y][x]!=0 { cnt[full[y][x] as usize]+=1; } } }
    let mut blanks=HashSet::new();
    for ch in 1..27usize {
        let over=cnt[ch]-bag[ch];
        for _ in 0..over.max(0) {
            // goedkoopste cel van deze letter (letterwaarde × premie), niet al blank
            let mut best:Option<(i64,usize,usize)>=None;
            for y in 0..15 { for x in 0..15 {
                if full[y][x] as usize==ch && !blanks.contains(&(x,y)) {
                    let prem = if (y==0||y==14)&&(x==0||x==7||x==14) {27} else if y==7&&(x==0||x==14) {9} else {1};
                    let c=sco.sc[ch]*prem;
                    if best.is_none()||c<best.unwrap().0 { best=Some((c,x,y)); }
                }
            }}
            if let Some((_,x,y))=best { blanks.insert((x,y)); }
        }
    }
    blanks
}
fn main(){
    let wall=load_words(&std::env::var("WORDS_ALL").unwrap());
    let wconn=load_words(&std::env::var("WORDS_CONN").unwrap());
    let mut words=HashSet::with_capacity(wall.len()*2);
    for w in &wall { words.insert(key(w)); }
    let mut byfl:HashMap<(u8,u8,u8),Vec<Vec<u8>>>=HashMap::new();
    let mut byfirst:HashMap<(u8,u8),Vec<Vec<u8>>>=HashMap::new();
    let mut bylast:HashMap<(u8,u8),Vec<Vec<u8>>>=HashMap::new();
    let mut c8:HashMap<(u8,u8),Vec<Vec<u8>>>=HashMap::new();
    let mut len7:Vec<Vec<u8>>=Vec::new();
    for w in wconn {
        let l=w.len() as u8; let (f,la)=(w[0],*w.last().unwrap());
        byfl.entry((f,la,l)).or_default().push(w.clone());
        byfirst.entry((f,l)).or_default().push(w.clone());
        bylast.entry((la,l)).or_default().push(w.clone());
        if l==8 { c8.entry((w[0],w[7])).or_default().push(w.clone()); }
        if l==7 { len7.push(w.clone()); }
    }
    let vals:Vec<i64>=parse_csv(&std::env::var("VALS").unwrap()).iter().map(|&x| x as i64).collect();
    let bagv:Vec<i64>=parse_csv(&std::env::var("BAG").unwrap()).iter().map(|&x| x as i64).collect();
    let mut val=[0i64;27]; let mut bag=[0i64;27];
    for i in 0..26 { val[i+1]=vals[i]; bag[i+1]=bagv[i]; }
    // stdin
    let mut inp=String::new(); io::stdin().read_to_string(&mut inp).unwrap();
    let mut lines=inp.lines();
    let l1:Vec<&str>=lines.next().unwrap().split_whitespace().collect();
    let enc=|w:&str|->[u8;15]{ let mut a=[0u8;15]; for (i,c) in w.bytes().enumerate(){a[i]=code(c);} a };
    let (r0,r7,r14)=(enc(l1[0]),enc(l1[1]),enc(l1[2]));
    let l2:Vec<&str>=lines.next().unwrap().split_whitespace().collect();
    let nrest:u64=l2[0].parse().unwrap(); let tl_ms:u128=l2[1].parse().unwrap();
    let s=Solver{words,byfl,byfirst,bylast,c8,len7,val,bag,r0,r7,r14};
    // scorer laden
    let pf=std::fs::read_to_string(&std::env::var("PREMIUM_FLAT").unwrap()).unwrap();
    let mut pl2=pf.lines();
    let lmv:Vec<i64>=pl2.next().unwrap().split_whitespace().map(|t|t.parse().unwrap()).collect();
    let wmv:Vec<i64>=pl2.next().unwrap().split_whitespace().map(|t|t.parse().unwrap()).collect();
    let scv:Vec<i64>=pl2.next().unwrap().split_whitespace().map(|t|t.parse().unwrap()).collect();
    let hb:Vec<i64>=pl2.next().unwrap().split_whitespace().map(|t|t.parse().unwrap()).collect();
    let mut lm=[[0i64;15];15]; let mut wm=[[0i64;15];15];
    for y in 0..15 { for x in 0..15 { lm[y][x]=lmv[y*15+x]; wm[y][x]=wmv[y*15+x]; } }
    let mut scarr=[0i64;27]; for i in 0..27 { scarr[i]=scv[i]; }
    let sco=Scorer{ lm, wm, sc:scarr, bonus:hb[1], hand:hb[0] as usize };
    let beam_w:usize=std::env::var("MGBEAMW").ok().and_then(|v|v.parse().ok()).unwrap_or(12);
    let mut combo_idx=0;
    for line in lines {
        let parts:Vec<&str>=line.split_whitespace().collect();
        if parts.len()<3 { continue; }
        let m0=parse_csv(parts[0]); let m14=parse_csv(parts[1]); let m7=parse_csv(parts[2]);
        let salt:u64=std::env::var("SEED_SALT").ok().and_then(|v|v.parse().ok()).unwrap_or(0);
        for r in 0..nrest {
            if let Some(g)=attempt(&s,&m0,&m14,&m7,(combo_idx as u64)*1_000_003 + r + 1 + salt.wrapping_mul(7919), tl_ms) {
                // reconstrueer VOL bord: vul masker-cellen met ankerletters
                let mut full=g;
                for &c in &m0 { full[0][c]=s.r0[c]; }
                for &c in &m7 { full[7][c]=s.r7[c]; }
                for &c in &m14 { full[14][c]=s.r14[c]; }
                let mut maskset:HashSet<(usize,usize)>=HashSet::new();
                for &c in &m0 { maskset.insert((c,0)); } for &c in &m7 { maskset.insert((c,7)); } for &c in &m14 { maskset.insert((c,14)); }
                let blanks=assign_blanks(&sco,&full,&s.bag);
                if let Some((prep,pmoves))=beam_decompose(&sco,&s,&full,&maskset,&blanks,beam_w) {
                    // finals: 3 masker-zetten op het volle bord
                    let mut finals=0i64; let mut okf=true;
                    for &(y,ms) in &[(7usize,&m7),(0usize,&m0),(14usize,&m14)] {
                        let cells:Vec<(usize,usize)>=ms.iter().map(|&c|(c,y)).collect();
                        let cset:HashSet<(usize,usize)>=cells.iter().cloned().collect();
                        match move_score(&sco,&s,&full,&cells,&cset,&blanks){ Some(v)=>finals+=v, None=>{okf=false;} }
                    }
                    if okf {
                        let total=prep+finals;
                        let mut bs=String::new();
                        for y in 0..15 { for x in 0..15 { bs.push((b'a'-1+g[y][x]) as char); } }
                        let j=|m:&[usize]| m.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(",");
                        // encodeer prep-zetten + blanks voor Python-verificatie
                        let mvenc:String=pmoves.iter().map(|mv| mv.iter().map(|&(x,y)| format!("{}.{}",x,y)).collect::<Vec<_>>().join(",")).collect::<Vec<_>>().join(";");
                        let blenc:String=blanks.iter().map(|&(x,y)| format!("{}.{}",x,y)).collect::<Vec<_>>().join(",");
                        println!("SCORED {} {} {} {} {} {} {} MV {} BL {}", total, prep, finals, j(&m0), j(&m14), j(&m7), bs, mvenc, blenc);
                    }
                }
            }
        }
        combo_idx+=1;
    }
    eprintln!("done {} combos", combo_idx);
}

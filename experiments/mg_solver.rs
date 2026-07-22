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
    let mut combo_idx=0;
    for line in lines {
        let parts:Vec<&str>=line.split_whitespace().collect();
        if parts.len()<3 { continue; }
        let m0=parse_csv(parts[0]); let m14=parse_csv(parts[1]); let m7=parse_csv(parts[2]);
        for r in 0..nrest {
            if let Some(g)=attempt(&s,&m0,&m14,&m7,(combo_idx as u64)*1_000_003 + r + 1, tl_ms) {
                // output: CLOSED combo_idx  M0 M14 M7  board(225 chars)
                let mut bs=String::new();
                for y in 0..15 { for x in 0..15 { bs.push((b'a'-1+g[y][x]) as char); } }
                // '`' voor leeg (g=0 -> b'a'-1 = '`')
                let j=|m:&[usize]| m.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(",");
                println!("CLOSED {} {} {} {} {}", combo_idx, j(&m0), j(&m14), j(&m7), bs);
                break;
            }
        }
        combo_idx+=1;
    }
    eprintln!("done {} combos", combo_idx);
}

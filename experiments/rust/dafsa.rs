// Minimal row-DFA builder (Rust) -- mirrors dawg.position_independent_row_automaton:
//   trie -> Revuz minimisation (acyclic minimal DAFSA) -> row DFA (GAP state + cyclic gaps).
// Letters a-z -> 1..26 (matches Alphabet for english/dutch). Single letters a..z are words
// (the solver adds set(abc)). Output state/edge counts are directly comparable to Python.
//
// Build:  rustc -O experiments/rust/dafsa.rs -o experiments/rust/dafsa
// Run:    experiments/rust/dafsa <wordlist> <maxlen1> [maxlen2 ...]
use std::collections::{HashMap, HashSet, BTreeSet, VecDeque};
use std::time::Instant;

fn build_row_dfa(words: &[Vec<u8>]) -> (usize, usize, usize) {
    // ---- trie ----  node 0 = root; children[node][letter] = child idx (0 = none)
    let mut children: Vec<[u32; 27]> = vec![[0u32; 27]];
    let mut terminal: Vec<bool> = vec![false];
    for w in words {
        let mut node = 0usize;
        for &c in w {
            let ci = c as usize;
            let nxt = children[node][ci];
            if nxt == 0 {
                let id = children.len() as u32;
                children.push([0u32; 27]);
                terminal.push(false);
                children[node][ci] = id;
                node = id as usize;
            } else {
                node = nxt as usize;
            }
        }
        terminal[node] = true;
    }
    let n = children.len();

    // ---- heights via reverse-BFS (trie is a tree: parent before children in BFS) ----
    let mut height = vec![0u32; n];
    let mut order: Vec<u32> = Vec::with_capacity(n);
    let mut q: VecDeque<u32> = VecDeque::new();
    q.push_back(0);
    while let Some(node) = q.pop_front() {
        order.push(node);
        for c in 1..27 { let ch = children[node as usize][c]; if ch != 0 { q.push_back(ch); } }
    }
    for &node in order.iter().rev() {
        let mut h = 0u32;
        for c in 1..27 { let ch = children[node as usize][c]; if ch != 0 { h = h.max(1 + height[ch as usize]); } }
        height[node as usize] = h;
    }

    // ---- Revuz minimisation: merge equal (is_final, [(letter, rep[child])]) bottom-up ----
    let maxh = *height.iter().max().unwrap();
    let mut by_h: Vec<Vec<u32>> = vec![Vec::new(); (maxh + 1) as usize];
    for i in 0..n { by_h[height[i] as usize].push(i as u32); }
    let mut rep: Vec<u32> = (0..n as u32).collect();
    let mut register: HashMap<(bool, Vec<(u8, u32)>), u32> = HashMap::new();
    for h in 0..=maxh {
        for &node in &by_h[h as usize] {
            let nu = node as usize;
            let mut sig: Vec<(u8, u32)> = Vec::new();
            for c in 1..27 { let ch = children[nu][c]; if ch != 0 { sig.push((c as u8, rep[ch as usize])); } }
            match register.get(&(terminal[nu], sig.clone())) {
                Some(&canon) => rep[nu] = canon,
                None => { register.insert((terminal[nu], sig), node); rep[nu] = node; }
            }
        }
    }

    // ---- row DFA: GAP = 0, canonical nodes -> 1.. ----
    let canon: BTreeSet<u32> = (0..n).map(|i| rep[i]).collect();
    let mut sid: HashMap<u32, u32> = HashMap::new();
    for (i, &c) in canon.iter().enumerate() { sid.insert(c, (i + 1) as u32); }
    let mut edges: HashSet<(u32, u32, u32)> = HashSet::new();
    let mut finals: HashSet<u32> = HashSet::new();
    edges.insert((0, 0, 0));
    finals.insert(0);
    for c in 1..27 { let ch = children[0][c]; if ch != 0 { edges.insert((0, c as u32, sid[&rep[ch as usize]])); } }
    for &node in &canon {
        let nu = node as usize;
        let s = sid[&node];
        for c in 1..27 { let ch = children[nu][c]; if ch != 0 { edges.insert((s, c as u32, sid[&rep[ch as usize]])); } }
        if terminal[nu] { finals.insert(s); edges.insert((s, 0, 0)); }
    }
    (canon.len() + 1, edges.len(), finals.len())
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let path = &args[1];
    let maxlens: Vec<usize> = args[2..].iter().map(|s| s.parse().unwrap()).collect();

    let t = Instant::now();
    let data = std::fs::read_to_string(path).unwrap();
    let mut base: Vec<Vec<u8>> = (0u8..26).map(|c| vec![c + 1]).collect(); // single letters a..z
    for line in data.lines() {
        let line = line.trim();
        if line.is_empty() { continue; }
        let mut w = Vec::with_capacity(line.len());
        let mut ok = true;
        for b in line.bytes() {
            let lc = b.to_ascii_lowercase();
            if (b'a'..=b'z').contains(&lc) { w.push(lc - b'a' + 1); } else { ok = false; break; }
        }
        if ok && !w.is_empty() { base.push(w); }
    }
    base.sort(); base.dedup();
    println!("read {} -> {} words in {:.2}s", path, base.len(), t.elapsed().as_secs_f64());

    for &ml in &maxlens {
        let words: Vec<Vec<u8>> = base.iter().filter(|w| w.len() <= ml).cloned().collect();
        let mut sorted = words.clone(); sorted.sort();   // (build doesn't require sorted, but keep parity)
        let tb = Instant::now();
        let (states, edges, finals) = build_row_dfa(&sorted);
        println!("words<= {:>2}: {:>8} words  ->  row-DFA build={:8.3}s  states={}  edges={}  finals={}",
                 ml, words.len(), tb.elapsed().as_secs_f64(), states, edges, finals);
    }
}

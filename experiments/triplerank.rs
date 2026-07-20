// Maxgame triple-ranker kernel. Leest maxgame_words.tsv (per 15-woord: s27,s9,open,26 letter-counts),
// enumereert alle bag-haalbare prepareerbare triplets (R0 x27, R14 x27, R7 x9), scoort
// A+B+C+D - blankpenalty, en dumpt de top-N. Bag + blancolimiet uit argumenten.
use std::fs::File;
use std::io::{BufRead, BufReader, Write, BufWriter};

const A: usize = 26;

#[derive(Clone)]
struct W { word: String, s27: i64, s9: i64, opn: i64, cnt: [u8; A] }

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let path = "experiments/results/maxgame_words.tsv";
    // dutch2026 bag counts (a..z), blanks apart
    // wordt doorgegeven als arg1 = comma-sep 26 counts, arg2 = blanks, arg3 = topN
    let bag: Vec<i64> = args[1].split(',').map(|x| x.parse().unwrap()).collect();
    let blanks: i64 = args[2].parse().unwrap();
    let topn: usize = args.get(3).map(|s| s.parse().unwrap()).unwrap_or(100);

    let f = BufReader::new(File::open(path).unwrap());
    let mut ws: Vec<W> = Vec::new();
    for (i, line) in f.lines().enumerate() {
        if i == 0 { continue; }
        let l = line.unwrap();
        let p: Vec<&str> = l.split('\t').collect();
        if p.len() < 4 + A { continue; }
        let mut cnt = [0u8; A];
        for k in 0..A { cnt[k] = p[4 + k].parse().unwrap(); }
        ws.push(W { word: p[0].to_string(), s27: p[1].parse().unwrap(),
                    s9: p[2].parse().unwrap(), opn: p[3].parse().unwrap(), cnt });
    }
    eprintln!("woorden geladen: {}", ws.len());

    // R0/R14-kandidaten: s27>0, gesorteerd desc; R7: s9>0 gesorteerd op s9+open desc
    let mut r27: Vec<&W> = ws.iter().filter(|w| w.s27 > 0).collect();
    r27.sort_by(|a, b| b.s27.cmp(&a.s27));
    let mut r7: Vec<&W> = ws.iter().filter(|w| w.s9 > 0).collect();
    r7.sort_by(|a, b| (b.s9 + b.opn).cmp(&(a.s9 + a.opn)));
    // cutoffs (ruim): score gedomineerd door top-s27; klein genoeg voor volledige enum
    let NC = r27.len().min(4000);
    let MC = r7.len().min(4000);
    eprintln!("r27={} (cut {}), r7={} (cut {})", r27.len(), NC, r7.len(), MC);

    // per-letter val (a..z) voor blankpenalty
    let valarr: [i64; A] = [1,3,5,2,1,4,3,4,1,4,3,3,3,1,1,3,10,2,2,2,4,4,5,8,8,4]; // dutch2026 waarden

    let mut heap: Vec<(i64, usize, usize, usize, i64, i64)> = Vec::new(); // (score,ai,bi,ci,blanks,pen)
    let mut worst = i64::MIN;

    for ci in 0..MC {
        let c = r7[ci];
        let s9o = c.s9 + c.opn;
        // vroege stop: zelfs 2x beste s27 + s9o kan de heap niet meer halen
        if heap.len() >= topn && r27[0].s27 * 2 + s9o - 400 < worst { /* geen break: s9o daalt, dus continue kan nog? nee ci-sorted desc */ break; }
        for ai in 0..NC {
            let a = r27[ai];
            if heap.len() >= topn && a.s27 + r27[0].s27 + s9o < worst { break; }
            for bi in ai..NC {
                let b = r27[bi];
                let core = a.s27 + b.s27 + s9o;
                if heap.len() >= topn && core < worst { break; }
                if std::ptr::eq(a, c) || std::ptr::eq(b, c) { continue; }
                // bag + blancos + penalty
                let mut over_tot = 0i64; let mut pen = 0i64; let mut feasible = true;
                for k in 0..A {
                    let need = a.cnt[k] as i64 + b.cnt[k] as i64 + c.cnt[k] as i64;
                    let ov = need - bag[k];
                    if ov > 0 {
                        over_tot += ov;
                        if over_tot > blanks { feasible = false; break; }
                        // blank op goedkoopste woord dat letter k bevat: x9 als in R7, anders x27
                        let wm = if c.cnt[k] > 0 { 9 } else { 27 };
                        pen += valarr[k] * wm * ov;
                    }
                }
                if !feasible { continue; }
                let score = core - pen;
                if heap.len() < topn {
                    heap.push((score, ai, bi, ci, over_tot, pen));
                    if heap.len() == topn { heap.sort_by(|x, y| x.0.cmp(&y.0)); worst = heap[0].0; }
                } else if score > worst {
                    heap[0] = (score, ai, bi, ci, over_tot, pen);
                    heap.sort_by(|x, y| x.0.cmp(&y.0));
                    worst = heap[0].0;
                }
            }
        }
    }
    heap.sort_by(|x, y| y.0.cmp(&x.0));
    let mut out = BufWriter::new(File::create("experiments/results/maxgame_triplerank.tsv").unwrap());
    writeln!(out, "rank\tscore\tR0\tR14\tR7\tA_s27\tB_s27\tC_s9\tD_open\tblanks\tpenalty").unwrap();
    for (i, (sc, ai, bi, ci, bl, pen)) in heap.iter().enumerate() {
        let a = r27[*ai]; let b = r27[*bi]; let c = r7[*ci];
        writeln!(out, "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}", i+1, sc, a.word, b.word, c.word,
                 a.s27, b.s27, c.s9, c.opn, bl, pen).unwrap();
        if i < topn { println!("{:>3} {:>6} {:<16}{:<16}{:<16} A{:>5} B{:>5} C{:>4} D{:>4} bl{} pen{}",
                 i+1, sc, a.word, b.word, c.word, a.s27, b.s27, c.s9, c.opn, bl, pen); }
    }
    eprintln!("top-{} -> maxgame_triplerank.tsv", heap.len());
}

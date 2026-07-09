# Artefact-beleid (bewijs vs reproduceerbaar) — 2026-07-09

**Het certificaat van een resultaat bestaat uit:**
1. **Witness-borden** (`results/turns/N15_*.json`) — in git, onafhankelijk her-controleerbaar met
   `witness_check.py` (met `N15_LANG=<lexicon>`).
2. **Verdict-bestanden** (`verdict_*.gz` per trede/band) — één `RES <key> <LE|MAX|TO>`-regel per
   band-combo; samen met de band-definitie (base + floor) het her-auditbare spoor.
3. **Ledgers** (`*.jsonl(.gz)`) — content-keyed per-combo CP-SAT/TB-beslissingen (residuen).
4. **Logs** (`*.log`, `driver.log`, `FINISH*`) + **bases** (`bases_*/`, `PROVENANCE`-regel) +
   de **code op de commit** in het log.

**NIET nodig voor het bewijs (reproduceerbaar, wordt getruncate bij schijfdruk):**
- `shard_*.txt` — de band-combolijsten; deterministisch herbouwbaar met
  `xfill --pinenum <base> --floor <f>` (key-set-gegate tegen Python, commit 4396200-era gates).
- `_keys_in/_keys_out.txt` — sorteer-derivaten van shards/verdicts (coverage-check), herbouwbaar
  met één sort-commando.
- Incomplete/vervangen runs (afgebroken solves waarvan een latere volledige run het spoor is).

**Audit-recept** (elke trede): (1) herbouw de band met pinenum (zelfde base+floor), (2) vergelijk
key-sets met de verdict-gz (`LC_ALL=C sort` + `cmp`), (3) her-solve een steekproef + alle TO's.

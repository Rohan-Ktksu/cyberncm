# R7g: does packet text reach a decision?

Review of the code in `ncm/` and `demo/` at the commit this branch started from (main after #19's base), plus the directive schema. Method: search for any read of payload, protocol text or free text (payload, HTTP, user agent, URL, host name, DNS query name, TLS name, JA3, banner, pcap tools), then read how each input column is used and what each output can carry.

## Inputs to the detector

Every prep script reads **flow-record columns only**: addresses, ports, protocol, timestamps, durations, packet and byte counts, TCP flag counts, initial window, packet length and inter-arrival statistics (the `COLS` maps in `prep.py` and `prep_*.py`). The only string columns read are the source and destination address (turned into integers) and the dataset's label (used for scoring and training of supervised baselines, never as a model input; the unsupervised v0 sees no label). `prep.py` calls its payload features "payload kinematics (encryption-invariant)": sizes and timings, not content. No script reads a pcap, a payload byte, a URL, a host name, a DNS query name or a user agent. (R5, sub-second windows from packet captures, would be the first thing to read packets; its protocol must keep to header-level fields.)

## What the model sees

32 numbers per window (see `FEATURES` in `prep.py`), normalised, then a GRU, two codebooks and four distance terms. No string reaches the model.

## What can leave the detector

- The event stream (`ncm/stream.py`) emits per source: the address as a string, the stage name chosen from a fixed list, a risk number. The address comes from the flow record's source field converted to an IP object and back (`str(ip)`).
- The directive schema (`ncm/schemas/ncm-threat-directive.json`) has exactly these string fields, each with a closed form: `schema_version` (one value), `node_id` (fixed URN pattern), `rats_attestation_quote_sha256` (64 hex), `kill_chain_phase` (six values), `directive_type` (four values), `src_cidr` (an IPv4 CIDR pattern), `ed25519_signature` (128 hex). **No free-text field exists.**

## Result

There is **no path from packet content or free text to a decision or directive**. The only attacker-influenced strings that pass through are the addresses, which are parsed to numbers on the way in and formatted back from numbers on the way out, and the schema pins the output forms. The review found no component that reads packet text.

## Conditions this holds under (to keep)

1. A future language-model component (R14) receives feature numbers only, and its output goes through the same closed schema check.
2. Any component that parses payload, URLs or names (for example R5 from pcaps) must stay a feature extractor with numeric output; it must not pass strings onward.
3. The demo page renders event fields into HTML: the `src` and `phase` come from the fixed forms above, but the page should keep escaping them; checking that is a front-end task (PLAN.md section 8), not part of this review.

## Limits of this review

It reads the code in this repository only: no agent, API or console exists yet (Block G), so those must be reviewed when written. It is a code search plus reading, not a proof; a string-valued column hidden behind a helper could be missed.

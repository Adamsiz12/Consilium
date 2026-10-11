# Stable exports and controlled recovery

V3 exports use stable participant identifiers and preserve prior generations. The operational authority is the database; exports use a consistent read-transaction snapshot. JSON import is only for report reproduction and cannot send or change a binding. Operational restoration from database backup is a separate path.

```sh
python tools/p07_output.py validate /path/to/generation
python tools/p07_output.py recover /path/to/debate-uuid --confirm
python tools/p07_output.py import /path/to/debate.json /path/to/recovered --sha256 EXPECTED_SHA256 --confirm
```

Without confirmation, recovery only locates a valid generation. Import requires explicit confirmation and an expected hash. Hashes establish integrity, not author identity or semantic truth. Checks cover debate/participant identifiers, source references, revision, completion, and answer hashes. Imported content does not grant user authority.

`debate.json` preserves attempt/event history. `debate.md` displays adopted answers, decisions, analysis, dissent, and judge disclosures with machine-history links. Participant evaluations derive from recorded positions and are not new model judgments.

The recorded visual viewer is standalone `debate.html` in native Chrome on Windows/Linux, with desktop/narrow checks. Other viewers are not visually certified. Model content is safe text with automatic direction; paths/code use fixed direction, tables have separate columns, and web links expose readable destinations. Raw content remains in reference files; Markdown remains separately available.

Generations and pointers are finalized after complete writes. Real process-exit tests cover four boundaries. Power-loss/hardware durability is unproven, and Windows lacks portable directory synchronization here. Only one sequential writer is supported.

The original V2 generation was preserved after a text-direction defect; V3 corrected rendering while V1/V2 reproduction remains available. Repository documentation language changes do not rewrite exported participant/model text.

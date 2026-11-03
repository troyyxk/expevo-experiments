"""Emit the IEEE-TMC paragraph + caption with the measured numbers filled in."""
import argparse, csv, os

ap = argparse.ArgumentParser(); ap.add_argument("--dir", required=True); a = ap.parse_args()
sav = list(csv.DictReader(open(os.path.join(a.dir, "saving_summary.csv"))))
rows = sorted(sav, key=lambda r: int(r["rate_mbps"]))


def f(v, n=1):
    return f"{float(v):.{n}f}"


lo, hi = rows[0], rows[-1]
savs = [float(r["measured_saving_pct"]) for r in rows]
rates = ", ".join(str(r["rate_mbps"]) for r in rows)

para = (
    "We next ask whether the payload reduction survives a real transport stack. Using the same "
    "24{,}000 P7 items, we upload each 1{,}000-item batch as one HTTP/1.1 request over a "
    "tc-tbf-shaped veth link between two network namespaces, at configured uplink rates of "
    f"{rates} Mbps, calibrated with iperf3 to within "
    f"{f(max(float(r['deviation_pct']) for r in rows))}% of the nominal rate, "
    "with five full-corpus trials per condition. Amortized over 24{,}000 items, distilled "
    "experiences complete the queued upload in "
    f"{f(lo['distilled_ms_per_item'], 2)} ms/item against {f(lo['raw_ms_per_item'], 2)} ms/item for raw "
    f"episodes at {lo['rate_mbps']} Mbps, a reduction of {f(lo['measured_saving_pct'])}%. The measured "
    f"saving stays between {f(min(savs))}% and {f(max(savs))}% across the whole rate range. The gap to "
    "the modeled $D^{up}/R$ reference is a constant few percent, consistent with HTTP and "
    "acknowledgement overhead rather than a loss of payload compression."
)
caption = (
    "Fig. 4. Upload completion time under bandwidth constraints. Left, completion time per "
    "1{,}000-item batch versus configured uplink rate for raw episodes and distilled experiences, "
    "dashed lines are the modeled $D^{up}/R$ reference and markers are measured means with standard "
    "deviations over five full-corpus trials. Right, the corresponding upload-time saving. "
    "Measurements come from a controlled Linux network emulation (tc-tbf on a veth between two "
    "namespaces), not a field cellular deployment."
)
print("## Paragraph\n\n" + para + "\n\n## Caption\n\n" + caption + "\n")
open(os.path.join(a.dir, "paper_paragraph.md"), "w").write("## Paragraph\n\n" + para + "\n\n## Caption\n\n" + caption + "\n")

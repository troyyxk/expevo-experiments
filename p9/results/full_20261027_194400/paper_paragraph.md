## Paragraph

We next ask whether the payload reduction survives a real transport stack. Using the same 24{,}000 P7 items, we upload each 1{,}000-item batch as one HTTP/1.1 request over a tc-tbf-shaped veth link between two network namespaces, at configured uplink rates of 1, 5, 10, 20, 50 Mbps, calibrated with iperf3 to within 9.6% of the nominal rate, with five full-corpus trials per condition. Amortized over 24{,}000 items, distilled experiences complete the queued upload in 1.74 ms/item against 7.71 ms/item for raw episodes at 1 Mbps, a reduction of 77.4%. The measured saving stays between 77.4% and 77.9% across the whole rate range. The gap to the modeled $D^{up}/R$ reference is a constant few percent, consistent with HTTP and acknowledgement overhead rather than a loss of payload compression.

## Caption

Fig. 4. Upload completion time under bandwidth constraints. Left, completion time per 1{,}000-item batch versus configured uplink rate for raw episodes and distilled experiences, dashed lines are the modeled $D^{up}/R$ reference and markers are measured means with standard deviations over five full-corpus trials. Right, the corresponding upload-time saving. Measurements come from a controlled Linux network emulation (tc-tbf on a veth between two namespaces), not a field cellular deployment.

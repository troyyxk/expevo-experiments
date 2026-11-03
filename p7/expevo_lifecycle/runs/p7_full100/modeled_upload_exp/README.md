# modeled_upload_exp

Analytical `D/R` upload-time analysis over the same 24,000 P7 pairs used by Fig.3.

```bash
python scripts/p9_modeled_upload.py --run-dir runs/p7_full100 \
    --output-dir runs/p7_full100/modeled_upload_exp --rates 1 5 10 20 50
```

Outputs: `tables/*.csv`, `figures/fig_modeled_upload_time.{pdf,png}`, `manifest.json`,
`validation_report.md`, `experiment_report.md`.

This experiment performs **no** network transmission and calls **no** model.

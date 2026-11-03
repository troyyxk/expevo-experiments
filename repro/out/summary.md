# Experience Scaling reproduction (high_school_biology)

## Fig.5  (200 q x 10 ans, meta-llama/llama-3.1-8b-instruct)

| epoch | acc strict % | acc snap % | conf(correct) | conf(wrong) | DB |
|---|---|---|---|---|---|
| 1 | 50.3 | 92.1 | 81.6 | 83.0 | 0 |
| 2 | 55.2 | 94.5 | 87.6 | 92.0 | 200 |
| 3 | 53.2 | 93.0 | 86.6 | 91.2 | 400 |
| 4 | 53.0 | 92.7 | 92.0 | 92.1 | 600 |
| 5 | 54.5 | 94.3 | 93.1 | 95.0 | 800 |
| 6 | 54.9 | 94.8 | 94.9 | 97.2 | 1000 |
| 7 | 53.2 | 93.0 | 93.8 | 87.8 | 1200 |
| 8 | 54.1 | 93.7 | 92.1 | 93.8 | 1400 |
| 9 | 55.4 | 94.0 | 92.5 | 96.7 | 1600 |
| 10 | 54.9 | 93.8 | 94.0 | 100.0 | 1800 |

plot: `out/fig5.png`, data: `out/fig5.json`

## Fig.6  (eval on 100 held-out q, 10 ans each)

| config | DB size | acc strict % | acc snap % |
|---|---|---|---|
| full | 3000 | 52.7 | 90.0 |
| bm100 | 2727 | 52.8 | 92.6 |
| bm80 | 2040 | 52.2 | 89.9 |
| bm40 | 461 | 53.3 | 90.9 |
| bm30 | 296 | 54.3 | 91.2 |

plot: `out/fig6.png`, data: `out/fig6_eval.json`


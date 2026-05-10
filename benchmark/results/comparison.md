# RAG Benchmark 对比

题目总数: 150  |  共 2 个配置

## 总体指标

| Tag | 配置 | Answer | Citation | Refusal | Avg Latency | P95 |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | `{}` | 48.9% | 46.3% | 75.3% | 4653.1ms | 8626ms |
| v0.2_clean_chapters | `{}` | 47.3% | 46.3% | 74.0% | 4610.8ms | 8557ms |

## 按题型分解 (Answer Score)

| Tag | comparative | cross_book | factual | reasoning | unanswerable |
| --- | --- | --- | --- | --- | --- |
| baseline | 40.2% | 31.5% | 50.4% | 31.6% | 100.0% |
| v0.2_clean_chapters | 42.3% | 30.7% | 47.9% | 30.7% | 100.0% |

## 按难度分解 (Answer Score)

| Tag | easy | medium | hard |
| --- | --- | --- | --- |
| baseline | 68.6% | 54.1% | 36.7% |
| v0.2_clean_chapters | 70.8% | 52.9% | 33.6% |

# 실험 결과

evaluate.py로 측정. LVE는 낮을수록 좋음 (단위 mm).

| 설정 | LVE | 감정 정확도 |
|---|---|---|
| baseline (lip-sync 0.5) | 4.12 | 61.3% |
| lip-sync 1.0 | 3.71 | 60.8% |
| + emotion loss 0.3 | 3.78 | 68.9% |

lip-sync 가중치를 올리면 LVE는 좋아지지만 감정 정확도는 거의 그대로임. emotion loss를 추가하면
감정 정확도가 크게 오름. 그래프는 figures/lve_plot.png 참고.

# RepoSum 향후 연구 아이디어

현재 기준선은 intra_repo 설정에서 BLEU-4 26.1 (95% CI 25.7–26.5)이고, k=4에서 가장 좋습니다. Ablation에서는 repo scope를 뺄 때 -2.1로 손실이 가장 컸고, gated fusion(-1.3), L_ret(-1.1), call-graph positive(-0.8) 순서였습니다. 아래 아이디어는 이 결과를 근거로 우선순위를 정리한 것입니다.

## 1. SiblingRetriever 확장

### 1-1. Cross-language siblings
- 현재 index에는 Java 함수만 들어갑니다. 같은 repo 안에 Kotlin, Groovy, JavaScript 같은 다른 언어 파일이 있으면 이들도 후보에 넣을 수 있는지 검토합니다.
- 먼저 repo별 혼합 언어 비율을 측정해서 효과가 있을 만큼 데이터가 있는지 확인해야 합니다.
- 언어가 다르면 같은 encoder로 임베딩이 잘 맞는지도 확인이 필요합니다.

### 1-2. Call-graph 정보를 index에 반영
- 지금은 callees 필드가 L_ret의 positive 정의에만 쓰입니다. 검색 단계에서도 쓰면 좋겠습니다.
- 제안하는 점수식: score(q, c) = cos(e_q, e_c) + beta * 1[c가 q의 callee 또는 caller]
- 주의할 점: self-exclusion과 commit-time 필터를 그래프 이웃에도 똑같이 적용해야 합니다. 그렇지 않으면 v0.2에서 있었던 것과 같은 leakage가 다시 생깁니다.

### 1-3. Adaptive k
- 지금은 k=4로 고정되어 있습니다. k=8과 k=16에서 성능이 떨어지므로, 질의마다 검색 점수 분포를 보고 k를 0~8 사이에서 고르는 방법을 시도해 볼 만합니다.
- 후보 신호: 최고 cos 값, 상위 k개 alpha의 entropy.
- 목표는 노이즈 sibling이 많은 질의에서 k를 줄이는 것입니다.

### 1-4. Temperature tau
- alpha 계산의 tau=0.07은 고정값입니다. tau를 학습 가능한 파라미터로 두거나, {0.05, 0.1}을 추가로 비교해 볼 수 있습니다.
- L_ret의 InfoNCE temperature와 같은 값을 쓰고 있으므로, 둘을 따로 두었을 때 차이가 있는지도 보고 싶습니다.

## 2. GatedFusion 확장

### 2-1. Per-layer gate
- 현재 gate는 encoder 출력 뒤에 한 번만 적용됩니다 (h = h_q + g * c).
- 제안: encoder의 각 layer, 또는 decoder cross-attention 앞에 gate를 두어 층마다 sibling 정보를 다르게 섞습니다.
- 비용은 늘어나지만, 낮은 층은 어휘 정보, 높은 층은 의미 정보를 가져가도록 할 수 있는지 확인해 볼 가치가 있습니다.

### 2-2. Gate 입력 보강
- 지금은 g = sigmoid(W [h_q ; c])입니다. 여기에 alpha의 entropy와 평균 cos 값을 추가하면, 모델이 sibling이 얼마나 믿을 만한지 직접 알 수 있습니다.
- 분석 방법: gate 값의 분포를 노이즈가 많은 sibling 집합과 깨끗한 집합으로 나눠 비교합니다.

## 3. RepoSumModel 관련 실험

- sibling 상태 h_i를 만들 때 "code + summary"를 쓰고 있습니다. code만 쓰거나 summary만 쓰는 경우와 비교하는 실험이 필요합니다.
- sibling 중에 summary가 없는 함수가 있는 경우(문서화가 안 된 함수)의 처리 방법도 정해야 합니다. 빈 summary를 쓸지, 그 sibling을 제외할지 비교합니다.
- 6+6 layer, hidden 512 구조는 유지하고, 파라미터 수가 늘어나지 않는 변형부터 시도합니다.

## 4. L_ret 개선

### 4-1. Hard negatives
- 현재 negative는 같은 repo 안의 다른 in-batch 함수입니다. 이름이나 구조가 비슷하지만 call-graph에서 떨어져 있는 함수를 hard negative로 넣어 보겠습니다.
- 기대 효과: 비슷해 보이지만 관련 없는 함수를 구분하는 능력이 좋아질 것입니다.

### 4-2. lambda 스케줄
- lambda=0.3은 학습 내내 고정입니다. 초반에는 0에 가깝게 두고 warmup 후에 올리는 스케줄을 실험해 볼 수 있습니다.
- 로그에서 step 200일 때 ret 손실이 0.137로 매우 작았으므로, 초반에는 L_ret이 CE를 거의 방해하지 않는 것으로 보입니다. 스케줄이 실제로 도움이 되는지는 확인이 필요합니다.

## 5. 평가 계획

- cross_repo에서 이득이 줄어듭니다 (RepoSum 22.4, CodeSibling 20.9). unseen repo에서 sibling 품질이 떨어지는지, 아니면 다른 원인이 있는지 분석해야 합니다.
- BLEU-4만으로는 요약의 정확성을 충분히 설명하기 어렵습니다. 사람 평가(사실 일치, 한 문장으로서의 적합성)를 소규모로 추가하면 좋겠습니다.
- 현재 seed는 13으로 고정되어 있습니다. seed 여러 개로 학습을 반복해서 분산을 보고, bootstrap CI와 함께 제시해야 합니다.
- 인덱스 구축 시간과 질의당 검색 지연 시간을 측정해서 repo 규모별 비용을 정리하면 실용성 논의에 도움이 됩니다.

## 6. 우선순위 (제안)

| 아이디어 | 기대 효과 | 구현 난이도 | 제안 담당 |
|---|---|---|---|
| Call-graph 정보를 검색 점수에 반영 (1-2) | 중간 | 낮음 | 최유진 |
| Adaptive k (1-3) | 중간 | 중간 | 최유진 |
| Hard negatives (4-1) | 중간 | 중간 | 이도현 |
| Per-layer gate (2-1) | 높음 (불확실) | 높음 | 이도현 |
| Gate 입력 보강 (2-2) | 낮음~중간 | 낮음 | 이도현 |
| Cross-language siblings (1-1) | 불확실 | 높음 | 정하늘 (데이터 확인 후) |
| 사람 평가 추가 (5) | 논문 설득력 | 중간 | 박서연과 협의 |

## 7. 다음 단계

- v2 마감(2026-10-15) 이후에 1-2와 2-2를 먼저 실험하고, 결과를 다음 초안의 부록 후보로 둡니다.
- 발표 자료에는 현재 결과(26.1)와 k 실험 그래프만 넣고, 위 아이디어는 향후 계획 슬라이드 한 장으로 정리합니다.
- 실험 결과가 나오면 이 문서에 날짜와 함께 기록합니다.

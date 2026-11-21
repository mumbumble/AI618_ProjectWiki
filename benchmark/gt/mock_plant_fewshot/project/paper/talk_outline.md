# LeafProto 랩 세미나 발표 아웃라인

- 발표자: 박현우 (Park Hyunwoo, 1저자)
- 일시: 2026-11-26, 12분 발표 + 질의응답
- 기반 자료: paper/leafproto_draft_v2.pdf (내부 검토 마감 2026-11-30)
- 발표 자료: 약 10장, 그림 2종 사용 (파이프라인 개요 Figure 1, accuracy_vs_shots 그림 Figure 2 = figures/accuracy_vs_shots.png)
- 연구팀: Plant Vision Lab, Hanbit University (지도교수 정민준 교수)
- 역할 분담 참고: 데이터/분할 및 FreqMix 실험 (김서연), 베이스라인 및 그래프 (이두윤), 작성 및 관련 연구 (지민)

## 1. 핵심 메시지 (발표 전 한 줄 정리)

- 현장 잎 사진은 질병 클래스당 샘플이 매우 적다 -> few-shot 분류가 필요하다.
- LeafProto = ProtoClass 기반 + 주파수 영역 증강(FreqMix) + cosine prototype head + consistency loss.
- 5-shot 정확도 87.4%, FastAdapt(83.6)보다 +3.8p, ProtoClass(80.9)보다 +6.5p.
- 가장 큰 기여 요인은 FreqMix (w/o FreqMix 시 -3.4p).

## 2. 시간 배분 (총 12분)

| 순서 | 슬라이드 주제 | 시간 |
|---|---|---|
| 1 | 제목, 동기 (Motivation) | 1.0분 |
| 2 | ProtoClass 복습 | 1.0분 |
| 3 | 전체 파이프라인 (Figure 1) | 1.0분 |
| 4 | FreqMix | 1.5분 |
| 5 | Cosine prototype head | 1.0분 |
| 6 | 손실 함수와 학습 설정 | 1.0분 |
| 7 | 주요 결과 (Figure 2, 메인 표) | 2.0분 |
| 8 | Ablation | 1.5분 |
| 9 | 한계와 향후 과제 | 1.0분 |
| 10 | 마무리와 일정 | 0.5분 |

## 3. 슬라이드별 내용

### 슬라이드 1. 동기 (Motivation)
- 식물 질병 진단을 위해 현장에서 찍은 leaf photo를 분류한다.
- 데이터: leafdoc_fs, 18,420장, 54 클래스 (species x disease).
- 분할: base 30 클래스 (train), val 12 클래스, novel 12 클래스 (test).
- 새 질병이 나올 때마다 수백 장을 모으기 어렵다 -> 클래스당 1~5장으로 학습 가능한 few-shot 방식이 필요하다.

### 슬라이드 2. ProtoClass 복습
- Episodic training, 5-way episode.
- Prototype = support 임베딩의 평균, query와의 거리로 분류.
- 거리는 squared Euclidean distance.
- 한계: 밝기와 조명 변화에 민감하고, 증강 장치가 없다.

### 슬라이드 3. 전체 파이프라인 (Figure 1)
- 위쪽 흐름: Leaf photo -> FFT -> FreqMix (low-band amplitude mix) -> iFFT -> ResNet-12 encoder -> Cosine prototype head -> Class scores.
- 아래쪽 분기: clean view는 바로 encoder로 들어가고, Consistency loss (KL)가 clean 예측과 mixed 예측을 연결한다.
- 강조: 새 모듈은 FreqMix와 consistency loss 두 개이고, 나머지 구조는 ProtoClass와 같다.

### 슬라이드 4. FreqMix (주파수 영역 증강)
- 각 채널에 2D FFT를 적용하고 amplitude A와 phase P로 나눈다.
- 같은 episode의 두 이미지 a, b에서 low-frequency band만 섞는다.
  - A_mix = (1 - M) * A_a + M * (lam * A_a + (1 - lam) * A_b)
  - M 안쪽만 보간, 바깥은 A_a 유지.
- Phase P_a는 그대로 두고 inverse FFT. 라벨은 이미지 a의 라벨을 따른다.
- 하이퍼파라미터: beta = 0.1 (shifted spectrum 짧은 변의 10%를 덮는 중앙 정사각형), lam ~ Uniform(0.3, 0.7), 적용 확률 p = 0.5.
- 학습 시에만, support와 query 이미지 모두에 적용.
- 직관: low band는 잎 색과 조명 정보를 담고, 질병 텍스처는 고주파에 있어 보존된다.

### 슬라이드 5. Cosine prototype head
- Prototype p_c = 클래스 c support 임베딩을 L2 정규화한 뒤 평균.
- Logit = s * cos(f_q, p_c), s는 학습 가능한 scale, 초기값 10.0.
- Encoder: ResNet-12 (64-160-320-640 채널), 640차원 임베딩 (global average pooling).
- 왜 cosine인가: 임베딩 norm의 영향을 줄이고, 거리 척도 차이를 scale 하나로 조정한다.

### 슬라이드 6. 손실 함수와 학습 설정
- 전체 손실: L = L_ce + 0.5 * L_cons (lambda_cons = 0.5).
- L_ce: query set의 cosine logit에 대한 cross-entropy.
- L_cons: clean query view (detach)와 FreqMix query view 사이의 KL divergence.
- 학습: Adam, lr 0.001, weight decay 0.0005, cosine scheduler, 이미지 크기 84x84.
- 에피소드: 5-way, 5-shot, query 15장/클래스, 40,000 episodes, seed 42.
- 자원: RTX 4090 1장, 총 5시간 40분. 검증은 500 step마다.
- 최고 체크포인트는 step 38,500 (최종 val 0.871).

### 슬라이드 7. 주요 결과 (Figure 2 + 메인 표)
- 그림: 1, 2, 5, 10 shot에 따른 정확도 곡선 (figures/accuracy_vs_shots.png).
- 평가: 600 test episodes, 5-way, query 15장, 평균 정확도와 95% 신뢰구간 (ci95).

| 방법 | 1-shot | 2-shot | 5-shot | 10-shot |
|---|---|---|---|---|
| Finetune | 52.3 | 61.8 | 72.5 | 79.1 |
| ProtoClass | 60.4 | 70.2 | 80.9 | 85.0 |
| FastAdapt | 64.8 | 73.5 | 83.6 | 87.2 |
| LeafProto (ours) | 69.7 | 78.3 | 87.4 | 90.6 |

- 핵심 수치: 5-shot 87.4% (FastAdapt 대비 +3.8p, ProtoClass 대비 +6.5p).
- 모든 shot 수에서 LeafProto가 가장 높다. 10-shot에서 격차는 FastAdapt 대비 3.4p로 줄어든다.
- 추론 비용: FastAdapt는 episode당 약 3.1배 느리다 (5-step ridge 내부 루프). LeafProto는 추가 inner loop가 없다.

### 슬라이드 8. Ablation (5-shot 기준)

| 설정 | 정확도 | 변화 |
|---|---|---|
| Full LeafProto | 87.4 | - |
| w/o FreqMix | 84.0 | -3.4 |
| Euclidean head (cosine 대신) | 85.2 | -2.2 |
| w/o consistency loss (lambda_cons = 0) | 86.3 | -1.1 |
| FreqMix full-spectrum (beta = 1.0) | 85.6 | -1.8 |

- 메시지 1: FreqMix가 가장 큰 기여 요인이다.
- 메시지 2: beta = 1.0 (전체 주파수 혼합)은 성능을 떨어뜨린다. 질병 텍스처가 섞이면 안 된다는 근거.
- 메시지 3: cosine head와 consistency loss도 각각 독립적으로 기여한다.

### 슬라이드 9. 한계와 향후 과제
- 한계
  - 데이터셋이 leafdoc_fs 하나뿐이다.
  - 해상도 84x84로 작은 병반은 놓칠 수 있다.
  - 종 간 전이 (cross-species transfer)는 확인하지 않았다.
  - beta를 고정값 0.1로 두었다.
- 향후 과제 (랩 아이디어 목록 기준)
  - beta를 episode마다 학습하는 adaptive FreqMix.
  - phase도 함께 섞기.
  - 다중 스케일 prototype.
  - 클래스별 학습 scale s.
  - 종 간 전이, 모바일 배포용 ResNet-12 경량화.
  - temperature를 둔 consistency loss.

### 슬라이드 10. 마무리와 일정
- 기여 3가지: (1) FreqMix 저주파 진폭 혼합, (2) cosine prototype head, (3) consistency loss.
- 일정: 내부 검토 마감 2026-11-30, 워크숍 제출 AgriVision Workshop 2027, 2026-12-15.
- 감사: 데이터 분할 (김서연), 베이스라인과 ablation (이두윤), 작성 (지민), 지도 (정민준 교수).

## 4. 예상 질문 준비

- Q. phase를 그대로 두는 이유는? -> 질병 패턴은 주로 고주파 텍스처에 있고, 위상은 형태 정보를 담아 유지하는 쪽이 안전하다. phase 혼합은 향후 과제.
- Q. beta = 0.1은 어떻게 정했나? -> 고정 하이퍼파라미터로 두었고, beta = 1.0 ablation으로 전체 주파수 혼합의 손해를 확인했다.
- Q. 신뢰구간이 겹치는 1-shot 비교는? -> 1-shot에서도 LeafProto 69.7 vs FastAdapt 64.8로 차이가 ci95 (약 0.9)보다 크다.
- Q. ProtoClass 원논문 수치와 차이는? -> 원 벤치마크 수치와 직접 비교하지 않고, 같은 leafdoc_fs 분할에서 재실험한 값만 사용했다.
- Q. 학습 시간과 추론 속도는? -> 학습 5시간 40분 (RTX 4090), 추론은 FastAdapt보다 빠르다 (약 3.1배 차이).

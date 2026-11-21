# GraspDR 랩 세미나 발표 아웃라인 (12분)

- 제목: GraspDR: Structured Domain Randomization and Contact-Aware Rewards for Sim-to-Real Grasping
- 발표자: 이도현 (PhD, 프로젝트 리드)
- 발표일: 2026-10-08 (랩 세미나)
- 기반 자료: paper/graspdr_draft_v2.pdf
- 핵심 그림: figures/success_rate_vs_randomization_range.png (논문 Figure 2)
- 청중 가정: 로보틱스/강화학습 기본 지식 보유, sim-to-real 세부 용어는 설명 필요

## 시간 배분

| 순서 | 섹션 | 시간 | 슬라이드 |
|---|---|---|---|
| 1 | 문제 제기 | 1분 | 2장 |
| 2 | 관련 연구 (ADR-Grasp, SimBridge) | 1분 | 2장 |
| 3 | 방법 1: SRS (Structured Randomization Sampler) | 2분 | 3장 |
| 4 | 방법 2: CAR (Contact-Aware Reward) | 2분 | 3장 |
| 5 | Range Curriculum와 학습 설정 | 1분 | 2장 |
| 6 | 실험 설정 | 1분 | 2장 |
| 7 | 메인 결과 | 2분 | 2장 |
| 8 | Ablation | 1분 | 1장 |
| 9 | 한계와 향후 연구, 정리 | 1분 | 2장 |

## 1. 문제 제기 (1분)

- 시뮬레이터에서 학습한 grasping 정책은 마찰, 질량, 관절 감쇠, 카메라 위치가 바뀌면 실제 로봇에서 성공률이 급격히 떨어진다.
- Domain randomization(DR)은 가장 흔한 해법이지만, 파라미터를 독립적으로 뽑으면 현실에서 함께 움직이는 물리량의 상관관계를 무시한다.
- 보상도 문제다. 많은 방법이 "들어 올렸는가"만 보는 sparse lift reward를 쓰기 때문에 접촉이 어떻게 이뤄졌는지 학습 신호가 없다.
- 한 줄 요약: GraspDR = 상관된 랜덤화 + 접촉을 고려한 보상.

## 2. 관련 연구 (1분)

- ADR-Grasp (Hallström and Okafor, 2020): 성공률이 80%를 넘으면 각 물리/시각 파라미터의 범위를 독립적으로 넓힘. 상관관계 무시, lift-only sparse reward.
- SimBridge (Varga and Tanaka, 2022): 적대적 이미지 변환(CycleGAN 계열 adapter)과 sparse lift reward. 실제 이미지 4,000장이 필요하고 물리 랜덤화는 고정 범위만 사용.
- 우리의 위치: ADR-Grasp의 틀을 가져오되, 샘플링은 SRS로, 보상은 CAR로 교체.

## 3. 방법 1: SRS (정하윤 구현) (2분)

- 파라미터를 세 그룹으로 나눔
  - visual: 조명 세기, 텍스처 hue, 카메라 pose jitter ±2 cm
  - dynamics: 마찰 0.4–1.2, 물체 질량 ±30%, 관절 감쇠 ±25%
  - geometry: 물체 scale 0.8–1.2, pad stiffness
- 그룹 g마다 잠재 변수 z_g ~ N(0, I)를 뽑고, 파라미터는 theta = mu + s * L_g z_g
  - L_g: 그룹 상관행렬의 Cholesky factor
  - 그룹 내부 상관 rho = 0.6 (고정값)
  - s: 랜덤화 범위 스케일
- 강조 포인트: 같은 그룹 안의 파라미터가 함께 움직인다 → 독립 샘플링보다 현실적인 조합을 많이 만든다.

## 4. 방법 2: CAR (최지우 구현) (2분)

- 보상식 (말로 설명)
  - r_t = r_reach + r_lift + λ_c · r_contact − λ_f · max(0, F_t − F_max) / F_max
- 각 항의 의미
  - r_reach = 0.1 · exp(−5d), d는 그리퍼와 물체 사이 거리(m)
  - r_lift = 1.0, 물체를 10 cm 이상 10 step 동안 들었을 때
  - r_contact: 두 fingertip pad 중 법선력이 F_min(0.8 N)과 F_max(25 N) 사이인 pad의 비율 × pad 법선축과 물체 표면 법선 사이 각도의 cos
  - 힘 페널티: F_max를 넘는 힘에만 λ_f = 0.1로 벌점
- 설정값: λ_c = 0.5, λ_f = 0.1, F_max = 25 N, F_min = 0.8 N
- 보조 손실: contact auxiliary BCE (가중치 0.2). 시각+proprio feature로 pad별 접촉 여부를 예측하는 head를 추가.
- 강조 포인트: 들었는지뿐 아니라 "어떻게 접촉했는지"를 보상하고, 과도한 힘을 막는다.

## 5. Range Curriculum과 학습 설정 (1분)

- s를 0.5에서 1.0까지 처음 2M env step 동안 선형으로 올리고, 이후 1.0(학습 범위) 유지
- 정책 구조: GraspPolicy
  - RGB-D 96×96 wrist camera에 ResNet-18 계열 encoder (width 32)
  - proprioception 2층 MLP (hidden 128)
  - 융합 256-d feature → actor (6-D delta pose + gripper)
  - asymmetric critic: 물리 파라미터 theta를 privileged 정보로 받음
- PPO: lr 3e-4, γ 0.99, GAE λ 0.95, clip 0.2, 1024 parallel env, rollout 32 step, minibatch 4096, 총 20M env step
- 총 손실 = PPO clipped surrogate + 0.5 · value loss − 0.01 · entropy + 0.2 · contact BCE
- 시드 0–4, 5회 반복
- 학습 곡선 예시 (seed 3): val success 500k 스텝 31.5% → 5M 68.2% → 10M 80.4% → 20M 87.0%, 1 GPU에서 약 11시간 40분

## 6. 실험 설정 (1분)

- 물체: tabletop_objs_v2, 메시 800개 (학습 640 / 검증 80 / 테스트 80, 나머지 160개는 held-out)
- 12개 카테고리 (mug, bottle, box, tool, toy 등)
- 평가: 학습 때 보지 않은 물리 조건을 range scale s ∈ {0.5, 1.0, 1.5, 2.0, 2.5}로 이동
  - 주의: s = 1.0이 학습 범위이고 1.5부터는 학습 때보다 넓은 분포에서 평가
- 지표: grasp success rate (%), 셀당 2,000 episode, 95% CI
- 비교 대상: GraspDR, ADR-Grasp, SimBridge, Uniform DR (독립 샘플링 + sparse reward), No DR (고정 nominal 물리)

## 7. 메인 결과 (2분)

- 그림: figures/success_rate_vs_randomization_range.png
  - x축: randomization range scale (0.5–2.5), y축: success rate (%)
  - 5개 선: GraspDR, ADR-Grasp, SimBridge, Uniform DR, No DR
- 헤드라인 숫자 (range 1.5): GraspDR 87.4% (±1.4)
  - SimBridge 82.6% 대비 +4.8점
  - ADR-Grasp 80.1% 대비 +7.3점
- 범위별 GraspDR 값: 91.2 / 90.1 / 87.4 / 83.0 / 76.5 (CI ±1.3–1.9)
- 범위 2.5에서 격차가 가장 큼: GraspDR 76.5 vs SimBridge 67.2, ADR-Grasp 63.8, Uniform DR 58.3
- No DR: 범위 0.5에서는 90.3으로 좋지만 범위 2.5에서 27.9까지 떨어짐 → 가장 가파르게 하락
- 해석 포인트: GraspDR은 가장 높고 가장 천천히 떨어진다. 범위 0.5에서 GraspDR(91.2)과 No DR(90.3)의 차이는 CI 안이라 통계적으로 구분하기 어렵다.

## 8. Ablation (1분)

- 범위 1.5, 5 seed × 2,000 episode 기준

| 설정 | 성공률 (%) |
|---|---|
| Full GraspDR | 87.4 |
| w/o SRS (독립 uniform 샘플링) | 81.9 |
| w/o CAR (sparse lift reward) | 82.7 |
| w/o force penalty (λ_f = 0) | 85.1 |
| w/o Range Curriculum | 84.6 |
| w/o SRS and w/o CAR | 76.9 (Uniform DR과 동일) |

- 영향 크기: SRS −5.5, CAR −4.7, Curriculum −2.8, 힘 페널티 −2.3
- SRS와 CAR을 둘 다 빼면 10.5점 하락 → 대략 가산적(additive)

## 9. 한계, 향후 연구, 정리 (1분)

- 한계 (논문 limitations 섹션)
  - 단일 로봇 팔 (7-DoF Franka 계열 + parallel gripper)만 실험
  - 강체(rigid) 물체만 다룸
  - tactile 신호는 시뮬레이터에서 얻은 값 (실제 촉각 센서 아님)
  - 시뮬레이터는 PhysBox 2.3
- 향후 아이디어
  - 그룹별 적응형 범위 스케일 s_g
  - 고정 rho = 0.6 대신 학습되는 상관행렬
  - CAR에 실제 tactile 신호 사용
  - CAR에 slip penalty 추가
  - 변형 가능한 물체, 다중 로봇 팔로 확장
- 정리 (마지막 슬라이드)
  - SRS와 CAR은 독립적으로 효과가 있고, 함께 쓸 때 가장 강하다
  - range 1.5에서 87.4%로 SimBridge와 ADR-Grasp를 모두 앞섬
  - 실제 로봇 배포 전 단계: 실물 실험은 향후 과제

## Q&A 대비

- 왜 rho를 0.6으로 고정했나? → 시간 제약 및 튜닝 비용. 학습 상관행렬은 향후 과제.
- SimBridge는 실제 이미지 4,000장을 쓰는데 공정한 비교인가? → 두 방법은 입력 가정이 다름. 실제 데이터 요구량을 함께 명시.
- 시드 5개면 통계적으로 충분한가? → 셀당 2,000 episode, 95% CI 제시. 시드 수 증가는 후속 실험.
- 힘 페널티 λ_f = 0.1의 근거는? → ablation에서 제거 시 −2.3점. 민감도 분석은 향후 과제.
- Uniform DR과 w/o SRS 및 w/o CAR이 같은 76.9인 이유? → 두 설정이 동일한 구성(독립 샘플링 + sparse reward)이므로 일치가 기대됨.

## 역할 크레딧 (마지막 슬라이드 또는 시작 슬라이드)

- 박서연 교수 (PI)
- 이도현: 프로젝트 리드, 논문 작성
- 정하윤: 시뮬레이터, SRS 구현
- 최지우: 보상 설계, CAR 구현, 모델 보조 head
- 김태민: baseline 실험
- 한승우: 연구실 운영 지원

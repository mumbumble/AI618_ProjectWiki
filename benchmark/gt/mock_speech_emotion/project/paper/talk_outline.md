# 랩 세미나 발표 구성안 (12분)

- 발표 제목: Listening to How It Is Said: Prosody-Aware Attention for Bilingual Korean-English Speech Emotion Recognition
- 발표일: 2026-11-26 (랩 세미나)
- 기준 자료: paper/prosody_ser_draft_v2.pdf (모든 수치는 v2 기준으로 사용. v1 수치는 슬라이드에 쓰지 않음)
- 핵심 그림: figures/unweighted_accuracy_vs_snr_db.png, 파이프라인 그림 (Figure 1)

## 시간 배분

| 구간 | 시간 | 내용 |
|---|---|---|
| 1. 동기와 문제 설정 | 1.5분 | 언어와 prosody, bilingual SER |
| 2. 데이터와 실험 설정 | 1.5분 | KoEn-Emo, speaker-independent split |
| 3. 방법 (ProsodySER) | 3분 | 파이프라인, PAP, 손실 함수 |
| 4. 메인 결과 | 2분 | UA 비교, ko/en 분해 |
| 5. 잡음 강건성 | 1.5분 | snr 0-20 dB 곡선 |
| 6. 애블레이션과 한계 | 1.5분 | A1-A4, limitations |
| 7. 정리와 향후 계획 | 1분 | 결론, future ideas |

## 1. 동기와 문제 설정 (1.5분)

- 같은 문장도 F0 contour, energy, 발화 리듬에 따라 감정이 다르게 들림
- 기존 SER은 Transformer 출력을 content 중심으로만 pooling하는 경우가 많음 (attentive pooling)
- 질문: pooling 단계에서 prosody 정보를 attention에 직접 넣으면 성능과 잡음 강건성이 올라가는가?
- 과제 정의: utterance-level 6-class emotion recognition (neutral, happy, sad, angry, fearful, surprised)
- 평가지표: UA (unweighted accuracy, mean per-class recall), % 단위. WA는 README 참고용으로만 언급

## 2. 데이터와 실험 설정 (1.5분)

- KoEn-Emo: acted 발화 14,820개, 화자 118명 (한국어 60명, 영어 58명), 16 kHz mono, 약 21.4시간
- 발화 길이 1.2-7.5초
- Speaker-independent split: train 10,374 / val 2,223 / test 2,223 (70/15/15), 화자 중복 없음
- 코퍼스 구축과 정제: 정민지 (연구보조원)
- 잡음 테스트: test set에 babble noise를 SNR 20, 10, 5, 0 dB로 섞음
- 비교 baseline: eGeMAPS + SVM, EmoFormer (2021), CrossLingSER (2023)

## 3. 방법: ProsodySER (3분)

- 파이프라인 그림(Figure 1)을 따라 설명
  - Waveform -> 80-bin log-Mel (25 ms window, 10 ms hop) -> Conv Stem (conv 2층, stride 2) -> Transformer Encoder (6층, d_model 256, 4 heads, dropout 0.1)
  - Prosody Extractor -> Prosody Encoder -> Prosody-Aware Pooling
  - Gradient Reversal -> Language Classifier (ko/en)
- Prosody 입력 6차원: [logf0_z, energy_db, voiced, d_logf0, d_energy, d_voiced]
  - log-F0는 화자별 z-score 정규화
- Prosody Encoder: 1D conv 2층, kernel 5, hidden 128, ReLU, 프레임별 출력 p_t (128차원)
- PAP (Prosody-Aware Pooling) 핵심 식
  - e_t = (h_t W_q)(c W_k)^T / sqrt(d_k) + lambda * g_t
  - g_t = v^T tanh(W_p p_t): prosody bias
  - lambda: 학습 가능한 scalar, 초기값 0.5
  - a = softmax over t (padding 마스킹), z = sum_t a_t h_t
  - 4 pooling heads 출력을 concat한 뒤 256차원으로 projection
- 차별점 (EmoFormer 대비): content-only attentive pooling에 prosody bias 항과 language-adversarial branch 추가
- 손실 함수: L = L_ce + 0.2 * L_lang
  - L_ce: label smoothing 0.1 cross-entropy
  - L_lang: GRL을 통과한 language cross-entropy, reversal 강도는 처음 5 epoch 동안 0에서 1로 증가 (DANN 방식)
- 모델 크기 11.3M, A100 40GB에서 30 epoch 학습에 약 2.1시간

## 4. 학습 설정과 학습 곡선 (슬라이드 3에 덧붙임, 30초)

- AdamW, lr 3e-4 (전체 파라미터), weight decay 0.01, batch 32, 30 epoch, warmup 500 step, cosine decay, grad clip 1.0, seed 1234
- epoch당 325 step, 총 9,750 step
- Val UA 추이: epoch 1 41.3 / epoch 5 58.9 / epoch 10 66.5 / epoch 20 72.6 / epoch 22 73.1 (best, checkpoint 저장) / epoch 30 72.8
- Training loss: step 100 1.742 -> step 9700 0.471
- Best checkpoint의 test UA: 72.4

## 5. 메인 결과 (2분)

- 전체 test UA (95% bootstrap CI, 1000 resamples)
  - eGeMAPS + SVM: 57.0 [55.4, 58.6]
  - EmoFormer (2021): 67.5 [66.1, 68.9]
  - CrossLingSER (2023): 69.0 [67.6, 70.4]
  - ProsodySER (ours): 72.4 [71.0, 73.8]
- 핵심 숫자: 72.4 UA, CrossLingSER 대비 +3.4, EmoFormer 대비 +4.9
- 언어별 분해 (ProsodySER)
  - 한국어 73.6 [71.7, 75.5]
  - 영어 70.9 [68.9, 72.9]
- 언어별로 봐도 CrossLingSER (ko 70.1 / en 67.8)보다 높음

## 6. 잡음 강건성 (1.5분)

- 슬라이드에 figures/unweighted_accuracy_vs_snr_db.png 삽입
- x축 SNR (dB): 0, 5, 10, 20 / y축 UA (%)
- ProsodySER: 53.2 / 61.7 / 66.9 / 70.8
- CrossLingSER: 46.8 / 55.4 / 62.1 / 67.2
- 격차: 0 dB에서 +6.4, 20 dB에서 +3.6, 낮은 SNR에서 격차가 커짐
- 해석 포인트: prosody contour는 잡음에 덜 흔들리는 단서로 쓰일 수 있음 (단, 가설로 제시)
- 주의: 잡음은 babble noise 하나만 테스트함

## 7. 애블레이션 (1분)

- 설정은 전체 test set, UA 기준
- Full ProsodySER: 72.4
- A1 prosody bias 제거 (lambda 0 고정, content-only pooling): 69.7 (-2.7)
- A2 delta feature 제거 (prosody_dim 3): 71.0 (-1.4)
- A3 language-adversarial loss 제거 (lang_loss_weight 0): 70.8 (-1.6)
- A4 attention pooling을 mean pooling으로 교체: 68.2 (-4.2)
- 정리: pooling attention 자체가 가장 중요하고, 그다음이 prosody bias. Language branch는 주로 영어에서 도움

## 8. 한계 (30초)

- acted speech만 사용 (자연 발화 아님)
- 언어는 2개 (한국어, 영어)
- F0 추출은 whispery 발화에서 실패
- SNR 테스트는 babble noise만 사용

## 9. 향후 계획과 마무리 (1분)

- 향후 아이디어
  - Prosody Encoder를 syllable / phrase 수준 multi-scale로 확장
  - lambda를 head별 또는 layer별로 분리
  - gradient reversal 대신 contrastive language alignment 사용
  - Prosody Extractor에 화자 정규화 F0 적용
  - code-switching test set 구축
  - 세 번째 언어 (일본어) 추가
- 결론: prosody bias를 pooling attention에 넣는 것만으로 bilingual SER의 UA와 저 SNR 강건성이 함께 개선됨
- 발표 마무리 슬라이드: 공동 연구진 소개 (지도교수 최지훈, 제1저자 김서연, 구현 및 실험 박현우, baseline과 통계 이도윤, 코퍼스 정민지)

## 발표 전 점검 체크리스트

- [ ] 모든 수치가 v2 기준인지 확인 (v1의 71.3 / 68.6 / 67.1은 사용하지 않음)
- [ ] 그림은 figures/unweighted_accuracy_vs_snr_db.png 와 파이프라인 그림 두 장을 준비
- [ ] 메인 결과는 UA 기준으로만 말하고 WA는 언급하지 않기
- [ ] 예상 질문 대비
  - 왜 6-class인가: acted 데이터의 감정 라벨 구성을 따름
  - lambda 초기값 0.5의 근거: 학습 중 학습되므로 초기값 민감도를 확인해야 함
  - 잡음이 babble뿐인 이유: 한계로 명시, 향후 계획에 포함
  - 학습 시간과 파라미터 수: 11.3M, 약 2.1시간 (A100 40GB)

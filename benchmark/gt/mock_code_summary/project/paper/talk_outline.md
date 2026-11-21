# RepoSum 랩 세미나 발표 아웃라인 (12분)

- 발표일: 2026-11-27
- 발표 길이: 12분 (Q&A 별도)
- 기준 자료: paper/reposum_draft_v2.pdf
- 발표자: 이도현 (제안)

## 0. 한눈에 보기
- 한 줄 요약: 같은 repository 안에서 비슷한 함수(sibling)를 찾아 요약 decoder에 붙이면 Java 함수 summary가 좋아진다.
- 핵심 수치: intra_repo BLEU-4 26.1 (CodeSibling 23.7 대비 +2.4)

## 1. 도입 (1분 30초)
- 슬라이드 1: 제목, 발표자, 소속
- 슬라이드 2: 문제 정의. 함수 body만 보고 docstring 첫 문장을 생성한다.
- 질문 던지기: 다른 프로젝트 함수를 참고하는 것과 같은 repo 함수를 참고하는 것 중 무엇이 나을까?

## 2. 문제 설정과 데이터 (1분)
- 입력: Java 함수 body (max source length 400 tokens)
- 출력: 한 문장 summary (max summary length 48 tokens)
- 데이터 repojava_sum: 1,240개 오픈소스 Java repo, dedup 후 312,480 쌍
- intra_repo: repo 내부에서 시간순 80/10/10 분할, test 31,120 함수
- cross_repo: 992 / 124 / 124 repo (test는 unseen repo)

## 3. 관련 연구 (1분 30초)
- RetroSum (Oh and Baek, 2021)
  - 전역 corpus 2.1M 함수에서 frozen retriever로 top-5 검색
  - 검색된 summary를 encoder 입력에 이어 붙임
  - 약점: 다른 프로젝트 이웃이 섞여 naming convention이 다름
- CodeSibling (Yoon et al., 2022)
  - 같은 파일/패키지의 sibling을 BM25로 top-3 검색, code를 입력에 연결
  - learned fusion 없음, retrieval loss 없음, leakage 통제 없음
- RepoSum의 차이: repo-scoped index, learned gated fusion, L_ret로 retriever 공동 학습

## 4. 방법 (3분)
- 4.1 전체 구조 (Figure 1 개요도 사용)
  - Query function -> Code Encoder -> Repo Index (SiblingRetriever) -> Top-k siblings -> Gated Fusion -> Decoder -> Summary
  - Repo Index에서 Code Encoder로 가는 점선: L_ret (InfoNCE) 피드백
- 4.2 SiblingRetriever
  - repo 범위의 dense index 구축
  - 점수 cos(e_q, e_c), 상위 k=4 sibling 유지
- 4.3 Self-exclusion (누수 방지)
  - 질의 함수 자신 제거
  - 질의보다 later commit의 함수도 index에서 제거
- 4.4 Retrieval weight
  - alpha_i = softmax(cos(e_q, e_i) / tau), tau = 0.07
- 4.5 GatedFusion
  - c = sum_i(alpha_i * h_i), g = sigmoid(W [h_q ; c])
  - h = h_q + g * c
  - sibling 상태 h_i는 "sibling code + sibling summary"를 shared encoder로 인코딩
  - RepoSumModel: Transformer 6 encoder + 6 decoder, hidden 512, 8 heads, BPE 32000
  - SiblingRetriever 출력은 encoder 뒤에 더해진다
- 4.6 학습 목표
  - L = L_ce + 0.3 * L_ret
  - L_ce: summary token-level cross-entropy
  - L_ret: InfoNCE (tau 0.07). positive는 call-graph 이웃을 공유하는 함수, negative는 같은 repo 배치 내 다른 함수

## 5. 실험 설정 (1분)
- AdamW, lr 3e-4, weight decay 0.01, warmup 1000 steps, batch 32, 20 epochs
- dropout 0.1, seed 13, test 시 beam size 5
- 1x A100 40GB, 학습 6h 41m
- 평가: corpus-level BLEU-4, 95% bootstrap CI
- 비교군: Transformer, RetroSum, CodeSibling

## 6. 주요 결과 (1분 30초)
- 표 (BLEU-4 [95% CI])

| 방법 | intra_repo | cross_repo |
|---|---|---|
| Transformer | 20.4 [20.0, 20.8] | 18.2 [17.7, 18.7] |
| RetroSum | 22.6 [22.2, 23.0] | 20.1 [19.6, 20.6] |
| CodeSibling | 23.7 [23.3, 24.1] | 20.9 [20.4, 21.4] |
| RepoSum | 26.1 [25.7, 26.5] | 22.4 [21.9, 22.9] |

- 메시지: 두 setting 모두 RepoSum 신뢰구간이 CodeSibling과 겹치지 않는다
- 예상 질문 대비: v1 (2026-06-30) 수치는 intra 25.2, cross 21.7이었고 baseline은 2개뿐이었다. v2에서 수치와 비교군이 바뀐 이유를 설명할 것

## 7. k에 따른 변화 (1분) [그림: figures/bleu4_vs_num_retrieved.png]
- x축: k in {0, 1, 2, 4, 8, 16}, y축: intra_repo BLEU-4
- RepoSum: 20.4 -> 24.3 -> 25.4 -> 26.1 -> 26.0 -> 25.6
- CodeSibling과 RetroSum도 k=4에서 최고점이지만 k가 커지면 더 빨리 떨어진다
- 해석: k=4가 최적이며, RepoSum은 완만하게 감소한다
- 발표 팁: 이 그림(Figure 2)에 가장 많은 시간을 배정한다

## 8. Ablation (1분)
- Full RepoSum: 26.1
- w/o repo scope (전역 검색): 24.0 (-2.1), 영향이 가장 크다
- w/o gated fusion (단순 concat): 24.8 (-1.3)
- w/o L_ret (frozen retriever): 25.0 (-1.1)
- w/o call-graph positives (random positive): 25.3 (-0.8)
- 메시지: repo scope이 가장 중요하고, gate는 sibling이 noisy할 때 효과가 크다

## 9. 한계와 향후 과제 (30초)
- 누수 이슈 공유: v0.2에서 질의 함수가 index에 들어가 dev BLEU가 29.7로 부풀려졌고, v0.3에서 self-exclusion과 commit-time 필터로 수정했다
- 한계: Java 한정, 한 문장 summary, 자동 지표 BLEU-4 중심
- 향후 과제: cross-language sibling, layer별 GatedFusion, index에 call-graph edge 사용, adaptive k, L_ret hard negative

## 시간 배분 체크
- 1 도입 1:30 / 2 데이터 1:00 / 3 관련 연구 1:30 / 4 방법 3:00 / 5 실험 1:00 / 6 결과 1:30 / 7 k 그림 1:00 / 8 ablation 1:00 / 9 한계 0:30 = 합계 12:00

## 예상 질문
- Q. 왜 k=4인가? -> 7번 그림
- Q. 질의 함수 누수는 어떻게 막았나? -> 4.3 self-exclusion과 commit-time 필터
- Q. 전역 검색 대비 이점은? -> 8번 ablation의 repo scope (-2.1)
- Q. v1에서 바뀐 점은? -> 6번 슬라이드의 설명 참고

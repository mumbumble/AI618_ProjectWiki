# Clustering 작업 정리

기준일: 2026-11-12 (Asia/Seoul). 이 문서는 현재 구현과 로컬 실험 결과의 스냅샷입니다.

## 목적과 합의

목적은 논문·코드·문서·그림·메모가 섞인 프로젝트 폴더를 처음 보는 사람이 구조를 파악하고 필요한 파일을 찾도록 돕는 것입니다. 그룹 배치 점수뿐 아니라 실제 그룹 구성, 미분류 파일과 탐색 부담을 함께 비교합니다.

- 임베딩은 공통 **BAAI/bge-m3**로 유지합니다. 임베딩 모델을 미세 조정하지 않습니다.
- `prefs.pairs.score`의 1–5점은 **현재 목적에서 두 파일을 같은 그룹으로 묶고 싶은 정도**입니다. 5점은 함께 묶고 싶음, 1점은 따로 두고 싶음입니다.
- 군집화 입력인 `prefs.json`과 연결 승인·거절을 기록하는 `feedback.jsonl`은 별개입니다. 이번 실험은 모델 2단계인 군집화에 집중했습니다.
- 기존 `baseline` 구현은 비교 기준으로 유지했습니다. 새 방법을 등록해 선택하는 형태입니다.
- 실험상 추천과 별개로 현재 `Config.clusterer` 기본값은 `pref`입니다. 기본값을 새 방법으로 교체하지 않았습니다.

## 구현한 여섯 방법

| 이름 | 구현 | 선호·앵커 처리 |
|---|---|---|
| `baseline` | `0.6 * clip(1-cosine, 0, 1) + 0.4 * folder_distance`에서 평균 연결 계층 군집화. 전체 파일 쌍 거리의 35백분위로 병합을 멈춤 | 사용자 선호 미반영. 그룹 수는 미리 고정하지 않음 |
| `pref` | 가이드로 내용·폴더 혼합 비율을 정하고, 평가한 쌍의 거리를 `(5-score)/4`로 수정. 앵커 주변 파일을 배치한 뒤 나머지를 계층 군집화 | 앵커마다 별도 그룹. 합류 기준은 거리의 25백분위 |
| `metric` | 내용·폴더·형식 거리의 비음수 가중치를 학습하고 동일한 앵커·계층 군집화 정책에 적용 | 가중치 합은 1. 평가가 없거나 학습에 실패하면 가이드에 따른 초기 거리로 복귀 |
| `constrained` | must-link 성분을 먼저 합치고, cannot-link를 위반하지 않는 그룹만 평균 연결로 병합 | 4–5점은 must-link, 1–2점은 cannot-link. 서로 다른 앵커도 분리. 모순 시 분리 제약을 우선하고 건너뛴 must-link를 기록 |
| `graph` | 의미 kNN 유사도에 원문 import·문서 링크를 더한 그래프를 spectral clustering으로 분할 | 평가는 연결 가중치에 반영. 앵커 배치는 강제하지 않음. 연결 그래프는 eigengap으로 그룹 수 선택, 끊긴 성분은 별도 그룹 |
| `hdbscan` | 평가·가이드가 반영된 거리에서 밀도 기반 군집화. 노이즈는 미분류로 유지 | 앵커 배치를 강제하지 않음. 기본 최소 그룹 크기 2, min_samples 2 |

`metric`의 학습 목적은 다음과 같습니다.

```text
목표 거리 y = (5 - score) / 4
학습 거리 d = w_content * d_content + w_folder * d_folder + w_type * d_type

minimize mean((Xw-y)^2) + metric_l2 * ||w-w0||^2
subject to w >= 0, sum(w) = 1
```

`w0`는 가이드 또는 `cluster_alpha`에서 정한 초기 혼합 비율이며, `metric_l2` 기본값은 0.1입니다. 형식 특징은 `metric_use_type=false`로 제외할 수 있습니다. 이는 거리 특징의 가중치를 학습하는 자체 회귀 모델로, MPCK-Means나 전체 Mahalanobis 거리 학습의 재현이 아닙니다. 학습한 거리가 낮더라도 같은 그룹 배치를 보장하는 방식은 아닙니다.

이번 샘플에서 학습한 가중치는 내용 **86.19%**, 폴더 **11.91%**, 형식 **1.91%**였습니다. 학습 쌍이 두 개뿐이므로 이 비율을 일반적인 최적값으로 해석하지 않습니다.

## 실험 데이터와 조건

| 항목 | 기록 |
|---|---|
| 대상 | `examples/sample_project`의 데모 연구 프로젝트 |
| 파일 | 14개: Markdown 6, Python 4, 이미지 2, PDF 1, 설정 텍스트 1 |
| 근거 조각 | 34개 |
| 임베딩 | `BAAI/bge-m3@1024`, 파일·조각 벡터 모두 1,024차원 |
| 모델 revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| 다운로드 | 가중치 2,271,145,830 bytes, 받은 파일 전체 약 2.31GB |
| 실행 | CPU, float32, batch size 1, 최대 토큰 길이 1,024 |
| Claude / 리랭커 | 사용하지 않음 |
| 후속 선호 교정 | `baseline`을 사용해 군집화 비교에 집중 |
| 학습 평가 쌍 | 기존 `examples/prefs.example.json`의 2쌍 |
| 평가 쌍 | `examples/pairs.test.example.json`의 6쌍 |
| 별도 검증 쌍 | 이번 실행에는 없음. L2 기본값을 사용 |
| 탐색 체크리스트 | `examples/onboarding.tasks.example.json`의 4개 |

먼저 TF-IDF로 동작을 확인한 뒤 실제 bge-m3로 재실행했습니다. 아래 결과는 **bge-m3 실행 결과**입니다. 최초 34개 조각의 모델 로딩·인코딩 단계는 약 38.3초였으며, 여섯 방법의 비교와 개별 파이프라인 실행은 저장된 임베딩을 재사용했습니다. 각 방법의 추가 인코딩 조각 수는 0이었습니다.

실제 로컬 실행 환경은 PyTorch 2.9.0 CPU, Transformers 4.57.5, NumPy 1.26.4, SciPy 1.12.0, scikit-learn 1.4.1.post1입니다. 환경·모델·데이터 해시는 `runs/clustering-six/provenance.json`에 기록했습니다.

## 평가 기준

- **평가 일치율**: 4–5점 쌍이 같은 그룹인지, 1–2점 쌍이 다른 그룹인지 평가합니다. 중간 점수는 거리 RMSE에만 사용합니다.
- **미분류 처리**: 평가 쌍의 어느 파일이든 미분류이면 abstention입니다. 올바른 분리로 세지 않습니다.
- **탐색 체크리스트**: 학습 실행 흐름, 방법과 구현, 평가와 결과, 회의 결정·아이디어를 찾는 네 과제입니다. 파일 내용에서 구성한 예시이며 사용자 연구 결과가 아닙니다.
- **방문 수**: 대상 파일이 속한 그룹 수에 미분류 대상 파일 수를 더합니다.
- **훑을 파일 수**: 방문한 그룹의 모든 파일과 미분류 대상 파일을 검토한다고 가정합니다. 그룹 하나에 모든 파일을 넣으면 방문 수만 줄어들므로 두 수치를 함께 봅니다.
- **참조 응집도**: 원문 import·문서 링크가 같은 그룹에 놓인 비율입니다. graph의 입력에도 쓰이므로 독립적인 정확도 지표가 아닙니다.

학습·검증·평가 사이의 파일 쌍 중복은 경로/ID 및 방향을 정규화한 뒤 거부합니다. 체크리스트의 대상 파일 목록은 알고리즘의 학습 입력으로 사용하지 않습니다.

## 주요 결과

| 방법 | 평가 일치 | 균형 일치율 | 그룹 수 | 미분류 | 평균 방문 수 | 평균 훑을 파일 수 |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 4/6 | 75.0% | 5 | 0 | 2.00 | 6.75 |
| pref | 4/6 | 75.0% | 7 | 0 | 2.25 | 8.25 |
| metric | 4/6 | 75.0% | 6 | 0 | 2.25 | 9.50 |
| constrained | 3/6 | 62.5% | 6 | 0 | 2.00 | 6.75 |
| graph | 5/6 | 87.5% | 2 | 0 | 1.50 | 10.50 |
| hdbscan | 4/6 | 62.5% | 2 | 3 | 1.50 | 7.75 |

해석은 다음과 같습니다.

- **baseline**: 문서·코드·그림·메모·설정의 다섯 그룹이 만들어졌습니다. 현재 예제에서 세부 파일 탐색의 비교 기준으로 무난했습니다.
- **graph**: 코드·설정 5개와 설명·기록·결과 9개로 나뉘어 전체 개요를 보여주었습니다. 평가 일치율은 가장 높았지만 큰 그룹을 훑는 부담도 컸습니다.
- **metric / pref**: 현재 예시 평가에서는 baseline보다 나은 그룹 일치율이나 탐색 비용을 보여주지 못했습니다. 사용자 선호 데이터가 더 필요합니다.
- **constrained**: 명시적인 학습 제약을 지키는 기능은 확인했지만, 평가 쌍에서는 더 좋은 일반화를 보이지 않았습니다.
- **hdbscan**: `configs/base.yaml`, `figures/lve_plot.png`, `figures/pipeline.svg`가 미분류였습니다. 미분류를 남기는 성격을 전체 프로젝트 지도 용도로 사용할 때 주의해서 해석해야 합니다.

현재 샘플에 대한 잠정 판단은 **baseline을 세부 탐색의 기준으로 두고 graph를 전체 개요용 보조 보기로 비교하는 구성**입니다. 일반적인 우승 방법을 확정한 것은 아닙니다.

## 설정 민감도

세 방법에 대해 사전에 정한 세 값씩 총 9조건을 모두 보고했습니다. 결과를 보고 최적 설정을 자동 선택하지 않았습니다.

| 방법 | 변경한 값 | 관찰 |
|---|---|---|
| constrained | 병합 백분위 25 / 35 / 45 | 평가 일치율은 모두 3/6. 그룹 수 7 / 6 / 5, 평균 훑을 파일 수 5.75 / 6.75 / 8.75 |
| graph | 의미 이웃 수 2 / 3 / 4 | 평가 일치율 3/6 / 5/6 / 4/6. 설정에 민감 |
| hdbscan | 최소 그룹 크기 2 / 3 / 4 | 크기 2에서는 3개 미분류. 크기 3·4에서는 14개 모두 미분류 |

## 근거 문헌과 자체 설계의 경계

함수 docstring에 논문명·저자·연도·URL과 적용 범위를 추가했습니다.

| 대상 | 문헌 | 적용 범위 |
|---|---|---|
| 평균 연결 | Muellner (2011), [Modern hierarchical, agglomerative clustering algorithms](https://arxiv.org/abs/1109.2378) | 표준 계층 군집화. 내용·폴더 혼합 및 절단 백분위는 자체 설정 |
| 앵커/시드 | Basu et al. (2002), [Semi-supervised Clustering by Seeding](https://www.cs.utexas.edu/~ai-lab/pub-view.php?PubID=51520) | 앵커 개념과 관련된 연구. pref는 Seeded K-Means 재현이 아닌 팀 회의안 |
| 거리 학습 | Bilenko et al. (2004), [Integrating Constraints and Metric Learning in Semi-Supervised Clustering](https://icml.cc/Conferences/2004/proceedings/papers/119.pdf) | 감독 정보로 거리를 조정하는 관련 연구. 현재 회귀 목적식과 특징 가중치는 자체 모델 |
| 제약 기반 계층 군집화 | Davidson & Ravi (2009), [Using instance-level constraints in agglomerative hierarchical clustering](https://doi.org/10.1007/s10618-008-0103-4) | 제약 적용의 관련 연구. 점수 임계값·앵커 분리·충돌 우선순위는 자체 정책 |
| Spectral | von Luxburg (2007), [A Tutorial on Spectral Clustering](https://arxiv.org/abs/0711.0189) | 유사도 그래프·Laplacian·eigengap. import·문서 링크 결합은 자체 확장 |
| QR 할당 | Damle et al. (2019), [Simple, direct and efficient multi-way spectral clustering](https://doi.org/10.1093/imaiai/iay008) | scikit-learn의 `assign_labels="cluster_qr"`에 대응 |
| HDBSCAN | Campello et al. (2015), [Hierarchical Density Estimates for Data Clustering, Visualization, and Outlier Detection](https://doi.org/10.1145/2733381) | scikit-learn의 표준 알고리즘 사용. 입력 거리·작은 기본 그룹 크기는 자체 선택 |
| 프로젝트 이해 목적 | Mancoridis et al. (1998), [Using Automatic Clustering to Produce High-Level System Organizations of Source Code](https://doi.org/10.1109/WPC.1998.693283) | 소프트웨어 구조 복원을 통한 이해라는 목적과 연결. 혼합 파일과 체크리스트의 효과를 보장하지 않음 |

## 코드와 산출물

| 위치 | 내용 |
|---|---|
| [`projectwiki/models/clustering.py`](../projectwiki/models/clustering.py) | 여섯 방법, 거리 가중치 학습, 공유 앵커 정책, 함수별 문헌·설계 주석 |
| [`projectwiki/config.py`](../projectwiki/config.py) | 방법 선택과 학습·그래프·밀도 매개변수 |
| [`projectwiki/srcs/cluster_eval.py`](../projectwiki/srcs/cluster_eval.py) | 평가 분리, 실제 `cluster()` 결과 비교, 커버리지·탐색 비용·설정 민감도 |
| [`projectwiki/srcs/cluster_report.py`](../projectwiki/srcs/cluster_report.py) | 그룹·중심 파일·원문·평가 결과·민감도를 보여주는 HTML |
| [`scripts/evaluate_clustering.py`](../scripts/evaluate_clustering.py) | 방법 선택과 JSON/HTML 비교 리포트 생성 |
| [`scripts/download_models.py`](../scripts/download_models.py) | 모델 선택·저장 위치 지정, safetensors/실제 `.bin` 가중치 다운로드 확인, Windows 순차 다운로드 |
| [`examples/pairs.test.example.json`](../examples/pairs.test.example.json) | 학습 쌍과 겹치지 않는 예시 평가 6쌍 |
| [`examples/onboarding.tasks.example.json`](../examples/onboarding.tasks.example.json) | 보고서 전용 탐색 체크리스트 4개 |
| [`runs/clustering-six/comparison.html`](../runs/clustering-six/comparison.html) | 현재 로컬 비교 리포트. 여섯 방법의 관계 그래프 뷰어 링크 포함 |
| [`runs/clustering-six/comparison.json`](../runs/clustering-six/comparison.json) | 전체 수치·그룹·평가 쌍별 결과·민감도 |
| [`runs/clustering-six/provenance.json`](../runs/clustering-six/provenance.json) | 모델 revision·실행 환경·데이터 해시 |
| [`runs/clustering-six/reproduce.py`](../runs/clustering-six/reproduce.py) | 현재 저장 레코드·캐시로 여섯 방법과 뷰어를 다시 생성하는 로컬 스크립트 |

다운로드 스크립트가 원래 bge-m3의 `.bin` 가중치를 받지 않는 문제를 수정했습니다. Windows에서의 캐시 심볼릭 링크 확인 충돌을 피하도록 순차 다운로드를 사용했습니다. 실제 인코딩에 필요한 PyMuPDF는 프로젝트 `.venv`에 설치했으며, CPU 실행 설정과 PyTorch 선로딩은 `runs/bge-m3-local/reproduce.ps1`에 저장했습니다.

`runs/`와 `.venv/`는 git에서 제외됩니다. 위 로컬 결과·모델·재실행 보조 스크립트는 저장소를 새로 복제하면 자동으로 포함되지 않습니다. 공유 가능한 일반 실행 경로는 README와 `scripts/evaluate_clustering.py`입니다.

## 검증과 작업 상태

- 최근 전체 실행 테스트: **57 passed, 2 skipped**. Windows에서 shebang 가짜 CLI를 실행하는 두 테스트는 건너뛰었습니다.
- 검사 범위: 거리 학습·미평가 쌍 적용, 기본 거리 복귀, 앵커 회귀, 제약 전이·충돌, 원문 참조 그래프, 밀도 그룹·노이즈, 데이터 분리, 체크리스트의 학습 독립성, HTML escaping, CLI·전체 파이프라인 통합.
- 논문 주석을 추가한 뒤에는 구문 검사와 docstring을 제외한 AST 비교로 실행 로직이 동일함을 확인했습니다.
- 작성 시점 브랜치는 `cluster/learned-distance`이며, 누적 변경사항은 아직 커밋하지 않았습니다.

## 한계와 다음 검증

1. 데모 한 프로젝트·학습 2쌍·평가 6쌍으로 일반화나 통계적 우위를 주장할 수 없습니다. 같은 작은 예제에 여러 방법과 설정을 반복 적용한 탐색입니다.
2. 실제 사용자가 제공한 풍부한 선호 데이터나 사용자 연구가 없습니다. 체크리스트 수치는 검증된 온보딩 도구나 실제 소요 시간이 아닙니다.
3. 방법별 가이드·앵커·제약 처리도 다르므로 여섯 조건은 전체 방법 비교입니다. 군집화 알고리즘 한 요소만 바꾼 통제 실험은 아닙니다.
4. Claude를 끈 조건이라 PNG는 경로를, SVG는 추출된 텍스트를 활용합니다. 그림 내용에 대한 시각적 설명까지 평가한 결과가 아닙니다.
5. 다음 단계는 여러 실제 프로젝트에서 선호·탐색 과제를 수집하고, 학습·검증·평가를 분리해 매개변수를 선택하는 것입니다. 가이드·앵커를 통제한 비교와 실제 탐색 시간·정확도 측정이 필요합니다.
6. baseline 세부 탐색과 graph 개요를 함께 보여주는 구성이 후속 검토 후보입니다. 아직 새로운 결합 알고리즘이나 제품 기본값 변경으로 구현한 것은 아닙니다.

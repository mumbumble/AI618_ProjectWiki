# ProjectWiki

로컬 프로젝트 폴더(논문·코드·노트·그림)를 위키처럼 정리하고 관리하는 도구입니다. KAIST AI618 Team 04 텀 프로젝트의 공통 베이스라인입니다.

![viewer](assets/viewer.png)

- 파일마다 요약과 역할이 붙고, 파일끼리의 관계에는 양쪽 원문 근거가 달립니다.
- 사용자가 고친 내용(승인·거절·추가·그룹 이동)은 파일이 바뀌어 다시 생성해도 유지되고, 이후 제안에도 반영됩니다.
- 파이프라인은 11/05 팀 회의에서 정했습니다. 군집화와 선호도 반영은 **실험 구간(🧪)** 이라 각자 방법을 끼워 넣어 비교합니다.

## 파이프라인

```mermaid
flowchart LR
  A[프로젝트 폴더] --> I[파일 입력<br/>근거 조각] --> R1[그림 설명·요약<br/>Claude]
  R1 --> M1[① 인코딩<br/>bge-m3] --> R2[프로젝트 레코드]
  R2 --> M2[② 군집화 🧪] --> M3[③ 구조 생성<br/>reranker + Claude 판정]
  M3 --> M4[④ 선호도 반영 🧪] --> F[최종 그래프<br/>직접 편집 재적용] --> M5[⑤ 시각화]
  M5 -. 사용자 피드백 .-> M4
  classDef model fill:#dbe9f7,stroke:#4e79a7,color:#1f2328
  class M1,M2,M3,M4,M5 model
```

파란 상자가 모델 단계(①–⑤)이고, 단계마다 [`projectwiki/models/`](projectwiki/models)의 파일 하나가 맡습니다.

| 모델 단계 | 파일 | 하는 일 | 모델·방법 |
|---|---|---|---|
| 1 인코딩 | [`encoder.py`](projectwiki/models/encoder.py) | 근거 조각과 파일 요약을 벡터로 (캐시) | **bge-m3** |
| 2 군집화 🧪 | [`clustering.py`](projectwiki/models/clustering.py) | 파일 → 그룹, 사용자 선호 반영 | `baseline`, `pref`, `metric`, `constrained`, `graph`, `hdbscan` |
| 3 구조 생성 | [`structure.py`](projectwiki/models/structure.py) | 후보 연결 → 근거 쌍 선택 → 관계·방향·직접/추론 판정, 인용 검증 | **bge-reranker-v2-m3**, **Claude Sonnet 5.5** |
| 4 선호도 반영 🧪 | [`preference.py`](projectwiki/models/preference.py) | 사용자 피드백을 건드리지 않은 연결에 일반화 | `drift`: 커널 끌림/밀어냄 (회의 4안) / `align`: Bradley–Terry 선호 정렬 (회의 1안) / `baseline` |
| 5 시각화 | [`visualization.py`](projectwiki/models/visualization.py) | 뷰어(근거 보기·교정·피드백 내보내기), Obsidian 볼트 | vis-network |

흰 상자는 모델 단계 사이의 데이터 준비이고 [`projectwiki/srcs/`](projectwiki/srcs)가 맡습니다.

- **파일 입력**: `ingest.py`, `parsers.py`. PDF·Markdown·Python·Jupyter·텍스트·SVG를 근거 조각으로 나누고 import·링크를 뽑습니다.
- **프로젝트 레코드**: `enrich.py`, `record.py`. Claude가 그림 설명과 파일 요약·역할을 쓰고(Sonnet·Haiku 5.5), 변경을 감지합니다.
- **최종 그래프**: `finalize.py`. 교정 제안에 사용자의 직접 편집을 항상 우선해서 매번 다시 적용합니다.

폴더마다 파일별 역할을 적은 `README.md`가 있습니다. 구현 상세는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), 방법 추가 절차는 [CONTRIBUTING.md](CONTRIBUTING.md)에 있습니다.

군집화의 합의 사항·구현·실험 결과·문헌·후속 검증은 [Clustering 작업 정리](docs/CLUSTERING_PROGRESS.md)에 모았습니다 (2026-11-12 기준).

## TODO

- [x] 공통 베이스라인 (인코딩·구조 생성·시각화, 파일 입력·레코드·최종 그래프)
- [x] 실험 구간 회의안: 군집화 `pref`, 교정 `drift`(4안)·`align`(1안), 대조군 `baseline`
- [x] Claude 연결: 구독 계정(Claude Code CLI)과 API 키 둘 다
- [x] 단계별 확인 리포트 (`projectwiki report`)
- [ ] 정렬도 측정: 사용자 관계도 ↔ AI 지도의 Gromov–Wasserstein 거리 (4안)
- [ ] 뷰어 이미지 썸네일 (1안 ⑥)
- [ ] 그룹·프로젝트 위키 페이지 생성
- [ ] 유저 스터디용 과제·로그 수집

## 설치

필요한 것:

- Python 3.11과 conda(Miniconda/Anaconda). conda가 없으면 스크립트가 `.venv`를 만듭니다.
- NVIDIA GPU 권장. CPU나 Apple MPS에서도 돌지만 느립니다.
- 디스크 약 10GB (PyTorch와 모델 4.5GB)
- Claude를 쓰는 방법 하나: **Claude 구독 계정으로 로그인한 Claude Code CLI**(기본) 또는 **API 키**. 둘 다 없으면 `--no-llm`으로 Claude 단계를 빼고 돌립니다. 아래 [Claude 연결 방식](#claude-연결-방식) 참고

### 한 번에 설치 (권장)

```bash
git clone git@github.com:mumbumble/AI618_ProjectWiki.git && cd AI618_ProjectWiki
bash scripts/setup.sh          # Linux / WSL / macOS   (GPU가 없으면 --cpu)
```

```powershell
# Windows PowerShell, conda를 쓸 수 있는 터미널에서
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1     # GPU가 없으면 -Cpu
```

스크립트는 다음을 순서대로 합니다.

1. conda env `projectwiki`(Python 3.11)를 만듭니다.
2. 이 컴퓨터에 맞는 PyTorch 2.7.1을 설치합니다. NVIDIA GPU가 있으면 CUDA 12.6 버전입니다.
3. `requirements-dev.txt`를 설치합니다 (버전 고정).
4. 패키지를 설치합니다 (`pip install -e .`).
5. 모델 두 개를 받습니다.
6. 테스트와 `projectwiki doctor`를 실행합니다.

### 직접 설치

```bash
conda create -n projectwiki python=3.11 -y && conda activate projectwiki
pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu126   # NVIDIA GPU
# pip install torch==2.7.1                                                    # macOS / CPU
pip install -r requirements-dev.txt
pip install -e . --no-deps
python scripts/download_models.py      # bge-m3, bge-reranker-v2-m3 (약 4.5GB)
```

군집화 실험만 할 때는 `python scripts/download_models.py --model BAAI/bge-m3`로 인코더만 받을 수 있습니다. `--cache-dir <폴더>`로 저장 위치를 지정했다면 실행 시 `HF_HUB_CACHE`도 같은 폴더로 설정합니다. 스크립트는 사용 가능한 safetensors 또는 PyTorch `.bin` 가중치를 선택하고, 다운로드 후 체크포인트가 있는지 확인합니다. 리랭커 없이 실행하려면 build에 `--no-rerank`를 추가합니다.

### Claude 연결 방식

요약, 그림 설명, 그룹 이름, 관계 판정에 Claude를 씁니다. 둘 중 편한 쪽을 고르세요.

| | A. 구독 계정 (기본, `--llm-backend cli`) | B. API 키 (`--llm-backend api`) |
|---|---|---|
| 준비 | Claude Code CLI 설치 후 Pro/Max 계정으로 로그인 | Anthropic Console에서 API 키 발급 |
| 비용 | 구독 사용 한도에서 차감, 추가 청구 없음* | 토큰당 과금 (Sonnet 5.5 $2/$10, Haiku 5.5 $0.10/$0.50 per MTok) |
| 속도 | 호출당 약 5초, 동시 4개 | 더 빠름, 동시 8개 |
| 추천 | 테스트, 작은 폴더 | 큰 폴더, 반복 실험 |

\* claude.ai 설정에서 '추가 사용량(extra usage)'을 켜 두었다면 한도를 넘긴 만큼 과금될 수 있습니다. 로그에 찍히는 비용은 CLI가 알려주는 API 환산 금액이고 실제 청구액이 아닙니다.

**A. 구독 계정으로 쓰기**

```bash
curl -fsSL https://claude.ai/install.sh | bash      # Claude Code 설치 (또는 npm install -g @anthropic-ai/claude-code)
claude auth login                                   # 브라우저에서 claude.ai 계정으로 로그인
claude auth status                                  # "authMethod": "claude.ai" 이면 구독 사용
projectwiki build examples/sample_project -o runs/sample      # 기본이 cli라 옵션 없이 실행
```

WSL에서 쓴다면 WSL 안에서 Claude Code를 설치하고 로그인해야 합니다. 구독 한도를 아끼려면 `--llm-model claude-haiku-5-5`로 관계 판정과 그림 설명까지 Haiku로 돌리세요.

**B. API 키로 쓰기**

```bash
cp .env.example .env            # ANTHROPIC_API_KEY=sk-ant-... 입력 (.env는 git에 올라가지 않음)
projectwiki build examples/sample_project -o runs/sample --llm-backend api
```

기본값을 API로 바꾸고 싶으면 `--config`에 `{"llm_backend": "api"}`를 넣으세요.

**점검**: `projectwiki doctor`가 패키지, GPU, 모델 캐시, API 키, Claude Code CLI를 확인합니다.

```
[ok] torch 2.7.1+cu126 (transformers 5.x needs >= 2.6)
[ok] GPU: NVIDIA GeForce RTX 2070 SUPER (CUDA 12.6)
[ok] model cached: BAAI/bge-m3
[ok] model cached: BAAI/bge-reranker-v2-m3
[!!] ANTHROPIC_API_KEY not set
[ok] Claude Code CLI: /home/<user>/.local/bin/claude (--llm-backend cli)
ready with --llm-backend cli (or --no-llm)
```

## 실행

```bash
# 예제 폴더로 전체 파이프라인 실행 후 뷰어 열기
projectwiki build examples/sample_project -o runs/sample --prefs examples/prefs.example.json --open

# 뷰어에서 교정하고 'feedback.jsonl 내보내기' → 선호도 반영·최종 그래프·뷰어만 다시 실행 (파일을 다시 읽지 않음)
projectwiki correct runs/sample --feedback ~/Downloads/feedback.jsonl --open

# 본인 프로젝트 폴더 (출력은 기본으로 <폴더>/.projectwiki)
projectwiki build ~/my_project --purpose "다음 주 발표 준비"

# 대조군
projectwiki build ~/my_project -o runs/base --clusterer baseline --corrector baseline

projectwiki report runs/sample --open        # 단계별 확인 리포트 stages.html (교정 방법 비교 포함, 아래 그림)
projectwiki view runs/sample --open          # view.html만 다시 만들기
projectwiki obsidian runs/sample vault/      # Obsidian 볼트로 내보내기
```

| 옵션 | 뜻 |
|---|---|
| `--purpose "..."` | 사용자 목적. 관계 판정에 들어감 |
| `--prefs prefs.json` | 군집화 선호 입력 (중요 파일, 같은 그룹으로 묶고 싶은 정도 1–5점, 가이드). [예시](examples/prefs.example.json) |
| `--clusterer` / `--corrector` | 군집화 `pref`(기본)·`metric`·`baseline`·`constrained`·`graph`·`hdbscan`, 교정 `drift`(기본)·`align`·`baseline`. `패키지.모듈:클래스`도 가능 |
| `--llm-backend cli\|api` | Claude 연결 방식 (기본 `cli`) |
| `--llm-model` | 관계 판정·그림 설명 모델 (기본 `claude-sonnet-5-5`, 아끼려면 `claude-haiku-5-5`) |
| `--no-llm` | Claude 단계를 끔 (요약·그림 설명·그룹 이름·관계 판정) |
| `--no-rerank` | 근거 쌍을 코사인으로만 고름 |
| `--language English` | 요약·설명 언어 (기본 Korean) |
| `--config cfg.json` | [`config.py`](projectwiki/config.py)의 다른 설정값 바꾸기 |

`projectwiki report`가 만드는 `stages.html`은 회의에서 정한 흐름(파일 입력부터 시각화까지 8칸) 그대로, 칸마다 실제 출력과 판정을 보여줍니다.

![stage report](assets/stage_report.png)

### 선호로 거리 학습하기 (`--clusterer metric`)

`prefs.pairs`의 점수는 **현재 목적에서 두 파일을 같은 그룹으로 묶고 싶은 정도**입니다. 5점은 함께 묶고 싶음, 1점은 따로 두고 싶음이며, 목표 거리는 `(5-score)/4`입니다. `feedback.jsonl`의 연결 승인·거절과는 별도 입력입니다.

`metric`은 bge-m3 벡터를 유지하면서 **내용 거리·폴더 거리·파일 형식 차이**의 가중치를 학습합니다. 가중치는 음수가 아니고 합이 1입니다. 평가한 쌍에서 학습한 계산법을 모든 파일 쌍에 적용하며, 이후 앵커 배치와 계층 군집화는 `pref`와 같습니다. 높은 점수도 같은 그룹 배치를 보장하지는 않으며, 앵커끼리는 기존 정책에 따라 별도 그룹이 됩니다.

```bash
python -m projectwiki build examples/sample_project -o runs/metric --clusterer metric --corrector baseline --prefs examples/prefs.example.json --no-llm
python scripts/evaluate_clustering.py runs/metric --test examples/pairs.test.example.json
```

모델 다운로드 없이 빠르게 동작을 확인하려면 build에 `--encoder tfidf --no-rerank`를 추가합니다. 실제 임베딩 비교 실험은 동일한 bge-m3 레코드를 사용합니다.

- `clustering_info.json`: 학습한 가중치, 초기 가중치, 유효 평가 수, 학습 전후 오차, 기본값 사용 이유를 저장합니다.
- `--config`의 `metric_l2`(기본 0.1)는 초기 가중치에서 벗어나는 정도에 벌점을 줍니다. 양수여야 하며, 이 기본값은 실제 데이터에서 최적화한 값이 아닙니다. `metric_use_type: false`로 파일 형식 특징을 제외할 수 있습니다.
- 초기 가중치는 `cluster_alpha` 또는 `guide.group_by`에서 정하며, 평가가 없으면 기존 내용·폴더 거리로 돌아갑니다. 학습 시에는 평가한 쌍의 거리를 다시 덮어쓰지 않습니다.
- 잘못된 경로·자기 자신·유효 범위를 벗어난 점수는 경고 후 제외하고, 같은 쌍의 중복 평가는 방향과 무관하게 마지막 유효 평가를 사용합니다.
- 평가 스크립트는 저장된 레코드로 `baseline`·`pref`·`metric`을 비교해 `clustering_eval.json`을 만듭니다. 새 인코딩·Claude 호출 없이 테스트 쌍의 거리 RMSE, 그룹 배치 일치율, 그룹 수, 시간을 기록합니다. 4–5점은 같은 그룹, 1–2점은 분리로 채점하고 중간 점수는 거리 오차에만 사용합니다.
- 학습·검증·테스트 사이에 같은 파일 쌍이 있으면 중단합니다. 이 비교는 같은 프로젝트의 미평가 쌍에 대한 평가이며, 새 프로젝트로의 일반화 평가는 프로젝트 단위로 별도 분리해야 합니다.

정규화 강도는 별도 검증 쌍으로 선택할 수 있습니다. `validation.json`과 `test.json`은 예제 테스트 파일처럼 평가 배열을 담습니다.

```bash
python scripts/evaluate_clustering.py runs/metric --validation validation.json --l2-grid 0.01 0.1 1.0 --test test.json
```

검증 RMSE로 `metric_l2`를 선택하고, 최종 가중치도 학습 쌍만으로 학습합니다. 테스트 쌍은 보고서 계산에만 사용합니다. 제공한 학습 2쌍·테스트 6쌍은 사용법을 보여주는 예시이므로, 실제 효과는 목적에 맞게 수집한 별도 평가로 확인해야 합니다. `projectwiki report`의 자동 방법 비교는 선호도 교정 대상이며 군집화 비교는 위 스크립트에서 수행합니다.

### 프로젝트 파악에 도움이 되는 군집화 비교

추가한 세 방법도 `--clusterer`로 선택할 수 있습니다. 기존 기본값은 `pref`입니다.

| 방법 | 정리 방식 | 선호·앵커 처리 |
|---|---|---|
| `constrained` | 같은 그룹/다른 그룹 제약을 적용한 평균 연결 계층 군집화 | 4–5점은 must-link, 1–2점은 cannot-link. 앵커끼리는 분리. 모순이 있으면 분리 제약을 우선하고 충돌한 must-link를 진단에 기록 |
| `graph` | 의미 kNN 유사도 + 원문 import·문서 링크의 spectral 군집화. 연결된 그래프의 그룹 수는 eigengap으로 선택하고, 끊긴 성분은 별도 그룹으로 유지 | 평가는 연결 가중치에 반영. 앵커별 그룹은 강제하지 않음 |
| `hdbscan` | 밀도가 높은 파일 묶음과 미분류 파일 | 가이드·평가가 반영된 거리를 사용. 앵커별 그룹은 강제하지 않음 |

`constrained`는 제약 아이디어를 현재 계층 군집화에 적용한 구현이며 COP-KMeans 재현은 아닙니다. `graph`는 구조 생성 뒤의 그래프를 가져오지 않고 `Record`의 원문 참조만 사용합니다. 세 방법 모두 같은 bge-m3 벡터를 유지합니다. HDBSCAN은 scikit-learn 1.3 이상이 필요합니다.

```bash
python scripts/evaluate_clustering.py runs/metric --test examples/pairs.test.example.json --methods baseline pref metric constrained graph hdbscan --tasks examples/onboarding.tasks.example.json --sensitivity -o runs/clustering-six/comparison.json --html runs/clustering-six/comparison.html
```

이 명령은 기존 build 출력의 레코드를 재사용합니다. `--methods`를 생략하면 이전처럼 baseline·pref·metric 세 방법만 비교합니다. HTML은 외부 라이브러리 없이 다음을 보여줍니다.

- 실제 그룹 구성, 임베딩상 중심 파일과 원문 일부, 파일별 원본 링크, 미분류 파일
- 평가 쌍별 결과와 균형 일치율, 파일·평가 쌍 커버리지. 미분류를 올바른 분리로 세지 않음
- import·링크가 같은 그룹에 놓인 비율. 이는 graph의 입력에도 쓰이는 내부 지표이며 독립 정확도가 아님
- 탐색 체크리스트별 방문 그룹 수와 훑을 파일 수. 미분류 대상은 개별 방문으로 계산. 큰 그룹 하나에 모두 넣으면 방문 수만 줄어들므로 두 지표를 함께 확인

체크리스트는 [`onboarding.tasks.example.json`](examples/onboarding.tasks.example.json)의 `name`·`files` 배열입니다. 현재 네 과제는 학습 실행 흐름, 방법과 구현, 평가와 결과, 회의 결정·아이디어 찾기입니다. 파일 내용에서 구성한 대리 과제로, 알고리즘 입력이나 실제 사용자 연구 정답으로 사용하지 않습니다.

`--sensitivity`는 사전에 정한 세 설정 범위(제약 병합 백분위 25/35/45, 그래프 이웃 수 2/3/4, HDBSCAN 최소 그룹 크기 2/3/4)를 모두 보고합니다. 같은 작은 평가셋을 반복 사용한 탐색이며 여기서 최적값을 자동 선택하지 않습니다. 기본 설정은 `config.py`의 `graph_*`, `hdbscan_*`, `cluster_seed`로 조정할 수 있습니다.

방법마다 선호·앵커를 사용하는 방식이 다르므로 여섯 조건은 전체 방법 비교입니다. 군집화 알고리즘 한 요소만의 효과를 분리한 실험은 아니며, 입력 거리 RMSE도 그룹 배치 자체의 품질을 뜻하지 않습니다.

### 뷰어 (`view.html`)

브라우저로 바로 엽니다. vis-network를 CDN에서 받으므로 인터넷이 필요합니다.

- **그래프 표시**
  - 노드 색: 그룹, 노드 모양: 파일 형식
  - 실선: 직접 근거, 점선: 추론
  - 파란 굵은 선: 승인, 초록 선: 사용자가 추가한 연결
- **노드 클릭**: 요약, 내용 미리보기, 연결 목록을 봅니다. 다른 그룹으로 옮기거나 그룹에서 뺄 수 있습니다.
- **연결 클릭**: 관계, 양쪽 원문 인용, 교정 반영 이유를 봅니다. **맞는 연결 / 잘못된 연결 / 목적상 불필요**로 표시합니다.
- **연결 추가**: 두 노드를 차례로 누르고 관계 이름을 적습니다 (예: "발표에 함께 쓸 자료").
- **피드백 내보내기**: `feedback.jsonl 내보내기`로 받은 파일을 `projectwiki correct`에 넘깁니다.

### 출력 폴더

```
runs/sample/
  record/              프로젝트 레코드: 파일·근거 조각·벡터 (파일 입력 + ① 인코딩)
  clustering_info.json  ② 군집화 방법·학습 진단 (metric: 가중치·오차)
  graph.json           ③ 구조 생성 결과 (교정 전)
  feedback.jsonl       누적 피드백 (실행할 때마다 다시 적용)
  correction.json      ④ 선호도 반영 결과     final_graph.json   최종 그래프
  view.html            뷰어              stages.html        단계별 확인 리포트 (report)
  run_info.json        변경 감지·단계별 시간  cache/        임베딩·Claude 응답 캐시
```

## 프로젝트 구조

```
AI618_ProjectWiki/
├── projectwiki/
│   ├── models/               모델 5단계 (단계마다 파일 하나)
│   │   ├── encoder.py            1 인코딩: bge-m3
│   │   ├── clustering.py         2 군집화 🧪: baseline · pref · metric · constrained · graph · hdbscan
│   │   ├── structure.py          3 구조 생성: reranker · Claude 판정
│   │   ├── preference.py         4 선호도 반영 🧪: baseline · drift · align
│   │   └── visualization.py      5 시각화: view.html · Obsidian
│   ├── srcs/                 모델 단계를 돕는 코드
│   │   ├── ingest.py · parsers.py      파일 → 근거 조각
│   │   ├── enrich.py · record.py       그림 설명·요약 → 프로젝트 레코드
│   │   ├── candidates.py · naming.py   후보 연결, 그룹 이름
│   │   ├── finalize.py · feedback.py   최종 그래프, 피드백 로그
│   │   ├── llm.py · claude_cli.py      Claude (API · 구독 CLI)
│   │   ├── report.py · doctor.py       단계별 리포트, 환경 점검
│   │   ├── cluster_eval.py · cluster_report.py  군집화 비교·탐색 과제·HTML
│   │   └── plugins.py · view_template.html
│   ├── pipeline.py           전체 순서
│   ├── cli.py                build / correct / view / report / obsidian / doctor
│   ├── config.py             모든 설정값
│   └── schema.py             단계 사이 데이터 형식
├── examples/                 예제 프로젝트 폴더, prefs·feedback 예시
├── scripts/                  setup.sh · setup.ps1 · download_models.py · make_sample_assets.py · evaluate_clustering.py
├── tests/                    pytest (GPU·API 키 없이 실행)
├── docs/ARCHITECTURE.md      구현 상세
├── assets/                   README 그림
└── requirements.txt · requirements-dev.txt · pyproject.toml
```

## 테스트

```bash
pytest -q
```

TF-IDF 인코더와 가짜 Claude 클라이언트를 쓰므로 GPU와 API 키가 없어도 됩니다. push하면 GitHub Actions에서도 돕니다.

## 현재 상태 (2026-11-05)

| 확인 항목 | 결과 |
|---|---|
| 테스트 8개 (가짜 Claude·가짜 CLI 포함) | 통과 |
| 예제 폴더, `--llm-backend cli` (Sonnet 판정 + Haiku 요약) | 파일 14개 요약·그림 설명, 연결 33개 모두 관계·라벨·검증된 인용. 52회 호출, 3분 20초 |
| AI618 프로젝트 폴더 (파일 133개), `--llm-backend cli --llm-model claude-haiku-5-5` | 근거 조각 1008개, 이미지 45개 설명, 그룹 14개(선호 입력 반영), 후보 437개 판정(16개 탈락). 579회 호출, 21분 30초 |
| 같은 폴더에 예시 피드백 9개 | `drift` 숨김 35·강화 37, `align` 숨김 8·강화 5, 직접 편집 9/9 유지 |
| 증분 갱신 (폴더 복사본에서 파일 1개 수정, 1개 추가) | 변경 2건 감지, 새로 인코딩한 조각 2개, 직접 편집 9/9 유지 |
| 아직 없는 것 | 정렬도 측정(Gromov–Wasserstein), 뷰어 이미지 썸네일, 위키 페이지 생성 |

`projectwiki report <출력폴더>`로 같은 확인을 직접 할 수 있습니다. 구독(CLI) 방식은 호출마다 CLI 기본 프롬프트가 붙어서 사용량이 API보다 큽니다. AI618 폴더 실행의 API 환산 금액은 $19.6이었고, 구독 한도에서 차감됐습니다.

## 문제 해결

| 증상 | 해결 |
|---|---|
| `AutoModel requires PyTorch >= 2.6` | torch가 오래됨. 위 PyTorch 설치 명령을 다시 실행 |
| `ANTHROPIC_API_KEY is not set` | `--llm-backend api`일 때만 필요. `.env`에 키를 넣거나 기본값 `cli`를 쓰거나 `--no-llm` |
| `claude CLI not found` | Claude Code를 설치하고 `claude auth login`. WSL이면 WSL 안에 설치 |
| `claude CLI returned no structured output` 경고가 많음 | 로그인 만료(`claude auth status` 확인) 또는 구독 한도 도달. 한도가 풀린 뒤 같은 명령을 다시 실행하면 성공한 응답은 캐시에서 재사용 |
| 실행 시작이 느림 | 모델을 받은 뒤 `.env`에 `HF_HUB_OFFLINE=1` 추가 |
| `CUDA out of memory` | `--config`로 `batch_size`를 8이나 4로 낮춤 |
| 뷰어가 빈 화면 | 인터넷 연결(CDN) 확인, 브라우저 개발자 도구 콘솔 확인 |
| 그림 설명이 없음 | PyMuPDF가 못 읽는 형식이거나 4.5MB 초과. 로그 경고 확인 |

## 알려진 한계

- 교정 방법은 import·링크를 숨기지 못하고 점수만 바꿉니다. 이런 연결은 사용자만 지울 수 있습니다.
- `drift` 커널은 끝점 하나만 같아도 비슷하다고 봅니다. 예제에서 'meeting – base.yaml'을 거절하자 맞는 연결인 'base.yaml → train.py'도 숨겨졌습니다.
- `align`은 피드백 몇 개로 학습하므로 피드백이 한쪽에 몰리면 그쪽으로 일반화합니다. AI618 예시에서 승인이 모두 문서 쌍이었더니 코드 쪽 언급·유사 연결의 점수가 내려갔습니다.
- 파일명 언급은 문자열 일치로 찾습니다. 같은 이름의 파일이 여러 개면 상대 경로가 적혀 있어야 연결됩니다.
- 동영상·오디오는 경로만 씁니다.
- 관계 판정은 `max_judge_edges`(기본 2000)개까지입니다. 큰 폴더는 먼저 `--no-llm`으로 연결 수를 확인하세요.

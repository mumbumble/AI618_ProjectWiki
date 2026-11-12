# models/ — 모델 5단계

파이프라인에서 모델이 하는 일을 단계마다 파일 하나로 둡니다. 데이터 준비와 보조 코드는 [`../srcs`](../srcs)에 있습니다.

| 단계 | 파일 | 하는 일 | 모델·방법 | 입력 → 출력 |
|---|---|---|---|---|
| 1 인코딩 | `encoder.py` | 근거 조각·파일 요약을 벡터로 바꿈, 텍스트 해시 캐시 | bge-m3 (테스트용 TF-IDF) | 조각·요약 → `Encoded` |
| 2 군집화 🧪 | `clustering.py` | 파일을 그룹으로 묶음 (사용자 선호 반영) | `baseline`, `pref`, `metric`, `constrained`, `graph`, `hdbscan` | `Record` + `Preferences` → `list[Group]` |
| 3 구조 생성 | `structure.py` | 후보 연결 → 근거 쌍 리랭킹 → 관계 판정·인용 검증 | bge-reranker-v2-m3, Claude | `Record` + 그룹 → `Graph` |
| 4 선호도 반영 🧪 | `preference.py` | 사용자 피드백을 건드리지 않은 연결에 일반화 | `baseline`, `drift`(4안), `align`(1안) | `Graph` + 피드백 → `Correction` |
| 5 시각화 | `visualization.py` | 뷰어 `view.html`, Obsidian 볼트 | vis-network (모델 없음) | 최종 `Graph` → 파일 |

## 실험 구간에 방법 넣기 (2·4단계)

군집화의 `pairs.score`는 같은 그룹으로 묶고 싶은 정도(1–5, 높을수록 함께 묶음)입니다. `metric`은 내용·폴더·형식 거리의 비음수 가중치를 학습하고, `pref`와 같은 앵커·계층 군집화 정책을 사용합니다. `clustering_info.json`에 진단을 저장하며, 비교는 `scripts/evaluate_clustering.py`에서 저장된 레코드를 재사용합니다. 자세한 설정과 검증·테스트 분리는 루트 README의 '선호로 거리 학습하기'를 참고하세요.

추가 비교 방법은 `constrained`(같은/다른 그룹 제약), `graph`(원문 참조+의미 그래프 spectral), `hdbscan`(밀도·미분류)입니다. `--methods baseline pref metric constrained graph hdbscan --tasks examples/onboarding.tasks.example.json --html <출력.html>`로 탐색 관점의 비교를 볼 수 있습니다. `--sensitivity`로 세 방법의 고정 설정 범위도 모두 보고합니다. 알고리즘별 앵커 처리와 노이즈 채점은 루트 README에 설명되어 있습니다.

`clustering.py`나 `preference.py`에 클래스를 추가하고 맨 아래 등록표(`CLUSTERERS` / `CORRECTORS`)에 이름을 넣습니다.

- 생성자: `__init__(self, cfg)` 하나만 받습니다.
- 군집화: `cluster(record, prefs) -> list[Group]`
- 선호도 반영: `correct(graph, feedback, record) -> Correction`

파일을 따로 두고 싶으면 아무 모듈에나 만들고 `--clusterer 패키지.모듈:클래스`처럼 경로로 지정해도 됩니다. 절차와 비교 방법은 [CONTRIBUTING.md](../../CONTRIBUTING.md)에 있습니다.

# models/ — 모델 5단계

파이프라인에서 모델이 하는 일을 단계마다 파일 하나로 둡니다. 데이터 준비와 보조 코드는 [`../srcs`](../srcs)에 있습니다.

| 단계 | 파일 | 하는 일 | 모델·방법 | 입력 → 출력 |
|---|---|---|---|---|
| 1 인코딩 | `encoder.py` | 근거 조각·파일 요약을 벡터로 바꿈, 텍스트 해시 캐시 | bge-m3 (테스트용 TF-IDF) | 조각·요약 → `Encoded` |
| 2 군집화 🧪 | `clustering.py` | 파일을 그룹으로 묶음 (사용자 선호 반영) | `baseline`, `pref` | `Record` + `Preferences` → `list[Group]` |
| 3 구조 생성 | `structure.py` | 후보 연결 → 근거 쌍 리랭킹 → 관계 판정·인용 검증 | bge-reranker-v2-m3, Claude | `Record` + 그룹 → `Graph` |
| 4 선호도 반영 🧪 | `preference.py` | 사용자 피드백을 건드리지 않은 연결에 일반화 | `baseline`, `drift`(4안), `align`(1안), `best-of-n`(Drift 강도 3개 중 피드백에 가장 맞는 것) | `Graph` + 피드백 → `Correction` |
| 5 시각화 | `visualization.py` | 뷰어 `view.html`(2D·3D·그룹 카드), Obsidian 볼트 | vis-network, 3d-force-graph (모델 없음) | 최종 `Graph` → 파일 |

## 실험 구간에 방법 넣기 (2·4단계)

`clustering.py`나 `preference.py`에 클래스를 추가하고 맨 아래 등록표(`CLUSTERERS` / `CORRECTORS`)에 이름을 넣습니다.

- 생성자: `__init__(self, cfg)` 하나만 받습니다.
- 군집화: `cluster(record, prefs) -> list[Group]`
- 선호도 반영: `correct(graph, feedback, record) -> Correction`

파일을 따로 두고 싶으면 아무 모듈에나 만들고 `--clusterer 패키지.모듈:클래스`처럼 경로로 지정해도 됩니다. 절차와 비교 방법은 [CONTRIBUTING.md](../../CONTRIBUTING.md)에 있습니다.

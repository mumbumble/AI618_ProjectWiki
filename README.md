# ProjectLens

로컬 프로젝트 폴더(논문·코드·노트·그림)를 근거가 달린 관계 그래프로 정리하고, 사용자의 교정을 다음 생성에 반영하는 파이프라인입니다. AI618 Team 04 텀 프로젝트의 공통 베이스라인입니다.

## 파이프라인

| 단계 | 모듈 | 구현 | 출력 |
|---|---|---|---|
| 1. 파일 입력 | `ingest.py` | PyMuPDF (PDF), Markdown 제목 단위, Python AST, Jupyter, SVG 텍스트, sha256 | 근거 조각 + 참조(import·링크) |
| 2. 인코딩 | `models.py` | bge-m3 dense (GPU fp16, 조각 해시 캐시) | `record/chunk_emb.npy` |
| 3. 프로젝트 레코드 | `record.py` | 파일 요약·역할: Claude Haiku 5.5 / 그림 설명: Claude Sonnet 5.5 | `record/` |
| 4. 군집화 **(실험 구간)** | `cluster/` | `pref`: 회의안 (아래) / `baseline`: 선호 미반영 대조군 | 그룹 |
| 5. 그래프 생성 | `graph.py` | 후보: import·링크·파일명 언급 + bge-m3 유사도 → 근거 쌍: bge-reranker-v2-m3 → 관계 판정·방향·직접/추론·인용 검증: Claude Sonnet 5.5 | `graph.json` |
| 6. 선호도 교정 **(실험 구간)** | `correct/` | `drift`: 회의 4안 (아래) / `baseline`: 일반화 없음 대조군 | `correction.json` |
| 7. 최종 그래프 | `finalize.py` | 교정 방법의 제안 + 사용자의 직접 편집(항상 우선, 매번 재적용) | `final_graph.json` |
| 8. 시각화 | `viz/` | HTML 뷰어 (vis-network) / Obsidian 볼트 내보내기 | `view.html` |

그룹 이름은 Claude Haiku 5.5가 붙입니다 (`groups.py`).

### 실험 구간에 들어 있는 회의안 (11/05)

- `pref` (군집화)
  - 중요 파일(1안): 사용자가 고른 파일이 그룹의 중심이 되고, 가까운 파일이 그 그룹에 붙습니다.
  - 쌍 평가: 예시 파일 쌍에 매긴 1–5 관련도 점수로 두 파일의 거리를 고정합니다.
  - 객관식 가이드(3안): `group_by` = `folder` / `content` / `mixed`로 폴더 구조를 얼마나 반영할지 정합니다.
- `drift` (교정, 4안): 학습 없이 커널로 끌림과 밀어냄을 계산합니다.
  - 승인한 연결과 비슷한 연결은 점수가 오릅니다.
  - '목적상 불필요'로 거절한 연결과 비슷한 연결은 숨깁니다.
  - '사실 오류'로 거절한 연결은 다시 제안하지 않을 뿐, 다른 연결을 밀어내지는 않습니다.
  - 바뀐 연결마다 이유를 남깁니다 (예: "승인한 'train.py – method.md'와 비슷함").

## 설치

```bash
conda create -n projectlens python=3.11 -y && conda activate projectlens
pip install torch --index-url https://download.pytorch.org/whl/cu126   # GPU; transformers 5.x는 torch>=2.6 필요
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=...        # Claude 단계 (없으면 --no-llm)
```

bge-m3와 bge-reranker-v2-m3는 첫 실행 때 Hugging Face에서 받습니다. 받은 뒤에는 `HF_HUB_OFFLINE=1`을 설정하면 실행이 빨라집니다.

## 실행

```bash
# 1-8단계
projectlens build examples/sample_project -o runs/sample --prefs examples/prefs.example.json

# 뷰어에서 내보낸 피드백으로 6-8단계만 다시 실행 (파일을 다시 읽지 않음)
projectlens correct runs/sample --feedback feedback.jsonl

# 대조군과 비교
projectlens build examples/sample_project -o runs/sample_base --clusterer baseline --corrector baseline

projectlens view runs/sample --open          # view.html 다시 만들기
projectlens obsidian runs/sample vault/      # Obsidian 볼트로 내보내기
```

자주 쓰는 옵션은 다음과 같습니다. 전체 설정은 `config.py`에 있고, `--config cfg.json`으로 바꿀 수 있습니다.

- `--purpose "..."`: 사용자 목적. 관계 판정에 들어갑니다.
- `--no-llm`: Claude 단계를 모두 끕니다.
- `--no-rerank`: 근거 쌍을 코사인 유사도로만 고릅니다.
- `--language English`: 요약과 관계 설명의 언어를 바꿉니다.

`examples/sample_project`의 PDF와 PNG는 `python examples/make_sample_assets.py`로 다시 만들 수 있습니다.

### 뷰어

`view.html`은 파일 하나로 된 페이지입니다. 브라우저로 열면 다음을 할 수 있습니다.

- **그래프 표시**
  - 노드 색: 그룹
  - 노드 모양: 파일 형식
  - 실선: 직접 근거, 점선: 추론
  - 초록 선: 사용자가 추가한 연결, 파란 선: 승인한 연결
- **노드 클릭**: 요약, 내용 미리보기, 연결 목록을 보고 그룹을 교정합니다.
- **연결 클릭**: 관계, 양쪽 근거 인용, 교정 이유를 보고 "맞는 연결 / 잘못된 연결 / 목적상 불필요"를 표시합니다.
- **연결 추가**: 두 노드를 고르고 관계 이름을 적습니다.
- **피드백 내보내기**: `feedback.jsonl 내보내기`로 받은 파일을 `projectlens correct`에 넘깁니다.

## 출력 폴더

```
runs/sample/
  config.json  prefs.json
  record/      files.json  chunks.jsonl  chunk_emb.npy  file_emb.npy  meta.json
  graph.json           5단계 그래프 (교정 전)
  feedback.jsonl       누적 피드백 로그 (재생성 때마다 다시 적용)
  correction.json      6단계 결과
  final_graph.json     7단계 결과
  view.html            8단계 뷰어
  cache/               임베딩·LLM 응답 캐시 (같은 입력은 다시 호출하지 않음)
```

## 입력 형식

`prefs.json` (군집화 단계 입력, `examples/prefs.example.json`):

```json
{"purpose": "논문 발표 준비", "anchors": ["docs/method.md"], "guide": {"group_by": "content"},
 "pairs": [{"a": "src/train.py", "b": "docs/method.md", "score": 5}]}
```

`feedback.jsonl` (한 줄에 이벤트 하나, 파일은 상대 경로나 파일 ID로 적음, `examples/feedback.example.jsonl`):

| type | 의미 | 필드 |
|---|---|---|
| `edge_add` | 빠진 연결 추가 | source, target, relation |
| `edge_wrong` | 잘못된 연결 (사실 오류) | source, target |
| `edge_irrelevant` | 관련은 있지만 목적상 불필요 | source, target |
| `edge_confirm` | 맞는 연결 (승인) | source, target |
| `node_move` | 다른 그룹으로 이동 (없는 이름이면 새 그룹) | node, group |
| `node_ungroup` | 그룹에서 빼기 | node |

## 실험 구간에 새 방법 넣기

```python
# projectlens/cluster/my_method.py
from projectlens.schema import Group

class MyClusterer:
    name = "mine"
    def __init__(self, cfg): ...
    def cluster(self, record, prefs) -> list[Group]:
        # record.files, record.file_emb (bge-m3), record.chunks, record.chunk_emb, prefs.anchors/pairs/guide
        ...
```

```python
# projectlens/correct/my_method.py
from projectlens.correct import Correction

class MyCorrector:
    name = "mine"
    def __init__(self, cfg): ...
    def correct(self, graph, feedback, record) -> Correction:
        # Correction(edge_scores={edge_id: score}, hide=[edge_id], new_edges=[...], explanations={edge_id: "이유"})
        ...
```

`cluster/__init__.py`의 `CLUSTERERS`나 `correct/__init__.py`의 `CORRECTORS`에 등록하면 `--clusterer mine`으로 쓸 수 있습니다. 등록하지 않아도 `--corrector projectlens.correct.my_method:MyCorrector`처럼 경로로 지정할 수 있습니다. 사용자의 직접 편집은 7단계에서 항상 적용되므로, 교정 방법은 사용자가 건드리지 않은 연결과 노드만 다루면 됩니다.

## 테스트

```bash
pytest -q     # TF-IDF 인코더와 가짜 Claude 클라이언트로 전체 흐름을 확인 (GPU·API 키 불필요)
```

## 알려진 한계

- `drift`의 커널은 끝점 하나만 같아도 비슷하다고 봅니다. 예제에서 'meeting – base.yaml'을 거절하자 'base.yaml → train.py'도 함께 숨겨졌습니다.
- 파일명 언급은 문자열 일치로 찾습니다. 같은 이름의 파일이 여러 개면 상대 경로가 그대로 적혀 있어야 연결됩니다.
- 이미지는 PyMuPDF로 읽을 수 있는 형식(PNG, JPEG, BMP, TIFF 등)만 설명을 붙입니다. SVG는 안의 텍스트를 쓰고, 동영상·오디오는 경로만 씁니다.
- 관계 판정은 `max_judge_edges`(기본 2000)개까지만 합니다. 큰 폴더는 비용을 먼저 확인하세요. 실행이 끝나면 토큰 사용량과 비용이 로그에 찍힙니다.

# 6. 사용자 선호도 교정 🧪 실험 구간 (`stage6_correct`)

사용자 피드백을, 사용자가 건드리지 않은 연결에까지 어떻게 일반화할지가 실험 대상입니다.

- **입력**: 5단계 `Graph`, 피드백 로그(`feedback.jsonl`), `Record`
- **출력**: `Correction`(`edge_scores`, `hide`, `new_edges`, `node_groups`, `explanations`). 저장 위치는 `<출력폴더>/correction.json`

| 파일 | 내용 |
|---|---|
| `base.py` | 인터페이스 `correct(graph, feedback, record) -> Correction` |
| `baseline.py` | 대조군: 일반화하지 않음 |
| `drift.py` | `drift` (회의 4안): 승인한 연결은 끌고 '목적상 불필요'는 밀어내는 커널, 학습 없음 |
| `align.py` | `align` (회의 1안): 승인 > 거절 쌍으로 학습한 Bradley–Terry 선호 모델 |
| `__init__.py` | 방법 등록표 `CORRECTORS` |

- 사용자의 직접 편집(추가·승인·거절·그룹 이동)은 7단계가 항상 다시 적용합니다. 그래서 여기서는 신경 쓰지 않아도 됩니다.
- import·링크는 7단계에서 숨기지 않습니다.

**새 방법 추가**: 이 폴더에 클래스 하나를 만들고 `CORRECTORS`에 등록합니다. `projectwiki report <출력폴더>`를 실행하면 등록된 모든 방법이 같은 피드백으로 비교됩니다.

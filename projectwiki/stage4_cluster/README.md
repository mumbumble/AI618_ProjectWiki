# 4. 군집화 🧪 실험 구간 (`stage4_cluster`)

파일을 그룹으로 묶습니다. 사용자 선호를 어떻게 반영할지가 실험 대상입니다.

- **입력**: `Record`, `Preferences`(`purpose`, `anchors`, `pairs`, `guide`, `prefs.json`)
- **출력**: `list[Group]` (이름은 비워 두면 `naming.py`가 붙임)

| 파일 | 내용 |
|---|---|
| `base.py` | 인터페이스 `cluster(record, prefs) -> list[Group]` |
| `baseline.py` | 대조군: 선호 미반영. bge-m3 거리 + 폴더 거리로 계층 군집 |
| `preference.py` | `pref` (회의안): 중요 파일(1안), 쌍 1–5 평가, 객관식 가이드(3안) |
| `naming.py` | 공통: Claude가 그룹 이름·설명을 붙임 |
| `__init__.py` | 방법 등록표 `CLUSTERERS` |

**새 방법 추가**: 이 폴더에 `my_method.py`를 만들고, `__init__(self, cfg)`와 `cluster(record, prefs)`를 가진 클래스를 쓴 뒤 `CLUSTERERS`에 등록합니다. `projectwiki build ... --clusterer my_method`로 실행합니다. 자세한 절차는 [CONTRIBUTING.md](../../CONTRIBUTING.md)에 있습니다.

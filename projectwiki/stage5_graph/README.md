# 5. 그래프 생성 (`stage5_graph`)

파일 사이의 관계 연결을 만들고, 원문 근거를 붙이고, Claude가 관계를 판정합니다.

- **입력**: `Record`, 4단계 그룹, 사용자 목적
- **출력**: `Graph` (`<출력폴더>/graph.json`, 교정 전)

| 파일 | 단계 | 내용 |
|---|---|---|
| `candidates.py` | ① 후보 | import·Markdown 링크·위키링크·파일명 언급(직접), bge-m3 유사도(그룹 안 상위 k개 + 그룹 밖 1개) |
| `evidence.py` | ② 근거 | 코사인 상위 조각 쌍을 bge-reranker-v2-m3로 다시 점수 매겨 가장 좋은 쌍을 고름 |
| `judge.py` | ③ 판정 | Claude가 관계 종류·방향·라벨·직접/추론을 정하고 양쪽 인용을 냄. 원문에 없는 인용은 버림 |
| `build.py` | 조립 | ①→②→③을 이어 `Graph`를 만듦 |

**고칠 때**

- 후보를 더 많게·적게: `Config.k_within`, `sim_pct`, `sim_cross_pct`
- 관계 종류: `schema.py`의 `RELATIONS`와 `judge.py`의 `JUDGE_SYSTEM`을 함께 바꿉니다.
- 판정 프롬프트: `JUDGE_SYSTEM` (바꾸면 Claude 캐시를 다시 씀)

# srcs/ — 모델 단계를 돕는 코드

| 파일 | 쓰이는 곳 | 내용 |
|---|---|---|
| `ingest.py` | 파일 입력 | 폴더 훑기(건너뛸 경로), 형식 판별, 파일 ID(경로 해시)·sha256, 근거 조각 만들기 |
| `parsers.py` | 파일 입력 | 형식별 분할: PDF(쪽), Markdown(제목), Python(AST), Jupyter(셀), 텍스트, SVG. 새 형식은 여기에 추가 |
| `enrich.py` | 프로젝트 레코드 | Claude가 쓰는 그림 설명·파일 요약/역할 (프롬프트 `IMAGE_SYSTEM`, `SUMMARY_SYSTEM`) |
| `record.py` | 프로젝트 레코드 | `Record`(파일·조각·벡터, 저장/불러오기), 변경 감지, 파일 벡터 |
| `candidates.py` | 3 구조 생성 | 후보 연결: import·링크·위키링크·파일명 언급, bge-m3 유사도 |
| `naming.py` | 2 군집화 | Claude가 그룹 이름·설명을 붙임 |
| `finalize.py` | 최종 그래프 | 교정 제안 + 사용자의 직접 편집(항상 우선)을 합침. import·링크는 교정 방법이 숨기지 못함 |
| `feedback.py` | 4 선호도 반영, 최종 그래프 | `feedback.jsonl` 읽기·병합, 경로 → 파일 ID |
| `llm.py` | 전체 | Claude 호출(JSON 스키마), 응답 캐시, 비용 기록 |
| `claude_cli.py` | 전체 | 구독 계정 백엔드: `claude -p --json-schema` 실행 (`--llm-backend cli`) |
| `plugins.py` | 2·4단계 | 방법을 등록 이름이나 `module:Class`로 불러오기 |
| `report.py` | 도구 | `projectwiki report` → `stages.html` (단계별 출력, 회의안 대비 판정, 교정 방법 비교) |
| `cluster_eval.py` | 도구 | 저장된 레코드로 선택한 군집화 방법 비교. 평가 분리, 탐색 체크리스트, 노이즈·커버리지, 설정 민감도 |
| `cluster_report.py` | 도구 | 자체 포함 HTML: 실제 그룹·중심 파일·원문, 평가 쌍과 탐색 비용·미분류 파일 비교 |
| `doctor.py` | 도구 | `projectwiki doctor` → 패키지·GPU·모델 캐시·Claude 연결 점검 |
| `view_template.html` | 5 시각화 | 뷰어 HTML. 안의 `applyEvents()`는 `finalize.py`와 같은 규칙을 따라야 함 |

데이터 형식은 [`../schema.py`](../schema.py), 설정값은 [`../config.py`](../config.py)에 있습니다.

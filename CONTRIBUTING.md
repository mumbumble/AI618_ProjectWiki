# 작업 방법

## 실험 구간에 방법 추가하기

모델 단계 2 군집화와 4 선호도 반영이 실험 구간입니다. 나머지는 공통 코드라 되도록 건드리지 않습니다.

1. 브랜치를 만듭니다: `git switch -c cluster/<방법이름>` 또는 `git switch -c correct/<방법이름>`.
2. 클래스 하나를 만듭니다.
   - 군집화: `projectwiki/models/clustering.py`에 추가, `cluster(record, prefs) -> list[Group]`
   - 선호도 반영: `projectwiki/models/preference.py`에 추가, `correct(graph, feedback, record) -> Correction`
   - 따로 파일을 두고 싶으면 아무 모듈에나 만들고 `--clusterer 패키지.모듈:클래스`처럼 경로로 지정해도 됩니다.
   - 생성자는 `__init__(self, cfg)` 하나만 받습니다. 새 설정값이 필요하면 `config.py`에 필드를 추가하고 기본값을 둡니다.
3. 같은 파일 맨 아래의 `CLUSTERERS`나 `CORRECTORS`에 이름을 등록합니다.
4. `tests/`에 작은 테스트를 추가합니다. 예시는 `tests/test_pipeline.py`의 `make_cfg()`로, TF-IDF 인코더를 써서 GPU나 API 키 없이 돕니다.
5. 같은 폴더에서 대조군과 비교합니다.
   ```bash
   projectwiki build <폴더> -o runs/base --clusterer baseline --corrector baseline --prefs prefs.json
   projectwiki build <폴더> -o runs/mine --clusterer <방법이름> --corrector <방법이름> --prefs prefs.json
   projectwiki correct runs/base --feedback feedback.jsonl
   projectwiki correct runs/mine --feedback feedback.jsonl
   ```
   두 실행은 프로젝트 레코드와 Claude 응답 캐시를 각자 만듭니다. 같은 `-o` 폴더에서 방법만 바꾸면 캐시를 그대로 다시 씁니다.

   교정 방법은 build를 두 번 할 필요 없이 리포트에서 바로 비교할 수 있습니다. `projectwiki report runs/mine --open`을 실행하면 리포트의 '6 선호도 교정' 표에 등록된 모든 교정 방법(baseline·drift·align·내 방법)이 같은 그래프와 피드백으로 계산돼 나란히 나옵니다.
6. `pytest -q`가 통과하면 PR을 올립니다.

`record`에서 쓸 수 있는 것:

- `record.files`: 경로, 형식, 요약, 역할
- `record.file_emb`: 파일별 bge-m3 벡터, 정규화됨
- `record.chunks`, `record.chunk_emb`: 근거 조각과 그 벡터
- `record.resolve(path)`: 경로를 파일 id로 바꿈

군집화 비교에는 `python scripts/evaluate_clustering.py <출력폴더> --test <평가쌍.json>`을 쓸 수 있습니다. `prefs.pairs`는 현재 목적에서 **같은 그룹으로 묶고 싶은 정도**(1–5)이며 테스트 쌍과 겹치면 안 됩니다. `--validation <검증쌍.json> --l2-grid 0.01 0.1 1.0`으로 `metric`의 정규화 강도를 검증 데이터에서 선택할 수 있습니다. 동일한 저장 레코드에서 `baseline`·`pref`·`metric`을 비교하므로 인코딩과 LLM 호출은 반복하지 않습니다.

`--methods baseline pref metric constrained graph hdbscan`으로 추가 방법을 선택하고, `--tasks examples/onboarding.tasks.example.json --html <출력.html>`로 실제 그룹과 탐색 부담을 검토할 수 있습니다. `--sensitivity`는 고정된 설정 범위의 결과를 모두 보여주며 최적값을 고르지 않습니다. 미분류 파일을 올바른 분리로 계산하지 않으며, 참조 응집도·체크리스트 비용은 보조 지표입니다. 방법별 선호·앵커 처리 차이를 기록하고, 작은 예제의 순위를 실제 사용자 효용으로 해석하지 않습니다.

## 지킬 것

- `runs/`, `.env`, 개인 프로젝트 폴더는 커밋하지 않습니다 (`.gitignore`에 있음).
- API 키는 `.env`나 환경 변수에만 둡니다.
- `baseline` 두 개는 비교 기준이라 바꾸지 않습니다.
- 새 패키지가 필요하면 `requirements.txt`에 버전을 고정해 추가하고 PR에 이유를 적습니다.

# 작업 방법

## 실험 구간에 방법 추가하기

군집화(4단계)와 선호도 교정(6단계)이 실험 구간입니다. 나머지 단계는 공통이라 되도록 건드리지 않습니다.

1. 브랜치를 만듭니다: `git switch -c cluster/<방법이름>` 또는 `correct/<방법이름>`.
2. 파일 하나에 클래스 하나를 만듭니다.
   - 군집화: `projectwiki/cluster/<방법이름>.py`, `cluster(record, prefs) -> list[Group]`
   - 교정: `projectwiki/correct/<방법이름>.py`, `correct(graph, feedback, record) -> Correction`
   - 생성자는 `__init__(self, cfg)` 하나만 받습니다. 새 설정값이 필요하면 `config.py`에 필드를 추가하고 기본값을 둡니다.
3. `cluster/__init__.py`의 `CLUSTERERS`나 `correct/__init__.py`의 `CORRECTORS`에 등록합니다.
4. `tests/`에 작은 테스트를 추가합니다. 예시는 `tests/test_pipeline.py`의 `make_cfg()`로, TF-IDF 인코더를 써서 GPU나 API 키 없이 돕니다.
5. 같은 폴더에서 대조군과 비교합니다.
   ```bash
   projectwiki build <폴더> -o runs/base --clusterer baseline --corrector baseline --prefs prefs.json
   projectwiki build <폴더> -o runs/mine --clusterer <방법이름> --corrector <방법이름> --prefs prefs.json
   projectwiki correct runs/base --feedback feedback.jsonl
   projectwiki correct runs/mine --feedback feedback.jsonl
   ```
   두 실행은 1–3단계와 Claude 응답 캐시를 각자 만듭니다. 같은 `-o` 폴더에서 방법만 바꾸면 캐시를 그대로 다시 씁니다.
6. `pytest -q`가 통과하면 PR을 올립니다.

`record`에서 쓸 수 있는 것:

- `record.files`: 경로, 형식, 요약, 역할
- `record.file_emb`: 파일별 bge-m3 벡터, 정규화됨
- `record.chunks`, `record.chunk_emb`: 근거 조각과 그 벡터
- `record.resolve(path)`: 경로를 파일 id로 바꿈

## 지킬 것

- `runs/`, `.env`, 개인 프로젝트 폴더는 커밋하지 않습니다 (`.gitignore`에 있음).
- API 키는 `.env`나 환경 변수에만 둡니다.
- `baseline` 두 개는 비교 기준이라 바꾸지 않습니다.
- 새 패키지가 필요하면 `requirements.txt`에 버전을 고정해 추가하고 PR에 이유를 적습니다.

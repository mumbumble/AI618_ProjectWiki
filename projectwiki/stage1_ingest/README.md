# 1. 파일 입력 (`stage1_ingest`)

프로젝트 폴더의 파일을 근거 조각(Chunk)으로 나눕니다.

- **입력**: 프로젝트 폴더, `Config`(`max_chars`, `max_file_mb`, `ignore`)
- **출력**: `list[FileRecord]`, `list[Chunk]` (`schema.py`)

| 파일 | 내용 |
|---|---|
| `ingest.py` | 폴더 훑기(건너뛸 경로), 형식 판별, 파일 ID(경로 해시)·sha256, 조각 만들기 |
| `parsers.py` | 형식별 parser: PDF(쪽), Markdown(제목 경로), Python(AST 함수·클래스), Jupyter(셀), 텍스트, SVG |
| `images.py` | 이미지를 PNG로 줄여 Claude에게 설명을 받고, 경로만 있던 조각을 설명 조각으로 바꿈 |

**고칠 때**

- 새 파일 형식: `parsers.py`에 `parse_xxx`를 추가하고 `parse()`에서 분기합니다. 형식 판별은 `ingest.py`의 `TYPES`/`TEXT_EXT`에 있습니다.
- 조각 크기: `Config.max_chars`
- 건너뛸 폴더: `ingest.py`의 `SKIP_DIRS`, 또는 실행할 때 `Config.ignore`

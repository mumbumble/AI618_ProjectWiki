# 3. 프로젝트 레코드 (`stage3_record`)

파일 요약·역할과 파일 벡터를 붙여, 이후 모든 단계가 읽는 `Record`를 만듭니다.

- **입력**: 파일·조각, 2단계 벡터
- **출력**: `Record` (`<출력폴더>/record/`에 저장: `files.json`, `chunks.jsonl`, `chunk_emb.npy`, `file_emb.npy`)

| 파일 | 내용 |
|---|---|
| `summarize.py` | Claude가 파일마다 요약 2–3문장과 역할을 씀 (프롬프트 `SUMMARY_SYSTEM`) |
| `record.py` | `Record` (파일·조각·벡터, 경로→id 변환, 저장/불러오기), 이전 실행과의 변경 감지(`diff_files`), 파일 벡터 계산(`build_record`) |

**고칠 때**

- 요약 내용이나 언어: `SUMMARY_SYSTEM`, `Config.language`
- 파일 벡터 계산(조각 평균 + 요약): `build_record`
- 이후 단계에서 쓰는 레코드 필드: `Record`

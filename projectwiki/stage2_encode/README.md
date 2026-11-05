# 2. 인코딩 (`stage2_encode`)

근거 조각과 파일 요약을 bge-m3 벡터로 바꿉니다.

- **입력**: 1단계의 파일·조각, 3단계 앞부분에서 만든 요약
- **출력**: `Encoded`(조각 벡터, 요약 벡터, 인코더 id, 새로 인코딩한 수)

| 파일 | 내용 |
|---|---|
| `encode.py` | 인코딩 입력 문장 만들기(`chunk_text`, `summary_text`), 텍스트 해시 캐시(`cache/emb_*.npz`) |

- 모델 자체는 `models/encoders.py`(bge-m3, 테스트용 TF-IDF)에 있습니다.
- 요약도 조각과 같은 호출에서 인코딩하기 때문에, 파이프라인은 3단계 요약을 2단계보다 먼저 만듭니다.

**고칠 때**

- 다른 임베딩 모델: `models/encoders.py`에 클래스를 추가하고 `make_encoder()`에 등록한 뒤 `Config.encoder`로 고릅니다.
- 인코딩할 문장 형식: `chunk_text` (바꾸면 캐시가 새로 만들어짐)

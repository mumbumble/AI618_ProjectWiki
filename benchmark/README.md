# 벤치마크: 프로젝트 폴더와 정답 관계 그래프

ProjectWiki가 만든 관계 그래프를 숫자로 평가하기 위한 벤치마크입니다. 프로젝트 폴더 20개(실제 공개 프로젝트 10개, 모의 프로젝트 10개)마다 정답 그래프를 만들었고, 두 가지를 잽니다.

1. **그래프 정확도**: 파일 사이의 연결과 관계 종류를 얼마나 맞히는지
2. **피드백 반영**: 가상 사용자가 피드백을 줬을 때, 피드백을 주지 않은 연결까지 얼마나 좋아지는지

피드백이 실제 사용자에게 도움이 되는지는 이 벤치마크가 아니라 Part 4 User Study에서 봅니다.

## 1. 폴더 구성

```
benchmark/
├── README.md        이 문서: 구성, 정답 설계, 평가 방식, 측정 지표
├── gt_graphs.html   정답 그림. 프로젝트마다 같은 정답을 두 가지로 나란히 그림
│                    (왼쪽: ProjectWiki 출력 화면처럼 모든 연결을 그대로, 오른쪽: 그룹과 핵심 연결로 정리)
├── gt/              정답 데이터 20개
│   └── <프로젝트>/
│       ├── project/   실제 프로젝트 파일 (평가 입력)
│       ├── gt.json    정답 그래프
│       └── LICENSE    원 저장소 라이선스 (실제 프로젝트만)
└── eval/            평가 코드
    ├── gt_format.py          정답 파일 형식
    ├── graph_metrics.py      그래프 정확도 지표
    ├── feedback_sim.py       가상 사용자 피드백 평가
    ├── llm_only_baseline.py  대조군: Claude가 파일 요약만 보고 한 번에 그래프를 그림
    ├── run_eval.py           모든 프로젝트·시스템 평가 → runs/bench/results/RESULTS.md
    ├── analyze.py            추가 분석 → runs/bench/results/ANALYSIS.md
    └── test_eval.py          테스트 (pytest benchmark/eval)
```

정답 파일(`gt.json`)은 `project/` 바깥에 있어서, 파이프라인이 `project/`를 읽을 때 정답이 섞이지 않습니다.

## 2. 데이터: 프로젝트 20개

### 실제 프로젝트 10개

쉬운 예제부터 논문 프로젝트까지 골랐고, 코드와 논문 모두 자유 라이선스인 것만 썼습니다. 커밋을 고정했고 바이너리, CI 설정, 대용량 데이터는 뺐습니다. 논문 프로젝트에는 본 논문(`paper/`)과, 그 프로젝트가 발전시키거나 비교하는 관련 논문(`related_work/`)을 함께 넣었습니다.

| 프로젝트 | 저장소 @ 커밋 | 코드 | 논문 (모두 CC BY 4.0) | 파일 |
|---|---|---|---|---:|
| mnist | pytorch/examples @ `acc295d` (mnist 예제 4종) | BSD-3 | – | 14 |
| micrograd | karpathy/micrograd @ `7bc720e` | MIT | – | 11 |
| mingpt | karpathy/minGPT @ `37baab7` | MIT | – | 16 |
| nanogpt | karpathy/nanoGPT @ `3adf61e` | MIT | – | 23 |
| llama2c | karpathy/llama2.c @ `350e04f` | MIT | – | 21 |
| annotated_transformer | harvardnlp/annotated-transformer @ `debc9fd` | MIT | Transformer 논문 PDF는 넣지 않음(arXiv 기본 라이선스) | 13 |
| convnext | facebookresearch/ConvNeXt @ `048efce` | MIT | 본 논문 2201.03545, 관련: Swin 2103.14030 | 21 |
| mamba | state-spaces/mamba @ `e9594ce` | Apache-2.0 | 본 논문 2312.00752, 관련: Mamba-2 2405.21060, S5 2208.04933, RWKV 2305.13048 | 30 |
| kan | KindXiaoming/pykan @ `ecde4ec` | MIT | 본 논문 2404.19756, 관련: KAN 2.0 2408.10205, KAN or MLP 2407.16674 | 34 |
| qlora | artidoro/qlora @ `7f4e95a` | MIT | 본 논문 2305.14314, 관련: LLM.int8() 2208.07339, 8-bit Optimizers 2110.02861, OpenAssistant 2304.07327 | 22 |

코드는 MIT·BSD·Apache 라이선스라 원 저장소의 LICENSE 파일을 함께 두면 다시 배포할 수 있어서, 프로젝트마다 `LICENSE`를 넣었습니다. 논문 PDF는 CC BY 4.0이라 출처를 밝히면 됩니다. 리포트에 쓸 때도 이 표를 출처로 함께 적습니다. 프로젝트 안의 사진(예: micrograd의 `puppy.jpg`)은 분석 대상으로만 쓰고 리포트에 그대로 싣지 않습니다.

### 모의 프로젝트 10개

실제 공개 프로젝트에는 회의록, 개인 메모, 초안 여러 버전처럼 연구 폴더에 흔한 파일이 거의 없어서 따로 만들었습니다.

| 유형 | 프로젝트 | 들어 있는 것 |
|---|---|---|
| ML 논문 (4) | mock_plant_fewshot, mock_speech_emotion, mock_code_summary, mock_robot_grasp | 논문 초안 v1·v2(PDF), 프로젝트 페이지, 관련 연구 노트, 코드, 설정, 결과·로그, 그림, 한국어 회의록 |
| 데이터 분석 과제 (2) | mock_bike_demand, mock_sleep_grades | 과제 명세(PDF), 원본·정제 CSV, 노트북, 보고서, 그림, 한국어 회의록·조교 피드백 |
| 소프트웨어 도구 (2) | mock_csv_diff_tool, mock_gpx_simplify | 패키지 코드, 테스트, 설계·API 문서, 버그 리포트, 벤치마크, 한국어 로드맵 |
| HCI 사용자 연구 (2) | mock_codereview_xai, mock_vr_text_entry | 연구 계획서(PDF), IRB 문서, 과제·설문, 프로토타입 코드, 데이터, 분석 스크립트, 한국어 파일럿 기록 |

모든 모의 프로젝트에는 관계없는 함정 파일(행정 메모, 다른 주제 읽기 목록 등)이 2개씩 들어 있습니다.

만드는 법: 먼저 유형마다 파일 역할과 그 사이에 심을 관계(종류, 단서, 필수 여부)를 설계도로 정했습니다. 그다음 Claude Sonnet이 주제별 사실표(이름, 수치, 날짜)를 만들고, Claude Haiku가 사실표를 따라 파일을 하나씩 썼습니다. 그래서 결과 CSV와 논문 표의 숫자가 실제로 일치합니다. 마지막으로 import·링크·파일명 언급을 정적 분석으로 다시 찾아, 설계대로 들어갔는지 확인했습니다.

## 3. 정답(GT) 설계

### 정답 파일 형식

정답은 파일 쌍 단위입니다.

```json
{"project": "nanogpt",
 "edges": [{"a": "train.py", "b": "model.py", "relation": "uses", "also": ["implements"],
            "direction": "a_to_b", "required": true, "layer": "explicit",
            "evidence": {"file": "train.py", "span": "from model import GPTConfig, GPT"},
            "source": "static-analysis", "note": "imports", "personas": []}],
 "negatives": [{"a": "bench.py", "b": "data/shakespeare/readme.md", "source": "manual", "note": ""}],
 "groups": [{"name": "모델·학습 코드", "members": ["train.py", "model.py", "sample.py"]}],
 "meta": {"repo": "karpathy/nanoGPT", "commit": "...", "cognitive_review": {}, "simplified": {}, "review_log": []}}
```

- `required: true`는 핵심 연결입니다. recall은 이것만 셉니다.
- `required: false`는 실제로 관련은 있지만 핵심은 아닌 연결입니다. 예측해도 감점하지 않고, 놓쳐도 감점하지 않습니다.
- `layer`: `explicit`은 파일이 직접 말하는 연결(import, 링크, 파일명 언급), `semantic`은 내용으로 이어지는 연결입니다.
- `negatives`는 관계가 없다고 판정한 쌍입니다. 어디에도 없는 쌍은 판정하지 않은 쌍이라 평가에서 뺍니다.
- `groups`는 사람이 이 프로젝트를 설명할 때 묶을 법한 그룹입니다.

### 실제 프로젝트 정답을 만든 순서

1. **명시적 연결**: import, 링크, 파일명 언급을 정적 분석으로 뽑았습니다.
2. **판정할 쌍 모으기(풀링)**: 모든 파일 쌍을 볼 수는 없어서, 비교하는 세 시스템이 고려한 후보에 파일 임베딩 이웃(파일당 4개)과 무작위 쌍을 더해 767쌍을 모았습니다. 무작위 쌍은 풀이 놓친 연결이 얼마나 되는지 추정하는 데 씁니다.
3. **Claude 1차 라벨**: Claude Sonnet이 쌍마다 Y(분명한 관계), W(약한 관계), N(관계 없음)과 관계 종류, 양쪽 파일의 근거 문장을 답했습니다. 한 번에 6쌍씩 봤고, 시스템이 낸 결과는 보여주지 않았습니다. 같은 182쌍을 1쌍씩 따로 판정한 결과와 비교하면 관계 유무가 92.9% 일치합니다(라벨러 일관성).
4. **인지 정렬 검토(3회, 다수결)**: 프로젝트의 정답 그래프 전체를 보고, 이 프로젝트를 이해하는 사람이 머릿속으로 파일을 이렇게 연결하는지 검토했습니다. 처음 보는 사람, 코드를 고치는 사람, 논문의 근거를 추적하는 사람의 시선으로 세 번 따로 보고, 두 번 이상 같은 수정(추가, 삭제, 약화, 강화, 관계 수정)이 나온 것만 반영했습니다. import는 사실이라 삭제하지 않고 약화만 했습니다.
5. **그룹과 핵심 연결(3회, 합의)**: 사람이 화이트보드에 그리듯 단순하게 만들었습니다. 파일을 3–7개 그룹으로 묶고 핵심 연결을 고르는 일을 세 번 따로 했습니다. 두 번 이상 같은 그룹이 된 파일끼리 한 그룹으로 묶었습니다. 핵심 연결은 그룹 안과 그룹 사이를 다르게 정했습니다.
   - 그룹 안: 두 번 이상 고른 연결로 나무 모양 뼈대를 만들고, 세 번 모두 고른 연결을 조금 더했습니다. 그룹 안 연결이 없는 파일은 그룹에 속한 것만으로 충분하다고 보고 핵심 연결을 따로 두지 않았습니다.
   - 그룹 사이: 최소한만 남겼습니다. 그룹 쌍마다 대표 연결 하나를 정하고, 그룹들이 모두 이어지는 데 필요한 만큼만(그룹이 N개면 최대 N−1개) 강한 쌍부터 골랐습니다. 사람은 그룹 사이 관계를 "튜토리얼들은 핵심 라이브러리를 쓴다"처럼 한 줄로 떠올리지, 파일마다의 연결을 다 떠올리지 않기 때문입니다.
   - 나머지 실제 연결은 지우지 않고 약한 연결로 남겼습니다.
6. **사람 검토와 정리**: 사람이 파일을 열어 의심 가는 핵심 연결을 확인하고, 틀린 관계와 방향을 고쳤습니다. import·링크 연결의 방향은 연결이 적힌 파일을 출발점으로 채웠습니다. 고친 연결은 `note`에 `review:`를 붙였고(사람이 직접 확인한 것은 `review: human:`), 프로젝트마다 `meta.review_log`에 고치기 전과 후를 남겼습니다.
   - 논문 폴더에서 가장 중요한 "이 논문을 어느 코드가 구현하나" 연결을 핵심 연결로 올렸습니다. 그룹 사이는 계속 최대 N−1개로 두기 위해, 이 연결을 그룹 사이 대표 연결로 먼저 쓰고 그 때문에 중복이 된 다른 대표 연결은 약한 연결로 내렸습니다.
   - 같은 코드 파일에 이미 핵심 연결로 이어진 문서와 requirements.txt 사이의 연결(README – main.py – requirements.txt 삼각형)은 약한 연결로 내렸습니다.

모의 프로젝트는 설계도에 심은 관계가 정답이고, 그 밖의 쌍은 모두 '관계 없음'입니다(closed world). 4·5단계는 실제 프로젝트와 똑같이 거쳤고, 6단계의 논문↔구현 규칙도 같게 적용했습니다(핵심 모델 코드 → `docs/method.md`). 검토와 단순화를 마친 정답은 `gt_graphs.html`에서 볼 수 있습니다.

### 라벨 기준

판단 질문은 하나입니다. "이 프로젝트를 처음 이해하려는 사람이 한 파일을 볼 때, 다른 파일도 이어서 봐야 하는가?"

- **Y**: 구체적인 관계가 있음. 한쪽이 다른 쪽을 import, 실행, 설정, 설명, 구현, 평가, 생성, 확장함
- **W**: 실제 관계는 있지만 꼭 이어 볼 필요는 없음. 같은 구성요소의 변형, 넓게 같은 주제
- **N**: 쓸모 있는 관계가 없음. 같은 폴더에 있다는 것, 'model'·'train' 같은 흔한 단어를 공유한다는 것만으로는 관계가 아님

관계 종류는 12가지입니다. "A <관계> B"로 읽습니다.

| 관계 | 뜻 | 예 |
|---|---|---|
| uses | A가 B의 코드·데이터·설정·결과에 의존 | train.py uses model.py |
| implements | 코드 A가 방법·설계 B를 구현 | mamba2.py implements Mamba-2 논문 |
| describes | 문서 A가 파일 B를 설명 | README describes train.py |
| produces | A가 B(결과·그림·로그)를 생성 | plot.py produces figure.png |
| extends | A가 B를 발전시키거나 상속 | KAN 2.0 논문 extends KAN 논문 |
| same_method | 같은 방법이나 구성요소 | 모델 크기만 다른 두 설정 |
| supports | A가 B의 근거 | results.csv supports 논문 |
| contradicts | 서로 모순 | |
| compares | 둘을 비교 | 논문 compares 경쟁 방법 |
| same_topic | 넓게 같은 주제 | 같은 분야의 두 논문 |
| duplicate | 같은 내용의 다른 버전 | 초안 v1과 v2 |
| other | 그 밖의 관계 | |

헷갈리는 경우: 문서 → 코드는 describes, 코드 → 문서·논문은 implements로 보되 둘 다 정답으로 인정합니다. A가 B를 읽으면 uses, 만들면 produces입니다. 결과 파일과 그것을 인용하는 문서는 supports입니다. 여러 관계가 다 맞으면 더 구체적인 것을 고릅니다(produces > uses > same_method > same_topic > other).

## 4. 참고한 평가 방식

기존 벤치마크의 평가 방식을 살펴보고, '파일 사이의 관계 그래프'라는 우리 문제에 맞는 부분만 가져왔습니다.

- **Text2KGBench** (ISWC 2023): 가장 많이 참고했습니다. 원래는 문장에서 (주어, 관계, 목적어) 트리플을 뽑는 과제인데, 이를 (파일, 관계, 파일)로 바꿔 씁니다. 정답이 판정한 쌍만 precision에 넣는 방식(locally closed)도 여기서 가져왔습니다. 온톨로지 준수율은 관계 어휘 준수율로, 환각 지표는 근거 인용률로 바꿨습니다. 참고로 "가상 사용자가 피드백을 만들어 채점한다"는 방식은 이 논문에 없습니다. 가상 사용자는 아래 시뮬레이션 오라클에서 가져왔습니다.
- **TREC 풀링** (정보 검색): 여러 시스템이 낸 후보의 합집합과 무작위 쌍만 판정하는 방식입니다. 정답을 만들 때 그대로 썼습니다.
- **시뮬레이션 오라클** (Basu et al., SDM 2004): 사람 대신 정답을 아는 가상 사용자가 피드백을 주게 하고, 그 피드백을 받은 교정 방법을 비교합니다.
- **DependEval** (arXiv 2025): 저장소 의존성 이해 평가로, 노드 F1과 엣지 F1을 0.15 : 0.85로 섞습니다. 우리는 노드(파일)가 처음부터 다 주어지므로 엣지 F1만 씁니다.
- **문서–코드 추적성** (ArDoCo, LiSSA 등): 문서↔코드 연결의 recall을 따로 보는 방식만 빌려 왔습니다. ArDoCo 데이터는 Java 저장소와 아키텍처 문서 위주라 쓰지 않았습니다.
- 쓰지 않은 것: 그래프 사이 거리(4안의 Gromov–Wasserstein 등). 파일 대응이 이미 정해져 있어서 그래프를 정렬할 필요가 없고, 쌍 단위 P/R/F1이 해석하기 쉽습니다.

## 5. 측정 지표

### 기호

- **G**: 정답 연결. 핵심 연결 `G_req`(그룹 안 뼈대와 그룹 사이 최소 연결)와 약한 연결 `G_opt`로 나뉩니다.
- **N**: 관계 없다고 판정한 쌍. **J**: 판정한 쌍 전체(G와 N).
- **P**: 시스템이 보여주는 연결(상태가 proposed 또는 confirmed).
- **C**: 정답 그룹.

### 그래프 정확도 (`graph_metrics.py`)

| 지표 | 계산 | 설명 |
|---|---|---|
| Precision | \|P ∩ G\| / \|P ∩ J\| | 판정하지 않은 예측은 빼고, 그 개수만 따로 보고 |
| Recall | \|P ∩ G_req\| / \|G_req\| | 명시적 연결과 의미 연결로 나눠서도 봄 |
| F1 | 2PR / (P + R) | |
| Strict precision | \|P ∩ G_req\| / \|P ∩ J\| | 약한 연결을 맞힌 것도 오답으로 침. 느슨한 연결을 많이 내서 점수를 올리는 것을 막음 |
| Strict precision (숨길 수 있는 연결만) | 위와 같되 import·링크 예측은 뺌 | import·링크는 사실이라 시스템이 숨길 수 없음. 이걸로 감점하면 방법 간 차이가 흐려짐 |
| Grouped recall | 그룹 안 핵심 연결은 하나씩, 그룹 사이는 그룹 쌍마다 한 자리 | 그룹 사이 자리는 두 그룹 사이 정답 연결(약한 연결 포함) 중 아무거나 맞히면 인정. 정답이 그룹 쌍마다 대표 쌍 하나만 골라서, 다른 실제 쌍을 찾아도 놓친 걸로 치던 문제를 막음 |
| 그래프 복잡도 | 파일당 연결 수, 정답에서 이어진 그룹 쌍마다 그룹 사이 연결 수 | 시스템이 보여주는 그래프가 얼마나 복잡한지. 낮을수록 단순함. 정답의 핵심 연결만 그리면 그룹 쌍마다 1개. 선을 줄여도 recall이 유지돼야 의미가 있어서 recall과 같이 봄 |
| 관계 정확도 | 맞힌 쌍 중 관계까지 맞힌 비율 | 12종 기준과 4개 묶음(코드·설명·연구·주제) 기준 |
| Typed P / R / F1 | 관계까지 맞아야 정답으로 치는 P/R/F1 | |
| 방향 정확도 | 관계가 같은 쌍 중 방향까지 맞힌 비율 | 정답에 방향이 있는 경우만. 채점한 비율(coverage)을 같이 보고 |
| 관계 어휘 준수율 | 12개 관계 안에서 답한 비율 | |
| 근거 인용률 | 원문에 그대로 있는 근거 문장을 붙인 비율 | |
| 그룹 ARI / NMI | 시스템 그룹과 정답 그룹 C의 일치도 | 그룹에 없는 파일은 혼자인 그룹으로 침 |

프로젝트별 점수의 평균(macro)과 전체 건수를 합친 값(micro)을 둘 다 냅니다. 두 시스템의 차이는 프로젝트 단위 부트스트랩 10,000회로 95% 신뢰구간을 구합니다(`analyze.py`).

### 피드백 반영 (`feedback_sim.py`)

가상 사용자가 정답과 현재 그래프를 비교해서 피드백을 k개(0–16, 시드 5개) 줍니다.

| 피드백 | 언제 주나 | 뽑힐 비중 |
|---|---|---:|
| 제거 | 보이는 연결이 틀렸거나 관심 밖일 때 | 3 |
| 추가 | 중요한 연결이 안 보일 때 | 3 |
| 관계 수정 | 연결은 맞는데 관계 종류가 틀렸을 때 | 3 |
| 승인 | 연결과 관계가 다 맞을 때 | 1 |

사람은 맞는 것을 승인하기보다 틀린 것을 고치는 경우가 많아서 승인의 비중을 낮췄습니다. 가상 사용자는 세 종류(전체, 코드 작업자, 문서 작업자)입니다. 실제 프로젝트는 파일 종류로, 모의 프로젝트는 설계도의 태그로 관심 연결을 정합니다.

- **반영률**: 시킨 대로 제거·추가·수정이 됐는지 종류별로 봅니다. `finalize()`가 보장하므로 100%가 정상입니다.
- **Held-out F1**: 피드백이 직접 건드리지 않은 쌍에서 계산한 F1입니다.
- **Δ vs baseline**: 같은 피드백을 받은 baseline(직접 고친 연결만 반영하는 방법)과의 held-out F1 차이입니다. 교정 방법이 정말 일반화하는지는 이 값으로 판단합니다. 가상 사용자는 주로 틀린 쌍을 고치고 고친 쌍은 held-out에서 빠지므로, 아무것도 일반화하지 않아도 held-out F1은 오르기 때문입니다.
- **부작용**: 맞는 연결을 지워 버린 비율과, 틀린 연결을 알아서 지운 비율입니다.

## 6. 실행

```bash
for d in benchmark/gt/*/; do p=$(basename $d)              # 1. 세 시스템으로 그래프 만들기
  projectwiki build $d/project -o runs/bench_nollm/$p --no-llm --corrector baseline
  projectwiki build $d/project -o runs/bench/$p --llm-model claude-haiku-5-5 --corrector baseline
  python benchmark/eval/llm_only_baseline.py runs/bench/$p
done
python benchmark/eval/run_eval.py     # 2. 점수와 피드백 시뮬레이션 -> runs/bench/results/RESULTS.md
python benchmark/eval/analyze.py      # 3. 분석 -> runs/bench/results/ANALYSIS.md
pytest benchmark/eval                 # 평가 코드 테스트
```

새 교정 방법을 `projectwiki/models/preference.py`의 `CORRECTORS`에 등록하면 `run_eval.py`의 피드백 평가에 자동으로 들어갑니다.

## 참고문헌

- Mihindukulasooriya, Tiwari, Enguix, Lata. Text2KGBench: A Benchmark for Ontology-Driven Knowledge Graph Generation from Text. ISWC 2023. https://arxiv.org/abs/2308.02357
- Du et al. DependEval: Benchmarking LLMs for Repository Dependency Understanding. arXiv 2025. https://arxiv.org/abs/2503.06689
- Alor, Khatoonabadi, Shihab. Evaluating the Use of LLMs for Documentation to Code Traceability. arXiv 2025. https://arxiv.org/abs/2506.16440
- ArDoCo Benchmark. https://github.com/ArDoCo/Benchmark
- Fuchß et al. LiSSA: Toward Generic Traceability Link Recovery through Retrieval-Augmented Generation. ICSE 2025.
- Basu, Banerjee, Mooney. Active Semi-Supervision for Pairwise Constrained Clustering. SDM 2004.
- Voorhees, Harman (eds.). TREC: Experiment and Evaluation in Information Retrieval. MIT Press, 2005.

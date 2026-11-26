# 사용자 스터디 v2

팀 미팅(2026-11-26)에서 정한 세 가지를 보여 주는 스터디입니다.
- **A.** 기존 정리 방식보다 낫다
- **B.** 사용자 의도에 맞게 만들어진다
- **C.** 교정이 잘 반영된다

참가자는 폴더를 모르니 정답을 맞히는 문제는 없습니다. 과제 1이 끝날 때까지는 어느 정리가 우리 것인지 드러나지 않게, 헤더·시작 화면에 ProjectWiki 이름을 쓰지 않고 도구 연습도 과제 1 뒤에 둡니다. 차이를 보여 주고 평가와 소감을 받습니다. 본인 폴더로 해 보는 단계는 뺐습니다. 설계 문서는 `스터디_v2_설계.md`(사용자 폴더)에 있습니다.

## 진행 (약 25분)

| 단계 | 내용 | 남는 값 |
|---|---|---|
| 시작 | 소개 → 참여 안내 → 정보 입력 세 장. 닉네임과 배경 3문항 (실명·이메일 받지 않음) | `name`, `level`, `organize`, `graphtool` |
| 과제 1 (A) | 짧은 화면 안내(위치만 알려 주고 특정 정리를 누르게 하지 않음) → 정리 A, B, C를 차례로 살펴보기: 정리마다 같은 할 일(파일 하나, 선 하나 누르기)과 "선은 무엇으로 이었고, 색 묶음은 무엇끼리 묶었는지" 사실 설명(이름은 가림) → 문항마다 세 정리를 나란히 1~7 (탭으로 다시 볼 수 있음). 시간 제한 없음 | `t1_<방식>_{glance,why,trust,use}`, 살펴본 시간 `_sec`, 평가 중 다시 본 시간 `_rsec`, 연 횟수 `_visits` |
| 과제 1 고르기 | 1순위, 이유, 폴더 소개 한두 문장 (역시 탭으로 다시 볼 수 있음). 제출 뒤 세 방식의 정체 공개 | `t1_best`, `t1_why`, `t1_desc` |
| 연습 | 정체 공개 뒤, 연습 폴더(`mock_sleep_grades`)에서 ProjectWiki로 파일 → 연결 → 그룹 → 고치기를 한 단계씩 해 봄 | 단계별 시간 |
| 과제 2-1 (B) | 의도 두 개(랩미팅 발표, 인수인계)를 차례로 적용. 그룹 재묶음, 굵어짐·흐려짐, 먼저 볼 파일 표시. 적용 전·후 토글 | `t2a_<의도>_{fit,change,note}` |
| 과제 2-2 (C) | 인수인계 그래프에 심어 둔 두 곳을 고치거나 그대로 둠. 함께 조정된 연결과 이유 표시, 동의 안 함 표시 가능 | `t2b_issue1/2`, `t2b_c_{fit,side,trust}`, `t2b_disagree` |
| 마무리 | A(양극 척도: 다른 방식보다 덜/더 도움)·B·C 요약, 고치기 쉬움, 재사용 의향, 좋았던 점·아쉬운 점·쓰고 싶은 상황 | `s_*` |

탭 순서(라틴 방진)와 의도 순서는 참가자 번호로 정해지며 `t1_order`, `intent_order`에 남습니다. 고친 내용은 시스템과 같은 `FeedbackEvent` 형식으로 `log.feedback`에 남습니다.

## 데이터

```
data/<project>/graphs/{obsidian,similar,ours}.json   Graph 형식 (= final_graph.json)
data/mock_plant_fewshot/intents/{talk,handover}.json  setup 세 답 + 그 결과 그래프 + 먼저 볼 파일
data/mock_plant_fewshot/corrections/issue{1,2}.json   심어 둔 곳 + 선택지별 feedback_changes 보고
```

`meta.source`는 데이터의 출처를 나타냅니다.
- `rule`: 규칙으로 만든 것
- `hand`: 실제 시스템 출력이 나오기 전까지 쓰는 임시 데이터
- `system`: 실제 시스템 출력

`hand`가 남아 있으면 빌드할 때 경고하고, 화면 위에 "시험판"이라고 표시합니다.

| 파일 | 지금 | 실제 출력으로 바꾸려면 |
|---|---|---|
| `graphs/obsidian.json`, `similar.json` | `make_baselines.py` 규칙 (rule). Obsidian식은 폴더별 그룹(Obsidian 그래프 뷰의 path 색 그룹)과 "A에 B의 파일 이름이 적혀 있습니다" 같은 연결 설명, 유사도는 공통 단어로 묶은 그룹(평균 연결 군집)과 "함께 자주 나오는 단어" 설명. 파일 요약은 둘 다 파일의 첫 제목·첫 줄 | `make_baselines.py <project> --from-graph runs/x/graph.json` (후보 단계를 reason으로 거름, 그룹과 설명은 같은 규칙) |
| `graphs/ours.json` | 정답 데이터 기반 (hand) | `projectwiki build` 의 `final_graph.json` |
| `intents/*.json` | groupings / purposes 정답 + 시스템의 `priority_nodes` 규칙 (hand) | 같은 세 답으로 `build --setup`, `graph`와 `priority_files` 교체 |
| `corrections/*.json` | 선택지별 보고를 손으로 작성 (hand) | 같은 events로 `projectwiki correct`, `feedback_changes()` 보고를 `options.<type>.report`에 |

연결 방향은 `source → target` 그대로 씁니다. 방향 있는 관계에는 화살표를 그립니다.
- 시스템은 아직 방향 교정을 반영하지 않습니다. 기존 연결에 `edge_add`를 보내면 관계 이름만 바뀝니다.
- 스터디의 "방향 바꾸기"는 source와 target을 바꾼 `edge_add`로 기록하고, 화면에서 화살표만 뒤집어 보여 줍니다.

## 빌드

```
python user_study_v2/make_baselines.py mock_plant_fewshot
python user_study_v2/make_baselines.py mock_sleep_grades
python user_study_v2/make_hand.py
python user_study_v2/build.py            # -> user_study_v2/study.html
```

결과는 `user_study_v2/send.json`의 Apps Script 웹앱 주소로 보냅니다(지금은 v1과 같은 웹앱, 같은 응답 시트의 `results` 탭에 열이 추가되며 쌓임). 보내지 못하면 끝 화면에서 다시 보내기나 파일 저장을 고를 수 있습니다.
- 받는 쪽은 `user_study/apps_script/Code.gs`의 `kind: "result"`이고, 값마다 열이 하나씩 생깁니다.
- 주소가 없으면 끝 화면에서 결과 파일을 저장하게 합니다.

## 화면

- 그래프 보기는 팀 뷰어의 색, 모양, 화살표, 인스펙터 순서를 따릅니다.
- 그룹은 2D 위에 색 영역과 이름으로 늘 보이고, 영역이 겹치지 않게 줄 맞춰 놓습니다.
- 화면 구성은 모든 단계에서 같습니다. 단계 시작 때 가운데 소개 한 번, 그 뒤 왼쪽 위 '지금 할 일' 체크리스트(해 보면 자동 체크). 과제 중 질문은 오른쪽 패널의 [질문] 탭에 크게 나오고(그래프를 누르면 [내용과 근거]로 바뀌었다가 탭으로 돌아옴), 다음·제출 버튼은 질문 아래에 고정됩니다.
- 과제 1의 각 정리가 어떻게 만들어졌는지(선, 색 묶음, 선을 누르면)는 그래프 왼쪽 위에 고정해 둡니다.
- 연결을 고칠 수 있는 단계에서는 선을 누르면 오른쪽 패널 맨 위에 고치기 막대가 붙어 나옵니다(스크롤해도 위에 남음).
- 의도 적용·되돌리기·그룹 이동 때는 새 배치를 화면 밖에서 미리 계산한 뒤 0.9초 동안 미끄러지듯 옮기고, 선 강조는 도착한 뒤 바꿉니다.
- 화면 담당자의 새 UI가 나오면 `study_template.html`의 viewer 부분(`workspace`부터 `showReport`까지)을 바꿔 끼우면 됩니다.

## 화면에 쓰는 피드백 이름

참가자 화면의 버튼 이름은 시스템 피드백 종류와 이렇게 대응합니다. 기록은 시스템 이름 그대로 남습니다.

| 화면 | 시스템 (`FeedbackEvent.type`) |
|---|---|
| 필요한 연결 | `edge_confirm` |
| 틀린 연결 | `edge_wrong` |
| 지금은 불필요 | `edge_irrelevant` |

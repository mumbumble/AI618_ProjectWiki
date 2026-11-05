# 8. 시각화 (`stage8_viz`, 후순위)

최종 그래프를 보고 교정할 수 있게 만듭니다.

- **입력**: 최종 `Graph`, `Record`
- **출력**: `<출력폴더>/view.html`, Obsidian 볼트(`projectwiki obsidian`)

| 파일 | 내용 |
|---|---|
| `template.html` | 뷰어 (vis-network, 인라인 JS). 근거 패널, 교정 버튼, 피드백 내보내기 |
| `html.py` | 그래프 데이터를 템플릿에 넣어 `view.html`을 씀. 관계 이름의 한국어 표시(`RELATION_NAMES`) |
| `obsidian.py` | 파일마다 노트 하나, 연결은 `[[위키링크]]`, 그룹은 태그 |

**고칠 때**

- 뷰어 화면이나 교정 버튼: `template.html`
  - 뷰어 안의 `applyEvents()`는 7단계 `finalize.py`의 편집 규칙을 그대로 따라야 합니다.
- 관계 이름 표시: `html.py`의 `RELATION_NAMES`

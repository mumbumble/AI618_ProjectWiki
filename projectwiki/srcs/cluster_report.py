"""Self-contained HTML for reviewing clustering as a project-onboarding aid."""
from __future__ import annotations

import html
import json
from pathlib import Path

from .record import Record

METHODS = {
    "baseline": "내용·폴더 거리의 평균 연결 군집화. 사용자 선호 미반영.",
    "pref": "평가한 쌍의 거리 수정과 앵커별 그룹 배치.",
    "metric": "내용·폴더·형식 거리 가중치 학습. 앵커 배치는 pref와 동일.",
    "constrained": "제약 기반 평균 연결. 4–5점은 함께 묶고 1–2점은 분리. 앵커 분리·cannot-link가 충돌한 must-link보다 우선.",
    "graph": "의미 유사도 kNN + import·문서 링크 그래프의 spectral 군집화. 앵커는 강제하지 않음.",
    "hdbscan": "밀도 기반 그룹과 미분류 파일. 앵커는 강제하지 않음.",
}
esc = html.escape


def percent(value) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def number(value) -> str:
    return "—" if value is None else f"{value:.2f}"


def table(headers: list[str], rows: list[list[str]]) -> str:
    return ('<div class="table-wrap"><table><thead><tr>'
            + "".join(f"<th>{esc(h)}</th>" for h in headers) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>" for row in rows)
            + "</tbody></table></div>")


def write_comparison_html(record: Record, result: dict, path: Path) -> Path:
    names = list(result["methods"])
    summary, sections = [], []
    for index, name in enumerate(names):
        metrics = result["methods"][name]
        ident = f"method-{index}"
        summary.append([f'<a href="#{ident}"><strong>{esc(name)}</strong></a>',
                        percent(metrics["pair_accuracy"]), percent(metrics["balanced_accuracy"]),
                        percent(metrics["file_coverage"]), str(metrics["group_count"]),
                        str(metrics["singleton_groups"]), number(metrics["mean_groups_to_visit"]),
                        number(metrics["mean_files_to_scan"]), percent(metrics["structural_cohesion"])])
        tasks = table(["탐색 체크리스트", "방문 그룹/미분류 파일 ↓", "훑을 파일 ↓", "그중 불필요 파일", "미분류 대상"],
                      [[esc(t["name"]), str(t["groups_to_visit"]), str(t["files_to_scan"]),
                        str(t["extra_files"]), str(t["ungrouped_targets"])] for t in metrics["task_scores"]])
        cards = []
        for group in metrics["groups"]:
            members = []
            for member in group["members"]:
                file = record.file_by_path[member]
                url = (Path(record.root) / member).resolve().as_uri()
                members.append(f'<li><a href="{esc(url, quote=True)}">{esc(member)}</a>'
                               f'<span class="type">{esc(file.type)}</span></li>')
            cards.append(f'<article class="group"><div class="group-head"><strong>{esc(group["id"])}</strong>'
                         f'<span>{len(group["members"])} files</span></div>'
                         f'<p class="representative">중심 파일 · <code>{esc(group["representative"])}</code></p>'
                         f'<blockquote>{esc(group["preview"]) or "경로만 있는 파일"}'
                         f'<small>{esc(group["locator"])}</small></blockquote>'
                         '<ul>' + "".join(members) + '</ul></article>')
        noise = "".join(f"<li>{esc(p)}</li>" for p in metrics["ungrouped_files"])
        if noise:
            cards.append(f'<article class="group noise"><strong>미분류 · {metrics["ungrouped"]} files</strong>'
                         f'<p>파일은 유지됩니다. 각 파일을 개별 탐색 대상으로 계산합니다.</p><ul>{noise}</ul></article>')
        outcomes = table(["파일 A", "파일 B", "점수", "기대", "실제", "일치"],
                         [[esc(p["a"]), esc(p["b"]), str(p["score"]), esc(p["expected"]), esc(p["predicted"]),
                           "—" if p["correct"] is None else "✓" if p["correct"] else "✕"]
                          for p in metrics["pair_outcomes"]])
        diagnostics = esc(json.dumps(metrics["diagnostics"], ensure_ascii=False, indent=2))
        viewer = (f'<p><a href="{esc(metrics["viewer"], quote=True)}">이 방법의 관계 그래프 뷰어 열기 →</a></p>'
                  if metrics.get("viewer") else "")
        sections.append(f'<section class="method" id="{ident}"><header><h2>{esc(name)}</h2>'
                        f'<p>{esc(METHODS.get(name, "사용자 지정 방법"))}</p></header>'
                        f'{viewer}'
                        f'<p class="detail">입력 거리 RMSE {number(metrics["distance_rmse"])} · '
                        f'평가 쌍 커버리지 {percent(metrics["pair_coverage"])} · '
                        f'군집화 {metrics["seconds"]:.4f}초</p>'
                        f'{tasks}<div class="groups">' + "".join(cards) + '</div>'
                        f'<details><summary>평가 쌍별 결과</summary>{outcomes}</details>'
                        f'<details><summary>알고리즘 진단</summary><pre>{diagnostics}</pre></details></section>')
    splits = result["splits"]
    options = "".join(f'<option value="method-{i}">{esc(name)}</option>' for i, name in enumerate(names))
    overview = table(["방법", "평가 일치율", "균형 일치율", "파일 커버리지", "그룹 수", "단독 그룹",
                      "평균 방문 수 ↓", "평균 훑을 파일 ↓", "참조 응집도"], summary)
    sensitivity = ""
    if result.get("sensitivity"):
        sensitivity = ('<h2>설정 변화에 따른 민감도</h2>'
                       '<p class="note">미리 정한 소규모 설정 범위를 모두 표시합니다. 같은 예시 평가셋을 반복 사용한 탐색이며 '
                       '최적 설정 선택이나 독립 검증이 아닙니다.</p>'
                       + table(["방법", "설정", "값", "평가 일치율", "파일 커버리지", "그룹 수", "평균 방문 수", "평균 훑을 파일"],
                               [[esc(row["method"]), esc(row["parameter"]),
                                 str(row["value"]) + (" · 본 실험" if row["main_setting"] else ""),
                                 percent(row["pair_accuracy"]), percent(row["file_coverage"]), str(row["group_count"]),
                                 number(row["mean_groups_to_visit"]), number(row["mean_files_to_scan"])]
                                for row in result["sensitivity"]]))
    page = PAGE.replace("__CONTENT__", f'''
<header class="hero"><p class="eyebrow">PROJECTWIKI · CLUSTERING EXPERIMENT</p>
<h1>프로젝트 파악을 위한 군집화 비교</h1>
<p>{esc(result['encoder'])} · {result['files']}개 파일 · 학습 {splits['train']['valid']}쌍 · 평가 {splits['test']['valid']}쌍</p>
<p class="purpose">{esc(result['settings']['purpose'])}</p></header>
<aside>작은 예제의 탐색 실험입니다. 체크리스트는 파일 내용에서 구성한 대리 과제이며 사용자 연구 결과가 아닙니다.
방문 수는 대상 파일이 속한 그룹 수에 미분류 대상 수를 더한 값입니다. 훑을 파일 수는 방문한 그룹의 모든 파일을 검토한다고 가정합니다.
한 그룹에 모두 넣으면 방문 수만 줄어들므로 두 값을 함께 보세요.</aside>
{overview}
<p class="note">미분류가 포함된 평가 쌍은 정답으로 세지 않습니다. 참조 응집도는 import·문서 링크가 같은 그룹에 놓인 비율이며,
graph 방법의 입력에도 사용하므로 독립적인 정확도 지표가 아닙니다. 거리 RMSE는 입력 거리의 평가로, 군집화 자체의 순위를 뜻하지 않습니다.</p>
<nav><label>방법 <select id="method-filter"><option value="all">전체 비교</option>{options}</select></label>
<label>파일·근거 검색 <input id="search" type="search" placeholder="예: src/train.py, loss"></label></nav>
{''.join(sections)}
{sensitivity}
<footer>새로 다운로드하거나 LLM을 호출하지 않고 동일한 저장 레코드로 비교했습니다.
<a href="https://www.wkiri.com/research/papers/wagstaff-kmeans-01.pdf">Pairwise constraints 연구</a> ·
<a href="https://scikit-learn.org/stable/modules/generated/sklearn.cluster.SpectralClustering.html">SpectralClustering</a> ·
<a href="https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html">HDBSCAN</a></footer>
''')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path


PAGE = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ProjectWiki · 군집화 비교</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f6fa;color:#202c40;font:15px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1440px;margin:auto;padding:40px 28px}h1{font-size:32px;letter-spacing:-1px;margin:8px 0}h2{font-size:25px;margin:0}
.eyebrow{color:#4870a5;letter-spacing:2px;font-size:12px;font-weight:700}.hero{margin-bottom:24px}.purpose{font-size:18px}
aside{background:#e9eff8;border-left:4px solid #4d73ad;padding:16px 20px;border-radius:6px;margin:24px 0}.note,.detail,footer{color:#596a80;font-size:13px}
.table-wrap{overflow-x:auto;border:1px solid #dce3ec;border-radius:10px;background:white;margin:16px 0}table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:12px 14px;border-bottom:1px solid #e8edf4;text-align:left}th{white-space:nowrap;background:#eef2f8;color:#4a5d77}tr:last-child td{border-bottom:0}
a{color:#285b9c;text-decoration:none}a:hover{text-decoration:underline}nav{position:sticky;top:0;z-index:1;background:#f4f6faf2;display:flex;gap:24px;padding:16px 0;border-bottom:1px solid #dce3ec}
label{display:flex;align-items:center;gap:10px;font-size:13px}input,select{font:inherit;padding:9px 12px;border:1px solid #cdd7e4;border-radius:7px;background:white}input{width:300px}
.method{padding:28px 0;border-bottom:1px solid #dce3ec;scroll-margin-top:85px}.method header p{margin:8px 0;color:#596a80}.groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px;margin:24px 0}
.group{background:white;border:1px solid #dce3ec;border-radius:12px;padding:20px;overflow-wrap:anywhere}.group-head{display:flex;justify-content:space-between;color:#4870a5}.representative{font-size:13px}
blockquote{margin:12px 0;background:#f5f7fb;padding:12px;border-radius:6px;font-size:12px;color:#53637a}blockquote small{display:block;color:#8090a5;margin-top:6px}
ul{padding-left:18px;margin-bottom:0}li{font-size:13px;margin:6px 0}.type{font-size:10px;color:#7b899c;margin-left:8px}.noise{border-color:#d8b889;background:#fffcf5}
details{padding:12px 0}summary{cursor:pointer;color:#4a6280;font-size:13px}pre{white-space:pre-wrap;background:white;padding:16px;border-radius:8px;font-size:12px}footer{padding-top:28px}
[hidden]{display:none!important}@media(max-width:650px){main{padding:24px 14px}h1{font-size:25px}nav{flex-wrap:wrap;gap:10px}input{width:210px}.groups{grid-template-columns:1fr}}
</style><main>__CONTENT__</main><script>
const methodFilter=document.getElementById('method-filter'), search=document.getElementById('search');
function filter(){document.querySelectorAll('.method').forEach(section=>{section.hidden=methodFilter.value!=='all'&&section.id!==methodFilter.value;section.querySelectorAll('.group').forEach(card=>{card.hidden=!card.textContent.toLowerCase().includes(search.value.toLowerCase())})})}
methodFilter.addEventListener('change',filter);search.addEventListener('input',filter);
document.querySelectorAll('a[href^="#method-"]').forEach(link=>link.addEventListener('click',()=>{methodFilter.value='all';filter()}));
</script></html>'''

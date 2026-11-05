"""`projectwiki report <out>`: one HTML page that shows each stage's actual output next to the meeting plan.

Charts are inline SVG built here (no plotting library). Stage 6 is recomputed for every registered corrector
on the saved graph and feedback, so the methods in the experimental slot can be compared on one page.
"""
from __future__ import annotations

import html
import json
import posixpath
from collections import Counter
from pathlib import Path

import numpy as np

from .config import Config
from .correct import CORRECTORS, get_corrector
from .feedback import read_events, resolve
from .graph import STRUCTURAL
from .record import Record
from .schema import FEEDBACK_TYPES, VISIBLE_STATUS, Graph, edge_key
from .viz.html import RELATION_NAMES

PALETTE = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#76b7b2", "#edc948", "#b07aa1", "#ff9da7",
           "#9c755f", "#86bcb6", "#d37295", "#8cd17d", "#a0cbe8", "#ffbe7d", "#f1ce63", "#bab0ac"]
GREY = "#9aa0a6"
esc = html.escape


def load(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def base(p: str) -> str:
    return posixpath.basename(p)


# ---- charts -------------------------------------------------------------------------------------

def hbar(items: list[tuple[str, float]], width: int = 460, fmt: str = "{:g}") -> str:
    if not items:
        return '<p class="muted">없음</p>'
    top = max(v for _, v in items) or 1
    row, lab = 22, 170
    out = [f'<svg viewBox="0 0 {width} {row * len(items) + 6}" class="chart bars" role="img">']
    for i, (k, v) in enumerate(items):
        y = 3 + i * row
        w = (width - lab - 70) * v / top
        out.append(f'<text x="{lab - 8}" y="{y + 15}" text-anchor="end" class="lab">{esc(str(k))[:28]}</text>'
                   f'<rect x="{lab}" y="{y + 4}" width="{w:.1f}" height="{row - 9}" rx="3" class="bar"/>'
                   f'<text x="{lab + w + 6:.1f}" y="{y + 15}" class="val">{fmt.format(v)}</text>')
    return "".join(out) + "</svg>"


def hist(values: list[float], bins: int = 10, width: int = 460, height: int = 150) -> str:
    if not values:
        return '<p class="muted">없음</p>'
    counts, edges = np.histogram(values, bins=bins)
    top, pad, bw = max(counts) or 1, 28, (width - 40) / bins
    out = [f'<svg viewBox="0 0 {width} {height}" class="chart bars" role="img">']
    for i, c in enumerate(counts):
        h = (height - pad - 10) * c / top
        out.append(f'<rect x="{30 + i * bw:.1f}" y="{height - pad - h:.1f}" width="{bw - 2:.1f}" height="{h:.1f}" '
                   f'class="bar"><title>{edges[i]:.2f}–{edges[i + 1]:.2f}: {c}</title></rect>')
    out.append(f'<text x="30" y="{height - 8}" class="val">{edges[0]:.2f}</text>'
               f'<text x="{width - 10}" y="{height - 8}" text-anchor="end" class="val">{edges[-1]:.2f}</text>')
    return "".join(out) + "</svg>"


def scatter(xy: np.ndarray, colors: list[str], titles: list[str], width: int = 520, height: int = 340) -> str:
    if len(xy) == 0:
        return '<p class="muted">없음</p>'
    lo, hi = xy.min(0), xy.max(0)
    span = np.where(hi - lo > 1e-9, hi - lo, 1.0)
    p = (xy - lo) / span * [width - 30, height - 30] + 15
    out = [f'<svg viewBox="0 0 {width} {height}" class="chart frame" role="img">']
    for (x, y), c, t in zip(p, colors, titles):
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{c}" fill-opacity="0.85"><title>{esc(t)}</title></circle>')
    return "".join(out) + "</svg>"


def legend(items: list[tuple[str, str]]) -> str:
    return '<div class="legend">' + "".join(
        f'<span><i style="background:{c}"></i>{esc(k)}</span>' for k, c in items) + "</div>"


def pca2(x: np.ndarray) -> np.ndarray:
    if len(x) < 3:
        return np.zeros((len(x), 2))
    x = x - x.mean(0)
    return x @ np.linalg.svd(x, full_matrices=False)[2][:2].T


def spring_layout(n: int, pairs: list[tuple[int, int]], iters: int = 400, seed: int = 0) -> np.ndarray:
    """Fruchterman–Reingold layout with a pull toward the centre, in numpy."""
    rng = np.random.default_rng(seed)
    pos = rng.uniform(-1, 1, (n, 2))
    if n < 2:
        return pos
    k = 1.6 / np.sqrt(n)
    a = np.array([i for i, _ in pairs], int)
    b = np.array([j for _, j in pairs], int)
    temp = 0.15
    for _ in range(iters):
        delta = pos[:, None, :] - pos[None, :, :]
        dist = np.linalg.norm(delta, axis=-1) + 1e-6
        disp = ((k * k / dist ** 2)[..., None] * delta).sum(1)
        if len(a):
            d = pos[a] - pos[b]
            f = d * (np.linalg.norm(d, axis=1, keepdims=True) / k)
            np.add.at(disp, a, -f)
            np.add.at(disp, b, f)
        disp -= pos * 0.6
        length = np.linalg.norm(disp, axis=1, keepdims=True) + 1e-9
        pos += disp / length * np.minimum(length, temp)
        temp = max(temp * 0.99, 0.005)
    return pos


def graph_svg(g: Graph, gcolor: dict, width: int = 980, height: int = 680, labels: int = 30) -> str:
    idx = {n.id: i for i, n in enumerate(g.nodes)}
    shown = [e for e in g.edges if e.status in VISIBLE_STATUS]
    pos = spring_layout(len(g.nodes), [(idx[e.source], idx[e.target]) for e in shown])
    lo, hi = pos.min(0), pos.max(0)
    p = (pos - lo) / np.where(hi - lo > 1e-9, hi - lo, 1.0) * [width - 160, height - 40] + [80, 20]
    deg = Counter([e.source for e in shown] + [e.target for e in shown])
    out = [f'<svg viewBox="0 0 {width} {height}" class="chart frame" role="img">']
    for e in g.edges:
        removed = e.status not in VISIBLE_STATUS
        color = "var(--bad)" if removed else "var(--ok)" if e.origin == "user" else (
            "var(--accent)" if e.status == "confirmed" else "var(--edge)")
        dash = ' stroke-dasharray="4 3"' if (not e.direct or removed) else ""
        width_ = 2.4 if e.status == "confirmed" else 0.8 if removed else 1.0
        opacity = 0.22 if removed else 0.7
        (x1, y1), (x2, y2) = p[idx[e.source]], p[idx[e.target]]
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" '
                   f'stroke-width="{width_}" stroke-opacity="{opacity}"{dash}>'
                   f'<title>{esc(base(g.nodes[idx[e.source]].path))} → {esc(base(g.nodes[idx[e.target]].path))}: '
                   f'{esc(RELATION_NAMES.get(e.relation, e.relation))} ({e.status})</title></line>')
    top = {nid for nid, _ in deg.most_common(labels)}
    for n, (x, y) in zip(g.nodes, p):
        r = 3.5 + min(9.0, 1.2 * deg[n.id] ** 0.8)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{gcolor.get(n.group, GREY)}" '
                   f'stroke="var(--bg)" stroke-width="1"><title>{esc(n.path)} (연결 {deg[n.id]})</title></circle>')
        if n.id in top:
            out.append(f'<text x="{x + r + 3:.1f}" y="{y + 4:.1f}" class="node">{esc(base(n.path))[:30]}</text>')
    return "".join(out) + "</svg>"


# ---- page parts ---------------------------------------------------------------------------------

def table(head: list[str], rows: list[list[str]], cls: str = "") -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tablewrap"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def badge(kind: str, text: str) -> str:
    return f'<span class="badge {kind}">{esc(text)}</span>'


def quote(text: str, n: int = 220) -> str:
    t = " ".join(text.split())
    return esc(t[:n] + ("…" if len(t) > n else ""))


def feedback_check(final: Graph, feedback) -> list[list[str]]:
    """Expected vs actual state of every explicit edit (the last event per target wins)."""
    edges = {e.id: e for e in final.edges}
    nodes = {n.id: n for n in final.nodes}
    gname = {g.id: g.name for g in final.groups}
    last = {}
    for ev in feedback:
        last[edge_key(ev.source, ev.target) if ev.type.startswith("edge_") else ("node", ev.node)] = ev
    rows = []
    for ev in last.values():
        if ev.type.startswith("edge_"):
            e = edges.get(edge_key(ev.source, ev.target))
            want = {"edge_confirm": "confirmed", "edge_add": "confirmed", "edge_wrong": "removed_wrong",
                    "edge_irrelevant": "removed_irrelevant"}[ev.type]
            # a rejected edge that this run did not propose again is also absent from the map, as intended
            got = e.status if e else ("제안 안 됨" if ev.type in ("edge_wrong", "edge_irrelevant") else "(없음)")
            want = "제안 안 됨" if got == "제안 안 됨" else want
            what = f"{esc(base(nodes[ev.source].path))} – {esc(base(nodes[ev.target].path))}"
        else:
            n = nodes[ev.node]
            want = ev.group if ev.type == "node_move" else "(그룹 없음)"
            got = gname.get(n.group, n.group) if n.group else "(그룹 없음)"
            got = ev.group if ev.type == "node_move" and n.group == ev.group else got
            what = esc(base(n.path))
        ok = got == want
        rows.append([esc(FEEDBACK_TYPES[ev.type]), what, esc(want), esc(str(got)),
                     badge("ok" if ok else "bad", "유지됨" if ok else "다름")])
    return rows


def report(out: Path) -> Path:
    out = Path(out)
    cfg = Config.load(out / "config.json")
    rec = Record.load(out)
    g5 = Graph.from_dict(load(out / "graph.json"))
    final = Graph.from_dict(load(out / "final_graph.json"))
    feedback = resolve(read_events(out / "feedback.jsonl"), rec)
    prefs = load(out / "prefs.json", {}) or {}
    info = load(out / "run_info.json", {}) or {}
    changes = info.get("changes", {})
    gcolor = {g.id: PALETTE[i % len(PALETTE)] for i, g in enumerate(final.groups)}
    types = Counter(f.type for f in rec.files)
    tcolor = {t: PALETTE[i % len(PALETTE)] for i, t in enumerate(sorted(types))}
    llm_on = cfg.llm and any(f.summary for f in rec.files)
    n_files, n_chunks = len(rec.files), len(rec.chunks)
    summarized = sum(1 for f in rec.files if f.summary and f.type != "image")
    images = [f for f in rec.files if f.type == "image"]
    described = sum(1 for f in images if f.summary)
    reasons = Counter(e.reason for e in g5.edges)
    judged = sum(1 for e in g5.edges if e.label)
    visible = [e for e in final.edges if e.status in VISIBLE_STATUS]
    fb_rows = feedback_check(final, feedback)
    kept = sum(1 for r in fb_rows if "유지됨" in r[-1])

    # stage 6 for every registered corrector, on the same graph and feedback
    compare = []
    for name in CORRECTORS:
        c = get_corrector(name, cfg).correct(g5, feedback, rec)
        hidden = {e.id for e in g5.edges if e.id in set(c.hide) and e.reason not in STRUCTURAL}
        reinforced = [e for e in g5.edges if e.id in c.explanations and e.id not in set(c.hide)]

        def line(e, tag):
            return (f"{tag} {esc(base(rec.file_by_id[e.source].path))} – {esc(base(rec.file_by_id[e.target].path))}: "
                    f"{esc(c.explanations.get(e.id, ''))}")
        examples = ([line(e, "숨김") for e in g5.edges if e.id in hidden][:3]
                    + [line(e, "강화") for e in reinforced][:3])
        compare.append((name, len(hidden), len(reinforced), c.notes, examples))
    current = next(x for x in compare if x[0] == cfg.corrector) if cfg.corrector in CORRECTORS else None

    # ---- pipeline strip and plan check
    off = "Claude 꺼짐"
    strip = [
        ("1", "파일 입력", "PyMuPDF · AST · Markdown", f"파일 {n_files} · 조각 {n_chunks}", "ok"),
        ("2", "인코딩", "bge-m3", f"{rec.chunk_emb.shape[1]}차원 · 새로 {changes.get('encoded', '?')}", "ok"),
        ("3", "프로젝트 레코드", "Haiku 요약 · Sonnet 그림", f"요약 {summarized} · 그림 {described}/{len(images)}",
         "ok" if llm_on else "warn"),
        ("4", "군집화 🧪", cfg.clusterer, f"그룹 {len(g5.groups)}", "ok"),
        ("5", "그래프 생성", "reranker · Sonnet 판정", f"연결 {len(g5.edges)} · 판정 {judged}",
         "ok" if judged else "warn"),
        ("6", "선호도 교정 🧪", cfg.corrector, f"피드백 {len(feedback)}" + (
            f" · 숨김 {current[1]} · 강화 {current[2]}" if current else ""), "ok" if feedback else "warn"),
        ("7", "최종 그래프", "편집 재적용", f"표시 {len(visible)} · 편집 유지 {kept}/{len(fb_rows)}",
         "ok" if kept == len(fb_rows) else "bad"),
        ("8", "시각화", "view.html · Obsidian", "지도 · 근거 · 교정", "ok"),
    ]
    strip_html = '<div class="strip">' + "".join(
        f'<div class="stage {s}"><div class="num">{n}</div><div class="name">{esc(t)}</div>'
        f'<div class="method">{esc(m)}</div><div class="metric">{esc(v)}</div></div>'
        + ('<div class="arrow">→</div>' if n != "8" else "") for n, t, m, v, s in strip) + "</div>"

    verdict = lambda ok, text: badge("ok" if ok is True else "warn" if ok is None else "bad", text)
    guide = prefs.get("guide") or {}
    plan_rows = [
        ["1 파일 입력", "1안 ① 파일·디렉토리 입력 / 4안 ① 문단·함수 단위 분할, 파일 고정 ID(경로+해시)",
         f"파일 {n_files}개 → 근거 조각 {n_chunks}개 ({', '.join(f'{k} {v}' for k, v in types.most_common())}). "
         "ID = 경로 해시, 내용 변경은 sha256", verdict(True, "일치")],
        ["2 인코딩", "4안 ① bge-m3", f"조각·요약 → bge-m3 {rec.chunk_emb.shape[1]}차원, 이번 실행에서 새로 인코딩 "
         f"{changes.get('encoded', '?')}개 (나머지 캐시)", verdict(True, "일치")],
        ["3 프로젝트 레코드", "4안 ① 근거 레코드(원문 + 출처 ID + 위치 + 임베딩)",
         f"조각마다 원문·위치·벡터 저장. 파일 요약 {summarized}개, 그림 설명 {described}/{len(images)}개",
         verdict(True if llm_on else None, "일치" if llm_on else f"부분 ({off})")],
        ["4 군집화 🧪", "1안 ② 제목·위치로 그룹 + 중요 파일 선택 / 회의: 쌍 1–5 평가, 객관식 가이드",
         f"{esc(cfg.clusterer)}: 그룹 {len(g5.groups)}개. 선호 입력: 중요 파일 {len(prefs.get('anchors', []))}, "
         f"쌍 평가 {len(prefs.get('pairs', []))}, 가이드 {esc(json.dumps(guide, ensure_ascii=False)) if guide else '없음'}",
         verdict(True if prefs.get("anchors") or prefs.get("pairs") or guide else None,
                 "동작" if prefs.get("anchors") or prefs.get("pairs") or guide else "선호 입력 없음 → 폴더 기준과 비슷")],
        ["5 그래프 생성", "1안 ③ 그룹 안 관계 검토(LLM) / 4안 ② 근거 인용 필수, 원문 불일치 제외",
         f"후보 {len(g5.edges)}개 ({', '.join(f'{k} {v}' for k, v in reasons.most_common())}), 근거 쌍은 reranker, "
         f"Claude 판정 {judged}개", verdict(True if judged else None, "일치" if judged else f"부분 ({off})")],
        ["6 선호도 교정 🧪", "1안 ⑤ 빠진·잘못된·목적상 불필요 피드백 → 선호 정렬 / 4안 ③ r(e)=sim(승인)−sim(거절), "
         "사실 오류는 재제안 차단",
         f"피드백 {len(feedback)}개. 방법별 비교는 6단계 표 참고", verdict(True if feedback else None,
                                                             "동작" if feedback else "피드백 없음")],
        ["7 최종 그래프", "4안 ⑤ 사용자가 수정한 부분은 유지",
         f"표시 연결 {len(visible)}개. 직접 편집 {kept}/{len(fb_rows)}개가 최종 그래프에 그대로 남음",
         verdict(kept == len(fb_rows), "일치" if kept == len(fb_rows) else "확인 필요")],
        ["8 시각화", "1안 ⑥ 누르면 연계 파일 목록·썸네일 / 4안 ④ 관계 클릭 → 양쪽 원문",
         "view.html: 연결 목록, 양쪽 근거 인용, 교정 버튼, 피드백 내보내기. 이미지 썸네일은 없음",
         verdict(None, "부분 (썸네일 없음)")],
        ["증분 갱신", "4안 ⑤ 해시 비교로 변경 감지, 변경 파일 주변만 재처리",
         f"추가 {len(changes.get('added', []))}, 변경 {len(changes.get('changed', []))}, "
         f"삭제 {len(changes.get('removed', []))} 감지. 인코딩·LLM은 변경분만, 후보 연결은 전체를 다시 만듦",
         verdict(None, "부분")],
        ["정렬도 측정", "4안 Gromov–Wasserstein (교정 전·후·신규 자료 후)", "—", verdict(False, "미구현")],
    ]

    # ---- stage sections
    folders = Counter(f.path.split("/")[0] if "/" in f.path else "(루트)" for f in rec.files)
    samples = []
    for t in sorted(types):
        f = next(f for f in rec.files if f.type == t)
        c = rec.file_chunks(f.id)[0]
        samples.append([esc(f.path), esc(t), esc(c.kind), esc(c.locator), quote(c.text, 120)])
    s1 = (f'<div class="two"><div><h4>파일 형식</h4>{hbar(types.most_common())}</div>'
          f'<div><h4>최상위 폴더</h4>{hbar(folders.most_common(10))}</div></div>'
          f'<h4>형식별 첫 근거 조각</h4>{table(["파일", "형식", "조각 종류", "위치", "본문"], samples)}')

    xy = pca2(rec.file_emb)
    s2 = ('<p>파일 벡터(조각 평균 + 요약)를 PCA 2차원으로 투영했습니다. 점에 마우스를 올리면 파일 이름이 보입니다.</p>'
          + scatter(xy, [tcolor[f.type] for f in rec.files], [f.path for f in rec.files])
          + legend([(t, tcolor[t]) for t in sorted(types)]))

    cards = []
    for t in ("pdf", "markdown", "python", "image", "notebook", "text"):
        f = next((f for f in rec.files if f.type == t and f.summary), None) or next(
            (f for f in rec.files if f.type == t), None)
        if not f:
            continue
        chunks = rec.file_chunks(f.id)
        locs = ", ".join(esc(c.locator) for c in chunks[:4]) + (" …" if len(chunks) > 4 else "")
        summary = esc(f.summary) if f.summary else f'<span class="muted">({off})</span>'
        cards.append(f'<div class="card"><div class="path">{esc(f.path)}</div>'
                     f'<div>{badge("", f.type)}{badge("", f.role) if f.role else ""}</div>'
                     f'<p>{summary}</p><div class="muted">조각 {len(chunks)}개: {locs}<br>참조 {len(f.refs)}개</div></div>')
    s3 = '<div class="cards">' + "".join(cards) + "</div>"

    grows = [[f'<i class="dot" style="background:{gcolor.get(g.id, GREY)}"></i>{esc(g.name)}', str(len(g.members)),
              esc(g.description) or '<span class="muted">—</span>',
              esc(", ".join(base(rec.file_by_id[m].path) for m in g.members[:6])) + (" …" if len(g.members) > 6 else "")]
             for g in g5.groups]
    g5color = {g.id: PALETTE[i % len(PALETTE)] for i, g in enumerate(g5.groups)}
    gof = {m: g.id for g in g5.groups for m in g.members}
    s4 = ('<p>2단계와 같은 PCA 투영에 그룹 색을 입혔습니다.</p>'
          + scatter(xy, [g5color.get(gof.get(f.id), GREY) for f in rec.files], [f.path for f in rec.files])
          + table(["그룹", "파일", "설명", "구성"], grows))

    rel = Counter(RELATION_NAMES.get(e.relation, e.relation) for e in g5.edges)
    sims = [e.score for e in g5.edges if e.reason == "similar"]
    ex = []
    for r in ("imports", "links_to", "mentions", "similar"):
        for e in [e for e in g5.edges if e.reason == r][:2]:
            ev = "<br>".join(f'<span class="muted">{esc(base(rec.file_by_id[v.file_id].path))} · {esc(v.locator)}</span> '
                             f'“{quote(v.quote, 140)}”' for v in e.evidence[:2])
            ex.append([esc(RELATION_NAMES.get(r, r)), f"{esc(base(rec.file_by_id[e.source].path))} → "
                       f"{esc(base(rec.file_by_id[e.target].path))}", esc(RELATION_NAMES.get(e.relation, e.relation)),
                       esc(e.label) or '<span class="muted">—</span>', "직접" if e.direct else "추론", f"{e.score:.2f}", ev])
    s5 = (f'<div class="two"><div><h4>후보 이유</h4>{hbar([(RELATION_NAMES.get(k, k), v) for k, v in reasons.most_common()])}'
          f'<h4>관계 종류 (판정 후)</h4>{hbar(rel.most_common(12))}</div>'
          f'<div><h4>유사 연결 점수 분포 (reranker)</h4>{hist(sims)}'
          f'<p class="muted">Claude 판정 {judged}/{len(g5.edges)}개, 판정에서 탈락 {sum(e.status == "llm_rejected" for e in g5.edges)}개</p></div></div>'
          f'<h4>후보 이유별 예시</h4>{table(["이유", "연결", "관계", "라벨", "구분", "점수", "근거 (양쪽)"], ex)}')

    fbt = [[esc(FEEDBACK_TYPES[ev.type]),
            esc(base(rec.file_by_id[ev.source].path) + " – " + base(rec.file_by_id[ev.target].path))
            if ev.type.startswith("edge_") else esc(base(rec.file_by_id[ev.node].path)),
            esc(ev.relation or ev.group or ev.note or "")] for ev in feedback]
    crow = [[("<b>" if n == cfg.corrector else "") + esc(n) + (" (사용 중)</b>" if n == cfg.corrector else ""),
             {"baseline": "대조군", "drift": "4안 커널 끌림/밀어냄", "align": "1안 선호 정렬 (Bradley–Terry)"}.get(n, ""),
             str(h), str(r), "<br>".join(esc(x) for x in notes), "<br>".join(exs) or '<span class="muted">—</span>']
            for n, h, r, notes, exs in compare]
    s6 = (f'<h4>피드백 {len(feedback)}개</h4>' + (table(["유형", "대상", "관계·그룹"], fbt) if fbt else
                                                '<p class="muted">feedback.jsonl이 비어 있습니다.</p>')
          + f'<h4>같은 그래프·피드백에서 방법별 결과</h4>{table(["방법", "출처", "숨김", "강화", "메모", "예시"], crow)}')

    status = Counter(e.status for e in final.edges)
    s7 = (graph_svg(final, gcolor)
          + legend([(g.name, gcolor[g.id]) for g in final.groups] + [("그룹 없음", GREY)])
          + '<p class="muted">실선: 직접 근거 · 점선: 추론 · 파란 굵은 선: 승인 · 초록: 사용자 추가 · 빨간 점선: 거절·숨김. '
            '연결이 많은 파일만 이름을 표시합니다.</p>'
          + f'<h4>연결 상태</h4>{hbar(status.most_common())}'
          + '<h4>직접 편집 유지 확인 (마지막 이벤트 기준)</h4>'
          + (table(["편집", "대상", "기대", "최종 그래프", ""], fb_rows) if fb_rows else '<p class="muted">편집 없음</p>'))

    secs = info.get("seconds", {})
    s8 = ('<p><a href="view.html">view.html 열기</a>: 노드를 누르면 요약·미리보기·연결 목록이, 연결을 누르면 관계·양쪽 근거 '
          '인용·교정 이유가 오른쪽 패널에 나오고, 교정 버튼으로 feedback.jsonl을 내보냅니다. '
          '<code>projectwiki obsidian</code>으로 볼트를 만들 수 있습니다.</p>'
          '<h4>증분 갱신 (마지막 실행)</h4>'
          + table(["추가", "변경", "삭제", "새로 인코딩한 조각"],
                  [[esc(", ".join(changes.get("added", [])[:8]) + (" …" if len(changes.get("added", [])) > 8 else "")) or "0",
                    esc(", ".join(changes.get("changed", []))) or "0", esc(", ".join(changes.get("removed", []))) or "0",
                    str(changes.get("encoded", "?"))]])
          + (f'<h4>단계별 시간 (초)</h4>{hbar(list(secs.items()), fmt="{:.1f}")}' if secs else "")
          + f'<p class="muted">LLM: {esc(str(info.get("llm", "off")))}</p>')

    sections = [("1 파일 입력", "ingest.py", s1), ("2 인코딩", "models.py · record.py", s2),
                ("3 프로젝트 레코드", "record.py", s3), ("4 군집화 🧪", f"cluster/{cfg.clusterer}", s4),
                ("5 그래프 생성", "graph.py", s5), ("6 선호도 교정 🧪", "correct/", s6),
                ("7 최종 그래프", "finalize.py", s7), ("8 시각화 · 증분 갱신", "viz/", s8)]
    body = "".join(f'<section><h2>{esc(t)} <span class="muted code">{esc(m)}</span></h2>{c}</section>'
                   for t, m, c in sections)
    meta = (f'{esc(rec.root)} · {esc(info.get("finished", ""))} · 인코더 {esc(rec.encoder_id)} · '
            f'군집 {esc(cfg.clusterer)} · 교정 {esc(cfg.corrector)} · LLM {esc(cfg.llm_backend if cfg.llm else "off")}')
    page = (PAGE.replace("{{META}}", meta).replace("{{STRIP}}", strip_html)
            .replace("{{PLAN}}", table(["확정 파이프라인 단계", "회의 PDF 근거", "이번 실행 출력", "판정"], plan_rows, "plan"))
            .replace("{{BODY}}", body))
    path = out / "stages.html"
    path.write_text(page, encoding="utf-8")
    return path


PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ProjectWiki Stage Report</title>
<style>
:root { --bg:#ffffff; --panel:#f6f7f9; --text:#1f2328; --muted:#656d76; --line:#d8dee4; --accent:#2e7dd1;
  --ok:#2e9d4a; --bad:#d9534f; --warn:#c98a00; --edge:#8a94a6; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#0f1115; --panel:#171a21; --text:#e6e8eb;
  --muted:#9aa3ad; --line:#2b313b; --accent:#5aa2f0; --ok:#4cc26a; --bad:#f06a66; --warn:#e0a82e; --edge:#7d8590; } }
:root[data-theme="dark"] { --bg:#0f1115; --panel:#171a21; --text:#e6e8eb; --muted:#9aa3ad; --line:#2b313b;
  --accent:#5aa2f0; --ok:#4cc26a; --bad:#f06a66; --warn:#e0a82e; --edge:#7d8590; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:14px/1.55 -apple-system,"Segoe UI","Malgun Gothic",
  "Apple SD Gothic Neo",sans-serif; }
main { max-width:1180px; margin:0 auto; padding:24px 16px 64px; }
h1 { font-size:22px; margin:0 0 4px; } h2 { font-size:17px; margin:0 0 12px; } h4 { margin:14px 0 6px; font-size:13px; color:var(--muted); }
.muted { color:var(--muted); } .code { font-family:ui-monospace,Consolas,monospace; font-size:12px; font-weight:400; }
section { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px; margin:16px 0; }
.strip { display:flex; flex-wrap:wrap; align-items:stretch; gap:6px; margin:16px 0; }
.stage { flex:1 1 118px; min-width:118px; border:1px solid var(--line); border-top:4px solid var(--ok); border-radius:8px;
  padding:8px; background:var(--panel); }
.stage.warn { border-top-color:var(--warn); } .stage.bad { border-top-color:var(--bad); }
.stage .num { font-size:11px; color:var(--muted); } .stage .name { font-weight:600; }
.stage .method { font-size:11px; color:var(--muted); } .stage .metric { font-size:12px; margin-top:4px; }
.arrow { align-self:center; color:var(--muted); }
.tablewrap { overflow-x:auto; } table { border-collapse:collapse; width:100%; font-size:12.5px; }
th, td { text-align:left; vertical-align:top; padding:6px 8px; border-bottom:1px solid var(--line); }
th { color:var(--muted); font-weight:600; } td:first-child { white-space:nowrap; } table.plan td:first-child { white-space:nowrap; font-weight:600; }
.badge { display:inline-block; font-size:11px; padding:1px 7px; border-radius:10px; background:var(--line); margin:0 4px 2px 0; white-space:nowrap; }
.badge.ok { background:var(--ok); color:#fff; } .badge.warn { background:var(--warn); color:#fff; } .badge.bad { background:var(--bad); color:#fff; }
.two { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; }
.chart { width:100%; height:auto; } .chart.bars { max-width:560px; } .frame { border:1px solid var(--line); border-radius:8px; background:var(--bg); }
.chart .lab, .chart .val, .chart .node { fill:var(--text); font-size:11px; } .chart .val { fill:var(--muted); }
.chart .bar { fill:var(--accent); } .chart .node { font-size:10px; paint-order:stroke; stroke:var(--bg); stroke-width:3px; }
.legend { display:flex; flex-wrap:wrap; gap:4px 14px; font-size:12px; margin:6px 0; }
.legend i, .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; vertical-align:-1px; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px; }
.card { background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:10px; font-size:12.5px; }
.card .path { font-family:ui-monospace,Consolas,monospace; font-size:12px; word-break:break-all; margin-bottom:4px; }
a { color:var(--accent); }
</style></head><body><main>
<h1>ProjectWiki 단계별 확인 리포트</h1>
<div class="muted">{{META}}</div>
{{STRIP}}
<section><h2>회의 파이프라인(1안 + 4안) 대비</h2>{{PLAN}}</section>
{{BODY}}
</main></body></html>
"""

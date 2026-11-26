"""Exercise the browser's directed height layout without requiring WebGL."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which("node"), reason="viewer layout check needs Node.js")
def test_leaf_heights():
    template = (Path(__file__).parents[1] / "projectwiki/srcs/view_template.html").read_text(encoding="utf-8")
    layout = template.split("function leafHeights3D(", 1)[1].split("function sync3D()", 1)[0]
    script = r'''
const assert = require('node:assert/strict');
const DIRECTED = new Set(['imports', 'links_to']);
eval(LAYOUT);
const nodes = (...ids) => ids.map(id => ({id}));
const edge = (source, target, relation = 'links_to') => ({source, target, relation});

const chain = leafHeights3D(nodes('root', 'branch', 'leaf'), [edge('root', 'branch'), edge('branch', 'leaf')]);
assert(chain.get('root') > chain.get('branch'));
assert(chain.get('branch') > chain.get('leaf'));
const fork = leafHeights3D(nodes('root', 'a', 'b'), [edge('root', 'a'), edge('root', 'b')]);
assert.equal(fork.get('a'), fork.get('b'));
assert(fork.get('root') > fork.get('a'));
const cycle = leafHeights3D(nodes('a', 'b', 'leaf'), [edge('a', 'b'), edge('b', 'a'), edge('b', 'leaf')]);
assert.equal(cycle.get('a'), cycle.get('b'));
assert(cycle.get('b') > cycle.get('leaf'));
const undirected = leafHeights3D(nodes('a', 'b'), [edge('a', 'b', 'similar')]);
assert.equal(undirected.get('a'), undirected.get('b'));
assert.equal(leafHeights3D([], []).size, 0);
assert.equal(leafHeights3D(nodes('solo'), [edge('missing', 'solo')]).get('solo'), 0);
// Traversal must also handle large cycles without recursive stack overflow.
const large = Array.from({length: 12000}, (_, i) => ({id: String(i)}));
const ring = large.map((n, i) => edge(n.id, large[(i + 1) % large.length].id));
const heights = leafHeights3D(large, ring);
assert.equal(heights.size, large.length);
assert([...heights.values()].every(y => y === 0));
'''.replace("LAYOUT", json.dumps("function leafHeights3D(" + layout))
    result = subprocess.run([shutil.which("node"), "-"], input=script.encode("utf-8"), capture_output=True)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")


@pytest.mark.skipif(not shutil.which("node"), reason="viewer aggregation check needs Node.js")
def test_group_connections():
    template = (Path(__file__).parents[1] / "projectwiki/srcs/view_template.html").read_text(encoding="utf-8")
    aggregate = template.split("function groupGraphData(", 1)[1].split("function transformGroupCards()", 1)[0]
    script = r'''
const assert = require('node:assert/strict');
eval(AGGREGATE);
const nodes = [{id:'a', group:'g1'}, {id:'b', group:'g1'}, {id:'c', group:'g2'}, {id:'d', group:null}];
const groups = [{id:'g1',name:'Code'}, {id:'g2',name:'Docs'}, {id:'g3',name:'Empty'}];
const edges = [
  {id:'ab',source:'a',target:'b'},
  {id:'ac',source:'a',target:'c'},
  {id:'cb',source:'c',target:'b'},
  {id:'cd',source:'c',target:'d'},
  {id:'missing',source:'missing',target:'a'}
];
const graph = groupGraphData(nodes, groups, edges);
assert.equal(graph.cards.length, 3);
assert.equal(graph.cards.find(c=>c.id==='g1').internal, 1);
assert.equal(graph.cards.find(c=>c.id==='g1').external, 2);
const link = graph.links.find(e=>e.a==='g1' && e.b==='g2');
assert.equal(link.count, 2);
assert.equal(link.edges.map(e=>e.id).sort().join(','), 'ac,cb');
assert.equal(graph.links.length, 2);
assert.equal(graph.cards.find(c=>c.id==='').members[0].id, 'd');
const filtered = groupGraphData(nodes.filter(n=>n.group!=='g2'), groups, edges);
assert.equal(filtered.links.length, 0);
assert.equal(filtered.cards.find(c=>c.id==='g1').internal, 1);
const empty = groupGraphData([], groups, edges);
assert.equal(empty.cards.length, 0);
assert.equal(empty.links.length, 0);
'''.replace("AGGREGATE", json.dumps("function groupGraphData(" + aggregate))
    result = subprocess.run([shutil.which("node"), "-"], input=script.encode("utf-8"), capture_output=True)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")

"""Check the viewer's net feedback, including side effects of group deletion."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which("node"), reason="viewer feedback check needs Node.js")
def test_pending_feedback():
    template = (Path(__file__).parents[1] / "projectwiki/srcs/view_template.html").read_text(encoding="utf-8")
    start = template.index("function replay(edits)")
    end = template.index("function visibleEdges()", start)
    setup = """
const assert = require("node:assert/strict");
const LEVEL_LABEL = {top:"상", middle:"중", bottom:"하"};
const PALETTE = ["purple"], groupColor = {};
const VISIBLE = new Set(["confirmed", "proposed"]);
const edgeKey = (a,b) => [a,b].sort().join("|");
const original = {id:"a|b", source:"a", target:"b", status:"proposed", relation:"uses", label:""};
const DATA = {nodes:[{id:"a",level:"top",manual_level:false,group:"g"}, {id:"b",level:"bottom",group:null}],
              groups:[{id:"g",name:"G"}], edges:[original]};
let events, state, pending;
"""
    cases = """
function run(...history) { events = history; applyEvents(); return pending.map(e => e.type); }
const level = value => ({type:"node_level", node:"a", level:value});
const addGroup = {type:"group_add", group:"h", note:"H"};
const delGroup = {type:"group_delete", group:"h"};
const move = group => ({type:"node_move", node:"a", group});
const edge = (type, source="a", target="b", relation="uses") => ({type,source,target,relation});
assert.deepEqual(run(level("middle"),level("top")), []);
assert.equal(state.nodes.get("a").manual_level, false);
assert.deepEqual(run(level("middle"),level("bottom")), ["node_level"]);
assert.equal(pending[0].level, "bottom");
assert.deepEqual(run(addGroup,delGroup), []);
assert.deepEqual(run(addGroup,move("h"),move("g"),delGroup), []);
assert.deepEqual(run(addGroup,move("h"),delGroup), ["node_ungroup"]);
assert.equal(state.nodes.get("a").group, null);
assert.deepEqual(run(edge("edge_add","a","c"),edge("edge_irrelevant","a","c")), []);
assert.ok(!state.edges.has("a|c"));
assert.deepEqual(run(edge("edge_wrong"),edge("edge_add")), []);
assert.equal(state.edges.get("a|b").status, "proposed");
const reverse = {...edge("edge_add","b","a"),set_direction:true};
const restore = {...edge("edge_add"),set_direction:true};
assert.deepEqual(run(reverse, restore), []);
assert.deepEqual(run(reverse, edge("edge_add","b","a","cites")), ["edge_add"]);
assert.equal(pending[0].set_direction, true);
assert.equal(state.edges.get("a|b").source, "b");
assert.deepEqual(run(edge("edge_confirm"),reverse,restore), ["edge_confirm"]);
assert.deepEqual(run(edge("edge_add","a","b","cites"),edge("edge_add")), []);
assert.deepEqual(run(addGroup,level("middle"),delGroup,edge("edge_confirm")), ["node_level","edge_confirm"]);
"""
    subprocess.run([shutil.which("node"), "-"], input=(setup + template[start:end] + cases).encode(),
                   check=True, capture_output=True)

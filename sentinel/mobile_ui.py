"""Mobile-optimized web UI — responsive HTML for phone usage."""

_MOBILE_CSS = """
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{background:#09090b;color:#e4e4e7;font-family:-apple-system,system-ui,sans-serif;font-size:16px}
body{padding:16px 16px 88px;max-width:100%;min-height:100vh}
h1{color:#ef4444;font-size:22px;margin-bottom:16px}
h2{color:#f4f4f5;font-size:16px;margin:12px 0 8px}
.card{background:#18181b;border:1px solid #27272a;border-radius:10px;padding:14px;margin-bottom:12px}
.row{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid #27272a}
.row:last-child{border-bottom:none}
.muted{color:#71717a;font-size:13px}
input,textarea,select,button{
  background:#27272a;color:#e4e4e7;border:1px solid #3f3f46;padding:12px;
  border-radius:8px;font-size:16px;width:100%;min-height:44px
}
button{cursor:pointer;background:#ef4444;border-color:#ef4444;font-weight:600}
.btn-row{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
.btn-row button{min-height:52px}
.tab{display:none}
.tab.active{display:block}
.bnav{position:fixed;bottom:0;left:0;right:0;background:#0f0f14;border-top:1px solid #27272a;
  display:grid;grid-template-columns:repeat(4,1fr);padding:0}
.bnav button{background:transparent;border:none;color:#a1a1aa;padding:12px 4px;
  font-size:12px;min-height:56px;border-radius:0}
.bnav button.on{color:#ef4444}
@media (max-width:375px){body{padding:12px 12px 80px}h1{font-size:20px}}
"""


def get_mobile_dashboard() -> str:
    """Simple mobile-first HTML that works on phones."""
    body = (
        '<div id="t-home" class="tab active">' + get_mobile_quick_actions() + "</div>"
        '<div id="t-rules" class="tab"><div class="card"><h2>Add rule</h2>'
        '<form onsubmit="addRule(event)">'
        '<textarea id="rule-text" rows="2" placeholder="e.g. block youtube.com"></textarea>'
        '<button type="submit" style="margin-top:8px">Add rule</button></form></div>'
        '<div class="card" id="rules-list"><h2>Rules</h2><div class="muted">Loading...</div></div></div>'
        '<div id="t-stats" class="tab"><div class="card" id="stats-box"><h2>Stats</h2>'
        '<div class="muted">Loading...</div></div></div>'
        + '<div id="t-chat" class="tab">' + get_mobile_chat() + "</div>"
        '<nav class="bnav">'
        '<button class="on" data-tab="home" onclick="showTab(\'home\',this)">Home</button>'
        '<button data-tab="rules" onclick="showTab(\'rules\',this)">Rules</button>'
        '<button data-tab="stats" onclick="showTab(\'stats\',this)">Stats</button>'
        '<button data-tab="chat" onclick="showTab(\'chat\',this)">Chat</button>'
        '</nav>'
        '<script>'
        'function showTab(n,btn){document.querySelectorAll(".tab").forEach(t=>t.classList.remove("active"));'
        'document.getElementById("t-"+n).classList.add("active");'
        'document.querySelectorAll(".bnav button").forEach(b=>b.classList.remove("on"));'
        'btn.classList.add("on");'
        'if(n=="rules")loadRules();if(n=="stats")loadStats();}'
        'async function loadRules(){try{const r=await fetch("/rules");const j=await r.json();'
        'const el=document.getElementById("rules-list");'
        'el.innerHTML="<h2>Rules</h2>"+(j.length?j.map(x=>'
        '`<div class="row"><span>${x.text}</span><span class="muted">${x.active?"on":"off"}</span></div>`'
        ').join(""):"<div class=\\"muted\\">No rules</div>");}catch(e){}}'
        'async function loadStats(){try{const r=await fetch("/stats");const j=await r.json();'
        'const el=document.getElementById("stats-box");'
        'el.innerHTML="<h2>Stats</h2>"+Object.entries(j).map(([k,v])=>'
        '`<div class="row"><span>${k}</span><span>${v}</span></div>`).join("");}catch(e){}}'
        'async function addRule(e){e.preventDefault();const t=document.getElementById("rule-text").value;'
        'if(!t)return;await fetch("/rules",{method:"POST",headers:{"Content-Type":"application/json"},'
        'body:JSON.stringify({text:t})});document.getElementById("rule-text").value="";loadRules();}'
        'async function quickAction(a){await fetch("/mobile/action",{method:"POST",'
        'headers:{"Content-Type":"application/json"},body:JSON.stringify({action:a})});}'
        'async function chatSend(){const q=document.getElementById("chat-q").value;if(!q)return;'
        'document.getElementById("chat-ans").textContent="...";'
        'try{const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},'
        'body:JSON.stringify({q})});const j=await r.json();'
        'document.getElementById("chat-ans").textContent=j.answer||JSON.stringify(j);}'
        'catch(e){document.getElementById("chat-ans").textContent="error";}}'
        '</script>'
    )
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">'
        '<title>Sentinel Mobile</title>'
        f'<style>{_MOBILE_CSS}</style></head>'
        f'<body><h1>Sentinel</h1>{body}</body></html>'
    )


def get_mobile_quick_actions() -> str:
    """Quick action buttons: start pomodoro, add rule, check score."""
    return (
        '<div class="card"><h2>Quick actions</h2>'
        '<div class="btn-row">'
        '<button onclick="quickAction(\'pomodoro\')">Start pomodoro</button>'
        '<button onclick="quickAction(\'focus\')">Focus mode</button>'
        '<button onclick="showTab(\'rules\',document.querySelector(\'.bnav button[data-tab=rules]\'))">Add rule</button>'
        '<button onclick="showTab(\'stats\',document.querySelector(\'.bnav button[data-tab=stats]\'))">Check score</button>'
        '</div></div>'
    )


def get_mobile_chat() -> str:
    """Mobile chat interface for /ask endpoint."""
    return (
        '<div class="card"><h2>Ask Sentinel</h2>'
        '<textarea id="chat-q" rows="3" placeholder="Ask about your activity..."></textarea>'
        '<button onclick="chatSend()" style="margin-top:8px">Ask</button>'
        '<pre id="chat-ans" class="muted" style="margin-top:12px;white-space:pre-wrap"></pre>'
        '</div>'
    )

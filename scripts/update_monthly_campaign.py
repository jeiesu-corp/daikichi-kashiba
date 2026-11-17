#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
買取大吉 香芝畑店 HP（index.html）のキャンペーンポップアップを、月ごとの季節タイトルで差し替える。

`index.html` の

    <!-- CAMPAIGN_POPUP_START -->
    ...（このスクリプトが生成した <style>/HTML/<script>）...
    <!-- CAMPAIGN_POPUP_END -->

の間だけを書き換える。マーカーの外側（店長ブログ、JSON-LD、本文など）には一切触れない。

必ず入る要素（康文さんの指示）:
  - 「香芝畑店限定！」             … 上部の金のピル
  - 「買取金額 30%UP」             … 特大の目玉
  - 季節・行事に合わせたタイトル    … 例: 11月「秋の特別感謝祭」／12月「歳末・冬の特別感謝祭」
あわせて期限（その月の末日 23:59:59 JST）と注記3行・ボタン3つも毎回そろえる。

使い方:
  python3 scripts/update_monthly_campaign.py                 # 今日の月（毎月1日の定期実行用）
  python3 scripts/update_monthly_campaign.py --month 12      # 12月分を生成（テスト用）
  python3 scripts/update_monthly_campaign.py --month 12 --dry-run   # 書き換えずに中身を標準出力へ
  python3 scripts/update_monthly_campaign.py --month 12 --commit-push
  python3 scripts/update_monthly_campaign.py --list           # 12か月分のタイトル一覧

終了コード: 0=更新した / 10=変更なし / 1=エラー
"""

import argparse
import calendar
import datetime
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_INDEX = os.path.join(BASE_DIR, "index.html")

START_MARK = "<!-- CAMPAIGN_POPUP_START -->"
END_MARK = "<!-- CAMPAIGN_POPUP_END -->"

TEL_TEL = "tel:0745515387"
LINE_URL = "https://lin.ee/y6bAOme"

# 月ごとの季節タイトル（lead=小さめの前置き / main=特大見出し）と配色・装飾
#   season: maple(紅葉) / snow(雪) / flower(花) / leaf(若葉) / fireworks(花火) / sun(太陽)
MONTHS = {
    1:  dict(lead="新春",         main="初売り感謝祭",   season="snow",      accent="#8fc4f0", soft="#dcefff", glow="rgba(120,180,245,.34)"),
    2:  dict(lead="早春",         main="特別感謝祭",     season="flower",    accent="#ffaecb", soft="#ffe1ec", glow="rgba(255,150,190,.30)"),
    3:  dict(lead="春のお片付け", main="感謝祭",         season="flower",    accent="#ffb3c7", soft="#ffe3eb", glow="rgba(255,160,190,.30)"),
    4:  dict(lead="春爛漫",       main="特別感謝祭",     season="flower",    accent="#ffc2d6", soft="#ffe8f0", glow="rgba(255,170,200,.30)"),
    5:  dict(lead="GW・初夏",     main="特別感謝祭",     season="leaf",      accent="#9fe0a5", soft="#dcf7dd", glow="rgba(120,210,140,.30)"),
    6:  dict(lead="初夏",         main="特別感謝祭",     season="leaf",      accent="#7fd4c8", soft="#d5f5f1", glow="rgba(110,205,195,.30)"),
    7:  dict(lead="夏本番",       main="特別感謝祭",     season="fireworks", accent="#ffcf5c", soft="#fff0c6", glow="rgba(255,190,90,.34)"),
    8:  dict(lead="真夏の",       main="特別感謝祭",     season="sun",       accent="#ffb066", soft="#ffe0c4", glow="rgba(255,150,90,.34)"),
    9:  dict(lead="秋のはじまり", main="特別感謝祭",     season="maple",     accent="#f0a76b", soft="#ffdcbb", glow="rgba(235,150,100,.32)"),
    10: dict(lead="実りの秋",     main="特別感謝祭",     season="maple",     accent="#f2b25c", soft="#ffe3bd", glow="rgba(240,165,85,.34)"),
    11: dict(lead="秋の",         main="特別感謝祭",     season="maple",     accent="#f0a04b", soft="#ffd9a8", glow="rgba(240,160,75,.34)"),
    12: dict(lead="歳末・冬の",   main="特別感謝祭",     season="snow",      accent="#ffb08a", soft="#ffe1d2", glow="rgba(255,155,120,.30)"),
}

SPARKLE = ('<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false" '
           'style="top:{t};left:{l};width:{s}px;height:{s}px;opacity:{o}">'
           '<path d="M12 0 14.3 9.7 24 12 14.3 14.3 12 24 9.7 14.3 0 12 9.7 9.7Z"/></svg>')

MOTIFS = {
    "maple": (
        '<svg viewBox="0 0 100 100" fill="currentColor" aria-hidden="true" focusable="false" '
        'style="{pos};opacity:{o};transform:rotate({rot}deg)">'
        '<path d="M50 4 61.2 36.6 93.7 37.8 68.1 57.9 77.1 89.2 50 71 22.9 89.2 31.9 57.9 6.3 37.8 38.8 36.6Z"/>'
        '<path d="M50 71V98" stroke="currentColor" stroke-width="4" fill="none"/></svg>'
    ),
    "snow": (
        '<svg viewBox="0 0 100 100" stroke="currentColor" fill="none" aria-hidden="true" focusable="false" '
        'style="{pos};opacity:{o};transform:rotate({rot}deg)" stroke-width="3.5" stroke-linecap="round">'
        '<line x1="50" y1="4" x2="50" y2="96"/><line x1="10" y1="27" x2="90" y2="73"/>'
        '<line x1="90" y1="27" x2="10" y2="73"/>'
        '<path d="M50 18 41 9M50 18 59 9M50 82 41 91M50 82 59 91"/>'
        '<path d="M24 36 20 24M24 36 12 40M76 64 80 76M76 64 88 60"/>'
        '<path d="M76 36 80 24M76 36 88 40M24 64 20 76M24 64 12 60"/></svg>'
    ),
    "flower": (
        '<svg viewBox="0 0 100 100" fill="currentColor" aria-hidden="true" focusable="false" '
        'style="{pos};opacity:{o};transform:rotate({rot}deg)">'
        '<g transform="rotate(0 50 50)"><ellipse cx="50" cy="25" rx="12" ry="20"/></g>'
        '<g transform="rotate(72 50 50)"><ellipse cx="50" cy="25" rx="12" ry="20"/></g>'
        '<g transform="rotate(144 50 50)"><ellipse cx="50" cy="25" rx="12" ry="20"/></g>'
        '<g transform="rotate(216 50 50)"><ellipse cx="50" cy="25" rx="12" ry="20"/></g>'
        '<g transform="rotate(288 50 50)"><ellipse cx="50" cy="25" rx="12" ry="20"/></g>'
        '<circle cx="50" cy="50" r="8" fill="#0b1440" opacity=".55"/></svg>'
    ),
    "leaf": (
        '<svg viewBox="0 0 100 100" fill="currentColor" aria-hidden="true" focusable="false" '
        'style="{pos};opacity:{o};transform:rotate({rot}deg)">'
        '<path d="M50 6C78 28 82 60 50 92 18 60 22 28 50 6Z"/>'
        '<path d="M50 18V86" stroke="#0b1440" stroke-width="3" fill="none" opacity=".5"/></svg>'
    ),
    "fireworks": (
        '<svg viewBox="0 0 100 100" stroke="currentColor" aria-hidden="true" focusable="false" '
        'style="{pos};opacity:{o};transform:rotate({rot}deg)" stroke-width="3.2" stroke-linecap="round">'
        '<line x1="50" y1="50" x2="50" y2="6"/><line x1="50" y1="50" x2="88" y2="28"/>'
        '<line x1="50" y1="50" x2="94" y2="50"/><line x1="50" y1="50" x2="88" y2="72"/>'
        '<line x1="50" y1="50" x2="50" y2="94"/><line x1="50" y1="50" x2="12" y2="72"/>'
        '<line x1="50" y1="50" x2="6" y2="50"/><line x1="50" y1="50" x2="12" y2="28"/>'
        '<line x1="50" y1="50" x2="72" y2="12" opacity=".6"/><line x1="50" y1="50" x2="72" y2="88" opacity=".6"/>'
        '<line x1="50" y1="50" x2="28" y2="88" opacity=".6"/><line x1="50" y1="50" x2="28" y2="12" opacity=".6"/>'
        '<circle cx="50" cy="50" r="5" fill="currentColor" stroke="none"/></svg>'
    ),
    "sun": (
        '<svg viewBox="0 0 100 100" aria-hidden="true" focusable="false" style="{pos};opacity:{o};transform:rotate({rot}deg)">'
        '<circle cx="50" cy="50" r="21" fill="currentColor"/>'
        '<g stroke="currentColor" stroke-width="3.4" stroke-linecap="round">'
        '<line x1="50" y1="4" x2="50" y2="18"/><line x1="50" y1="82" x2="50" y2="96"/>'
        '<line x1="4" y1="50" x2="18" y2="50"/><line x1="82" y1="50" x2="96" y2="50"/>'
        '<line x1="17" y1="17" x2="27" y2="27"/><line x1="73" y1="73" x2="83" y2="83"/>'
        '<line x1="83" y1="17" x2="73" y2="27"/><line x1="27" y1="73" x2="17" y2="83"/>'
        '</g></svg>'
    ),
}

CSS = """/* ============ キャンペーンポップアップ ============
   このブロック（スタイル・HTML・スクリプト）は scripts/update_monthly_campaign.py が毎月生成する。
   CAMPAIGN_POPUP_START 〜 END の中を手作業で編集しない（次の自動更新で上書きされる）。 */
html.cp-locked,html.cp-locked body{overflow:hidden;}
.cp-modal{position:fixed;inset:0;z-index:200;display:flex;align-items:center;justify-content:center;padding:14px;background:rgba(5,10,30,.8);opacity:0;visibility:hidden;transition:opacity .35s ease,visibility 0s linear .35s;}
.cp-modal.is-open{opacity:1;visibility:visible;transition:opacity .35s ease,visibility 0s;}
.cp-card{--cp-accent:#f0a04b;--cp-soft:#ffd9a8;--cp-glow:rgba(240,160,75,.34);position:relative;width:100%;max-width:430px;max-height:92vh;max-height:92dvh;display:flex;flex-direction:column;border-radius:20px;overflow:hidden;background:#0b1440;color:#fff;text-align:center;box-shadow:0 26px 70px rgba(0,0,0,.62),0 0 0 1px rgba(230,196,124,.4);transform:translateY(16px) scale(.97);opacity:0;transition:transform .4s cubic-bezier(.2,.8,.3,1),opacity .4s ease;}
.cp-modal.is-open .cp-card{transform:none;opacity:1;}
.cp-main{position:relative;flex:1 1 auto;min-height:0;overflow-y:auto;padding:30px 18px 22px;background:radial-gradient(120% 72% at 50% -16%,var(--cp-glow),transparent 62%),radial-gradient(90% 60% at 0% 108%,var(--cp-glow),transparent 58%),linear-gradient(160deg,#17285f 0%,#0b1440 55%,#131d4d 100%);}
.cp-main::after{content:"";position:absolute;inset:9px;border:1px solid rgba(230,196,124,.4);border-radius:12px;pointer-events:none;}
.cp-deco{position:absolute;inset:0;overflow:hidden;pointer-events:none;color:var(--cp-accent);}
.cp-deco svg{position:absolute;display:block;}
.cp-inner{position:relative;z-index:1;}
.cp-store{display:inline-block;margin:0 0 14px;padding:6px 20px;border-radius:999px;background:linear-gradient(180deg,#ffeab4,#e6b95c 58%,#c99a3c);color:#101c52;font-size:15.5px;font-weight:900;letter-spacing:.1em;line-height:1.5;box-shadow:0 6px 16px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.7);}
.cp-lead{margin:0;font-size:18px;font-weight:700;letter-spacing:.24em;text-indent:.24em;line-height:1.45;color:var(--cp-soft);}
.cp-title{margin:0;font-size:clamp(38px,12.4vw,54px);font-weight:900;line-height:1.12;letter-spacing:.03em;background:linear-gradient(180deg,#fff 6%,#ffeece 52%,#f0c274 100%);-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent;filter:drop-shadow(0 3px 0 rgba(4,8,26,.55));}
@supports not ((background-clip:text) or (-webkit-background-clip:text)){
  .cp-title,.cp-rate-num .n{background:none;color:#ffe6b8;-webkit-text-fill-color:currentColor;}
}
.cp-rate{margin-top:15px;padding-top:13px;border-top:1px solid rgba(255,255,255,.18);}
.cp-rate-label{display:block;font-size:15px;font-weight:700;letter-spacing:.34em;text-indent:.34em;color:#ffeccb;}
.cp-rate-num{display:flex;align-items:flex-end;justify-content:center;gap:2px;margin:2px 0 0;line-height:.9;}
.cp-rate-num .n{font-size:clamp(72px,23vw,100px);font-weight:900;letter-spacing:-.02em;background:linear-gradient(180deg,#fffdf7 1%,#ffd977 48%,#f0a94b 100%);-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent;filter:drop-shadow(0 4px 0 #7a4410) drop-shadow(0 10px 26px rgba(240,169,75,.45));}
.cp-rate-num .u{font-size:clamp(34px,11vw,46px);font-weight:900;letter-spacing:.02em;color:#fff;text-shadow:0 3px 0 #7a4410;padding-bottom:.16em;}
.cp-due{display:inline-flex;align-items:baseline;gap:3px;margin:16px 0 0;padding:7px 22px;border-radius:999px;background:#fff;color:#101c52;font-size:15px;font-weight:800;letter-spacing:.03em;box-shadow:0 8px 22px rgba(0,0,0,.35);}
.cp-due b{font-size:21px;font-weight:900;}
.cp-notes{margin:0;padding:11px 18px 3px;list-style:none;background:#fff;color:#39445a;font-size:12.5px;line-height:1.7;letter-spacing:.01em;text-align:left;}
.cp-notes li{position:relative;padding-left:1.1em;}
.cp-notes li::before{content:"・";position:absolute;left:0;top:0;color:#b98c2f;font-weight:700;}
.cp-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:11px 14px 14px;background:#fff;}
.cp-btn{display:flex;align-items:center;justify-content:center;gap:6px;min-height:46px;padding:0 8px;border:none;border-radius:10px;font-family:inherit;font-size:14.5px;font-weight:700;letter-spacing:.02em;text-align:center;cursor:pointer;-webkit-tap-highlight-color:transparent;transition:filter .2s ease;}
.cp-btn:hover{filter:brightness(1.06);}
.cp-btn-line{background:#06c755;color:#fff;}
.cp-btn-tel{background:#1a2f7e;color:#fff;}
.cp-btn-page{grid-column:1/-1;min-height:42px;background:#f1f3f8;border:1px solid #e3e6ee;color:#4a5568;font-size:13px;font-weight:600;}
.cp-close{position:absolute;top:10px;right:10px;z-index:4;width:38px;height:38px;padding:0;border:1px solid rgba(255,255,255,.5);border-radius:50%;background:rgba(255,255,255,.92);color:#101c52;font-family:inherit;font-size:25px;font-weight:400;line-height:1;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,.35);-webkit-tap-highlight-color:transparent;}
.cp-close:hover{background:#fff;}
.cp-close:focus-visible,.cp-btn:focus-visible{outline:3px solid #d9b45e;outline-offset:2px;}
.cp-sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;}
@media (max-width:400px){
  .cp-modal{padding:10px;}
  .cp-main{padding:24px 14px 18px;}
  .cp-store{font-size:14px;padding:5px 16px;letter-spacing:.08em;}
  .cp-lead{font-size:16px;}
  .cp-notes{font-size:12px;padding:9px 14px 2px;}
  .cp-btn{font-size:13.5px;min-height:44px;}
}
@media (max-height:670px){
  .cp-main{padding-top:20px;padding-bottom:14px;}
  .cp-rate{margin-top:10px;padding-top:10px;}
  .cp-due{margin-top:11px;}
}
@media (prefers-reduced-motion:reduce){
  .cp-modal,.cp-card{transition:none;}
  .cp-card{transform:none;}
}
"""

HTML_TEMPLATE = """<div class="cp-modal" id="cpModal" role="dialog" aria-modal="true" aria-labelledby="cpFull">
  <div class="cp-card" style="--cp-accent:@@ACCENT@@;--cp-soft:@@SOFT@@;--cp-glow:@@GLOW@@">
    <button type="button" class="cp-close" id="cpClose" aria-label="ポップアップを閉じる">×</button>
    <div class="cp-main">
      <div class="cp-deco" aria-hidden="true">
@@DECO@@
      </div>
      <div class="cp-inner">
        <span class="cp-sr" id="cpFull">@@FULLTITLE@@。買取金額30%UP、@@DUE@@まで。</span>
        <p class="cp-store">香芝畑店限定！</p>
        <p class="cp-lead">@@LEAD@@</p>
        <h2 class="cp-title">@@MAIN@@</h2>
        <div class="cp-rate">
          <span class="cp-rate-label">買取金額</span>
          <p class="cp-rate-num"><span class="n">30</span><span class="u">%UP</span></p>
        </div>
        <p class="cp-due"><b>@@DUE@@</b>まで</p>
      </div>
    </div>
    <ul class="cp-notes">
      <li>金券など対象外商品あり</li>
      <li>上限100,000円まで</li>
      <li>査定前に「HPをみた」とお伝えください</li>
    </ul>
    <div class="cp-actions">
      <a class="cp-btn cp-btn-line" href="@@LINE@@" target="_blank" rel="noopener noreferrer">💬 LINE査定で相談</a>
      <a class="cp-btn cp-btn-tel" href="@@TEL@@">📞 電話で相談</a>
      <button type="button" class="cp-btn cp-btn-page" data-cp-close>ページを見る（閉じる）</button>
    </div>
  </div>
</div>
<script>
(function(){
  var modal = document.getElementById('cpModal');
  if(!modal) return;
  var DEADLINE = '@@DEADLINE@@';
  var KEY = '@@KEY@@';
  var params = new URLSearchParams(window.location.search);
  var force = params.get('campaign') === '1';
  function todayKey(){
    var d = new Date();
    return d.getFullYear() + '-' + ('0'+(d.getMonth()+1)).slice(-2) + '-' + ('0'+d.getDate()).slice(-2);
  }
  var stored = null;
  try { stored = localStorage.getItem(KEY); } catch(e){}
  var inPeriod = Date.now() <= Date.parse(DEADLINE);
  if(!force && (!inPeriod || stored === todayKey())) return;

  var lastFocus = null;
  function open(){
    lastFocus = document.activeElement;
    modal.classList.add('is-open');
    document.documentElement.classList.add('cp-locked');
    var c = document.getElementById('cpClose');
    if(c) c.focus({preventScroll:true});
  }
  function close(){
    modal.classList.remove('is-open');
    document.documentElement.classList.remove('cp-locked');
    try { localStorage.setItem(KEY, todayKey()); } catch(e){}
    if(lastFocus && lastFocus.focus) lastFocus.focus({preventScroll:true});
  }
  window.setTimeout(open, 650);

  Array.prototype.forEach.call(modal.querySelectorAll('.cp-close,[data-cp-close]'), function(el){
    el.addEventListener('click', close);
  });
  modal.addEventListener('click', function(e){ if(e.target === modal) close(); });
  document.addEventListener('keydown', function(e){
    if(!modal.classList.contains('is-open')) return;
    if(e.key === 'Escape' || e.key === 'Esc'){ close(); return; }
    if(e.key === 'Tab'){
      var f = modal.querySelectorAll('a[href],button:not([disabled])');
      if(!f.length) return;
      var first = f[0], last = f[f.length-1];
      if(e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
      else if(!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
    }
  });
})();
</script>"""

REQUIRED_TOKENS = ["香芝畑店限定！", "買取金額", "30", "%UP", "金券など対象外商品あり", "上限100,000円まで", "査定前に「HPをみた」とお伝えください"]


def build_deco(season):
    motif = MOTIFS[season]
    parts = [
        motif.format(pos="right:-26px;bottom:-30px;width:112px;height:112px", o=".20", rot="14"),
        motif.format(pos="left:-24px;top:-26px;width:76px;height:76px", o=".15", rot="-18"),
        SPARKLE.format(t="21%", l="83%", s=18, o=".55"),
        SPARKLE.format(t="78%", l="8%", s=12, o=".4"),
        SPARKLE.format(t="93%", l="86%", s=10, o=".3"),
    ]
    return "\n".join("        " + p for p in parts)


def build_block(year, month, title_override=None):
    info = MONTHS[month]
    last_day = calendar.monthrange(year, month)[1]
    due = f"{month}月{last_day}日"
    deadline = f"{year}-{month:02d}-{last_day:02d}T23:59:59+09:00"
    key = f"cp{year}{month:02d}_closed"

    lead, main = info["lead"], info["main"]
    if title_override:
        lead, main = "", title_override
    full = (lead + main) if lead else main
    if info["lead"] and title_override:
        full = title_override

    html = (HTML_TEMPLATE
            .replace("@@ACCENT@@", info["accent"])
            .replace("@@SOFT@@", info["soft"])
            .replace("@@GLOW@@", info["glow"])
            .replace("@@DECO@@", build_deco(info["season"]))
            .replace("@@LEAD@@", lead)
            .replace("@@MAIN@@", main)
            .replace("@@FULLTITLE@@", full)
            .replace("@@DUE@@", due)
            .replace("@@DEADLINE@@", deadline)
            .replace("@@KEY@@", key)
            .replace("@@LINE@@", LINE_URL)
            .replace("@@TEL@@", TEL_TEL))

    block = ("<style>\n" + CSS + "</style>\n" + html + "\n")
    block = block.replace("@@LEAD@@", lead).replace("@@MAIN@@", main)

    for token in REQUIRED_TOKENS:
        if token not in block:
            raise SystemExit(f"生成したブロックに必須要素がありません: {token}")

    meta = dict(year=year, month=month, full=full, due=due, deadline=deadline, key=key)
    return block, meta


def replace_in_index(index_path, block, dry_run=False):
    with open(index_path, encoding="utf-8") as f:
        src = f.read()

    if src.count(START_MARK) != 1 or src.count(END_MARK) != 1:
        raise SystemExit(f"マーカーが不正です（START={src.count(START_MARK)} / END={src.count(END_MARK)}）")
    s = src.index(START_MARK) + len(START_MARK)
    e = src.index(END_MARK)
    if e < s:
        raise SystemExit("END マーカーが START より前にあります")

    current = src[s:e].strip()
    if current == block.strip():
        return 10, src, current

    new_src = src[:s] + "\n" + block + src[e:]
    if not dry_run:
        tmp = index_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(new_src)
        os.replace(tmp, index_path)
    return 0, new_src, current


def main():
    ap = argparse.ArgumentParser(description="キャンペーンポップアップを月ごとに差し替える")
    ap.add_argument("--month", type=int, help="対象月 1-12（既定: 今日の月）")
    ap.add_argument("--year", type=int, help="対象年（既定: 今日の年）")
    ap.add_argument("--title", help="タイトル見出しを丸ごと指定（既定: 月ごとの季節タイトル）")
    ap.add_argument("--index", default=DEFAULT_INDEX, help="index.html のパス")
    ap.add_argument("--dry-run", action="store_true", help="書き換えずに生成結果を標準出力へ")
    ap.add_argument("--commit-push", action="store_true", help="変更を commit して origin HEAD へ push する")
    ap.add_argument("--list", action="store_true", help="12か月分のタイトル一覧を表示")
    args = ap.parse_args()

    if args.list:
        for m in range(1, 13):
            print(f"{m:2d}月: {MONTHS[m]['lead']}{MONTHS[m]['main']}（装飾: {MONTHS[m]['season']}）")
        return 0

    today = datetime.date.today()
    month = args.month or today.month
    year = args.year or today.year
    if not 1 <= month <= 12:
        raise SystemExit("--month は 1〜12 で指定してください")

    block, meta = build_block(year, month, args.title)

    if args.dry_run:
        code, _, _ = replace_in_index(args.index, block, dry_run=True)
        sys.stdout.write(block)
        print(f"\n# dry-run: {meta['year']}-{meta['month']:02d} / {meta['full']} / 期限 {meta['due']} / {meta['deadline']} / KEY {meta['key']} / 変更{'あり' if code == 0 else 'なし'}",
              file=sys.stderr)
        return 0

    code, _, _ = replace_in_index(args.index, block)
    if code == 10:
        print(f"変更なし: {meta['full']}（{meta['due']}まで）")
        return 10

    print(f"更新しました: {meta['full']}（{meta['due']}まで / 期限 {meta['deadline']}）")

    if args.commit_push:
        subprocess.run(["git", "add", "index.html"], cwd=BASE_DIR, check=True)
        msg = f"Update monthly campaign popup for {meta['year']}-{meta['month']:02d} ({meta['full']})"
        subprocess.run(["git", "commit", "-m", msg], cwd=BASE_DIR, check=True)
        subprocess.run(["git", "push", "origin", "HEAD"], cwd=BASE_DIR, check=True)
        print("commit & push 完了")

    return 0


if __name__ == "__main__":
    sys.exit(main())

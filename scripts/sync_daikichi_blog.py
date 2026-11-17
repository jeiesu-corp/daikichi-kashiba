#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
買取大吉 香芝畑店 公式ブログ → 店舗HP「店長ブログ」セクション 自動同期スクリプト

  取得元 : https://www.kaitori-daikichi.jp/blog/kashiba-hata （買取大吉 店長ブログ 香芝畑店）
  更新先 : index.html の <!-- BLOG_RESULTS_START --> 〜 <!-- BLOG_RESULTS_END --> の間

  ・最新3件（3列×1行）を取得し、カードHTMLを書き換える
  ・記事サムネイルは個別記事ページの本文（div.blog_txt）先頭の商品写真URLを直リンク
  ・内容に変更があったときだけ index.html を書き換える
  ・変更がなければファイルを触らない（mtime も更新しない）

使い方:
  python3 scripts/sync_daikichi_blog.py               # 取得して必要なら更新（通常）
  python3 scripts/sync_daikichi_blog.py --dry-run     # 更新内容を表示するだけ（書き込まない）
  python3 scripts/sync_daikichi_blog.py --check-only  # 更新が必要かだけ判定して終了
  python3 scripts/sync_daikichi_blog.py --commit-push # 更新があったら git add/commit/push まで実行
  python3 scripts/sync_daikichi_blog.py --limit 3 --verbose

終了コード:
  0  更新した（--dry-run / --check-only では「更新が必要」）
  10 変更なし
  1  エラー（取得失敗・マーカー不在など）

定期実行の例（GitHub Actions / cron どちらでも）:
  0 9 * * * cd /path/to/daikichi-kashiba && python3 scripts/sync_daikichi_blog.py --commit-push
  ※ 終了コード 10（変更なし）は正常系。cron から呼ぶ場合は `|| [ $? -eq 10 ]` などで握りつぶす。
"""

from __future__ import annotations

import argparse
import html
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

BLOG_LIST_URL = "https://www.kaitori-daikichi.jp/blog/kashiba-hata"
BLOG_BASE = "https://www.kaitori-daikichi.jp"
DEFAULT_LIMIT = 3
JST = timezone(timedelta(hours=9))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(REPO_ROOT, "index.html")

MARK_START = "<!-- BLOG_RESULTS_START -->"
MARK_END = "<!-- BLOG_RESULTS_END -->"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# 記事本文の末尾に毎回入っている共通バナー（商品写真ではない画像）
BANNER_PATTERNS = (
    "ca368b950a150a889cf0",   # 共通バナー（買取大吉 キャンペーン）
    "IMG_FREE_URL_TMP",       # 共通バナー
)

EXIT_UPDATED = 0
EXIT_UNCHANGED = 10
EXIT_ERROR = 1


# ---------------------------------------------------------------- HTTP
def http_get(url: str, retries: int = 3, timeout: int = 30) -> str:
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,image/avif,image/webp,*/*",
                "Accept-Language": "ja,en;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            return raw.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
            if i < retries - 1:
                time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"取得に失敗しました: {url} ({last})")


# ---------------------------------------------------------------- 取得・解析
def strip_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"[ \t]+", " ", s).strip()


def clean_title(raw: str) -> str:
    """「〜をお買取りさせて頂きました！〇〇の高価買取なら…」の定型後半を落として読みやすくする。"""
    t = strip_tags(raw)
    t = re.sub(r"\s*[｜|]\s*香芝畑店\s*$", "", t)
    # 「ロレックスの高価買取なら信頼と実績の買取専門店『買取大吉 香芝畑店』へ」以降を削除
    t = re.sub(r"\s*[^\s。！!]*?の?高価買取なら.*$", "", t)
    t = re.sub(r"\s*高額買取なら.*$", "", t)
    t = re.sub(r"\s*信頼と実績の買取専門店.*$", "", t)
    t = re.sub(r"[\s　]+", " ", t).strip()
    t = re.sub(r"[へ\s]+$", "", t)
    return t


def parse_date(text: str) -> tuple[str, str]:
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if not m:
        return "", ""
    y, mo, d = (int(x) for x in m.groups())
    return f"{y}.{mo:02d}.{d:02d}", f"{y}-{mo:02d}-{d:02d}"


def fetch_entries(limit: int) -> list[dict]:
    page = http_get(BLOG_LIST_URL)
    # 記事は <div class="entry" id="post<ID>"> 単位で並ぶ。次の entry の直前までを1件分とする
    blocks = re.findall(
        r'<div class="entry" id="post(\d+)">(.*?)(?=<div class="entry" id="post|\Z)',
        page, re.S)
    if not blocks:
        raise RuntimeError("記事一覧の解析に失敗しました（div.entry が見つかりません）")

    entries = []
    for post_id, body in blocks:
        m = re.search(r'<h2 class="blog_title"><a href="([^"]+)">(.*?)</a></h2>', body, re.S)
        if not m:
            continue
        url, raw_title = html.unescape(m.group(1)), m.group(2)
        d = re.search(r'<div class="blog_date">(.*?)</div>', body, re.S)
        date_show, date_iso = parse_date(strip_tags(d.group(1)) if d else "")
        cats = [strip_tags(c) for c in
                re.findall(r'<a class="blog-list-categories-item"[^>]*>(.*?)</a>', body, re.S)]
        cats = [c for c in cats if c and c != "お知らせ"]
        prev = re.search(r'<div class="blog-list-item-txt">(.*?)</div>', body, re.S)
        entries.append({
            "id": post_id,
            "url": url,
            "title": clean_title(raw_title),
            "raw_title": strip_tags(raw_title),
            "date": date_show,
            "date_iso": date_iso,
            "tags": cats[:2],
            "preview": strip_tags(prev.group(1)) if prev else "",
            "image": "",
            "excerpt": "",
        })
        if len(entries) >= limit:
            break

    if not entries:
        raise RuntimeError("記事が1件も抽出できませんでした（HTML構造の変更？）")
    return entries


# 定型的な挨拶だけの段落（＝紹介文には使わない）
GREETING_RE = re.compile(
    r"^(?:こんにちは。?|買取大吉[^。]{0,20}ございます。?|いつも店長ブログ[^。]{0,20}。?"
    r"|よろしくお願い[^。]{0,20}。?|(?:有難う|ありがとう)ございます[！!。]*"
    r")+"
)


def tidy(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"[。、]{2,}", "。", t)          # 「です。。」のような重複を1つに
    return t.strip()


def is_greeting(t: str) -> bool:
    if len(t) < 18:
        return True
    if t.startswith(("こんにちは", "買取大吉", "いつも店長ブログ")):
        return True
    return bool(GREETING_RE.fullmatch(t))


def build_excerpt(body: str, limit: int = 100) -> str:
    """記事本文から挨拶を飛ばして最初の中身のある一文を100文字程度に整える。"""
    for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S):
        if "<img" in p.lower():
            continue
        t = tidy(strip_tags(p))
        if is_greeting(t):
            continue
        if len(t) <= limit:
            return t
        cut = t[:limit]
        i = cut.rfind("。")
        if i >= limit * 0.5:
            return cut[: i + 1]
        return tidy(cut.rstrip("、。 ") + "…")
    return ""


def pick_image(body: str) -> str:
    """記事本文（div.blog_txt）先頭の商品写真URLを返す。共通バナーは除外。"""
    for tag in re.findall(r"<img[^>]+>", body, re.I):
        src = re.search(r'src="([^"]+)"', tag)
        if not src:
            continue
        src = html.unescape(src.group(1))
        if "/wp-content/uploads/" not in src:
            continue
        if any(b in src for b in BANNER_PATTERNS):
            continue
        srcset = re.search(r'srcset="([^"]+)"', tag)
        if srcset:
            best, best_w = None, -1
            for part in srcset.group(1).split(","):
                bits = part.strip().split()
                if not bits:
                    continue
                w = 0
                m = re.search(r"(\d+)w$", bits[-1]) if len(bits) > 1 else None
                if m:
                    w = int(m.group(1))
                if w > best_w:
                    best, best_w = bits[0], w
            if best:
                src = html.unescape(best)
        if src.startswith("/"):
            src = BLOG_BASE + src
        return src
    return ""


def enrich(entries: list[dict], old_images: dict[str, str], verbose: bool) -> None:
    """各記事ページを取得して商品写真と紹介文を補う。既出URLの画像は再利用して通信を減らす。"""
    for e in entries:
        cached = old_images.get(e["url"])
        if cached:
            e["image"] = cached
        # 紹介文は一覧の preview からも作れるが、記事本文の方が読みやすいのでページを取得する
        try:
            art = http_get(e["url"])
            m = re.search(r'<div class="blog_txt">', art)
            body = art[m.start(): m.start() + 40000] if m else art
            if not cached:
                e["image"] = pick_image(body)
            e["excerpt"] = build_excerpt(body) or clamp_preview(e["preview"])
        except Exception as ex:  # noqa: BLE001
            print(f"  ! 記事の取得に失敗（{e['url']}）: {ex}", file=sys.stderr)
            e["excerpt"] = clamp_preview(e["preview"])
        if verbose:
            print(f"  - {e['date']} {e['title'][:40]} | img={'あり' if e['image'] else 'なし'}")


def clamp_preview(prev: str, limit: int = 100) -> str:
    if not prev:
        return ""
    # 一覧の冒頭には商品名の英字が連結されているので、挨拶以降を優先
    for g in ("こんにちは", "買取大吉", "いつも店長ブログ"):
        i = prev.find(g)
        if i > 0:
            prev = prev[i:]
            break
    prev = re.sub(r"^(こんにちは。?|買取大吉[^。]*。|いつも店長ブログをご覧頂き有難うございます。)+", "", prev)
    prev = tidy(prev)
    if len(prev) <= limit:
        return prev.strip()
    cut = prev[:limit]
    i = cut.rfind("。")
    return (cut[: i + 1] if i >= limit * 0.5 else cut.rstrip("、。 ") + "…").strip()


# ---------------------------------------------------------------- 生成
def esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_card(e: dict) -> str:
    ttl = esc(e["title"])
    url = esc(e["url"])
    tags = "".join(f'<span class="blog-tag">{esc(t)}</span>' for t in e["tags"])
    excerpt = esc(e["excerpt"]) if e["excerpt"] else ""
    if e["image"]:
        thumb = (f'<figure class="blog-thumb"><img src="{esc(e["image"])}" '
                 f'alt="{ttl}" loading="lazy" decoding="async"></figure>')
    else:
        thumb = '<figure class="blog-thumb blog-thumb--noimg"><span>買取大吉</span></figure>'
    exc_html = f'<p class="blog-exc">{excerpt}</p>' if excerpt else ""
    return f"""      <a class="blog-card" href="{url}" target="_blank" rel="noopener noreferrer">
        {thumb}
        <div class="blog-body">
          <div class="blog-meta"><time datetime="{esc(e['date_iso'])}">{esc(e['date'])}</time>{tags}</div>
          <h3 class="blog-ttl">{ttl}</h3>
          {exc_html}
          <span class="blog-read">記事を読む ▷</span>
        </div>
      </a>"""


def render_block(entries: list[dict]) -> str:
    cards = "\n".join(render_card(e) for e in entries)
    return f"""{MARK_START}
    <!-- このブロックは scripts/sync_daikichi_blog.py が自動生成しています（手動編集しないでください） -->
    <div class="blog-grid">
{cards}
    </div>
    <p class="blog-more">
      <a class="cta-btn" href="{BLOG_LIST_URL}" target="_blank" rel="noopener noreferrer">店長ブログ一覧を見る ▶</a>
    </p>
    {MARK_END}"""


def read_old_images(index_html: str) -> dict[str, str]:
    """現在 index.html に入っているカードから URL→画像URL を拾う（再取得の省略用）。"""
    out: dict[str, str] = {}
    for m in re.finditer(r'<a class="blog-card" href="([^"]+)".*?</a>', index_html, re.S):
        card = m.group(0)
        img = re.search(r'<img src="([^"]+)"', card)
        if img:
            out[html.unescape(m.group(1))] = html.unescape(img.group(1))
    return out


def replace_block(index_html: str, block: str) -> str:
    pat = re.compile(r"<!--\s*BLOG_RESULTS_START\s*-->.*?<!--\s*BLOG_RESULTS_END\s*-->", re.S)
    if not pat.search(index_html):
        raise RuntimeError(f"index.html にマーカー（{MARK_START} / {MARK_END}）が見つかりません")
    return pat.sub(lambda _m: block, index_html, count=1)


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="大吉公式ブログ → 店長ブログセクション同期")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="取得件数（既定3）")
    ap.add_argument("--dry-run", action="store_true", help="書き込まずに差分の有無だけ表示")
    ap.add_argument("--check-only", action="store_true", help="更新の要否だけ判定（--dry-run と同じ判定）")
    ap.add_argument("--commit-push", action="store_true", help="更新があったら git commit & push する")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    try:
        print(f"[1/3] 記事一覧を取得: {BLOG_LIST_URL}")
        entries = fetch_entries(args.limit)
        print(f"      {len(entries)}件を検出（最新: {entries[0]['date']} {entries[0]['title'][:30]}）")

        index_path = INDEX_PATH
        with open(index_path, encoding="utf-8") as f:
            old_html = f.read()

        print("[2/3] 各記事の商品写真・紹介文を取得")
        enrich(entries, read_old_images(old_html), args.verbose)

        new_block = render_block(entries)
        new_html = replace_block(old_html, new_block)
        changed = new_html != old_html

        if args.check_only or args.dry_run:
            print("[3/3] " + ("更新が必要です（差分あり）" if changed else "変更なし（最新の状態です）"))
            if args.verbose and changed:
                import difflib
                for line in difflib.unified_diff(old_html.splitlines(), new_html.splitlines(),
                                                 "index.html (now)", "index.html (new)", n=1,
                                                 lineterm=""):
                    print(line)
            return EXIT_UPDATED if changed else EXIT_UNCHANGED

        if not changed:
            print("[3/3] 変更なし。index.html は更新していません。")
            return EXIT_UNCHANGED

        with open(index_path, "w", encoding="utf-8") as f:
            f.write(new_html)
        print(f"[3/3] index.html を更新しました（{len(entries)}件 / "
              f"{datetime.now(JST):%Y-%m-%d %H:%M}）")
        for e in entries:
            print(f"      {e['date']} {e['title'][:52]}")

        if args.commit_push:
            msg = f"Sync 店長ブログ section ({len(entries)} posts, {datetime.now(JST):%Y-%m-%d})"
            for cmd in (["git", "add", "index.html"],
                        ["git", "commit", "-m", msg],
                        ["git", "push", "origin", "HEAD"]):
                print("      $ " + " ".join(cmd))
                subprocess.run(cmd, cwd=REPO_ROOT, check=True)
            print("      git push 完了")
        return EXIT_UPDATED

    except Exception as e:  # noqa: BLE001
        print(f"エラー: {e}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())

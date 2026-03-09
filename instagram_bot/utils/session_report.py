"""
Live session report: who we followed, liked, commented — with links and graphs.
One HTML file per session, updated after each action. Open in browser and refresh to see latest.
"""
import json
from datetime import datetime
from pathlib import Path

_REPORT_DIR = Path(__file__).resolve().parent.parent
_session_start: datetime | None = None
_report_path: Path | None = None

_follows: list[dict] = []
_likes: list[dict] = []
_comments: list[dict] = []
_comment_likes_count = 0
_reels_viewed = 0


def start_session() -> str:
    """Call at bot start. Creates new report file for this session. Returns report file path."""
    global _session_start, _report_path, _follows, _likes, _comments, _comment_likes_count, _reels_viewed
    _session_start = datetime.utcnow()
    _follows = []
    _likes = []
    _comments = []
    _comment_likes_count = 0
    _reels_viewed = 0
    sid = _session_start.strftime("%Y%m%d_%H%M%S")
    _report_path = _REPORT_DIR / f"session_report_{sid}.html"
    _write_html()
    return str(_report_path)


def _norm_user(u: str | None) -> str:
    """Store without leading @ so display is always @username."""
    if not u:
        return ""
    return (u or "").strip().lstrip("@").strip()


def log_follow(username: str) -> None:
    if not username:
        return
    u = _norm_user(username)
    if not u:
        return
    _follows.append({
        "username": u,
        "profile_url": f"https://www.instagram.com/{u}/",
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    })
    _write_html()


def log_like(reel_url: str, author: str) -> None:
    _likes.append({
        "reel_url": reel_url or "",
        "author": _norm_user(author),
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    })
    _write_html()


def log_comment(reel_url: str, author: str, comment_text: str) -> None:
    _comments.append({
        "reel_url": reel_url or "",
        "author": _norm_user(author),
        "comment": (comment_text or "").strip()[:500],
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    })
    _write_html()


def log_comment_likes(count: int) -> None:
    global _comment_likes_count
    _comment_likes_count += count
    _write_html()


def log_reel_viewed() -> None:
    """Increment total reels viewed this session."""
    global _reels_viewed
    _reels_viewed += 1
    _write_html()


def _write_html() -> None:
    if _report_path is None or _session_start is None:
        return
    now = datetime.utcnow()
    duration_sec = (now - _session_start).total_seconds()
    duration_str = f"{int(duration_sec // 3600)}h {int((duration_sec % 3600) // 60)}m {int(duration_sec % 60)}s"

    html = _build_html(
        session_start=_session_start.strftime("%Y-%m-%d %H:%M:%S UTC"),
        last_updated=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        duration=duration_str,
        follows=_follows,
        likes=_likes,
        comments=_comments,
        comment_likes=_comment_likes_count,
        reels_viewed=_reels_viewed,
    )
    try:
        _report_path.write_text(html, encoding="utf-8")
    except Exception:
        pass


def _build_html(
    session_start: str,
    last_updated: str,
    duration: str,
    follows: list[dict],
    likes: list[dict],
    comments: list[dict],
    comment_likes: int,
    reels_viewed: int = 0,
) -> str:
    n_f = len(follows)
    n_l = len(likes)
    n_c = len(comments)

    def _at(name: str) -> str:
        return f"@{name}" if name else "—"

    follows_rows = "".join(
        f'<tr><td>{i+1}</td><td>{_at(e["username"])}</td>'
        f'<td><a href="{e["profile_url"]}" target="_blank" rel="noopener">Profile</a></td>'
        f'<td>{e["time"]}</td></tr>'
        for i, e in enumerate(reversed(follows))
    )
    likes_rows = "".join(
        f'<tr><td>{i+1}</td><td><a href="{e["reel_url"]}" target="_blank" rel="noopener">Reel</a></td>'
        f'<td>{_at(e["author"])}</td><td>{e["time"]}</td></tr>'
        for i, e in enumerate(reversed(likes))
    )
    comments_rows = "".join(
        f'<tr><td>{i+1}</td><td><a href="{e["reel_url"]}" target="_blank" rel="noopener">Reel</a></td>'
        f'<td>{_at(e["author"])}</td><td class="comment-cell">{e["comment"]}</td><td>{e["time"]}</td></tr>'
        for i, e in enumerate(reversed(comments))
    )

    chart_data = json.dumps({
        "follows": n_f,
        "likes": n_l,
        "comments": n_c,
        "comment_likes": comment_likes,
        "reels_viewed": reels_viewed,
    })

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Session Report — {last_updated}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1rem 2rem; background: #1a1a1a; color: #e0e0e0; }}
h1 {{ color: #fff; }}
h2 {{ color: #b0b0b0; margin-top: 2rem; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 0.5rem; }}
th, td {{ border: 1px solid #444; padding: 0.5rem 0.75rem; text-align: left; }}
th {{ background: #333; color: #fff; }}
tr:nth-child(even) {{ background: #252525; }}
a {{ color: #6eb8ff; }}
a:hover {{ text-decoration: underline; }}
.comment-cell {{ max-width: 320px; word-break: break-word; }}
.meta {{ color: #888; margin: 0.5rem 0; }}
.chart-wrap {{ max-width: 400px; margin: 1.5rem 0; }}
</style>
</head>
<body>
<h1>Instagram Bot — Session Report</h1>
<p class="meta">Started: <strong>{session_start}</strong></p>
<p class="meta">Duration: <strong>{duration}</strong> · Last updated: <strong>{last_updated}</strong></p>
<p class="meta">Total reels viewed: <strong>{reels_viewed}</strong></p>
<p class="meta">Refresh this page to see live updates.</p>

<div class="chart-wrap">
<canvas id="chart"></canvas>
</div>

<h2>Followed ({n_f})</h2>
<table>
<thead><tr><th>#</th><th>Username</th><th>Link</th><th>Time</th></tr></thead>
<tbody>{follows_rows or "<tr><td colspan='4'>None yet</td></tr>"}</tbody>
</table>

<h2>Liked reels ({n_l})</h2>
<table>
<thead><tr><th>#</th><th>Reel</th><th>Author</th><th>Time</th></tr></thead>
<tbody>{likes_rows or "<tr><td colspan='4'>None yet</td></tr>"}</tbody>
</table>

<h2>Comments ({n_c})</h2>
<table>
<thead><tr><th>#</th><th>Reel</th><th>Author</th><th>Our comment</th><th>Time</th></tr></thead>
<tbody>{comments_rows or "<tr><td colspan='5'>None yet</td></tr>"}</tbody>
</table>

<h2>Comment likes (this session)</h2>
<p>{comment_likes} comment(s) liked.</p>

<script>
const data = {chart_data};
new Chart(document.getElementById("chart"), {{
  type: "bar",
  data: {{
    labels: ["Reels viewed", "Follows", "Reel likes", "Comments", "Comment likes"],
    datasets: [{{ label: "Count", data: [data.reels_viewed, data.follows, data.likes, data.comments, data.comment_likes], backgroundColor: ["#868e96","#6eb8ff","#ff6b6b","#69db7c","#ffd43b"] }}]
  }},
  options: {{ responsive: true, scales: {{ y: {{ beginAtZero: true }} }} }}
}});
</script>
</body>
</html>"""

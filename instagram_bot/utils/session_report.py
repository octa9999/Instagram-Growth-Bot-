"""
Live session report: who we followed, liked, commented — with links and graphs.
One HTML file per session, updated after each action. Open in browser and refresh to see latest.
"""
import html
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
_current_platform = "ig"  # "ig" or "tt"


def start_session() -> str:
    """Call at bot start. Creates new report file for this session. Returns report file path."""
    global _session_start, _report_path, _follows, _likes, _comments, _comment_likes_count, _reels_viewed, _current_platform
    _session_start = datetime.utcnow()
    _follows = []
    _likes = []
    _comments = []
    _comment_likes_count = 0
    _reels_viewed = 0
    _current_platform = "ig"
    sid = _session_start.strftime("%Y%m%d_%H%M%S")
    _report_path = _REPORT_DIR / f"session_report_{sid}.html"
    _write_html()
    return str(_report_path)


def _norm_user(u: str | None) -> str:
    """Store without leading @ so display is always @username."""
    if not u:
        return ""
    return (u or "").strip().lstrip("@").strip()


def set_platform(platform: str) -> None:
    """Set current platform label used for subsequent log entries."""
    global _current_platform
    p = (platform or "").lower()
    if p.startswith("t"):
        _current_platform = "tt"
    else:
        _current_platform = "ig"


def log_follow(username: str) -> None:
    if not username:
        return
    u = _norm_user(username)
    if not u:
        return
    profile_url = (
        f"https://www.tiktok.com/@{u}"
        if _current_platform == "tt"
        else f"https://www.instagram.com/{u}/"
    )
    _follows.append({
        "username": u,
        "profile_url": profile_url,
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "platform": _current_platform,
    })
    _write_html()


def log_like(reel_url: str, author: str) -> None:
    _likes.append({
        "reel_url": reel_url or "",
        "author": _norm_user(author),
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "platform": _current_platform,
    })
    _write_html()


def log_comment(reel_url: str, author: str, comment_text: str) -> None:
    _comments.append({
        "reel_url": reel_url or "",
        "author": _norm_user(author),
        "comment": (comment_text or "").strip()[:500],
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "platform": _current_platform,
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

    def _platform_counts(items: list[dict]) -> tuple[int, int]:
        ig = sum(1 for e in items if e.get("platform", "ig") == "ig")
        tt = sum(1 for e in items if e.get("platform", "ig") == "tt")
        return ig, tt

    ig_follows, tt_follows = _platform_counts(follows)
    ig_likes, tt_likes = _platform_counts(likes)
    ig_comments, tt_comments = _platform_counts(comments)

    def _at(name: str) -> str:
        return f"@{name}" if name else "—"

    # Combined recent activity (follows, likes, comments) sorted by time desc
    def _parse_time(e: dict) -> str:
        return e.get("time", "") or ""

    activities: list[dict] = []
    for e in follows:
        activities.append({
            "type": "Follow",
            "time": e["time"],
            "detail": _at(e["username"]),
            "origin": "Instagram" if e.get("platform") == "ig" else "TikTok",
            "link": e.get("profile_url", "#"),
            "raw_time": _parse_time(e),
        })
    for e in likes:
        activities.append({
            "type": "Like",
            "time": e["time"],
            "detail": _at(e["author"]),
            "origin": "Instagram" if e.get("platform") == "ig" else "TikTok",
            "link": e.get("reel_url", "#"),
            "raw_time": _parse_time(e),
        })
    for e in comments:
        activities.append({
            "type": "Comment",
            "time": e["time"],
            "detail": _at(e.get("author") or ""),
            "comment_full": (e.get("comment") or "").strip()[:500],
            "origin": "Instagram" if e.get("platform") == "ig" else "TikTok",
            "link": e.get("reel_url", "#"),
            "raw_time": _parse_time(e),
        })
    activities.sort(key=lambda x: x["raw_time"], reverse=True)

    # Risk Alerts–style rows: Alert Type (icon), Date, AI Response (pill), Origin, Method (link)
    def _row_icon(t: str) -> str:
        if t == "Follow":
            return "user-plus"
        if t == "Like":
            return "heart"
        return "message-circle"

    def _detail_cell(a: dict) -> str:
        if a["type"] == "Comment":
            comment = a.get("comment_full") or ""
            return f'<td class="px-4 py-3 font-geist text-white/90 max-w-[280px] break-words" title="{html.escape(comment)}">{html.escape(comment) or "—"}</td>'
        return f'<td class="px-4 py-3 font-geist">{html.escape(a.get("detail") or "—")}</td>'

    activity_rows = "".join(
        f'<tr class="border-t border-white/5 hover:bg-white/5">'
        f'<td class="px-4 py-3 font-geist">'
        f'<span class="inline-flex items-center gap-2"><i data-lucide="{_row_icon(a["type"])}" class="w-4 h-4 text-violet-400"></i>{a["type"]}</span></td>'
        f'<td class="px-4 py-3 font-geist">{a["time"]}</td>'
        f'{_detail_cell(a)}'
        f'<td class="px-4 py-3 font-geist">{html.escape(a["origin"])}</td>'
        f'<td class="px-4 py-3 font-geist"><a href="{html.escape(a["link"])}" target="_blank" rel="noopener" class="text-white/80 hover:text-white hover:underline">Open</a></td>'
        f"</tr>"
        for a in activities[:50]
    )
    if not activity_rows:
        activity_rows = '<tr class="border-t border-white/5"><td colspan="5" class="px-4 py-3 font-geist text-white/60">No activity yet. Refresh after the bot runs.</td></tr>'

    # Real chart data from session activities (chronological)
    activities_chrono = sorted(activities, key=lambda x: x["raw_time"])
    n_act = len(activities_chrono)
    num_buckets_health = 12
    num_buckets_eng = 8
    security_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    budget_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"]

    # Views chart: 12 points = cumulative reels viewed (real). Evenly spread over session.
    views_data = []
    for i in range(num_buckets_health):
        cumulative = int((i + 1) * reels_viewed / num_buckets_health) if num_buckets_health else 0
        views_data.append(cumulative)

    # Engagement: 8 buckets = real follows and likes+comments per time segment
    follows_per_bucket = [0] * num_buckets_eng
    likes_comments_per_bucket = [0] * num_buckets_eng
    if n_act > 0:
        for i, a in enumerate(activities_chrono):
            b = int(i * num_buckets_eng / n_act)
            if b >= num_buckets_eng:
                b = num_buckets_eng - 1
            if a["type"] == "Follow":
                follows_per_bucket[b] += 1
            else:
                likes_comments_per_bucket[b] += 1
    actual_data = follows_per_bucket
    target_data = likes_comments_per_bucket

    chart_data = json.dumps({
        "follows": n_f,
        "likes": n_l,
        "comments": n_c,
        "comment_likes": comment_likes,
        "reels_viewed": reels_viewed,
        "ig_follows": ig_follows,
        "tt_follows": tt_follows,
        "ig_likes": ig_likes,
        "tt_likes": tt_likes,
        "ig_comments": ig_comments,
        "tt_comments": tt_comments,
        "views_data": views_data,
        "security_labels": security_labels,
        "budget_labels": budget_labels,
        "actual_data": actual_data,
        "target_data": target_data,
    })

    card1_bg = "https://hoirqrkdgbmvpwutwuwj.supabase.co/storage/v1/object/public/assets/assets/8d0f3c19-2547-4b20-8911-9713329c4ca6_800w.jpg"
    card2_bg = "https://hoirqrkdgbmvpwutwuwj.supabase.co/storage/v1/object/public/assets/assets/9dead2ce-9640-41bd-8153-af6e7acc42cf_800w.jpg"
    card3_bg = "https://hoirqrkdgbmvpwutwuwj.supabase.co/storage/v1/object/public/assets/assets/86c20217-e734-45e2-a50b-0e5602db415c_800w.jpg"

    return f"""<!DOCTYPE html>
<html lang="en" class="h-full antialiased" style="font-family:'Inter',sans-serif">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Social Handler — Session</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://unpkg.com/lucide@latest/dist/umd.lucide.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body class="h-full flex items-center justify-center bg-[#585662] bg-[url(https://hoirqrkdgbmvpwutwuwj.supabase.co/storage/v1/object/public/assets/assets/a7b93216-616b-4c47-9f50-09f8fd2f70a2_3840w.jpg)] bg-cover pt-4 pr-4 pb-4 pl-4">
  <div id="app" class="w-full max-w-[1440px] min-h-[600px] h-[min(900px,calc(100vh-2rem))] bg-gradient-to-br from-[#0d0b16] to-[#151226] rounded-3xl overflow-hidden text-white shadow-2xl">
    <div class="flex h-full flex-col lg:flex-row">
      <aside class="w-full lg:w-64 bg-gradient-to-br from-[#0d0b16] to-[#151226] flex flex-col lg:max-h-full overflow-y-auto border-r border-white/5">
        <div class="flex items-center gap-2 px-6 py-4 lg:py-6 flex-shrink-0">
          <div class="w-4 h-4 bg-stone-500 rounded-full"></div>
          <span class="text-lg font-semibold tracking-tight font-geist">AI Social Handler</span>
        </div>
        <nav class="flex-1 px-4 space-y-1 overflow-y-auto">
          <button type="button" data-section="section-overview" class="nav-section group w-full flex items-center gap-3 px-4 py-3 rounded-lg bg-stone-600/20 hover:bg-stone-600/30">
            <i data-lucide="home" class="w-[20px] h-[20px]"></i>
            <span class="text-sm font-medium font-geist">Overview</span>
          </button>
          <button type="button" data-section="section-activity-log" class="nav-section group w-full flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-stone-600/20">
            <i data-lucide="camera" class="w-[20px] h-[20px]"></i>
            <span class="text-sm font-medium font-geist">Instagram</span>
          </button>
          <button type="button" data-section="section-charts" class="nav-section group w-full flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-stone-600/20">
            <i data-lucide="chart-line" class="w-[20px] h-[20px]"></i>
            <span class="text-sm font-medium font-geist">Analytics</span>
          </button>
          <button type="button" data-section="section-activity-log" class="nav-section group w-full flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-stone-600/20">
            <i data-lucide="video" class="w-[20px] h-[20px]"></i>
            <span class="text-sm font-medium font-geist">TikTok</span>
          </button>
          <div>
            <button id="aiToggle" class="w-full flex items-center justify-between px-4 py-3 rounded-lg hover:bg-stone-600/20">
              <div class="flex items-center gap-3">
                <i data-lucide="sparkles" class="w-[20px] h-[20px]"></i>
                <span class="text-sm font-medium font-geist">Smart Insights</span>
              </div>
              <i data-lucide="chevron-down" class="w-4 h-4 transition-transform" id="aiChevron"></i>
            </button>
            <div id="aiMenu" class="space-y-1 pl-11 mt-1 hidden">
              <button type="button" data-section="section-activity-log" class="nav-section w-full flex items-center gap-2 px-4 py-2 rounded-lg hover:bg-stone-600/20 text-xs font-geist text-left">Follows</button>
              <button type="button" data-section="section-activity-log" class="nav-section w-full flex items-center gap-2 px-4 py-2 rounded-lg hover:bg-stone-600/20 text-xs font-geist text-left">Likes</button>
              <button type="button" data-section="section-activity-log" class="nav-section w-full flex items-center gap-2 px-4 py-2 rounded-lg hover:bg-stone-600/20 text-xs font-geist text-left">Comments</button>
            </div>
          </div>
        </nav>
        <div class="flex items-center gap-3 px-6 py-4 lg:py-6 flex-shrink-0">
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium font-geist truncate">Session</p>
            <p class="text-xs text-white/60 font-geist truncate">Started {session_start}</p>
          </div>
        </div>
      </aside>

      <main class="flex-1 flex flex-col min-h-0 overflow-hidden">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between px-4 sm:px-8 py-4 lg:py-6 border-b border-white/10 gap-4 flex-shrink-0">
          <div>
            <h1 class="text-2xl font-jakarta font-medium">Engagement Overview</h1>
            <p class="text-xs text-white/60 font-geist">Reels viewed, follows, likes and comments. Refresh to see live updates.</p>
          </div>
          <div class="flex items-center gap-3">
            <button onclick="location.reload()" class="w-9 h-9 flex items-center justify-center rounded-full hover:bg-white/10" title="Refresh"><i data-lucide="refresh-cw" class="w-5 h-5"></i></button>
          </div>
        </div>

        <div id="section-overview" class="flex-1 overflow-y-auto">
          <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-6 px-4 sm:px-8 py-4 lg:py-6">
            <div class="relative bg-white/5 bg-[url({card1_bg})] bg-cover rounded-xl pt-5 pr-5 pb-5 pl-5 backdrop-blur-lg">
              <div class="flex mb-4 items-center justify-between">
                <p class="text-xs text-white/60 flex items-center gap-1 font-geist"><i data-lucide="play-circle" class="w-4 h-4"></i> Reels Viewed</p>
                <span class="text-xs text-orange-400 font-geist">This session</span>
              </div>
              <div class="text-2xl mb-6 font-jakarta font-medium">{reels_viewed}</div>
              <div class="flex items-center justify-between text-xs">
                <button type="button" class="view-details-btn underline underline-offset-2 font-geist bg-transparent border-none cursor-pointer text-inherit p-0">View Details</button>
                <button type="button" class="view-details-btn w-7 h-7 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 border-none cursor-pointer"><i data-lucide="external-link" class="w-4 h-4"></i></button>
              </div>
            </div>
            <div class="relative bg-white/5 bg-[url({card2_bg})] bg-cover rounded-xl pt-5 pr-5 pb-5 pl-5 backdrop-blur-lg">
              <div class="flex items-center justify-between mb-4">
                <p class="text-xs text-white/60 flex items-center gap-1 font-geist"><i data-lucide="user-plus" class="w-4 h-4"></i> Follows</p>
                <span class="text-xs text-orange-400 font-geist">IG: {ig_follows} · TT: {tt_follows}</span>
              </div>
              <div class="text-2xl mb-6 font-jakarta font-medium">{n_f}</div>
              <div class="flex items-center justify-between text-xs">
                <button type="button" class="view-details-btn underline underline-offset-2 font-geist bg-transparent border-none cursor-pointer text-inherit p-0">View Details</button>
                <button type="button" class="view-details-btn w-7 h-7 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 border-none cursor-pointer"><i data-lucide="external-link" class="w-4 h-4"></i></button>
              </div>
            </div>
            <div class="relative md:col-span-2 xl:col-span-1 bg-white/5 bg-[url({card3_bg})] bg-cover rounded-xl pt-5 pr-5 pb-5 pl-5 backdrop-blur-lg">
              <div class="flex items-center justify-between mb-4">
                <p class="text-xs text-white/60 flex items-center gap-1 font-geist"><i data-lucide="message-circle" class="w-4 h-4"></i> Likes &amp; Comments</p>
                <span class="text-xs text-orange-400 font-geist">{n_l} likes · {n_c} comments</span>
              </div>
              <div class="text-2xl mb-6 font-jakarta font-medium">{n_l + n_c}</div>
              <div class="flex items-center justify-between text-xs">
                <button type="button" class="view-details-btn underline underline-offset-2 font-geist bg-transparent border-none cursor-pointer text-inherit p-0">View Details</button>
                <button type="button" class="view-details-btn w-7 h-7 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 border-none cursor-pointer"><i data-lucide="external-link" class="w-4 h-4"></i></button>
              </div>
              <p class="text-xs text-white/60 font-geist mt-1">Comment likes: {comment_likes}</p>
            </div>
          </div>

          <div id="section-charts" class="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 px-4 sm:px-8">
            <div class="bg-white/5 backdrop-blur-lg rounded-xl p-5 flex flex-col">
              <div class="flex items-center justify-between mb-4">
                <p class="text-sm font-medium flex items-center gap-2 font-geist"><i data-lucide="eye" class="w-5 h-5"></i> Views</p>
              </div>
              <div class="flex-1 min-h-[180px] h-[220px]"><canvas id="viewsChart"></canvas></div>
              <div class="flex justify-end mt-4">
                <span class="text-xs px-3 py-1 rounded-full bg-orange-500/20 text-orange-400 font-geist">Duration: {duration}</span>
              </div>
            </div>
            <div class="bg-white/5 backdrop-blur-lg rounded-xl p-5 flex flex-col">
              <div class="flex items-center justify-between mb-4">
                <p class="text-sm font-medium flex items-center gap-2 font-geist"><i data-lucide="target" class="w-5 h-5"></i> Engagement</p>
              </div>
              <div class="flex-1 min-h-[180px] h-[220px]"><canvas id="budgetChart"></canvas></div>
            </div>
          </div>

          <div id="activity-log" class="px-4 sm:px-8 py-4 lg:py-6">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-2">
              <h2 class="text-lg font-semibold font-geist">Activity Log</h2>
              <button class="flex items-center gap-1 text-xs hover:underline font-geist">Filters <i data-lucide="filter" class="w-3 h-3"></i></button>
            </div>
            <div class="overflow-x-auto rounded-lg border border-white/10">
              <table class="min-w-full text-xs">
                <thead class="bg-white/5">
                  <tr>
                    <th class="px-4 py-3 text-left font-medium font-geist">Action</th>
                    <th class="px-4 py-3 text-left font-medium font-geist">Date</th>
                    <th class="px-4 py-3 text-left font-medium font-geist">Who / Comment</th>
                    <th class="px-4 py-3 text-left font-medium font-geist">Platform</th>
                    <th class="px-4 py-3 text-left font-medium font-geist">Link</th>
                  </tr>
                </thead>
                <tbody class="">{activity_rows}</tbody>
              </table>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>

  <script>
    window.addEventListener('load', function() {{
      if (typeof lucide !== 'undefined') lucide.createIcons();
      var scrollContainer = document.getElementById('section-overview');
      function scrollToSection(id) {{
        var el = document.getElementById(id);
        if (!el || !scrollContainer) return;
        if (id === 'section-overview') {{
          scrollContainer.scrollTop = 0;
        }} else {{
          var diff = el.getBoundingClientRect().top - scrollContainer.getBoundingClientRect().top;
          scrollContainer.scrollBy({{ top: diff - 20, behavior: 'smooth' }});
        }}
      }}
      document.querySelectorAll('.nav-section').forEach(function(btn) {{
        btn.addEventListener('click', function() {{
          scrollToSection(this.getAttribute('data-section'));
        }});
      }});
      document.getElementById('app').addEventListener('click', function(ev) {{
        var btn = ev.target.closest('.view-details-btn');
        if (btn) {{
          ev.preventDefault();
          ev.stopPropagation();
          scrollToSection('activity-log');
        }}
      }});
    }});
    document.getElementById('aiToggle').addEventListener('click', function() {{
      var menu = document.getElementById('aiMenu');
      var chevron = document.getElementById('aiChevron');
      menu.classList.toggle('hidden');
      chevron.classList.toggle('rotate-180');
    }});

    var data = {chart_data};
    var ctx1 = document.getElementById('viewsChart').getContext('2d');
    new Chart(ctx1, {{
      type: 'line',
      data: {{
        labels: data.security_labels,
        datasets: [{{
          label: 'Reels viewed',
          data: data.views_data,
          borderColor: '#8b5cf6',
          backgroundColor: 'rgba(139, 92, 246, 0.1)',
          tension: 0.4,
          fill: true,
          pointBackgroundColor: '#8b5cf6',
          pointBorderColor: '#ffffff',
          pointBorderWidth: 2,
          pointRadius: 4
        }}]
      }},
      options: {{
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
          x: {{ grid: {{ color: 'rgba(255, 255, 255, 0.1)' }}, ticks: {{ color: 'rgba(255, 255, 255, 0.6)', font: {{ size: 10 }} }} }},
          y: {{ grid: {{ color: 'rgba(255, 255, 255, 0.1)' }}, ticks: {{ color: 'rgba(255, 255, 255, 0.6)', font: {{ size: 10 }} }}, beginAtZero: true }}
        }},
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ intersect: false, mode: 'index' }}
      }}
    }});
    var ctx2 = document.getElementById('budgetChart').getContext('2d');
    new Chart(ctx2, {{
      type: 'line',
      data: {{
        labels: data.budget_labels,
        datasets: [
          {{ label: 'Follows', data: data.actual_data, borderColor: '#8b5cf6', backgroundColor: 'rgba(139, 92, 246, 0.1)', tension: 0.4, fill: false, pointBackgroundColor: '#8b5cf6', pointBorderColor: '#ffffff', pointBorderWidth: 2, pointRadius: 4 }},
          {{ label: 'Likes & Comments', data: data.target_data, borderColor: '#ec4899', backgroundColor: 'rgba(236, 72, 153, 0.1)', tension: 0.4, fill: false, pointBackgroundColor: '#ec4899', pointBorderColor: '#ffffff', pointBorderWidth: 2, pointRadius: 4, borderDash: [5, 5] }}
        ]
      }},
      options: {{
        plugins: {{ legend: {{ display: true, position: 'top', labels: {{ color: 'rgba(255, 255, 255, 0.8)', font: {{ size: 11 }}, usePointStyle: true, pointStyle: 'line' }} }} }},
        scales: {{
          x: {{ grid: {{ color: 'rgba(255, 255, 255, 0.1)' }}, ticks: {{ color: 'rgba(255, 255, 255, 0.6)', font: {{ size: 10 }} }} }},
          y: {{ grid: {{ color: 'rgba(255, 255, 255, 0.1)' }}, ticks: {{ color: 'rgba(255, 255, 255, 0.6)', font: {{ size: 10 }} }}, beginAtZero: true }}
        }},
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ intersect: false, mode: 'index' }}
      }}
    }});
  </script>
</body>
</html>"""

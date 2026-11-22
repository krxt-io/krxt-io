"""Refresh profile artwork from the public contribution calendar (Python 3.10+)."""
from collections import Counter
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
HANDLE = "krxt-io"


class Calendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}
        self.tips = {}
        self.current = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "td" and a.get("data-date") and a.get("id"):
            self.days[a["id"]] = date.fromisoformat(a["data-date"])
        elif tag == "tool-tip":
            self.current = a.get("for")

    def handle_data(self, text):
        if self.current:
            self.tips[self.current] = self.tips.get(self.current, "") + text

    def handle_endtag(self, tag):
        if tag == "tool-tip":
            self.current = None

    def counts(self):
        result = {}
        for key, day in self.days.items():
            match = re.match(r"\s*(No|[\d,]+) contributions? on ", self.tips.get(key, ""), re.I)
            if not match:
                raise ValueError(f"Missing public contribution count for {day}")
            value = match[1].replace(",", "")
            result[day] = 0 if value.lower() == "no" else int(value)
        if len(result) < 360 or (max(result) - min(result)).days + 1 != len(result):
            raise ValueError("The calendar is incomplete.")
        return result


def text(x, y, label, size=17, color="#c4b0d5", bold=False):
    weight = 700 if bold else 400
    return f'<text x="{x}" y="{y}" font-family="system-ui,sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}">{label}</text>'


def svg(height, title, shapes):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" viewBox="0 0 960 {height}" role="img">'
            f'<title>{title}</title><rect width="960" height="{height}" rx="12" fill="#191322"/>'+ "".join(shapes) + "</svg>\n")


def metrics(counts):
    latest = max(counts)
    runs = []
    run = 0
    for d in sorted(counts):
        run = run + 1 if counts[d] else 0
        runs.append(run)
    current = runs[-1] or runs[-2]
    vals = (("Contributions", sum(counts.values())), ("Active days",sum(v>0 for v in counts.values())),
            ("Current streak", f"{current}d"), ("Longest streak",f"{max(runs)}d"))
    shapes=[text(28,36,"PUBLIC CONTRIBUTION HISTORY",17,"#ba9cdb",True),
            text(710,36,latest.strftime("Through %d %b %Y"),16)]
    for i,(label,value) in enumerate(vals):
        x=28+i*234
        shapes.extend([text(x,101,value,44,"#f0e6fc",True),text(x,136,label,21)])
    return svg(164,"Contribution totals and streaks for the displayed calendar",shapes)


def calendar(counts):
    first=min(counts)
    start=first-timedelta(days=(first.weekday()+1)%7)
    peak=max(counts.values())
    shapes=[text(27,39,"Contribution skyline",26,"#f1e7fb",True),
            text(27,67,"Each tile is one day. Taller columns mark more contributions.",17)]
    labels=set()
    for day,n in sorted(counts.items()):
        days=(day-start).days
        week,row=divmod(days,7)
        x=83+week*15.5-row*6.3
        y=169+row*5.5-week*0.58
        height=2 if not n else 8+44*(n/max(peak,1))**0.6
        top=y-height
        colors=("#352b42","#282133","#473952") if not n else ("#9070b9","#63508c","#dfb7ff")
        def quad(points,color):
            p=" ".join(f"{a:.1f},{b:.1f}" for a,b in points)
            return f'<polygon points="{p}" fill="{color}"/>'
        shapes.extend([quad([(x,top),(x+14,top-.5),(x+8.5,top+4.3),(x-5.5,top+4.8)],colors[2]),
                       quad([(x-5.5,top+4.8),(x+8.5,top+4.3),(x+8.5,y+4.3),(x-5.5,y+4.8)],colors[0]),
                       quad([(x+8.5,top+4.3),(x+14,top-.5),(x+14,y-.5),(x+8.5,y+4.3)],colors[1])])
        if day.day==1 and day.month%2==0 and week not in labels:
            labels.add(week)
            shapes.append(text(x-24,237,day.strftime("%b"),15))
    return svg(255,"Isometric daily contribution calendar",shapes)


def snake(counts):
    start=min(counts)
    start-=timedelta(days=(start.weekday()+1)%7)
    shapes=[text(27,34,"Contribution snake",23,"#f1e7fb",True)]
    occupied=[]
    for day,n in sorted(counts.items()):
        col,row=divmod((day-start).days,7)
        x,y=31+17*col,50+15*row
        fill="#c0a0ed" if n else "#352c40"
        shapes.append(f'<rect x="{x}" y="{y}" width="13" height="12" rx="3" fill="{fill}"/>')
        if n:
            occupied.append((col,row))
    route=[(0,3)]
    for x,y in [*occupied,(52,3),*reversed(occupied),(0,3)]:
        a,b=route[-1]
        while a!=x or b!=y:
            if a!=x: a += 1 if a<x else -1
            else: b += 1 if b<y else -1
            route.append((a,b))
    path="M"+" L".join(f"{37+17*x},{56+15*y}" for x,y in route)
    for index,color in enumerate(("#78649a","#9d81bb","#cba5cd","#ffc389")):
        shapes.append(f'<circle r="5.7" fill="{color}"><animateMotion dur="18s" begin="-{index*.15}s" repeatCount="indefinite" path="{path}"/></circle>')
    return svg(170,"Animated snake visiting active dates in the contribution grid",shapes)


if __name__=="__main__":
    if len(sys.argv)==2:
        page=Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        req=Request(f"https://github.com/users/{HANDLE}/contributions",headers={"User-Agent":"public-profile-artwork","Accept-Language":"en-US"})
        with urlopen(req,timeout=30) as response:
            page=response.read().decode("utf-8")
    parser=Calendar()
    parser.feed(page)
    counts=parser.counts()
    for name,render in (("activity",metrics),("skyline",calendar),("snake",snake)):
        (ASSETS/f"{name}.svg").write_text(render(counts),encoding="utf-8")

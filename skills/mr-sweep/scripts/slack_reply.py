#!/usr/bin/env python3
"""Group a sweep's posted reviews into one Slack thread reply per channel post.

Usage: slack_reply.py <channel.txt> <reviews.json>

<channel.txt> is the saved read of #collective-mrs. <reviews.json> is the sweep's `reviews` list
(url, repo, iid, verdict, comments, status). Each posted review is matched to the newest post that
links its MR, so a bump gets the reply. Prints JSON: a list of {thread_ts, text}, one per post.
Reviews with no post in the read are listed under `unmatched` and get no reply.
"""
import json, sys
from pathlib import Path

from candidates import mentions, parse

VERDICTS = {
    "APPROVE": "✅ approved",
    "CHANGES": "🔁 changes requested",
    "COMMENTS": "💬 comments",
}


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def line(review):
    verdict = VERDICTS.get(review["verdict"], review["verdict"].lower())
    detail = f", {plural(review['comments'], 'comment')}" if review.get("comments") else ""
    return f"• [{review['repo']}!{review['iid']}]({review['url']}): {verdict}{detail}"


def replies(messages, reviews):
    newest_post = {m.url: m.posted_ts for m in mentions(messages)}
    threads, unmatched = {}, []
    for r in reviews:
        if r.get("status") != "posted":
            continue
        ts = newest_post.get(r["url"])
        if ts is None:
            unmatched.append(r["url"])
        else:
            threads.setdefault(ts, []).append(r)
    out = [
        {"thread_ts": ts, "text": "\n".join(["🧑‍🌾 Mr. Sweep has been through these:", *map(line, rs)])}
        for ts, rs in sorted(threads.items())
    ]
    return {"replies": out, "unmatched": unmatched}


if __name__ == "__main__":
    channel, reviews = sys.argv[1:3]
    result = replies(parse(Path(channel).read_text()), json.loads(Path(reviews).read_text()))
    print(json.dumps(result, indent=2, ensure_ascii=False))

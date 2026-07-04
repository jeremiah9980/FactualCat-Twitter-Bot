#!/usr/bin/env python3
"""Content bot for scheduling SFW promotional posts.

Selects a post from content/posts.json and surfaces it. When X/Twitter API
credentials are provided as environment variables the post is sent to X as well;
otherwise it is printed and written to the GitHub Actions job summary so it can
be copied and posted manually.

Only SFW teaser content belongs in content/posts.json — X's rules prohibit
posting explicit material via the API, and doing so risks the account and its
API access.
"""
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path

POSTS_FILE = Path(__file__).parent / "content" / "posts.json"
TWEET_LIMIT = 280


def load_posts():
    with open(POSTS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    posts = data.get("posts", [])
    if not posts:
        raise SystemExit("No posts found in content/posts.json")
    return posts


def select_post(posts):
    if os.environ.get("RANDOM_POST", "").lower() in ("1", "true", "yes"):
        return random.choice(posts)
    # Deterministic daily rotation: a given day always maps to the same post.
    day_of_year = datetime.now(timezone.utc).timetuple().tm_yday
    return posts[day_of_year % len(posts)]


def build_message(post):
    text = post.get("text", "").strip()
    hashtags = post.get("hashtags", [])
    tag_line = " ".join(hashtags).strip()
    message = f"{text}\n\n{tag_line}".strip() if tag_line else text
    if len(message) > TWEET_LIMIT:
        # Drop the hashtags first, then hard-trim, to stay within the limit.
        message = text[:TWEET_LIMIT].rstrip()
    return message


def connect_to_oauth(consumer_key, consumer_secret, access_token, access_token_secret):
    from requests_oauthlib import OAuth1
    return OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)


def post_to_x(message):
    keys = (
        os.environ.get("CONSUMER_KEY"),
        os.environ.get("CONSUMER_SECRET"),
        os.environ.get("ACCESS_TOKEN"),
        os.environ.get("ACCESS_TOKEN_SECRET"),
    )
    if not all(keys):
        return False
    import requests
    auth = connect_to_oauth(*keys)
    resp = requests.post(
        "https://api.twitter.com/2/tweets",
        json={"text": message},
        auth=auth,
    )
    if resp.status_code not in (200, 201):
        raise SystemExit(f"Failed to post to X: {resp.status_code} {resp.text}")
    print("Posted to X successfully.")
    return True


def write_summary(message, posted):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    status = (
        "✅ Posted to X automatically."
        if posted
        else "📋 No X API credentials found — copy the post below and share it manually."
    )
    with open(summary_path, "a", encoding="utf-8") as f:
        f.write("## Today's post\n\n")
        f.write(status + "\n\n")
        f.write("```\n" + message + "\n```\n")


def main():
    posts = load_posts()
    post = select_post(posts)
    message = build_message(post)
    print(message)
    posted = post_to_x(message)
    write_summary(message, posted)


if __name__ == "__main__":
    main()

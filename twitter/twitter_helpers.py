import os

import tweepy

PROGRAM_URL = "https://2024.pycon.de/program/"


def build_session_tweet(chosen):
    """Build session tweet text from the chose pandas serie"""
    the_text = chosen["Q: Abstract as a tweet (X) or toot (Mastodon)"]
    the_link = f"{PROGRAM_URL}{chosen['Submission']}/"
    the_handles = " ".join([f"@{cleanhandle(x)}" for x in chosen["Q: X / Twitter handle"] if isinstance(x, str)])

    tweet_len = len(f"{the_text} {the_handles} at #PyConDE #PyDataBerlin")
    if tweet_len > 200:
        # shorten text if needed
        the_text = the_text[: 200 - tweet_len + 200] + "…"

    the_tweet = f"{the_text} {the_handles} at #PyConDE #PyDataBerlin\n{the_link}"
    return the_tweet


def build_sponsor_tweet(chosen):
    text = f"""Sponsors help us to make our conference happen. Thanks to our sponsor {chosen["sponsor_name"]}"""
    return text


def get_tweepy_client():
    """Get tweepy client object to send tweet"""
    consumer_key = os.environ["TWITTER_CONSUMER_KEY"]
    consumer_secret = os.environ["TWITTER_CONSUMER_SECRET"]
    access_token = os.environ["TWITTER_ACCESS_TOKEN"]
    access_token_secret = os.environ["TWITTER_ACCESS_TOKEN_SECRET"]
    client = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )
    return client


def get_tweepy_api():
    """Get tweepy api object to upload medias"""
    consumer_key = os.environ["TWITTER_CONSUMER_KEY"]
    consumer_secret = os.environ["TWITTER_CONSUMER_SECRET"]
    access_token = os.environ["TWITTER_ACCESS_TOKEN"]
    access_token_secret = os.environ["TWITTER_ACCESS_TOKEN_SECRET"]
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)
    return api


def send_tweet(the_tweet, media_path=None):
    client = get_tweepy_client()
    api = get_tweepy_api()
    if media_path is not None:
        media = api.media_upload(media_path)
        media_ids = [media.media_id]
    else:
        media_ids = None
    tweet = client.create_tweet(
        text=the_tweet,
        media_ids=media_ids,
    )
    return tweet


def cleanhandle(handle):
    if "/" in handle:
        return handle.lower().strip().split("/")[-1]
    else:
        return handle.lower().replace("@", "").strip()

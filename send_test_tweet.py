from twitter_poster import post_tweet

result = post_tweet(
    "Kapernicus Picks system test — ignore this tweet")

if result:
    print(f"Success — tweet ID: {result}")
else:
    print("Failed — check credentials")

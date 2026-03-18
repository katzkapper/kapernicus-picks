import os
import time
import hmac
import hashlib
import base64
import urllib.parse
import uuid
import requests
import json

X_API_KEY       = os.environ.get("X_API_KEY", "")
X_API_SECRET    = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN  = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET", "")

print("\n" + "="*50)
print("  X CREDENTIAL DIAGNOSTIC")
print("="*50)

# Check if credentials are present
print(f"\n  X_API_KEY:       "
      f"{'SET' if X_API_KEY else 'MISSING'} "
      f"({len(X_API_KEY)} chars)")
print(f"  X_API_SECRET:    "
      f"{'SET' if X_API_SECRET else 'MISSING'} "
      f"({len(X_API_SECRET)} chars)")
print(f"  X_ACCESS_TOKEN:  "
      f"{'SET' if X_ACCESS_TOKEN else 'MISSING'} "
      f"({len(X_ACCESS_TOKEN)} chars)")
print(f"  X_ACCESS_SECRET: "
      f"{'SET' if X_ACCESS_SECRET else 'MISSING'} "
      f"({len(X_ACCESS_SECRET)} chars)")

if not all([X_API_KEY, X_API_SECRET,
            X_ACCESS_TOKEN, X_ACCESS_SECRET]):
    print("\n  ERROR: One or more credentials missing.")
    print("  Add them to Replit Secrets and try again.")
    exit()

print("\n  All credentials present.")
print("  Testing API connection...\n")

# Check Access Token format
# Should be: numbers-letters
# e.g. 1234567890-abcdefghij
if "-" not in X_ACCESS_TOKEN:
    print("  WARNING: Access Token format looks wrong.")
    print("  It should contain a dash (-)")
    print("  e.g. 1234567890-ABCdefGHIjkl")
    print("  Current value starts with: "
          f"{X_ACCESS_TOKEN[:8]}...")
else:
    print("  Access Token format: OK")

# Try to verify credentials using
# Twitter API v1.1 account/verify_credentials
# This is a lightweight check
def build_oauth(method, url):
    params = {
        "oauth_consumer_key":     X_API_KEY,
        "oauth_nonce":            uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        str(int(time.time())),
        "oauth_token":            X_ACCESS_TOKEN,
        "oauth_version":          "1.0",
    }

    def encode(s):
        return urllib.parse.quote(str(s), safe="")

    sorted_params = sorted(params.items())
    param_string  = "&".join(
        f"{encode(k)}={encode(v)}"
        for k, v in sorted_params
    )

    base = "&".join([
        method.upper(),
        encode(url),
        encode(param_string)
    ])

    key = (f"{encode(X_API_SECRET)}"
           f"&{encode(X_ACCESS_SECRET)}")

    sig = base64.b64encode(
        hmac.new(
            key.encode(),
            base.encode(),
            hashlib.sha1
        ).digest()
    ).decode()

    params["oauth_signature"] = sig

    return "OAuth " + ", ".join(
        f'{encode(k)}="{encode(v)}"'
        for k, v in sorted(params.items())
    )

# Test 1 — verify credentials endpoint
print("\n  Test 1: Verifying credentials...")
verify_url = (
    "https://api.twitter.com/1.1/"
    "account/verify_credentials.json"
)
header = build_oauth("GET", verify_url)

try:
    resp = requests.get(
        verify_url,
        headers={"Authorization": header},
        timeout=10
    )
    print(f"  Status: {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        print(f"  ✓ Credentials VALID")
        print(f"  Account: @{data.get('screen_name')}")
        print(f"  Name: {data.get('name')}")
    elif resp.status_code == 401:
        data = resp.json()
        errors = data.get("errors", [])
        for e in errors:
            print(f"  ✗ Error {e.get('code')}: "
                  f"{e.get('message')}")
        print("\n  DIAGNOSIS:")
        print("  Error 32 = Bad credentials "
              "— wrong key/secret")
        print("  Error 89 = Invalid/expired token "
              "— regenerate access token")
        print("  Error 135 = Timestamp too far off "
              "— clock sync issue")
    elif resp.status_code == 403:
        print("  ✗ 403 Forbidden — app may not have")
        print("  Read/Write permissions enabled")
    else:
        print(f"  Unexpected status: {resp.status_code}")
        print(f"  Response: {resp.text[:200]}")

except Exception as e:
    print(f"  ✗ Connection error: {e}")

# Test 2 — try posting a test tweet
print("\n  Test 2: Attempting test tweet post...")

def build_oauth_post(method, url):
    params = {
        "oauth_consumer_key":     X_API_KEY,
        "oauth_nonce":            uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        str(int(time.time())),
        "oauth_token":            X_ACCESS_TOKEN,
        "oauth_version":          "1.0",
    }

    def encode(s):
        return urllib.parse.quote(str(s), safe="")

    sorted_params = sorted(params.items())
    param_string  = "&".join(
        f"{encode(k)}={encode(v)}"
        for k, v in sorted_params
    )

    base = "&".join([
        method.upper(),
        encode(url),
        encode(param_string)
    ])

    key = (f"{encode(X_API_SECRET)}"
           f"&{encode(X_ACCESS_SECRET)}")

    sig = base64.b64encode(
        hmac.new(
            key.encode(),
            base.encode(),
            hashlib.sha1
        ).digest()
    ).decode()

    params["oauth_signature"] = sig

    return "OAuth " + ", ".join(
        f'{encode(k)}="{encode(v)}"'
        for k, v in sorted(params.items())
    )

tweet_url = "https://api.twitter.com/2/tweets"
header2   = build_oauth_post("POST", tweet_url)

try:
    resp2 = requests.post(
        tweet_url,
        headers={
            "Authorization":  header2,
            "Content-Type":   "application/json"
        },
        json={"text": "Kapernicus Picks — "
                      "credential test tweet"},
        timeout=10
    )
    print(f"  Status: {resp2.status_code}")

    if resp2.status_code in [200, 201]:
        data2    = resp2.json()
        tweet_id = data2.get("data",{}).get("id","")
        print(f"  ✓ Tweet posted successfully!")
        print(f"  Tweet ID: {tweet_id}")
        print(f"  Check your X account to confirm.")
    elif resp2.status_code == 401:
        print(f"  ✗ 401 Unauthorized")
        print(f"  Response: {resp2.text[:300]}")
    elif resp2.status_code == 403:
        print(f"  ✗ 403 Forbidden")
        print(f"  Response: {resp2.text[:300]}")
        print("\n  This usually means:")
        print("  - App needs Read+Write permissions")
        print("  - Or your developer account needs")
        print("    basic access tier approval")
    else:
        print(f"  Status {resp2.status_code}")
        print(f"  Response: {resp2.text[:300]}")

except Exception as e:
    print(f"  ✗ Error: {e}")

print("\n" + "="*50 + "\n")

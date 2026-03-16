import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_ADDRESS      = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

# ─────────────────────────────────────────────
# CHANGE THIS to the email you want to test with
# ─────────────────────────────────────────────
TEST_RECIPIENT = "jrkatz123@gmail.com"

print("\n" + "="*50)
print("   KAPERNICUS PICKS — EMAIL TEST")
print("="*50)

if not GMAIL_ADDRESS:
    print("ERROR: GMAIL_ADDRESS not found in Secrets")
    exit()

if not GMAIL_APP_PASSWORD:
    print("ERROR: GMAIL_APP_PASSWORD not found in Secrets")
    exit()

print(f"\nFrom:    {GMAIL_ADDRESS}")
print(f"To:      {TEST_RECIPIENT}")
print(f"Method:  Trying SSL port 465 first...")

html = """
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#F4F6F9;
             font-family:Arial,sans-serif;">
<div style="max-width:600px;margin:20px auto;
            background:white;border-radius:8px;
            overflow:hidden;
            box-shadow:0 2px 8px rgba(0,0,0,0.1);">

    <div style="background:#0D2240;padding:24px;
                text-align:center;">
        <div style="font-size:11px;color:#C8A951;
                    letter-spacing:3px;margin-bottom:8px;">
            KAPERNICUS PICKS
        </div>
        <div style="font-size:22px;font-weight:bold;
                    color:white;">
            Email Test Successful
        </div>
        <div style="font-size:13px;color:#aaa;
                    margin-top:6px;">
            Your betting analyzer is connected and ready
        </div>
    </div>

    <div style="padding:24px;">

        <div style="background:#1A7A3E;padding:16px;
                    border-radius:6px;text-align:center;
                    margin:16px 0;">
            <div style="font-size:20px;font-weight:bold;
                        color:white;margin:6px 0;">
                System Online
            </div>
            <div style="font-size:14px;color:#90EE90;">
                Gmail credentials verified successfully
            </div>
        </div>

        <table style="width:100%;border-collapse:collapse;
                      margin:16px 0;font-size:13px;">
            <thead>
                <tr style="background:#0D2240;color:white;">
                    <th style="padding:10px;text-align:left;">
                        Component</th>
                    <th style="padding:10px;text-align:center;">
                        Status</th>
                </tr>
            </thead>
            <tbody>
                <tr style="background:#D4EDDA;">
                    <td style="padding:10px;font-weight:bold;">
                        Gmail Connection</td>
                    <td style="padding:10px;text-align:center;
                               color:#1A7A3E;font-weight:bold;">
                        CONNECTED</td>
                </tr>
                <tr style="background:#D4EDDA;">
                    <td style="padding:10px;font-weight:bold;">
                        App Password</td>
                    <td style="padding:10px;text-align:center;
                               color:#1A7A3E;font-weight:bold;">
                        VERIFIED</td>
                </tr>
                <tr style="background:#D4EDDA;">
                    <td style="padding:10px;font-weight:bold;">
                        HTML Email Rendering</td>
                    <td style="padding:10px;text-align:center;
                               color:#1A7A3E;font-weight:bold;">
                        WORKING</td>
                </tr>
                <tr style="background:#D4EDDA;">
                    <td style="padding:10px;font-weight:bold;">
                        Distribution List</td>
                    <td style="padding:10px;text-align:center;
                               color:#1A7A3E;font-weight:bold;">
                        READY</td>
                </tr>
            </tbody>
        </table>

        <div style="background:#F8F9FA;border-radius:6px;
                    padding:12px;text-align:center;
                    margin:12px 0;">
            <span style="font-size:12px;color:#666;">
                Confidence Tiers Active: </span>
            <span style="font-size:13px;font-weight:bold;
                         color:#0D2240;">
                57-61% = 1u | 62%+ = 1.5u | R20+R32 = 2u
            </span>
        </div>

        <div style="font-size:11px;color:#999;
                    text-align:center;margin-top:20px;
                    padding-top:16px;
                    border-top:1px solid #eee;">
            Kapernicus Picks — 32-Rule Model v7<br>
            For entertainment and informational
            purposes only.<br>
            Gambling involves risk.
            Problem Gambling Helpline: 1-800-GAMBLER.
        </div>

    </div>
</div>
</body>
</html>
"""

msg = MIMEMultipart("alternative")
msg["From"]    = GMAIL_ADDRESS
msg["To"]      = TEST_RECIPIENT
msg["Subject"] = "Kapernicus Picks — Email System Test"

msg.attach(MIMEText("Email test successful. "
                    "HTML version attached.", "plain"))
msg.attach(MIMEText(html, "html"))

# Try SSL port 465 first
sent = False

try:
    with smtplib.SMTP_SSL(
        "smtp.gmail.com", 465, timeout=15
    ) as server:
        server.ehlo()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(
            GMAIL_ADDRESS,
            TEST_RECIPIENT,
            msg.as_string()
        )
    sent = True
    print("SSL port 465: SUCCESS")

except Exception as e:
    print(f"SSL port 465 failed: {e}")
    print("Trying TLS port 587...")

    try:
        with smtplib.SMTP(
            "smtp.gmail.com", 587, timeout=15
        ) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(
                GMAIL_ADDRESS,
                TEST_RECIPIENT,
                msg.as_string()
            )
        sent = True
        print("TLS port 587: SUCCESS")

    except Exception as e2:
        print(f"TLS port 587 failed: {e2}")

print("\n" + "="*50)
if sent:
    print(f"Email sent to {TEST_RECIPIENT}")
    print("Check your inbox — may take 1-2 minutes.")
    print("Check spam folder if not in inbox.")
else:
    print("Both methods failed.")
    print("Fix: Go to sendgrid.com, create a free")
    print("account, get an API key, add it to Replit")
    print("Secrets as SENDGRID_API_KEY and let me know.")
print("="*50 + "\n")

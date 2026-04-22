# External software references

## Payment

- **Mollie Payments API**
  - Purpose: Dutch-native payment provider (iDEAL, creditcard, Bancontact)
  - Link: https://docs.mollie.com/reference/v2/payments-api/create-payment
  - Licence: commercial SaaS
  - Notes: used for one-off report purchases; test mode available with `test_...` API key

## Email

- **Resend**
  - Purpose: transactional email for report delivery
  - Link: https://resend.com/docs/api-reference/emails/send-email
  - Licence: commercial SaaS (free tier available)
  - Notes: called via httpx (no extra SDK); falls back to stdout logging when `RESEND_API_KEY` is unset

## Token signing

- **itsdangerous** ≥ 2.2
  - Purpose: HMAC-signed, time-limited access tokens for paid reports
  - Link: https://itsdangerous.palletsprojects.com/
  - Licence: BSD-3-Clause
  - Notes: uses `URLSafeTimedSerializer`; default expiry 1 year; SECRET_KEY must be set in production

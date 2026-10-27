# Collivra Test Suite

This directory contains integration test suites for the Collivra Edge Function API (`/api/v1`).

## Target Environment

The test scripts default to the deployed remote Supabase Edge Function environment:
`https://eetmsobqxlbsvcoscjnb.supabase.co/functions/v1/api/v1`

To target a local development server or staging environment, override the `COLLIVRA_BASE_URL` environment variable.

## Environment Variables (Names Only)

The following environment variables may be configured when running the test suites:

- `COLLIVRA_BASE_URL`: Base URL for the Edge Function API (e.g. `http://localhost:54321/functions/v1/api/v1` or remote URL). Defaults to the remote deployed instance.
- `COLLIVRA_TEST_PASSWORD`: Password used when generating disposable test brand accounts.
- `COLLIVRA_CREATOR_MOBILE`: Mobile number of an existing seeded/test creator for onboarding and creator-role gating tests.
- `COLLIVRA_CREATOR_PASSWORD`: Password for the test creator account.

> **Security Note**: No real secrets, production API keys, database passwords, or persistent session tokens are stored in these test scripts. Brand tests create disposable accounts dynamically, and creator tests utilize seeded test credentials.

## Test Scripts Overview

| Script | Area | Description |
|--------|------|-------------|
| `tests/auth.sh` | Brand Auth & OAuth | Brand signup, login, session inspection (`/auth/me`), Google OAuth (`/auth/oauth/google`), Apple OAuth (`/auth/oauth/apple`), and logout (`/auth/logout`). |
| `tests/onboarding.sh` | Creator Onboarding & KYC | Creator mobile login, presigned upload URLs, KYC ID/PAN validation, bank details, social connect stub, and onboarding submission. |
| `tests/marketplace.sh` | Discovery & Route Gating | Public endpoints (`/creators`, `/creators/suggestions`, `/creators/filters`), route gating verification (401 unauthenticated, 403 creator token), and brand access to creator details and shortlists. |
| `tests/cart.sh` | Cart & Custom Offers | Cart inspection, item additions, quantity updates, item deletions, and custom brand offer submissions. |
| `tests/campaigns.sh` | Campaigns & Bids | Campaign creation, B2 edit rules (validation, field locking when bids exist, owner 404), B2 delete rules (409 conflict when bids exist, 204 soft delete for drafts), bid submission, and bid selection. |
| `tests/orders.sh` | Orders & Escrow | Order creation, order listing and details, escrow funding (`/pay`), revision requests (`/request-changes`), deliverable approval (`/approve`), and idempotency. |
| `tests/dashboard.sh` | Dashboard & Content Library | Brand dashboard overview, onboarding todo completion, custom brand shortlists, and deliverable content library. |

## Running the Tests

Make the test scripts executable and run them via bash:

```bash
chmod +x tests/*.sh

# Run individual test suites
./tests/auth.sh
./tests/onboarding.sh
./tests/marketplace.sh
./tests/cart.sh
./tests/campaigns.sh
./tests/orders.sh
./tests/dashboard.sh
```

Or run all test suites in sequence:
```bash
for test in tests/*.sh; do
  echo ">>> Running $test..."
  bash "$test"
done
```

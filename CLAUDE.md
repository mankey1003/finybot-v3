# FinyBot — Developer Reference

## Project Overview
Monthly credit card expense tracker. Fetches PDF statements from Gmail, extracts
transactions via Gemini AI, and presents spending insights across cards and months.

---

## Architecture Summary

```
Frontend (React + Vite + TypeScript)   → Firebase Hosting
Backend  (Python FastAPI)              → Cloud Run
Database                               → Firestore (Native mode)
Auth                                   → Firebase Auth + Google OAuth2 (dual-flow)
AI                                     → Gemini 3 Flash (gemini-3-flash-preview) via Vertex AI
PDF Decrypt                            → pikepdf (libqpdf required in Dockerfile)
PDF Extract                            → pdfplumber (fallback) + Gemini (primary)
```

---

## Google Auth: Dual-Flow Design

### Why Two Flows?
- **Firebase signInWithPopup** only returns a short-lived Google access token (~1 hour).
  It does NOT return a long-lived refresh token suitable for background Gmail sync.
- Background sync (runs once a month without user interaction) requires a proper OAuth2
  refresh token obtained via `google-auth-oauthlib` with `access_type=offline`.

### Flow 1 — Firebase Auth (every login)
Used for: App authentication, protecting backend routes via ID token.

```
User → signInWithPopup(GoogleAuthProvider) → Firebase ID token
     → All backend API calls: Authorization: Bearer <firebase_id_token>
     → Backend verifies with firebase_admin.auth.verify_id_token()
```

### Flow 2 — Gmail OAuth2 (one-time per user, or on refresh token expiry)
Used for: Authorizing the backend to read Gmail on the user's behalf in the background.

```
Frontend → GET /api/auth/gmail  (user must be Firebase-authenticated)
        → Backend builds google-auth-oauthlib Flow with:
             scopes=["https://www.googleapis.com/auth/gmail.readonly"]
             access_type="offline"
             prompt="consent"           ← forces refresh token issuance
        → Redirects user to Google consent screen
        → Google redirects back to /api/auth/gmail/callback?code=...
        → Backend exchanges code for {access_token, refresh_token}
        → Encrypts refresh_token with Fernet (FERNET_KEY env var)
        → Stores encrypted token in Firestore: users/{uid}.gmailRefreshToken
        → Sets users/{uid}.gmailConnected = true
        → Redirects user back to frontend dashboard
```

### Login UX State Machine
```
App load
  └─ Not authenticated → Show "Sign in with Google" (Flow 1)
  └─ Authenticated, gmailConnected=false → Show "Connect Gmail" prompt (Flow 2)
  └─ Authenticated, gmailConnected=true  → Show Dashboard + transactions
       └─ No transactions yet → Show "Sync Now" button prominently
       └─ Has transactions   → Show transactions + "Refresh" button in header
```

---

## Secret / Credential Storage (POC)

### Current Approach (POC — Fernet symmetric encryption)

| Secret | Storage | Encryption |
|--------|---------|------------|
| Gmail refresh token | Firestore `users/{uid}.gmailRefreshToken` | Fernet (FERNET_KEY env var) |
| PDF passwords per card provider | Firestore `users/{uid}/card_providers/{id}.encryptedPassword` | Fernet (same key) |

**Fernet key** is generated once and stored as a Cloud Run environment variable `FERNET_KEY`.
Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

### ⚠️ Technical Debt — Replace Fernet with Cloud KMS (before production)

The current Fernet approach uses a single app-level key stored in an environment variable.
This means:
- All user secrets share one key — compromise of the key exposes all users.
- No key rotation audit trail.
- No per-user isolation.

**Production fix:** Replace with Cloud KMS envelope encryption:
- One KMS Key Encryption Key (KEK) per environment (not per user)
- Per-user Data Encryption Key (DEK) generated at write time, encrypted by KEK
- Store `{encrypted_dek, ciphertext}` in Firestore per user
- Decrypt path: KMS.decrypt(encrypted_dek) → Fernet(dek).decrypt(ciphertext)

Reference: https://cloud.google.com/kms/docs/envelope-encryption

---

## Gemini Model

**Model ID:** `gemini-2.0-flash-001`
**Status:** GA
**SDK:** Vertex AI (`vertexai` Python package)
**Limits:** 1M input tokens, 65K output tokens, up to 900 PDF pages per file, 50MB via Cloud Storage

```python
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig

vertexai.init(project=PROJECT_ID, location="us-central1")
model = GenerativeModel("gemini-2.0-flash-001")
```

**⚠️ Technical Debt:** Upgrade to Gemini 3 Flash once it's GA and available in your project.

---

## Firestore Data Model

```
users/{uid}
  .email, .displayName, .gmailConnected: bool, .lastSyncAt: timestamp
  .gmailRefreshToken: string (Fernet-encrypted)

users/{uid}/card_providers/{provider_id}
  .name: string                          e.g. "HDFC Credit Card"
  .emailSenderPattern: string            e.g. "@hdfcbank.com"
  .subjectKeyword: string                e.g. "credit card statement"
  .encryptedPassword: string             Fernet-encrypted PDF password

users/{uid}/statements/{statement_id}   compound: {provider_id}_{YYYY-MM}
  .cardProvider: string
  .billingMonth: string                  "YYYY-MM"
  .statementDate: timestamp
  .dueDate: timestamp
  .totalAmountDue: number
  .minPaymentDue: number
  .currency: string
  .gmailMessageId: string                idempotency key
  .status: "pending"|"processing"|"processed"|"failed"
  .errorReason: string|null
  .processedAt: timestamp

users/{uid}/transactions/{tx_id}        auto-ID
  .cardProvider: string
  .statementId: string
  .date: timestamp                       purchase date — primary sort key
  .billingMonth: string                  "YYYY-MM" — for month filter queries
  .description: string
  .amount: number
  .currency: string
  .debitOrCredit: "debit"|"credit"
  .category: string                      Gemini-inferred
  .createdAt: timestamp

jobs/{job_id}                            ephemeral — TTL 24h
  .uid: string
  .status: "pending"|"processing"|"done"|"failed"
  .triggeredAt: timestamp
  .completedAt: timestamp
  .results: { processed: int, failed: int, errors: string[] }
```

**Composite indexes required:**
- `transactions`: (uid, date DESC) — for infinite scroll
- `transactions`: (uid, billingMonth, date DESC) — for monthly filter
- `statements`: (uid, billingMonth DESC) — for reports

---

## API Endpoints

```
Auth
  GET  /api/auth/gmail              → Initiates Gmail OAuth2 flow (Flow 2)
  GET  /api/auth/gmail/callback     → Handles OAuth callback, stores refresh token

Cards
  GET  /api/cards                   → List user's card providers
  POST /api/cards                   → Add card provider + PDF password
  PUT  /api/cards/{id}/password     → Update PDF password for a provider
  DEL  /api/cards/{id}              → Remove card provider

Sync
  POST /api/sync                    → Trigger Gmail sync (manual "Refresh" button)
  GET  /api/sync/status/{job_id}    → Poll sync job status

Data
  GET  /api/transactions            → Paginated; params: limit, cursor, month, card
  GET  /api/statements              → All statement summaries
  GET  /api/statements/{month}      → Single month report across cards

Insights
  GET  /api/insights                → params: months (comma-sep YYYY-MM list)
                                      Gemini-powered spend comparison narrative

Logging
  POST /api/log-error               → Frontend error sink
```

---

## PDF Processing Pipeline

```
1. Gmail API: search "has:attachment filename:pdf {subjectKeyword}"
   → for each card provider's emailSenderPattern
   → skip if gmailMessageId already exists in statements (idempotency)

2. Download attachment bytes (base64url-decode from Gmail API response)

3. pikepdf.open(io.BytesIO(pdf_bytes), password=fernet_decrypt(encryptedPassword))
   → PasswordError → set statement.status="failed", errorReason="wrong_password"
   → Prompt user to update password via PUT /api/cards/{id}/password

4. pdfplumber sanity check: can we extract any text?
   → If blank/scanned: set errorReason="scanned_pdf_unsupported" (OCR is future work)

5. Gemini 3 Flash (Vertex AI):
   pdf_part = Part.from_data(decrypted_bytes, mime_type="application/pdf")
   response_schema enforces structured JSON output

6. Validation: abs(sum(debit amounts) - statement.totalAmountDue) < tolerance
   → Log warning if mismatch; still store data

7. Batch write to Firestore (500 docs per batch)
   → statement doc (status="processed")
   → N transaction docs

8. Update job doc with results
```

---

## Error Logging

- **Backend:** `google-cloud-logging` handler attached to Python `logging` module
  → All `logger.error(...)` calls emit structured JSON to Cloud Logging
  → Cloud Error Reporting auto-captures unhandled exceptions from Cloud Run stderr
- **PDF failures:** Logged with `uid`, `provider`, `gmailMessageId`, `errorReason`
- **Gemini failures:** Log raw response text before JSON parse; fall back to pdfplumber regex
- **Frontend:** `window.onerror` + unhandled promise rejections → POST /api/log-error

---

## Backend Project Structure

```
backend/
├── app/
│   ├── main.py                  FastAPI app init, middleware, router registration
│   ├── config.py                Env vars (PROJECT_ID, FERNET_KEY, OAUTH_CLIENT_*)
│   ├── routers/
│   │   ├── auth.py              /api/auth/gmail, /api/auth/gmail/callback
│   │   ├── cards.py             /api/cards CRUD
│   │   ├── sync.py              /api/sync, /api/sync/status/{job_id}
│   │   ├── transactions.py      /api/transactions
│   │   ├── statements.py        /api/statements
│   │   └── insights.py          /api/insights
│   ├── services/
│   │   ├── auth_service.py      Firebase token verification, Fernet encrypt/decrypt
│   │   ├── gmail_service.py     Gmail API: list messages, download attachments
│   │   ├── pdf_service.py       pikepdf decrypt, pdfplumber extract
│   │   ├── gemini_service.py    Vertex AI Gemini 3 Flash calls, response schema
│   │   └── firestore_service.py Firestore read/write helpers
│   ├── models/
│   │   ├── statement.py         Pydantic models for statement + Gemini schema
│   │   └── transaction.py       Pydantic models for transaction
│   └── middleware/
│       └── auth_middleware.py   Firebase ID token verification on protected routes
├── Dockerfile
└── requirements.txt
```

---

## Frontend Project Structure

```
frontend/
├── src/
│   ├── pages/
│   │   ├── Login.tsx            "Sign in with Google" — Flow 1
│   │   ├── ConnectGmail.tsx     "Connect Gmail" — triggers Flow 2
│   │   ├── Dashboard.tsx        Monthly overview, bills per card
│   │   ├── Transactions.tsx     Infinite scroll list with filter by month/card
│   │   ├── Insights.tsx         Gemini spend comparison narrative
│   │   └── Cards.tsx            Add/manage card providers + PDF passwords
│   ├── components/
│   │   ├── RefreshButton.tsx    Manual sync trigger + polling logic
│   │   ├── TransactionList.tsx  Virtualized list with lazy loading
│   │   └── SyncStatusBanner.tsx Shows sync progress/errors inline
│   ├── hooks/
│   │   ├── useAuth.ts           Firebase auth state, gmailConnected check
│   │   ├── useInfiniteTransactions.ts  Firestore cursor pagination
│   │   └── useSyncJob.ts        Poll /api/sync/status, update UI
│   ├── lib/
│   │   ├── firebase.ts          Firebase app init
│   │   └── api.ts               Fetch wrapper with auto ID token injection
│   └── router.tsx               Protected routes based on auth state
├── firebase.json
└── .firebaserc
```

---

## Environment Variables (Cloud Run)

```
GOOGLE_CLOUD_PROJECT=your-project-id
FERNET_KEY=<generated Fernet key>
GOOGLE_OAUTH_CLIENT_ID=<OAuth2 client ID>
GOOGLE_OAUTH_CLIENT_SECRET=<OAuth2 client secret>
OAUTH_REDIRECT_URI=https://yourapp.web.app/api/auth/gmail/callback
FIREBASE_PROJECT_ID=your-project-id
```

---

## Technical Debt Register

| # | Item | Priority | Reference |
|---|------|----------|-----------|
| 1 | Replace Fernet env-key encryption with Cloud KMS envelope encryption | High (before prod) | See Secret Storage section above |
| 2 | Gemini 3 Flash is in Preview — migrate to stable model ID when GA | Medium | Monitor Vertex AI release notes |
| 3 | OCR support for scanned/image-based PDFs (pytesseract + pdf2image) | Low | Future feature |
| 4 | Gmail OAuth scope verification with Google (required for >100 users) | High (before public launch) | https://support.google.com/cloud/answer/9110914 |
| 5 | Cloud Tasks queue for PDF processing (replace background threads) | Medium | For >10 concurrent users |
| 6 | Firestore Security Rules hardening | High (before prod) | Currently dev-open |
| 7 | Rate limiting on /api/sync to prevent abuse | Medium | Token bucket per uid |

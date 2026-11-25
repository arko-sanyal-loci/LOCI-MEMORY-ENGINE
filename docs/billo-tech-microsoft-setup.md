# Billo Tech Microsoft 365 and GNOME setup

**Status checked:** 2026-11-22  
**State:** planning only; no Microsoft tenant was created or changed in this review.

## What the records establish

The accessible conversation history shows the Microsoft setup was still at the
sign-up stage. It contains no verified `*.onmicrosoft.com` tenant name, tenant
ID, custom-domain TXT value, or Entra app registration/client ID. Searches of
the connected Drive and Dropbox accounts for Billo Tech/Microsoft tenant setup
material returned no matching files. An email-address mailbox provisioned by a
separate mail host does not by itself establish a Microsoft Entra tenant or
Microsoft 365 account.

## Setup path

1. Sign up for the intended Microsoft 365 business subscription using Billo
   Tech's organization details. Microsoft provisions an initial tenant and an
   immutable `*.onmicrosoft.com` fallback domain. Save the initial admin sign-in
   and tenant ID in a private password manager.
2. In Microsoft 365 admin center, add `billo.tech` under **Settings → Domains**.
   Publish only the TXT ownership-verification record Microsoft gives you in
   Hostinger DNS, then verify it. Verification proves domain control; it does
   not require moving the website.
3. Keep current web and mail routing records unchanged during verification.
   In particular, do not replace Titan's MX records unless email migration is
   intended. If moving mail to Microsoft later, create licensed users/mailboxes
   first, then schedule the MX change and configure SPF/DKIM/DMARC.
4. After domain verification, create the intended Microsoft work account, such
   as `arko@billo.tech`, assign the needed license, and secure the admin account
   with MFA and a separate recovery method.
5. On GNOME, open **Settings → Online Accounts → Microsoft 365**, sign in as
   that work account, and approve the requested access. GNOME's built-in
   Microsoft 365 account provider normally handles its own OAuth client; it
   does not require a Billo Tech custom client ID. Actual available services
   depend on the distro build and tenant policy.
6. For a separate LOCI/Arc Microsoft Graph integration, register an app in
   **Microsoft Entra → App registrations** after the tenant exists. Select
   single-tenant access unless a documented multi-tenant use case requires
   otherwise. Record the **Directory (tenant) ID** and **Application (client)
   ID**. Configure only the needed Graph permissions and admin consent. Keep
   credentials/certificates in a secret manager; never commit them or send them
   in chat.

Microsoft's current documentation: [Microsoft 365 business sign-up](https://learn.microsoft.com/en-us/microsoft-365/admin/simplified-signup/signup-business-standard?view=o365-worldwide),
[add a custom domain](https://learn.microsoft.com/en-us/microsoft-365/admin/setup/add-domain?view=o365-worldwide),
[create an Entra tenant](https://learn.microsoft.com/en-us/entra/fundamentals/sign-up-organization),
and [register an application and retrieve IDs](https://learn.microsoft.com/en-us/entra/msidweb/getting-started/quickstart-webapp).
GNOME lists Microsoft 365 as a supported Online Accounts provider with mail,
calendar, contacts, and files in its [service matrix](https://gnome.pages.gitlab.gnome.org/gnome-online-accounts/services.html).

## LOCI retrieval state and remaining work

The RAG index is local: agents can recall only content already ingested into its
SQLite store. The connected Gmail, Drive, and Dropbox tools available in this
ChatGPT session are not currently callable by local LOCI agents. Enabling that
requires explicit per-source OAuth/MCP adapters, user-approved scopes, and
source-level access checks. Search results must preserve source URI, timestamp,
owner/access boundary, and retrieval provenance; external private content must
not be copied into the public Glassbox or Git repository by default.

The TRS repository includes its verification package and SymPrev taxonomy; the
email ZIP named `loci_trs_verification_package final package` is not yet
ingested into LOCI. The current RAG implementation now does bounded document
order expansion for multi-session and temporal queries: it follows adjacent
chunks only within the same file and page, with source/page labels, and cold
chunks remain eligible. This is not yet cross-stream TRS traversal or a
Gmail/Drive/Dropbox connector. CARD's RAG and live-session paths now use one
shared rule-based category classifier; semantic grading remains unvalidated.

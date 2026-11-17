"""crypto_util.py — two-factor (sigword + book) crypto for STRATEGIES tier.

Key derivation:
    combined = lowercase(sigword) + '|' + normalize(book_answer)
    key      = PBKDF2-HMAC-SHA256(combined, per-strategy salt, 600_000, dklen=32)
    token    = Fernet(base64(key)).encrypt(payload)   # AES-128-CBC + HMAC-SHA256

Verification of each factor uses SHA-256(factor_salt || factor).
"""
from __future__ import annotations
import base64, hashlib, json, os, sys, time, unicodedata
from pathlib import Path

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:
    sys.exit("[crypto_util] pip3 install cryptography  (or --user)")

CONFIG_DIR   = Path.home() / ".config" / "loci"
SIG_SALT     = CONFIG_DIR / "sigword.salt"
SIG_HASH     = CONFIG_DIR / "sigword.hash"
BOOK_SALT    = CONFIG_DIR / "book.salt"
BOOK_HASH    = CONFIG_DIR / "book.hash"
BACKOFF_PATH = CONFIG_DIR / "strategy.backoff"
PBKDF2_ITERS = 600_000
LOCKOUT_MAX  = 5
LOCKOUT_SECS = 15 * 60


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return " ".join(s.strip().lower().split())


def verify_factors(sigword: str, book: str) -> bool:
    if not (SIG_SALT.exists() and SIG_HASH.exists() and BOOK_SALT.exists() and BOOK_HASH.exists()):
        sys.exit("[crypto_util] sigword and/or book not set. Run set_sigword.py + set_book.py first.")
    sw = sigword.strip().lower()
    bk = _norm(book)
    sig_ok  = hashlib.sha256(SIG_SALT.read_bytes()  + sw.encode()).hexdigest() == SIG_HASH.read_text().strip()
    book_ok = hashlib.sha256(BOOK_SALT.read_bytes() + bk.encode()).hexdigest() == BOOK_HASH.read_text().strip()
    ok = sig_ok and book_ok
    _record_attempt(ok)
    return ok


def _record_attempt(ok: bool):
    st = {"failures": 0, "lockout_until": 0}
    if BACKOFF_PATH.exists():
        try: st = json.loads(BACKOFF_PATH.read_text())
        except: pass
    if ok:
        st = {"failures": 0, "lockout_until": 0}
    else:
        st["failures"] = st.get("failures", 0) + 1
        if st["failures"] >= LOCKOUT_MAX:
            st["lockout_until"] = int(time.time()) + LOCKOUT_SECS
    BACKOFF_PATH.write_text(json.dumps(st))
    os.chmod(BACKOFF_PATH, 0o600)


def check_lockout():
    if not BACKOFF_PATH.exists(): return
    try: st = json.loads(BACKOFF_PATH.read_text())
    except: return
    now = int(time.time())
    if st.get("lockout_until", 0) > now:
        sys.exit(f"[crypto_util] locked out for {st['lockout_until']-now}s")


def derive_key(sigword: str, book: str, salt: bytes) -> bytes:
    combined = f"{sigword.strip().lower()}|{_norm(book)}".encode()
    return hashlib.pbkdf2_hmac("sha256", combined, salt, PBKDF2_ITERS, dklen=32)


def fernet_from(sigword: str, book: str, salt: bytes) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(derive_key(sigword, book, salt)))


def encrypt(payload: bytes, sigword: str, book: str, salt: bytes) -> bytes:
    return fernet_from(sigword, book, salt).encrypt(payload)


def decrypt(token: bytes, sigword: str, book: str, salt: bytes) -> bytes:
    try:
        return fernet_from(sigword, book, salt).decrypt(token)
    except InvalidToken:
        sys.exit("[crypto_util] decryption failed — wrong sigword or book")

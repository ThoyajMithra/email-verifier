import asyncio
import logging
import re
import smtplib
import socket
from functools import lru_cache

import aiodns


# --------------------------------------------------
# Configuration
# --------------------------------------------------

EMAIL_REGEX = re.compile(
    r"^[A-Za-z0-9._+-]+@"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)

DEFAULT_TIMEOUT = 10

logger = logging.getLogger("verify_email")

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    )
    logger.addHandler(handler)

logger.setLevel(logging.WARNING)
logger.propagate = False


# --------------------------------------------------
# Email syntax validation
# --------------------------------------------------

def syntax_check(email):
    """Return True if the email has a plausible syntax."""

    if not isinstance(email, str):
        return False

    email = email.strip()

    if len(email) > 254:
        return False

    if not EMAIL_REGEX.fullmatch(email):
        return False

    local, domain = email.rsplit("@", 1)

    if len(local) > 64:
        return False

    if local.startswith(".") or local.endswith("."):
        return False

    if ".." in local or ".." in domain:
        return False

    if any(len(label) > 63 for label in domain.split(".")):
        return False

    return True


# --------------------------------------------------
# DNS MX lookup
# --------------------------------------------------

@lru_cache(maxsize=1024)
def _cached_dns_placeholder(hostname):
    # The actual asynchronous lookup is implemented below.
    return hostname


MX_DNS_CACHE = {}


async def get_mx_hosts(email):
    """
    Return MX hosts for the email domain.

    None: DNS lookup failed.
    []: No usable MX records were found.
    List: MX records were found.
    """

    domain = email.rsplit("@", 1)[1].lower()

    if domain in MX_DNS_CACHE:
        return MX_DNS_CACHE[domain]

    try:
        resolver = aiodns.DNSResolver()
        records = await resolver.query(domain, "MX")

        hosts = sorted(
            records,
            key=lambda record: record.priority
        )

        MX_DNS_CACHE[domain] = hosts
        return hosts

    except aiodns.error.DNSError as exc:
        logger.debug("MX lookup failed for %s: %s", domain, exc)

        # Check whether the domain has an address record.
        # RFC 5321 permits an implicit MX when no MX record exists.
        try:
            resolver = aiodns.DNSResolver()
            await resolver.query(domain, "A")

            # The domain exists, but there was no MX record.
            # Use the domain itself as the implicit MX host.
            class ImplicitMX:
                host = domain
                priority = 0

            result = [ImplicitMX()]
            MX_DNS_CACHE[domain] = result
            return result

        except aiodns.error.DNSError:
            MX_DNS_CACHE[domain] = None
            return None

    except Exception:
        logger.exception("Unexpected DNS error for %s", domain)
        return None


# --------------------------------------------------
# SMTP recipient check
# --------------------------------------------------

def _smtp_check_sync(host, email, timeout):
    """
    Perform a blocking SMTP recipient check.

    True: SMTP server accepted the recipient.
    False: SMTP server explicitly rejected the recipient.
    None: The result was inconclusive.
    """

    smtp = None

    try:
        smtp = smtplib.SMTP(
            host=host,
            port=25,
            timeout=timeout
        )

        code, _ = smtp.ehlo()

        if code >= 400:
            return None

        # A null reverse-path is valid SMTP syntax.
        code, _ = smtp.mail("")

        if code >= 400:
            return None

        code, message = smtp.rcpt(email)

        if 200 <= code < 300:
            return True

        if code in (550, 551, 553):
            logger.debug(
                "Recipient rejected by %s: %s %s",
                host,
                code,
                message
            )
            return False

        # Includes temporary rejections and responses such as
        # 252, which do not establish whether the mailbox exists.
        return None

    except (
        smtplib.SMTPException,
        socket.timeout,
        socket.error,
        OSError,
    ) as exc:
        logger.debug("SMTP check failed for %s: %s", host, exc)
        return None

    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                try:
                    smtp.close()
                except Exception:
                    pass


async def network_calls(mx, email, timeout=DEFAULT_TIMEOUT):
    """Run blocking SMTP operations without blocking the event loop."""

    return await asyncio.to_thread(
        _smtp_check_sync,
        mx.host,
        email,
        timeout
    )


# --------------------------------------------------
# MX verification
# --------------------------------------------------

async def handler_verify(mx_hosts, email, timeout=DEFAULT_TIMEOUT):
    """
    Try each MX server.

    True: At least one server accepted the recipient.
    False: All checked servers explicitly rejected it.
    None: No conclusive result was obtained.
    """

    if not mx_hosts:
        return False

    inconclusive = False

    for mx in mx_hosts:
        result = await network_calls(mx, email, timeout)

        if result is True:
            return True

        if result is None:
            inconclusive = True

    if inconclusive:
        return None

    return False


# --------------------------------------------------
# Asynchronous verification API
# --------------------------------------------------

async def _verify_email(email, timeout=DEFAULT_TIMEOUT, verify=True):
    """
    Validate syntax and optionally check DNS and SMTP.
    """

    if not isinstance(email, str):
        return False

    email = email.strip()

    if not syntax_check(email):
        return False

    # Syntax-only mode.
    if not verify:
        return True

    mx_hosts = await get_mx_hosts(email)

    if mx_hosts is None:
        return None

    if not mx_hosts:
        return False

    return await handler_verify(
        mx_hosts,
        email,
        timeout
    )


async def verify_email_async(
    emails,
    timeout=DEFAULT_TIMEOUT,
    verify=True,
    debug=False
):
    """
    Verify one email or a list of emails asynchronously.

    Returns:
        True  - SMTP recipient accepted, or syntax valid in syntax-only mode.
        False - Invalid syntax or a definitive negative check.
        None  - Verification inconclusive.
    """

    if debug:
        logger.setLevel(logging.DEBUG)

    single = isinstance(emails, str)

    if single:
        emails = [emails]
    else:
        try:
            emails = list(emails)
        except TypeError:
            raise TypeError(
                "emails must be a string or an iterable of strings"
            )

    results = await asyncio.gather(
        *(
            _verify_email(email, timeout, verify)
            for email in emails
        )
    )

    return results[0] if single else results


# --------------------------------------------------
# Synchronous verification API
# --------------------------------------------------

def verify_email(
    emails,
    timeout=DEFAULT_TIMEOUT,
    verify=True,
    debug=False
):
    """
    Synchronous wrapper around verify_email_async().

    Do not call this function from inside an already-running
    asyncio event loop. Use verify_email_async() instead.
    """

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "An event loop is already running. "
            "Use 'await verify_email_async(...)' instead."
        )

    return asyncio.run(
        verify_email_async(
            emails,
            timeout=timeout,
            verify=verify,
            debug=debug
        )
    )

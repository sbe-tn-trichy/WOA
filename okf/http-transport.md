---
type: Reference
title: HTTP transport
---

# HTTP transport

Project-owned HTTP calls use `utils.http_transport` backed by pinned
`pyqwest==0.13.0`. Zoho clients retain their existing request arguments and
domain-specific error/retry policies; the token broker and direct Sheets REST
callers use the same transport. Google SDK internals still use their own
transports. Requests remains a transitive Google dependency and supplies some
legacy test fixtures; project source does not call it directly.

## Request and response contracts

The adapter translates `params`, `json`, form `data`, and `files` into native
pyqwest requests. Query/form fields omit `None` and expand list values. JSON
uses the shared [RapidJSON codec](json-codec.md), emitting Decimal numbers without
float conversion and rejecting NaN and infinity. Multipart bodies are buffered before sending, matching
the former fixed Content-Length behavior; the migration does not introduce
chunked uploads. Caller-owned upload streams remain open, and the Zoho base
client still snapshots/rewinds offsets for 401 and rate-limit retries (SDK-001).
Neither HTTP transport errors nor failed financial writes gain a new automatic
application retry.

`Session` owns native connection pools and closes them explicitly. Pools are
keyed by connect/read timeout settings, since pyqwest configures inactivity
timeouts on the native transport. Scalar timeouts apply separately to connection
and read inactivity; two-element tuples specify them individually. They are not
converted into total-response deadlines. Cookie storage is scoped to each native
pool; existing bearer-token workflows do not depend on cross-timeout cookie
sharing. Module-level helpers pool connections without persisting cookies.

The adapter response exposes `status_code`, case-insensitive mapping `headers`,
`reason`, `text`, `content`, `json()`, `raise_for_status()`, `iter_content()` and
`close()`. It is not a Requests Response. Buffered requests consume and close the
native response before returning; streamed responses retain ownership until read
or closed. The shared file writer never accesses `.content` before iterating a
stream, and closes responses on write/transfer failures. Network failures become
`TransportError`; HTTP status failures from `raise_for_status()` become its
`HTTPError` subclass. Zoho status errors retain service-specific exceptions.

## TLS and verification

TLS validation uses the existing certifi CA bundle, preserving the previous
default trust source. `REQUESTS_CA_BUNDLE`, then `CURL_CA_BUNDLE`, can select a
PEM bundle file; these legacy environment names remain supported. System DNS is
used. Redirects retain a 30-hop limit, and native redirect handling strips
Authorization when the destination host changes.

Tests use local HTTP servers for actual encoding, fixed-length multipart replay
after 401/429, cookie isolation, redirect credential stripping, binary streaming,
interrupted downloads and read timeouts. A read-only public HTTPS smoke check
verified native TLS on macOS arm64 CPython 3.14.10. Windows, hosted CI and live
Zoho/Google endpoint behavior remain unverified. This migration does not close
the separate SDK-003 URL logging finding.

Native API: [pyqwest synchronous transport](https://pyqwest.dev/reference/sync/).

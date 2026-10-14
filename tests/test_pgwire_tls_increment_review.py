"""Independent fault-injection review of the D-110 TLS preparation boundary."""

from __future__ import annotations

import ssl

import pytest

from maskgw.errors import ConfigError
from maskgw.pgwire import tls
from maskgw.pgwire.channel_binding import tls_server_end_point
from tests.pgwire_support import make_certificate


def _assert_sanitized(error: ConfigError) -> None:
    assert "review-canary" not in str(error) + repr(error)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_context_creation_failure_is_sanitized(tmp_path, monkeypatch):
    certificate, _, _ = make_certificate(tmp_path)

    def fail():
        raise OSError("review-canary-server-context")

    monkeypatch.setattr(tls, "_new_context", fail)
    with pytest.raises(ConfigError) as captured:
        tls.prepare_server_tls(certificate.cert_path, certificate.key_path)
    _assert_sanitized(captured.value)


def test_leaf_probe_context_creation_failure_is_sanitized(tmp_path, monkeypatch):
    certificate, _, _ = make_certificate(tmp_path)
    original = ssl.SSLContext

    class SslProxy:
        @staticmethod
        def SSLContext(protocol):  # noqa: N802 - exact stdlib API name
            if protocol == ssl.PROTOCOL_TLS_CLIENT:
                raise OSError("review-canary-probe-context")
            return original(protocol)

        def __getattr__(self, name):
            return getattr(ssl, name)

    monkeypatch.setattr(tls, "ssl", SslProxy())
    with pytest.raises(ConfigError) as captured:
        tls.prepare_server_tls(certificate.cert_path, certificate.key_path)
    _assert_sanitized(captured.value)


def test_embedded_nul_path_is_sanitized():
    with pytest.raises(ConfigError) as captured:
        tls.prepare_server_tls("review-canary\x00.crt", "unused.key")
    _assert_sanitized(captured.value)


def test_certificate_binding_and_key_logging_are_independent(tmp_path, monkeypatch):
    certificate, _, _ = make_certificate(tmp_path)
    keylog = tmp_path / "review-canary-keylog.txt"
    monkeypatch.setenv("SSLKEYLOGFILE", str(keylog))
    prepared = tls.prepare_server_tls(certificate.cert_path, certificate.key_path)
    # The installed ssl stub says str, but an unset key logger returns None.
    assert getattr(prepared.context, "keylog_filename") is None  # noqa: B009 - stub mismatch
    assert not keylog.exists()
    assert prepared.channel_binding == tls_server_end_point(certificate.der)
    assert prepared.context.minimum_version >= ssl.TLSVersion.TLSv1_2

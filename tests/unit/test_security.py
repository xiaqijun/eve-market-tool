"""Unit tests for JWT handler and token utilities."""

from app.core.security import JwtHandler, hash_token


class TestJwtHandler:
    def test_create_and_decode_token(self):
        token = JwtHandler.create_session_token(12345, "TestPilot")
        payload = JwtHandler.decode_session_token(token)

        assert payload is not None
        assert payload["sub"] == "12345"
        assert payload["name"] == "TestPilot"
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_invalid_token(self):
        assert JwtHandler.decode_session_token("not-a-valid-token") is None

    def test_decode_empty_token(self):
        assert JwtHandler.decode_session_token("") is None

    def test_decode_tampered_token(self):
        token = JwtHandler.create_session_token(1, "Pilot")
        # Tamper with the signature
        tampered = token[:-5] + "XXXXX"
        assert JwtHandler.decode_session_token(tampered) is None


class TestHashToken:
    def test_hash_is_deterministic(self):
        assert hash_token("abc123") == hash_token("abc123")

    def test_hash_differs_for_different_inputs(self):
        assert hash_token("token_a") != hash_token("token_b")

    def test_hash_returns_hex_string(self):
        h = hash_token("test")
        assert len(h) == 64  # SHA-256 hex digest length
        assert all(c in "0123456789abcdef" for c in h)

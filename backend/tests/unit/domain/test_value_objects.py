import pytest
from src.core.domain.value_objects import Email, PhoneNumber, NIP, URL, ConfidenceScore


class TestEmail:
    def test_valid_email_creates_successfully(self):
        email = Email("user@example.com")
        assert email.value == "user@example.com"

    def test_invalid_email_raises_value_error(self):
        with pytest.raises(ValueError):
            Email("not-an-email")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            Email("")

    def test_missing_domain_raises(self):
        with pytest.raises(ValueError):
            Email("user@")

    def test_email_is_normalized_to_lowercase(self):
        email = Email("User@EXAMPLE.COM")
        assert email.value == "user@example.com"

    def test_whitespace_is_stripped(self):
        email = Email("  user@example.com  ")
        assert email.value == "user@example.com"

    def test_disposable_email_detected(self):
        email = Email("test@mailinator.com")
        assert email.is_disposable() is True

    def test_non_disposable_email(self):
        email = Email("test@gmail.com")
        assert email.is_disposable() is False

    def test_domain_extraction(self):
        email = Email("user@example.com")
        assert email.domain() == "example.com"

    def test_frozen_immutability(self):
        email = Email("user@example.com")
        with pytest.raises(AttributeError):
            email.value = "other@example.com"

    def test_equality(self):
        assert Email("user@example.com") == Email("user@example.com")
        assert Email("a@b.com") != Email("c@d.com")

    def test_hashable(self):
        emails = {Email("a@b.com"), Email("a@b.com"), Email("c@d.com")}
        assert len(emails) == 2

    def test_str_returns_value(self):
        assert str(Email("user@example.com")) == "user@example.com"


class TestPhoneNumber:
    def test_valid_phone_creates(self):
        phone = PhoneNumber("+48123456789", "PL")
        assert phone.value == "+48123456789"

    def test_phone_must_start_with_plus(self):
        with pytest.raises(ValueError):
            PhoneNumber("48123456789", "PL")

    def test_phone_too_short_raises(self):
        with pytest.raises(ValueError):
            PhoneNumber("+123", "PL")

    def test_phone_too_long_raises(self):
        with pytest.raises(ValueError):
            PhoneNumber("+1234567890123456", "US")

    def test_non_digits_after_plus_raises(self):
        with pytest.raises(ValueError):
            PhoneNumber("+48-123-456", "PL")

    def test_region_returns_country_code(self):
        phone = PhoneNumber("+48123456789", "PL")
        assert phone.region() == "PL"

    def test_frozen(self):
        phone = PhoneNumber("+48123456789", "PL")
        with pytest.raises(AttributeError):
            phone.value = "+1234"


class TestNIP:
    def test_valid_nip_with_correct_checksum(self):
        # Known valid NIP: 5261040828 (Polish Ministry of Finance)
        nip = NIP("5261040828")
        assert nip.value == "5261040828"

    def test_nip_with_dashes_normalized(self):
        nip = NIP("526-104-08-28")
        assert nip.value == "5261040828"

    def test_nip_with_spaces_normalized(self):
        nip = NIP("526 104 08 28")
        assert nip.value == "5261040828"

    def test_invalid_checksum_raises(self):
        with pytest.raises(ValueError):
            NIP("1234567890")

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError):
            NIP("123")

    def test_non_digits_raises(self):
        with pytest.raises(ValueError):
            NIP("abcdefghij")

    def test_formatted_output(self):
        nip = NIP("5261040828")
        assert nip.formatted() == "526-104-08-28"

    def test_known_valid_nips(self):
        # A few verifiable Polish NIPs
        valid_nips = ["5261040828", "5252344078", "7740001454"]
        for nip_value in valid_nips:
            nip = NIP(nip_value)
            assert nip.value == nip_value

    def test_frozen(self):
        nip = NIP("5261040828")
        with pytest.raises(AttributeError):
            nip.value = "0000000000"


class TestURL:
    def test_valid_url_creates(self):
        url = URL("https://example.com")
        assert url.value == "https://example.com"

    def test_http_url_valid(self):
        url = URL("http://example.com/path?q=1")
        assert url.value == "http://example.com/path?q=1"

    def test_missing_scheme_raises(self):
        with pytest.raises(ValueError):
            URL("example.com")

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError):
            URL("not a url at all")

    def test_domain_extraction(self):
        url = URL("https://sub.example.com/path")
        assert url.domain() == "sub.example.com"

    def test_social_media_detection(self):
        assert URL("https://twitter.com/user").is_social_media() is True
        assert URL("https://github.com/user").is_social_media() is True
        assert URL("https://example.com").is_social_media() is False

    def test_platform_name(self):
        assert URL("https://twitter.com/user").platform() == "twitter"
        assert URL("https://x.com/user").platform() == "twitter"
        assert URL("https://linkedin.com/in/user").platform() == "linkedin"
        assert URL("https://github.com/user").platform() == "github"
        assert URL("https://example.com").platform() is None

    def test_frozen(self):
        url = URL("https://example.com")
        with pytest.raises(AttributeError):
            url.value = "https://other.com"


class TestConfidenceScore:
    def test_valid_score(self):
        score = ConfidenceScore(0.5)
        assert score.value == 0.5

    def test_zero_is_valid(self):
        score = ConfidenceScore(0.0)
        assert score.value == 0.0

    def test_one_is_valid(self):
        score = ConfidenceScore(1.0)
        assert score.value == 1.0

    def test_below_zero_raises(self):
        with pytest.raises(ValueError):
            ConfidenceScore(-0.1)

    def test_above_one_raises(self):
        with pytest.raises(ValueError):
            ConfidenceScore(1.1)

    def test_level_low(self):
        assert ConfidenceScore(0.1).level() == "low"
        assert ConfidenceScore(0.29).level() == "low"

    def test_level_medium(self):
        assert ConfidenceScore(0.3).level() == "medium"
        assert ConfidenceScore(0.59).level() == "medium"

    def test_level_high(self):
        assert ConfidenceScore(0.6).level() == "high"
        assert ConfidenceScore(0.94).level() == "high"

    def test_level_certain(self):
        assert ConfidenceScore(0.95).level() == "certain"
        assert ConfidenceScore(1.0).level() == "certain"

    def test_addition_normal(self):
        result = ConfidenceScore(0.3) + ConfidenceScore(0.4)
        assert result.value == pytest.approx(0.7)

    def test_addition_caps_at_one(self):
        result = ConfidenceScore(0.8) + ConfidenceScore(0.5)
        assert result.value == 1.0

    def test_float_conversion(self):
        assert float(ConfidenceScore(0.75)) == 0.75

    def test_comparison(self):
        low = ConfidenceScore(0.2)
        high = ConfidenceScore(0.8)
        assert low < high
        assert high > low
        assert low <= low
        assert high >= high

    def test_frozen(self):
        score = ConfidenceScore(0.5)
        with pytest.raises(AttributeError):
            score.value = 0.9

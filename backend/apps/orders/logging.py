import logging
import re


class RedactGuestTrackingToken(logging.Filter):
    """Remove bearer tokens from Django's request and development access logs."""

    pattern = re.compile(r"(/api/v1/orders/track/)[^/\s?]+")

    def filter(self, record):
        message = record.getMessage()
        redacted = self.pattern.sub(r"\1[REDACTED]", message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True

"""Finite UTF-8 SSE data framing, without networking or reconnection policy.

CR, LF and CRLF are line endings, including pairs split across input chunks.
Only one leading BOM and one optional space after a colon are removed.
Invalid UTF-8 is rejected conservatively; an unfinished event is never emitted.
"""


class SseFramingError(ValueError):
    pass


class SseFramer:
    def __init__(self, *, max_bytes=1048576):
        if type(max_bytes) is not int or not 0 < max_bytes <= 1048576:
            raise SseFramingError("SSE_CONFIGURATION_INVALID")
        self.limit, self.size = max_bytes, 0
        self.line = bytearray()
        self.data = []
        self.first_line = True
        self.skip_lf = False
        self.failed = False

    @property
    def pending(self):
        return bool(self.line or self.data)

    def _line(self):
        failed = False
        try:
            line = bytes(self.line).decode("utf-8-sig" if self.first_line else "utf-8")
        except UnicodeError:
            failed = True
        self.line.clear()
        self.first_line = False
        if failed:
            self.failed = True
            raise SseFramingError("STREAM_INVALID_UTF8")
        if not line:
            payload = "\n".join(self.data).encode("utf-8") if self.data else None
            self.data.clear()
            return payload
        if not line.startswith(":"):
            field, colon, value = line.partition(":")
            if colon and value.startswith(" "):
                value = value[1:]
            if field == "data":
                self.data.append(value)
        return None

    def feed(self, chunk):
        if self.failed or type(chunk) is not bytes:
            self.failed = True
            raise SseFramingError("STREAM_CLOSED_OR_TYPE")
        self.size += len(chunk)
        if self.size > self.limit:
            self.failed = True
            raise SseFramingError("STREAM_TOO_LARGE")
        for byte in chunk:
            if self.skip_lf:
                self.skip_lf = False
                if byte == 10:
                    continue
            if byte in (10, 13):
                self.skip_lf = byte == 13
                payload = self._line()
                if payload is not None:
                    yield payload
            else:
                self.line.append(byte)

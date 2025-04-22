import pathlib


def read_text_with_encoding_retry(self: pathlib.Path) -> str:
    try:
        return self.read_text()
    except UnicodeDecodeError:
        try:
            return self.read_text("latin-1")
        except UnicodeDecodeError:
            try:
                return self.read_text("utf-8")
            except UnicodeDecodeError as e:
                raise e


pathlib.Path.read_text_with_encoding_retry = read_text_with_encoding_retry

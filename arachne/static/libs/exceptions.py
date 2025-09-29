class URLError(Exception):
    def __init__(self, message="URL is not valid"):
        super().__init__(message)
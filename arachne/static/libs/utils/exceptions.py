class URLError(Exception):
    def __init__(self, message="URL is not valid"):
        super().__init__(message)

class UnknownScrapeTypeError(Exception):
    def __init__(self, message="Unknown scrape type"):
        super().__init__(message)

class ItemSaveError(Exception):
    def __init__(self, message="There was an error while trying to log items to the database"):
        super().__init__(message)

class ItemScrapeError(Exception):
    def __init__(self, message="There was an error while trying to scrape items"):
        super().__init__(message)

#Connection Code Exceptions
class CC403(Exception):
    def __init__(self, message="403: Forbidden"):
        super().__init__(message)

class CC404(Exception):
    def __init__(self, message="404: Not Found"):
        super().__init__(message)

class CC429(Exception):
    def __init__(self, message="429: Too Many Requests"):
        super().__init__(message)

class CC503(Exception):
    def __init__(self, message="503: Service Unavailable"):
        super().__init__(message)

class CC522(Exception):
    def __init__(self, message="522: Connection Timed Out"):
        super().__init__(message)
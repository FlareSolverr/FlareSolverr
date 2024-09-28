
STATUS_OK = "ok"
STATUS_ERROR = "error"


class ChallengeResolutionResultT:
    url: str = None
    status: int = None
    headers: list = None
    response: str = None
    cookies: list = None
    userAgent: str = None

    def __init__(self, _dict):
        self.__dict__.update(_dict)


class ChallengeResolutionT:
    status: str = None
    message: str = None
    result: ChallengeResolutionResultT = None

    def __init__(self, _dict):
        self.__dict__.update(_dict)
        if self.result is not None:
            self.result = ChallengeResolutionResultT(self.result)


class V1RequestBase(object):
    # V1RequestBase
    cmd: str = None
    cookies: list = None
    maxTimeout: int = None
    proxy: dict = None
    session: str = None
    session_ttl_minutes: int = None
    headers: list = None  # deprecated v2.0.0, not used
    userAgent: str = None

    # V1Request
    url: str = None
    postData: str = None
    returnOnlyCookies: bool = None
    download: bool = None   # deprecated v2.0.0, not used
    returnRawHtml: bool = None  # deprecated v2.0.0, not used

    def __init__(self, _dict):
        self.__dict__.update(_dict)


class V1ResponseBase(object):
    # V1ResponseBase
    status: str = None
    message: str = None
    session: str = None
    sessions: list[str] = None
    startTimestamp: int = None
    endTimestamp: int = None
    version: str = None

    # V1ResponseSolution
    solution: ChallengeResolutionResultT = None

    # hidden vars
    __error_500__: bool = False

    def __init__(self, _dict):
        self.__dict__.update(_dict)
        if self.solution is not None:
            self.solution = ChallengeResolutionResultT(self.solution)


class IndexResponse(object):
    msg: str = None
    version: str = None
    userAgent: str = None

    def __init__(self, _dict):
        self.__dict__.update(_dict)


class HealthResponse(object):
    status: str = None

    def __init__(self, _dict):
        self.__dict__.update(_dict)

class Config(object):
    TESTING = False
    DEFAULT_PAGE_SIZE = 1000
    DEFAULT_RESPONSE_LINES_SIZE = 1000
    DEFAULT_CHUNK_SIZE = 1024 * 1024 * 10
    MAX_LINE_SIZE = 200000
    DEFAULT_READ_TIMEOUT = 30


class DevelopmentConfig(Config):
    ENV = 'development'
    DEBUG = True
    LOG_DIR = "./log"

class TestingConfig(Config):
    ENV = 'testing'
    TESTING = True

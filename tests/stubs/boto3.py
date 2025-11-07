class _DummyClient:
    def __getattr__(self, name):
        raise NotImplementedError("AWS not available in tests")


def client(*args, **kwargs):
    return _DummyClient()

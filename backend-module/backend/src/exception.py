class BackendException(Exception):
    """Base backend exception root class."""
    _base_code: int = 0
    _code: int
    msg: str

    @property
    def code(self) -> int:
        return self._code + self._base_code

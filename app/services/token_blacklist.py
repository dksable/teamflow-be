class TokenBlacklist:
    """Interface for future token revocation storage such as Redis."""

    def revoke(self, token: str) -> None:
        raise NotImplementedError

    def is_revoked(self, token: str) -> bool:
        raise NotImplementedError


class InMemoryTokenBlacklist(TokenBlacklist):
    def __init__(self) -> None:
        self._tokens: set[str] = set()

    def revoke(self, token: str) -> None:
        self._tokens.add(token)

    def is_revoked(self, token: str) -> bool:
        return token in self._tokens


token_blacklist = InMemoryTokenBlacklist()

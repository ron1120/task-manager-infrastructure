# Who is doing something: a signed-in person, a machine with an API key, or the system itself.
# Everything that changes state records its actor on the incident timeline and in the audit log.
from dataclasses import dataclass


@dataclass(frozen=True)
class Actor:
    kind: str  # user | api_key | system | anonymous
    label: str  # "user:ana@example.com", "key:github-ci", "system"
    user_id: int | None = None

    @classmethod
    def user(cls, user) -> "Actor":
        return cls("user", f"user:{user.email}", user.id)

    @classmethod
    def api_key(cls, key) -> "Actor":
        return cls("api_key", f"key:{key.name}")

    @classmethod
    def system(cls) -> "Actor":
        return cls("system", "system")

    @classmethod
    def anonymous(cls, name: str = "unknown") -> "Actor":
        return cls("anonymous", f"anonymous:{name}")

def is_strong_password(pw: str) -> bool:
    return bool(pw and len(pw) >= 8)

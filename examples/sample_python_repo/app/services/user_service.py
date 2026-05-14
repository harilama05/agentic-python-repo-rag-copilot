def create_user(email: str) -> dict:
    return {
        "email": email,
        "is_active": True,
    }


class UserService:
    def get_user(self, user_id: int) -> dict:
        return {
            "id": user_id,
            "email": "demo@example.com",
        }
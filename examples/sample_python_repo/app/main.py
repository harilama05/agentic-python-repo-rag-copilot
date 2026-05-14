from app.services.user_service import create_user


def main():
    user = create_user("alice@example.com")
    print(user)


if __name__ == "__main__":
    main()
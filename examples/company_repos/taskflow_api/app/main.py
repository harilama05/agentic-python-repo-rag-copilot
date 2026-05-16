from app.api.tasks import list_tasks


def main():
    tasks = list_tasks()
    print(tasks)


if __name__ == "__main__":
    main()
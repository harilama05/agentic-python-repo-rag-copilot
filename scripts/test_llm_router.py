from src.agent_core.query_router import LLMQueryRouter
from src.generation.llm import GeminiLLM


def main():
    router = LLMQueryRouter(llm=GeminiLLM())

    questions = [
        "Dự án này dùng để làm gì?",
        "Where is create_task implemented?",
        "TaskService.create_task được gọi bởi ai?",
        "create_task gọi những hàm nào?",
        "Nếu bỏ method tạo task thì chỗ nào bị ảnh hưởng?",
        "Mình sửa TaskService.create_task thì cần kiểm tra những chỗ nào?",
    ]

    for question in questions:
        plan = router.route(question)
        print("=" * 100)
        print("Question:", question)
        print("Query type:", plan.query_type)
        print("Symbol:", plan.symbol)
        print("Rewritten query:", plan.rewritten_query)
        print("Confidence:", plan.confidence)
        print("Router:", plan.router)
        print("Reason:", plan.reason)


if __name__ == "__main__":
    main()

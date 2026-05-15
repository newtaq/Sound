from app.application.message_splitter import AIMessageSplitter


def main() -> None:
    splitter = AIMessageSplitter()

    text = (
        "Первая часть длинного сообщения. "
        "Вторая часть длинного сообщения. "
        "Третья часть длинного сообщения. "
        "Четвертая часть длинного сообщения."
    )

    parts = splitter.split(text=text, max_length=45)

    for part in parts:
        print(f"PART {part.index}/{part.total}: {part.text!r} len={len(part.text)}")


if __name__ == "__main__":
    main()
    

"""Application entry points backed by the reusable rag_core pipeline."""


def answer_with_rag(question, chat_history=None, lang="zh"):
    from rag_core.pipeline import answer

    return answer(question, history=chat_history, lang=lang)


def build_index_from_folder(folder=None, backend=None):
    from rag_core.pipeline import build_index

    return build_index(folder=folder, backend=backend)

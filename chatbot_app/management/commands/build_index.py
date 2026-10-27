import json

from django.core.management.base import BaseCommand, CommandError

from chatbot_app.rag import build_index_from_folder


class Command(BaseCommand):
    help = "Build an application-owned index from trusted text documents."

    def add_arguments(self, parser):
        parser.add_argument("--backend", choices=["demo", "openai"], default=None)
        parser.add_argument("--folder", default=None, help="UTF-8 text corpus folder; default is sample_docs.")

    def handle(self, *args, **options):
        try:
            result = build_index_from_folder(folder=options["folder"], backend=options["backend"])
        except Exception as exc:
            from rag_core.errors import RAGError

            if isinstance(exc, RAGError):
                raise CommandError(f"{exc.code}: {exc.public_message}") from None
            raise CommandError("Index construction failed; check the local configuration and corpus.") from None
        self.stdout.write(json.dumps(result, ensure_ascii=False))

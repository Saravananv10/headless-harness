"""Task-bank-driven datagen pipeline.

Reads tasks from the local forged task bank under
artifacts/datagen_task_bank/by_category/ and runs each one through the
existing Chakra harness (ConversationRunner + verification contract), with
independent re-verification, near-duplicate detection, a per-task cost
circuit breaker, and an append-only dataset manifest layered on top.
"""

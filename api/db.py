"""Shared database connection helper."""

import os
import psycopg2

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")


def get_conn():
    return psycopg2.connect(POSTGRES_URL)

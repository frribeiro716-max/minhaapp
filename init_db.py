import sqlite3

DB_NAME = "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # -------------------------
    # TABELA USERS
    # -------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    """)

    # -------------------------
    # TABELA DESPESAS
    # -------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS despesas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        data TEXT NOT NULL
    );
    """)

    # -------------------------
    # TABELA APORTES
    # -------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS aportes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        valor REAL NOT NULL,
        data TEXT NOT NULL
    );
    """)

    # -------------------------
    # HISTÓRICO DESPESAS
    # -------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico_despesas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        data TEXT NOT NULL,
        mes_referente TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    # -------------------------
    # HISTÓRICO APORTES
    # -------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico_aportes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        valor REAL NOT NULL,
        data TEXT NOT NULL,
        mes_referente TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    conn.commit()
    conn.close()
    print("Base de dados inicializada com sucesso!")


if __name__ == "__main__":
    init_db()

import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "gyro.db")


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS flows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                schedule TEXT,
                schedule_enabled INTEGER DEFAULT 1,
                next_run_at TEXT,
                last_run_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                archived INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS assistants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                instructions TEXT DEFAULT '',
                context TEXT DEFAULT '[]',
                default_model TEXT DEFAULT 'claude-sonnet-4-20250514',
                default_permissions TEXT DEFAULT '{}',
                default_work_dir TEXT DEFAULT '',
                default_flow_id TEXT REFERENCES flows(id),
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT DEFAULT 'active' CHECK(status IN ('active','paused')),
                priority INTEGER DEFAULT 0,
                model TEXT DEFAULT 'claude-sonnet-4-20250514',
                work_dir TEXT DEFAULT '',
                flow_id TEXT REFERENCES flows(id),
                assistant_id TEXT REFERENCES assistants(id),
                permissions TEXT DEFAULT '{}',
                schedule TEXT,
                schedule_enabled INTEGER DEFAULT 1,
                next_run_at TEXT,
                last_run_at TEXT,
                max_retries INTEGER DEFAULT 0,
                retry_delay_seconds INTEGER DEFAULT 10,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS task_dependencies (
                task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                depends_on_task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                PRIMARY KEY (task_id, depends_on_task_id)
            );
            CREATE INDEX IF NOT EXISTS idx_task_deps_task ON task_dependencies(task_id);
            CREATE INDEX IF NOT EXISTS idx_task_deps_depends ON task_dependencies(depends_on_task_id);

            CREATE TABLE IF NOT EXISTS task_runs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES tasks(id),
                run_number INTEGER NOT NULL,
                trigger TEXT DEFAULT 'manual' CHECK(trigger IN ('manual','schedule','dependency','retry')),
                status TEXT DEFAULT 'queued' CHECK(status IN ('queued','running','success','failed','cancelled')),
                pid INTEGER,
                exit_code INTEGER,
                cost_usd REAL DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                num_turns INTEGER DEFAULT 0,
                started_at TEXT DEFAULT (datetime('now')),
                finished_at TEXT,
                error_message TEXT,
                attempt_number INTEGER DEFAULT 1,
                retry_of_run_id TEXT REFERENCES task_runs(id),
                UNIQUE(task_id, run_number)
            );

            CREATE TABLE IF NOT EXISTS task_run_output (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_run_id TEXT NOT NULL REFERENCES task_runs(id),
                seq INTEGER NOT NULL,
                type TEXT DEFAULT 'text',
                content TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                task_run_id TEXT NOT NULL REFERENCES task_runs(id),
                task_id TEXT NOT NULL REFERENCES tasks(id),
                question TEXT NOT NULL,
                answer TEXT,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending','answered','timeout')),
                created_at TEXT DEFAULT (datetime('now')),
                answered_at TEXT
            );
        """)
        await db.commit()

        # Migrations for existing databases
        async def column_exists(table, column):
            cursor = await db.execute(f"PRAGMA table_info({table})")
            cols = await cursor.fetchall()
            return any(c["name"] == column for c in cols)

        if not await column_exists("tasks", "max_retries"):
            await db.execute("ALTER TABLE tasks ADD COLUMN max_retries INTEGER DEFAULT 0")
        if not await column_exists("tasks", "retry_delay_seconds"):
            await db.execute("ALTER TABLE tasks ADD COLUMN retry_delay_seconds INTEGER DEFAULT 10")
        if not await column_exists("task_runs", "attempt_number"):
            await db.execute("ALTER TABLE task_runs ADD COLUMN attempt_number INTEGER DEFAULT 1")
        if not await column_exists("task_runs", "retry_of_run_id"):
            await db.execute("ALTER TABLE task_runs ADD COLUMN retry_of_run_id TEXT REFERENCES task_runs(id)")
        await db.commit()
    finally:
        await db.close()

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
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                archived INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT DEFAULT 'queued' CHECK(status IN ('queued','assigned','running','done','failed','cancelled')),
                priority INTEGER DEFAULT 0,
                model TEXT DEFAULT 'claude-sonnet-4-20250514',
                work_dir TEXT DEFAULT '',
                project_id TEXT REFERENCES projects(id),
                permissions TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES jobs(id),
                pid INTEGER,
                status TEXT DEFAULT 'starting' CHECK(status IN ('starting','running','done','failed','cancelled')),
                exit_code INTEGER,
                cost_usd REAL DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                num_turns INTEGER DEFAULT 0,
                started_at TEXT DEFAULT (datetime('now')),
                finished_at TEXT,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS agent_output (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL REFERENCES agents(id),
                seq INTEGER NOT NULL,
                type TEXT DEFAULT 'text',
                content TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL REFERENCES agents(id),
                job_id TEXT NOT NULL REFERENCES jobs(id),
                question TEXT NOT NULL,
                answer TEXT,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending','answered','timeout')),
                created_at TEXT DEFAULT (datetime('now')),
                answered_at TEXT
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
                default_project_id TEXT REFERENCES projects(id),
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        await db.commit()

        # Migrate: add permissions column if missing
        cursor = await db.execute("PRAGMA table_info(jobs)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "permissions" not in columns:
            await db.execute("ALTER TABLE jobs ADD COLUMN permissions TEXT DEFAULT '{}'")
            await db.commit()

        # Migrate: add assistant_id column if missing
        if "assistant_id" not in columns:
            await db.execute("ALTER TABLE jobs ADD COLUMN assistant_id TEXT REFERENCES assistants(id)")
            await db.commit()

        # Migrate: add scheduled_for column if missing
        if "scheduled_for" not in columns:
            await db.execute("ALTER TABLE jobs ADD COLUMN scheduled_for TEXT")
            await db.commit()

        # Migrate: add schedule_id column if missing
        if "schedule_id" not in columns:
            await db.execute("ALTER TABLE jobs ADD COLUMN schedule_id TEXT REFERENCES schedules(id)")
            await db.commit()

        # Migrate: add parent_job_id column if missing
        if "parent_job_id" not in columns:
            await db.execute("ALTER TABLE jobs ADD COLUMN parent_job_id TEXT REFERENCES jobs(id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_parent ON jobs(parent_job_id)")
            await db.commit()

        # Create schedules table
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS schedules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                cron_expression TEXT NOT NULL,
                title_template TEXT NOT NULL,
                prompt TEXT NOT NULL,
                model TEXT DEFAULT 'claude-sonnet-4-20250514',
                priority INTEGER DEFAULT 0,
                work_dir TEXT DEFAULT '',
                project_id TEXT REFERENCES projects(id),
                permissions TEXT DEFAULT '{}',
                assistant_id TEXT REFERENCES assistants(id),
                enabled INTEGER DEFAULT 1,
                last_run_at TEXT,
                next_run_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        await db.commit()
    finally:
        await db.close()

-- Database
-- At the moment, sqlite3.

CREATE TABLE IF NOT EXISTS user (
    user_id INTEGER NOT NULL PRIMARY KEY ASC,
    ignoramus BOOLEAN default false
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS channel (
    channel_id INTEGER NOT NULL PRIMARY KEY ASC,
    guild_id INTEGER NOT NULL,
    radio BOOLEAN default false
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS watchword (
    guild_id INTEGER,
    user_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    cooldown INTEGER NOT NULL default 900,
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    UNIQUE (guild_id, user_id, word) ON CONFLICT REPLACE
);
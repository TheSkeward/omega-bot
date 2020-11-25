-- Database for triggers stuff
-- At the moment, sqlite3 only. Probably will stay that way.

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER NOT NULL PRIMARY KEY ASC,
    triggers TEXT NOT NULL,
    remark TEXT NOT NULL,
    protected BOOLEAN default false,
    UNIQUE (triggers, remark) ON CONFLICT FAIL
);

CREATE TABLE IF NOT EXISTS auto_responses (
    id INTEGER NOT NULL PRIMARY KEY ASC,
    command TEXT NOT NULL,
    response TEXT NOT NULL,
    UNIQUE (command, response) ON CONFLICT FAIL
);

CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER NOT NULL PRIMARY KEY ASC,
    item TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS ignore (
    id INTEGER NOT NULL PRIMARY KEY ASC,
    ignoramus INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER NOT NULL PRIMARY KEY ASC,
    author_id INTEGER NOT NULL,
    quote TEXT NOT NULL,
    UNIQUE (author_id, quote) ON CONFLICT FAIL
);

CREATE TABLE IF NOT EXISTS radio (
    id INTEGER NOT NULL PRIMARY KEY ASC,
    channel_id INTEGER NOT NULL UNIQUE
);